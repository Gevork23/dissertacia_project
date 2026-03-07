from __future__ import annotations

import re
from typing import Any

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

WORKING_DAYS_RE = re.compile(
    r"(?P<value>\d+)\s+рабоч(?:их|его)\s+дн(?:ей|я)",
    re.IGNORECASE,
)
CALENDAR_DAYS_RE = re.compile(
    r"(?P<value>\d+)\s+календарн(?:ых|ого)\s+дн(?:ей|я)",
    re.IGNORECASE,
)
HOURS_RE = re.compile(r"(?P<value>\d+)\s+час(?:ов|а)?", re.IGNORECASE)
MINUTES_RE = re.compile(r"(?P<value>\d+)\s+минут(?:ы|у)?", re.IGNORECASE)
SAME_DAY_RE = re.compile(r"в\s+день\s+обращения", re.IGNORECASE)
UP_TO_PREFIX_RE = re.compile(r"не\s+более\s+чем", re.IGNORECASE)
AT_LEAST_PREFIX_RE = re.compile(r"не\s+менее\s+чем", re.IGNORECASE)

CONDITION_RE = re.compile(
    r"(?P<value>(?:в\s+случае|при|если)\s+[^\.;\n]+)",
    re.IGNORECASE,
)

OBLIGATION_RE = re.compile(
    r"(?P<value>[^\.;\n]*?(?:обязан|обязана|обязано|обязаны|должен|должна)\s+[^\.;\n]+)",
    re.IGNORECASE,
)

SERVICE_RE = re.compile(
    r"(?P<value>(?:предоставлен(?:ие|ия)|получени(?:е|я)|выдач(?:а|и)|прием)\s+[^\.;\n]*?услуг[аиуы]?)",
    re.IGNORECASE,
)

AUTHORITY_PATTERNS = (
    (
        re.compile(r"специалист\s+МФЦ", re.IGNORECASE),
        "специалист МФЦ",
        AuthorityKind.EMPLOYEE_UNIT.value,
    ),
    (
        re.compile(r"сотрудник\s+МФЦ", re.IGNORECASE),
        "сотрудник МФЦ",
        AuthorityKind.EMPLOYEE_UNIT.value,
    ),
    (
        re.compile(
            r"многофункциональн(?:ый|ом|ого)?\s+центр",
            re.IGNORECASE,
        ),
        "многофункциональный центр",
        AuthorityKind.MFC.value,
    ),
    (
        re.compile(r"МФЦ", re.IGNORECASE),
        "МФЦ",
        AuthorityKind.MFC.value,
    ),
    (
        re.compile(r"уполномоченн(?:ый|ого|ым)?\s+орган", re.IGNORECASE),
        "уполномоченный орган",
        AuthorityKind.GOVERNMENT_AUTHORITY.value,
    ),
    (
        re.compile(
            r"структурн(?:ое|ого|ым)?\s+подразделени(?:е|я)",
            re.IGNORECASE,
        ),
        "структурное подразделение",
        AuthorityKind.STRUCTURAL_UNIT.value,
    ),
)

APPLICANT_PATTERNS = (
    (
        re.compile(r"заявител(?:ь|я|ем|ю)", re.IGNORECASE),
        "заявитель",
        ApplicantKind.APPLICANT.value,
    ),
    (
        re.compile(r"представител(?:ь|я|ем|ю)", re.IGNORECASE),
        "представитель",
        ApplicantKind.REPRESENTATIVE.value,
    ),
    (
        re.compile(
            r"гражданин(?:а|у|ом)?\s+Российской\s+Федерации",
            re.IGNORECASE,
        ),
        "гражданин Российской Федерации",
        ApplicantKind.CITIZEN.value,
    ),
)

REFUSAL_CATEGORY_KEYWORDS = (
    (
        "неполного комплекта документов",
        RefusalCategory.INCOMPLETE_DOCUMENTS.value,
    ),
    (
        "недостоверных сведений",
        RefusalCategory.FALSE_INFORMATION.value,
    ),
    (
        "отсутствия у заявителя права",
        RefusalCategory.NO_ELIGIBILITY.value,
    ),
    (
        "не подтвердившим полномочия представителя",
        RefusalCategory.AUTHORITY_OF_REPRESENTATIVE.value,
    ),
)


