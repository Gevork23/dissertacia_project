from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any

from django.conf import settings

from .entity_schema import (
    ApplicantKind,
    AuthorityKind,
    ConditionKind,
    ConditionScope,
    DeadlineModifier,
    DeadlineScope,
    DeadlineUnit,
    DocumentActor,
    DocumentRole,
    EntityType,
    ExtractionMethod,
    ObligationActor,
    ObligationPhase,
    RefusalCategory,
)

logger = logging.getLogger(__name__)

ALLOWED_ENTITY_TYPES = {item.value for item in EntityType}

ENTITY_TYPE_PRIORITY = {
    EntityType.DEADLINE.value: 100,
    EntityType.REQUIRED_DOCUMENT.value: 95,
    EntityType.REFUSAL_REASON.value: 90,
    EntityType.OBLIGATION.value: 85,
    EntityType.CONDITION.value: 80,
    EntityType.AUTHORITY_UNIT.value: 75,
    EntityType.APPLICANT_CATEGORY.value: 70,
    EntityType.SERVICE.value: 65,
}


class LLMEntityExtractionError(Exception):
    pass


def _strip_code_fences(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_text_value(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _find_span(source_text: str, value: str) -> tuple[int, int]:
    normalized = _normalize_text_value(value)
    if not normalized:
        return 0, 0

    start = source_text.find(normalized)
    if start >= 0:
        return start, start + len(normalized)

    compact_source = " ".join(source_text.split())
    compact_start = compact_source.find(normalized)
    if compact_start >= 0:
        return 0, 0

    return 0, 0


def _normalize_deadline_entity(entity: dict[str, Any]) -> None:
    value = _normalize_text_value(entity.get("value"))
    normalized_value = _normalize_text_value(entity.get("normalized_value"))
    source = f"{value} {normalized_value}".lower()

    if "в день обращения" in source:
        entity["deadline_value"] = 0
        entity["deadline_unit"] = DeadlineUnit.SAME_DAY.value
        entity["deadline_modifier"] = DeadlineModifier.EXACT.value
        entity["normalized_value"] = "P0D_SAME_DAY"
        if not entity.get("deadline_scope"):
            entity["deadline_scope"] = DeadlineScope.SERVICE_PROVISION.value
        return

    number_match = re.search(r"(\d+)", source)
    amount = int(number_match.group(1)) if number_match else None

    if amount is not None:
        entity["deadline_value"] = amount

    if "рабоч" in source:
        entity["deadline_unit"] = DeadlineUnit.WORKING_DAYS.value
    elif "календар" in source:
        entity["deadline_unit"] = DeadlineUnit.CALENDAR_DAYS.value
    elif "час" in source:
        entity["deadline_unit"] = DeadlineUnit.HOURS.value
    elif "минут" in source:
        entity["deadline_unit"] = DeadlineUnit.MINUTES.value
    else:
        entity.setdefault("deadline_unit", DeadlineUnit.UNSPECIFIED.value)

    if "не более" in source or "up_to" in source:
        entity["deadline_modifier"] = DeadlineModifier.UP_TO.value
    elif "не менее" in source or "at_least" in source:
        entity["deadline_modifier"] = DeadlineModifier.AT_LEAST.value
    else:
        entity.setdefault("deadline_modifier", DeadlineModifier.EXACT.value)

    if "межведомствен" in source:
        entity["deadline_scope"] = DeadlineScope.INTERAGENCY_REQUEST.value
    elif "информ" in source:
        entity["deadline_scope"] = DeadlineScope.INFORMING.value
    elif "результат" in source or "выдач" in source:
        entity["deadline_scope"] = DeadlineScope.RESULT_ISSUE.value
    else:
        entity.setdefault("deadline_scope", DeadlineScope.SERVICE_PROVISION.value)

    if amount is not None:
        unit = entity.get("deadline_unit", DeadlineUnit.UNSPECIFIED.value)
        entity["normalized_value"] = f"P{amount}_{str(unit).upper()}"


def _normalize_required_document_entity(entity: dict[str, Any]) -> None:
    value = _normalize_text_value(entity.get("value"))
    lowered = value.lower()

    entity["document_name"] = value
    entity["normalized_value"] = lowered

    if "представител" in lowered or "полномоч" in lowered:
        entity["for_actor"] = DocumentActor.REPRESENTATIVE.value
        entity.setdefault("document_role", DocumentRole.ADDITIONAL.value)
    else:
        entity.setdefault("for_actor", DocumentActor.APPLICANT.value)
        entity.setdefault("document_role", DocumentRole.MANDATORY.value)


def _normalize_obligation_entity(entity: dict[str, Any]) -> None:
    value = _normalize_text_value(entity.get("value"))
    lowered = value.lower()

    action = re.sub(
        r"^.*?(?:обязан|обязана|обязано|обязаны|должен|должна)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()
    entity["obligation_action"] = action or value
    entity["normalized_value"] = (action or value).lower()

    if "сотрудник" in lowered or "специалист" in lowered:
        entity["obligation_actor"] = ObligationActor.EMPLOYEE.value
    elif "заявител" in lowered:
        entity["obligation_actor"] = ObligationActor.APPLICANT.value
    elif "представител" in lowered:
        entity["obligation_actor"] = ObligationActor.REPRESENTATIVE.value
    elif "орган" in lowered or "подразделени" in lowered or "мфц" in lowered:
        entity["obligation_actor"] = ObligationActor.AUTHORITY_UNIT.value
    else:
        entity.setdefault("obligation_actor", ObligationActor.UNSPECIFIED.value)

    if "до регистрации" in lowered:
        entity["obligation_phase"] = ObligationPhase.BEFORE_REGISTRATION.value
    elif "после регистрации" in lowered:
        entity["obligation_phase"] = ObligationPhase.AFTER_REGISTRATION.value
    elif "консульт" in lowered:
        entity["obligation_phase"] = ObligationPhase.DURING_CONSULTATION.value
    elif "выдать" in lowered or "получения результата" in lowered:
        entity["obligation_phase"] = ObligationPhase.RESULT_DELIVERY.value
    elif "рассмотр" in lowered or "провер" in lowered:
        entity["obligation_phase"] = ObligationPhase.DURING_REVIEW.value
    else:
        entity.setdefault("obligation_phase", ObligationPhase.UNSPECIFIED.value)


def _normalize_condition_entity(entity: dict[str, Any]) -> None:
    value = _normalize_text_value(entity.get("value"))
    lowered = value.lower()

    entity["normalized_value"] = lowered

    if "представител" in lowered:
        entity["condition_kind"] = ConditionKind.REPRESENTATIVE_CASE.value
    elif "межведомствен" in lowered:
        entity["condition_kind"] = ConditionKind.INTERAGENCY_REQUEST.value
    elif "не предусмотрено" in lowered:
        entity["condition_kind"] = ConditionKind.EXCEPTION_CASE.value
    elif "неполного комплекта документов" in lowered:
        entity["condition_kind"] = ConditionKind.DOCUMENT_DEFICIENCY_CASE.value
    elif "права на получение" in lowered:
        entity["condition_kind"] = ConditionKind.ELIGIBILITY_CASE.value
    else:
        entity.setdefault("condition_kind", ConditionKind.UNSPECIFIED.value)

    heading = _normalize_text_value(entity.get("heading")).lower()
    source_text = _normalize_text_value(entity.get("source_text")).lower()
    source = f"{heading} {source_text}"

    if "отказ" in source:
        entity["condition_scope"] = ConditionScope.REFUSAL.value
    elif "документ" in source:
        entity["condition_scope"] = ConditionScope.REQUIRED_DOCUMENTS.value
    elif "срок" in source or "дн" in source:
        entity["condition_scope"] = ConditionScope.DEADLINE.value
    elif "обязан" in source or "должен" in source:
        entity["condition_scope"] = ConditionScope.OBLIGATION.value
    elif "порядок" in source or "процедур" in source:
        entity["condition_scope"] = ConditionScope.PROCEDURE.value
    else:
        entity.setdefault("condition_scope", ConditionScope.UNSPECIFIED.value)


def _normalize_refusal_reason_entity(entity: dict[str, Any]) -> None:
    value = _normalize_text_value(entity.get("value"))
    lowered = value.lower()

    entity["refusal_reason_text"] = value
    entity["normalized_value"] = lowered

    if "неполного комплекта документов" in lowered:
        entity["refusal_category"] = RefusalCategory.INCOMPLETE_DOCUMENTS.value
    elif "недостоверных сведений" in lowered:
        entity["refusal_category"] = RefusalCategory.FALSE_INFORMATION.value
    elif "отсутствия у заявителя права" in lowered:
        entity["refusal_category"] = RefusalCategory.NO_ELIGIBILITY.value
    elif "не подтвердившим полномочия представителя" in lowered:
        entity["refusal_category"] = RefusalCategory.AUTHORITY_OF_REPRESENTATIVE.value
    else:
        entity.setdefault("refusal_category", RefusalCategory.UNSPECIFIED.value)


def _normalize_applicant_category_entity(entity: dict[str, Any]) -> None:
    value = _normalize_text_value(entity.get("value"))
    lowered = value.lower()

    if "представител" in lowered:
        entity["applicant_kind"] = ApplicantKind.REPRESENTATIVE.value
    elif "гражданин российской федерации" in lowered:
        entity["applicant_kind"] = ApplicantKind.CITIZEN.value
    elif "заявител" in lowered:
        entity["applicant_kind"] = ApplicantKind.APPLICANT.value
    else:
        entity.setdefault("applicant_kind", ApplicantKind.UNSPECIFIED.value)

    entity["normalized_value"] = entity["applicant_kind"]


def _normalize_authority_unit_entity(entity: dict[str, Any]) -> None:
    value = _normalize_text_value(entity.get("value"))
    lowered = value.lower()

    if "специалист мфц" in lowered:
        entity["authority_name"] = "специалист МФЦ"
        entity["authority_kind"] = AuthorityKind.EMPLOYEE_UNIT.value
    elif "сотрудник мфц" in lowered:
        entity["authority_name"] = "сотрудник МФЦ"
        entity["authority_kind"] = AuthorityKind.EMPLOYEE_UNIT.value
    elif "многофункциональный центр" in lowered:
        entity["authority_name"] = "многофункциональный центр"
        entity["authority_kind"] = AuthorityKind.MFC.value
    elif lowered == "мфц":
        entity["authority_name"] = "МФЦ"
        entity["authority_kind"] = AuthorityKind.MFC.value
    elif "уполномоченный орган" in lowered:
        entity["authority_name"] = "уполномоченный орган"
        entity["authority_kind"] = AuthorityKind.GOVERNMENT_AUTHORITY.value
    elif "структурное подразделение" in lowered:
        entity["authority_name"] = "структурное подразделение"
        entity["authority_kind"] = AuthorityKind.STRUCTURAL_UNIT.value
    else:
        entity.setdefault("authority_name", value)
        entity.setdefault("authority_kind", AuthorityKind.UNSPECIFIED.value)

    entity["normalized_value"] = _normalize_text_value(
        entity.get("authority_name", value)
    ).lower()


def _normalize_service_entity(entity: dict[str, Any]) -> None:
    value = _normalize_text_value(entity.get("value"))
    lowered = value.lower()

    action = "предоставление"
    if "прием" in lowered:
        action = "прием"
    elif "выдач" in lowered:
        action = "выдача"
    elif "получени" in lowered:
        action = "получение"

    entity["service_name"] = value
    entity["service_action"] = action
    entity["normalized_value"] = lowered


def _normalize_entity_payload(entity: dict[str, Any]) -> dict[str, Any]:
    entity_type = entity["entity_type"]

    if entity_type == EntityType.DEADLINE.value:
        _normalize_deadline_entity(entity)
    elif entity_type == EntityType.REQUIRED_DOCUMENT.value:
        _normalize_required_document_entity(entity)
    elif entity_type == EntityType.OBLIGATION.value:
        _normalize_obligation_entity(entity)
    elif entity_type == EntityType.CONDITION.value:
        _normalize_condition_entity(entity)
    elif entity_type == EntityType.REFUSAL_REASON.value:
        _normalize_refusal_reason_entity(entity)
    elif entity_type == EntityType.APPLICANT_CATEGORY.value:
        _normalize_applicant_category_entity(entity)
    elif entity_type == EntityType.AUTHORITY_UNIT.value:
        _normalize_authority_unit_entity(entity)
    elif entity_type == EntityType.SERVICE.value:
        _normalize_service_entity(entity)

    return entity


def _sanitize_entity(
    raw: dict[str, Any],
    *,
    source_text: str,
    heading: str,
    section_path: str,
    extraction_method: str,
) -> dict[str, Any] | None:
    entity_type = _normalize_text_value(raw.get("entity_type"))
    if entity_type not in ALLOWED_ENTITY_TYPES:
        return None

    value = _normalize_text_value(raw.get("value"))
    if not value:
        return None

    normalized_value = _normalize_text_value(raw.get("normalized_value")) or value
    start_char, end_char = _find_span(source_text, value)

    entity = {
        "entity_type": entity_type,
        "value": value,
        "normalized_value": normalized_value,
        "source_text": source_text,
        "start_char": int(raw.get("start_char", start_char) or start_char),
        "end_char": int(raw.get("end_char", end_char) or end_char),
        "section_path": _normalize_text_value(raw.get("section_path")) or section_path,
        "heading": _normalize_text_value(raw.get("heading")) or heading,
        "confidence": _safe_float(raw.get("confidence"), 0.85),
        "extraction_method": extraction_method,
    }

    reserved_keys = set(entity.keys())
    for key, item in raw.items():
        if key in reserved_keys:
            continue
        entity[key] = item

    return _normalize_entity_payload(entity)


def _parse_response_content(content: str) -> list[dict[str, Any]]:
    cleaned = _strip_code_fences(content)
    if not cleaned:
        return []

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise LLMEntityExtractionError("Failed to parse LLM JSON response.")
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as error:
            raise LLMEntityExtractionError(
                f"Failed to parse LLM JSON response: {error}"
            ) from error

    if isinstance(payload, dict):
        entities = payload.get("entities", [])
    elif isinstance(payload, list):
        entities = payload
    else:
        entities = []

    if not isinstance(entities, list):
        raise LLMEntityExtractionError("LLM response must contain a list of entities.")

    normalized_entities: list[dict[str, Any]] = []
    for item in entities:
        if isinstance(item, dict):
            normalized_entities.append(item)

    return normalized_entities


def _few_shot_examples() -> str:
    return """
Пример 1
TEXT:
"Общий срок предоставления государственной услуги составляет 7 рабочих дней со дня регистрации заявления."
JSON:
{
  "entities": [
    {
      "entity_type": "deadline",
      "value": "7 рабочих дней",
      "normalized_value": "P7_WORKING_DAYS",
      "deadline_value": 7,
      "deadline_unit": "working_days",
      "deadline_modifier": "exact",
      "deadline_scope": "service_provision",
      "confidence": 0.98
    },
    {
      "entity_type": "service",
      "value": "предоставления государственной услуги",
      "normalized_value": "предоставления государственной услуги",
      "service_name": "предоставления государственной услуги",
      "service_action": "предоставление",
      "confidence": 0.88
    }
  ]
}

Пример 2
TEXT:
"Для получения услуги заявитель представляет:
1) заявление по установленной форме;
2) паспорт гражданина Российской Федерации;
3) документ, подтверждающий место жительства."
JSON:
{
  "entities": [
    {
      "entity_type": "service",
      "value": "получения услуги",
      "normalized_value": "получения услуги",
      "service_name": "получения услуги",
      "service_action": "получение",
      "confidence": 0.86
    },
    {
      "entity_type": "applicant_category",
      "value": "заявитель",
      "normalized_value": "applicant",
      "applicant_kind": "applicant",
      "confidence": 0.95
    },
    {
      "entity_type": "required_document",
      "value": "заявление по установленной форме",
      "normalized_value": "заявление по установленной форме",
      "document_name": "заявление по установленной форме",
      "document_role": "mandatory",
      "for_actor": "applicant",
      "confidence": 0.97
    },
    {
      "entity_type": "required_document",
      "value": "паспорт гражданина Российской Федерации",
      "normalized_value": "паспорт гражданина российской федерации",
      "document_name": "паспорт гражданина Российской Федерации",
      "document_role": "mandatory",
      "for_actor": "applicant",
      "confidence": 0.97
    },
    {
      "entity_type": "required_document",
      "value": "документ, подтверждающий место жительства",
      "normalized_value": "документ, подтверждающий место жительства",
      "document_name": "документ, подтверждающий место жительства",
      "document_role": "mandatory",
      "for_actor": "applicant",
      "confidence": 0.96
    }
  ]
}

Пример 3
TEXT:
"В предоставлении услуги отказывается в случае:
1) представления неполного комплекта документов;
2) представления недостоверных сведений."
JSON:
{
  "entities": [
    {
      "entity_type": "service",
      "value": "предоставлении услуги",
      "normalized_value": "предоставлении услуги",
      "service_name": "предоставлении услуги",
      "service_action": "предоставление",
      "confidence": 0.85
    },
    {
      "entity_type": "condition",
      "value": "в случае",
      "normalized_value": "в случае",
      "condition_kind": "unspecified",
      "condition_scope": "refusal",
      "confidence": 0.75
    },
    {
      "entity_type": "refusal_reason",
      "value": "представления неполного комплекта документов",
      "normalized_value": "представления неполного комплекта документов",
      "refusal_reason_text": "представления неполного комплекта документов",
      "refusal_category": "incomplete_documents",
      "confidence": 0.98
    },
    {
      "entity_type": "refusal_reason",
      "value": "представления недостоверных сведений",
      "normalized_value": "представления недостоверных сведений",
      "refusal_reason_text": "представления недостоверных сведений",
      "refusal_category": "false_information",
      "confidence": 0.98
    }
  ]
}
""".strip()


def _build_prompt(text: str, heading: str, section_path: str) -> str:
    return f"""
Ты модуль извлечения сущностей из нормативно-правового текста в логике МФЦ.

Нужно извлечь сущности только из данного фрагмента.
Верни СТРОГО JSON без пояснений.
Никакого markdown, code fences, комментариев и текста вне JSON.

Формат ответа:
{{
  "entities": [
    {{
      "entity_type": "deadline",
      "value": "7 рабочих дней",
      "normalized_value": "P7_WORKING_DAYS",
      "confidence": 0.95
    }}
  ]
}}

Разрешённые entity_type:
- service
- required_document
- deadline
- obligation
- condition
- refusal_reason
- applicant_category
- authority_unit

Критерии:
1. Извлекай только сущности, которые явно есть в тексте.
2. Для списков документов извлекай каждый документ отдельно.
3. Для списков оснований отказа извлекай каждое основание отдельно.
4. Для сроков старайся извлекать deadline_value, deadline_unit, deadline_modifier, deadline_scope.
5. Для документов старайся извлекать document_name, document_role, for_actor.
6. Для обязанностей старайся извлекать obligation_actor, obligation_action, obligation_phase.
7. Для оснований отказа старайся извлекать refusal_reason_text, refusal_category.
8. Если сущность сомнительная, лучше пропусти её.
9. Предпочитай точность и полноту по документам, срокам, обязанностям и основаниям отказа.

Ниже примеры правильного ответа.

{_few_shot_examples()}

heading: {heading}
section_path: {section_path}

TEXT:
\"\"\"
{text}
\"\"\"
""".strip()


def _deduplicate_entities(
    entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    best_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}

    for entity in entities:
        key = (
            str(entity.get("entity_type", "")),
            str(entity.get("normalized_value", "")),
            str(entity.get("value", "")),
        )
        existing = best_by_key.get(key)
        if existing is None:
            best_by_key[key] = entity
            continue

        current_score = (
            float(entity.get("confidence", 0)),
            ENTITY_TYPE_PRIORITY.get(str(entity.get("entity_type", "")), 0),
            len(str(entity.get("value", ""))),
        )
        existing_score = (
            float(existing.get("confidence", 0)),
            ENTITY_TYPE_PRIORITY.get(str(existing.get("entity_type", "")), 0),
            len(str(existing.get("value", ""))),
        )
        if current_score >= existing_score:
            best_by_key[key] = entity

    return sorted(
        best_by_key.values(),
        key=lambda item: (
            int(item.get("start_char", 0)),
            str(item.get("entity_type", "")),
            str(item.get("value", "")),
        ),
    )


class OpenAICompatibleLLMEntityExtractor:
    def __init__(self) -> None:
        self.api_url = settings.ENTITY_LLM_API_URL
        self.api_key = settings.ENTITY_LLM_API_KEY
        self.model = settings.ENTITY_LLM_MODEL
        self.timeout = settings.ENTITY_LLM_TIMEOUT_SECONDS

        if not self.api_url:
            raise LLMEntityExtractionError("ENTITY_LLM_API_URL is not configured.")
        if not self.api_key:
            raise LLMEntityExtractionError("ENTITY_LLM_API_KEY is not configured.")
        if not self.model:
            raise LLMEntityExtractionError("ENTITY_LLM_MODEL is not configured.")

    def extract(
        self,
        text: str,
        *,
        heading: str = "",
        section_path: str = "",
    ) -> list[dict[str, Any]]:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You extract structured entities from Russian legal text "
                        "and always return valid JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": _build_prompt(
                        text=text,
                        heading=heading,
                        section_path=section_path,
                    ),
                },
            ],
        }

        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw_response = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="ignore")
            raise LLMEntityExtractionError(
                f"LLM HTTP error {error.code}: {body}"
            ) from error
        except urllib.error.URLError as error:
            raise LLMEntityExtractionError(f"LLM network error: {error}") from error

        try:
            data = json.loads(raw_response)
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise LLMEntityExtractionError("Unexpected LLM response format.") from error

        raw_entities = _parse_response_content(content)
        entities: list[dict[str, Any]] = []

        for item in raw_entities:
            entity = _sanitize_entity(
                item,
                source_text=text,
                heading=heading,
                section_path=section_path,
                extraction_method=ExtractionMethod.LLM.value,
            )
            if entity is not None:
                entities.append(entity)

        entities = _deduplicate_entities(entities)

        logger.info(
            "LLM entity extraction done: heading=%s section_path=%s entities=%s",
            heading,
            section_path,
            len(entities),
        )
        return entities


def get_default_llm_entity_extractor() -> OpenAICompatibleLLMEntityExtractor:
    return OpenAICompatibleLLMEntityExtractor()