def _build_base_entity(
    *,
    entity_type: str,
    value: str,
    source_text: str,
    start_char: int,
    end_char: int,
    heading: str = "",
    section_path: str = "",
    normalized_value: str | None = None,
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "value": value.strip(),
        "normalized_value": (normalized_value or value).strip(),
        "source_text": source_text,
        "start_char": start_char,
        "end_char": end_char,
        "section_path": section_path or "",
        "heading": heading or "",
        "confidence": confidence,
        "extraction_method": ExtractionMethod.RULE_BASED.value,
    }


def _infer_deadline_scope(text: str, heading: str) -> str:
    source = f"{heading} {text}".lower()
    if "межведомствен" in source:
        return DeadlineScope.INTERAGENCY_REQUEST.value
    if "информ" in source:
        return DeadlineScope.INFORMING.value
    if "выдач" in source or "результат" in source:
        return DeadlineScope.RESULT_ISSUE.value
    if "рассмотрен" in source or "провер" in source:
        return DeadlineScope.DOCUMENT_REVIEW.value
    return DeadlineScope.SERVICE_PROVISION.value


def _infer_condition_kind(value: str) -> str:
    lowered = value.lower()
    if "представител" in lowered:
        return ConditionKind.REPRESENTATIVE_CASE.value
    if "межведомствен" in lowered:
        return ConditionKind.INTERAGENCY_REQUEST.value
    if "не предусмотрено" in lowered:
        return ConditionKind.EXCEPTION_CASE.value
    if "неполного комплекта документов" in lowered:
        return ConditionKind.DOCUMENT_DEFICIENCY_CASE.value
    if "права на получение" in lowered:
        return ConditionKind.ELIGIBILITY_CASE.value
    return ConditionKind.UNSPECIFIED.value


def _infer_condition_scope(text: str, heading: str) -> str:
    source = f"{heading} {text}".lower()
    if "отказ" in source:
        return ConditionScope.REFUSAL.value
    if "документ" in source:
        return ConditionScope.REQUIRED_DOCUMENTS.value
    if "срок" in source or "дн" in source:
        return ConditionScope.DEADLINE.value
    if "обязан" in source or "должен" in source:
        return ConditionScope.OBLIGATION.value
    if "порядок" in source or "процедур" in source:
        return ConditionScope.PROCEDURE.value
    return ConditionScope.UNSPECIFIED.value


def _infer_obligation_actor(value: str) -> str:
    lowered = value.lower()
    if "сотрудник" in lowered or "специалист" in lowered:
        return ObligationActor.EMPLOYEE.value
    if "заявител" in lowered:
        return ObligationActor.APPLICANT.value
    if "представител" in lowered:
        return ObligationActor.REPRESENTATIVE.value
    if "орган" in lowered or "подразделени" in lowered or "мфц" in lowered:
        return ObligationActor.AUTHORITY_UNIT.value
    return ObligationActor.UNSPECIFIED.value


def _infer_obligation_phase(value: str) -> str:
    lowered = value.lower()
    if "до регистрации" in lowered:
        return ObligationPhase.BEFORE_REGISTRATION.value
    if "после регистрации" in lowered:
        return ObligationPhase.AFTER_REGISTRATION.value
    if "консульт" in lowered:
        return ObligationPhase.DURING_CONSULTATION.value
    if "выдать" in lowered or "получения результата" in lowered:
        return ObligationPhase.RESULT_DELIVERY.value
    if "рассмотр" in lowered or "провер" in lowered:
        return ObligationPhase.DURING_REVIEW.value
    return ObligationPhase.UNSPECIFIED.value


def _normalize_spaces(value: str) -> str:
    return " ".join(value.strip().split())


def extract_deadlines(
    text: str,
    heading: str = "",
    section_path: str = "",
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    patterns = [
        (WORKING_DAYS_RE, DeadlineUnit.WORKING_DAYS.value),
        (CALENDAR_DAYS_RE, DeadlineUnit.CALENDAR_DAYS.value),
        (HOURS_RE, DeadlineUnit.HOURS.value),
        (MINUTES_RE, DeadlineUnit.MINUTES.value),
    ]
    scope = _infer_deadline_scope(text, heading)

    for pattern, unit in patterns:
        for match in pattern.finditer(text):
            value = match.group(0)
            amount = int(match.group("value"))
            prefix = text[max(0, match.start() - 25) : match.start()]
            modifier = DeadlineModifier.EXACT.value
            if UP_TO_PREFIX_RE.search(prefix):
                modifier = DeadlineModifier.UP_TO.value
            elif AT_LEAST_PREFIX_RE.search(prefix):
                modifier = DeadlineModifier.AT_LEAST.value

            entity = _build_base_entity(
                entity_type=EntityType.DEADLINE.value,
                value=value,
                normalized_value=f"P{amount}_{unit.upper()}",
                source_text=text,
                start_char=match.start(),
                end_char=match.end(),
                heading=heading,
                section_path=section_path,
                confidence=0.97,
            )
            entity.update(
                {
                    "deadline_value": amount,
                    "deadline_unit": unit,
                    "deadline_modifier": modifier,
                    "deadline_scope": scope,
                }
            )
            entities.append(entity)

    for match in SAME_DAY_RE.finditer(text):
        entity = _build_base_entity(
            entity_type=EntityType.DEADLINE.value,
            value=match.group(0),
            normalized_value="P0D_SAME_DAY",
            source_text=text,
            start_char=match.start(),
            end_char=match.end(),
            heading=heading,
            section_path=section_path,
            confidence=0.95,
        )
        entity.update(
            {
                "deadline_value": 0,
                "deadline_unit": DeadlineUnit.SAME_DAY.value,
                "deadline_modifier": DeadlineModifier.EXACT.value,
                "deadline_scope": scope,
            }
        )
        entities.append(entity)

    return entities


def extract_conditions(
    text: str,
    heading: str = "",
    section_path: str = "",
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for match in CONDITION_RE.finditer(text):
        value = _normalize_spaces(match.group("value"))
        entity = _build_base_entity(
            entity_type=EntityType.CONDITION.value,
            value=value,
            normalized_value=value.lower(),
            source_text=text,
            start_char=match.start(),
            end_char=match.end(),
            heading=heading,
            section_path=section_path,
            confidence=0.9,
        )
        entity.update(
            {
                "condition_kind": _infer_condition_kind(value),
                "condition_scope": _infer_condition_scope(text, heading),
            }
        )
        entities.append(entity)
    return entities


def extract_obligations(
    text: str,
    heading: str = "",
    section_path: str = "",
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for match in OBLIGATION_RE.finditer(text):
        value = _normalize_spaces(match.group("value"))
        action = re.sub(
            r"^.*?(?:обязан|обязана|обязано|обязаны|должен|должна)\s+",
            "",
            value,
            flags=re.IGNORECASE,
        )
        entity = _build_base_entity(
            entity_type=EntityType.OBLIGATION.value,
            value=value,
            normalized_value=action.lower(),
            source_text=text,
            start_char=match.start(),
            end_char=match.end(),
            heading=heading,
            section_path=section_path,
            confidence=0.94,
        )
        entity.update(
            {
                "obligation_actor": _infer_obligation_actor(value),
                "obligation_action": action,
                "obligation_phase": _infer_obligation_phase(value),
            }
        )
        entities.append(entity)
    return entities


def extract_required_documents(
    text: str,
    heading: str = "",
    section_path: str = "",
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    trigger_mode = False

    for line in lines:
        lowered = line.lower()

        if (
            "заявитель представляет" in lowered
            or "дополнительно представляется" in lowered
            or "дополнительно представляются" in lowered
        ):
            trigger_mode = True
            if ":" in line:
                tail = line.split(":", 1)[1].strip()
                lines_to_check = [tail] if tail else []
            else:
                lines_to_check = []
        elif trigger_mode and re.match(r"^\d+\)", line):
            lines_to_check = [re.sub(r"^\d+\)\s*", "", line).rstrip(";.")]
        elif trigger_mode and lowered.startswith("документы принимаются"):
            trigger_mode = False
            lines_to_check = []
        else:
            lines_to_check = []

        for candidate in lines_to_check:
            candidate_clean = _normalize_spaces(candidate)
            if not candidate_clean:
                continue

            start_char = text.find(candidate)
            if start_char < 0:
                start_char = text.find(candidate_clean)
            end_char = start_char + len(candidate_clean) if start_char >= 0 else 0

            lowered_candidate = candidate_clean.lower()
            actor = DocumentActor.APPLICANT.value
            role = DocumentRole.MANDATORY.value

            if "представител" in lowered_candidate or "полномоч" in lowered_candidate:
                actor = DocumentActor.REPRESENTATIVE.value
                role = DocumentRole.ADDITIONAL.value

            if "дополнительно" in lowered:
                role = DocumentRole.ADDITIONAL.value

            entity = _build_base_entity(
                entity_type=EntityType.REQUIRED_DOCUMENT.value,
                value=candidate_clean,
                normalized_value=candidate_clean.lower(),
                source_text=text,
                start_char=max(start_char, 0),
                end_char=max(end_char, 0),
                heading=heading,
                section_path=section_path,
                confidence=0.93,
            )
            entity.update(
                {
                    "document_name": candidate_clean,
                    "document_role": role,
                    "for_actor": actor,
                }
            )
            entities.append(entity)

    return entities


def extract_refusal_reasons(
    text: str,
    heading: str = "",
    section_path: str = "",
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    if "отказ" not in f"{heading} {text}".lower():
        return entities

    for line in [line.strip() for line in text.splitlines() if line.strip()]:
        if not re.match(r"^\d+\)", line):
            continue

        value = re.sub(r"^\d+\)\s*", "", line).rstrip(";.")
        lowered = value.lower()
        category = RefusalCategory.UNSPECIFIED.value

        for keyword, mapped in REFUSAL_CATEGORY_KEYWORDS:
            if keyword in lowered:
                category = mapped
                break

        start_char = text.find(value)
        end_char = start_char + len(value) if start_char >= 0 else 0

        entity = _build_base_entity(
            entity_type=EntityType.REFUSAL_REASON.value,
            value=value,
            normalized_value=lowered,
            source_text=text,
            start_char=max(start_char, 0),
            end_char=max(end_char, 0),
            heading=heading,
            section_path=section_path,
            confidence=0.95,
        )
        entity.update(
            {
                "refusal_reason_text": value,
                "refusal_category": category,
            }
        )
        entities.append(entity)

    return entities


def extract_authority_units(
    text: str,
    heading: str = "",
    section_path: str = "",
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()

    for pattern, canonical_name, authority_kind in AUTHORITY_PATTERNS:
        for match in pattern.finditer(text):
            key = (match.start(), match.end(), authority_kind)
            if key in seen:
                continue
            seen.add(key)

            entity = _build_base_entity(
                entity_type=EntityType.AUTHORITY_UNIT.value,
                value=match.group(0),
                normalized_value=canonical_name.lower(),
                source_text=text,
                start_char=match.start(),
                end_char=match.end(),
                heading=heading,
                section_path=section_path,
                confidence=0.92,
            )
            entity.update(
                {
                    "authority_name": canonical_name,
                    "authority_kind": authority_kind,
                }
            )
            entities.append(entity)

    return entities


def extract_applicant_categories(
    text: str,
    heading: str = "",
    section_path: str = "",
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()

    for pattern, canonical_name, applicant_kind in APPLICANT_PATTERNS:
        for match in pattern.finditer(text):
            key = (match.start(), match.end(), applicant_kind)
            if key in seen:
                continue
            seen.add(key)

            entity = _build_base_entity(
                entity_type=EntityType.APPLICANT_CATEGORY.value,
                value=match.group(0),
                normalized_value=applicant_kind,
                source_text=text,
                start_char=match.start(),
                end_char=match.end(),
                heading=heading,
                section_path=section_path,
                confidence=0.9,
            )
            entity.update({"applicant_kind": applicant_kind})
            entities.append(entity)

    return entities


def extract_services(
    text: str,
    heading: str = "",
    section_path: str = "",
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for match in SERVICE_RE.finditer(text):
        value = _normalize_spaces(match.group("value"))
        action = "предоставление"
        lowered = value.lower()

        if "прием" in lowered:
            action = "прием"
        elif "выдач" in lowered:
            action = "выдача"
        elif "получени" in lowered:
            action = "получение"

        entity = _build_base_entity(
            entity_type=EntityType.SERVICE.value,
            value=value,
            normalized_value=value.lower(),
            source_text=text,
            start_char=match.start(),
            end_char=match.end(),
            heading=heading,
            section_path=section_path,
            confidence=0.88,
        )
        entity.update(
            {
                "service_name": value,
                "service_action": action,
            }
        )
        entities.append(entity)

    return entities


def extract_entities_from_text(
    text: str,
    *,
    heading: str = "",
    section_path: str = "",
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    extractors = (
        extract_services,
        extract_required_documents,
        extract_deadlines,
        extract_obligations,
        extract_conditions,
        extract_refusal_reasons,
        extract_applicant_categories,
        extract_authority_units,
    )

    for extractor in extractors:
        entities.extend(
            extractor(
                text,
                heading=heading,
                section_path=section_path,
            )
        )

    entities.sort(
        key=lambda item: (
            item["start_char"],
            item["entity_type"],
            item["value"],
        )
    )
    return entities