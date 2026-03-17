from __future__ import annotations

import csv
import json
import random
from collections import Counter
from itertools import product
from pathlib import Path


OUT_PATH = Path("data/importance_dataset/changes_seed_v1.csv")
FIELDNAMES = [
    "sample_id",
    "source_kind",
    "document_type",
    "scenario",
    "old_text",
    "new_text",
    "diff_text",
    "change_type",
    "extracted_entities",
    "importance_label",
]


def build_diff(old_text: str, new_text: str) -> str:
    return f"OLD: {old_text}\nNEW: {new_text}"


def make_row(
    sample_id: int,
    *,
    source_kind: str,
    document_type: str,
    scenario: str,
    old_text: str,
    new_text: str,
    change_type: str,
    extracted_entities: list[dict[str, str]],
    importance_label: str,
) -> dict[str, str]:
    return {
        "sample_id": f"S{sample_id:04d}",
        "source_kind": source_kind,
        "document_type": document_type,
        "scenario": scenario,
        "old_text": old_text,
        "new_text": new_text,
        "diff_text": build_diff(old_text, new_text),
        "change_type": change_type,
        "extracted_entities": json.dumps(extracted_entities, ensure_ascii=False),
        "importance_label": importance_label,
    }


def main() -> None:
    rows: list[dict[str, str]] = []
    sample_id = 1

    def add(
        *,
        document_type: str,
        scenario: str,
        old_text: str,
        new_text: str,
        change_type: str,
        entities: list[dict[str, str]],
        importance: str,
        source_kind: str = "synthetic",
    ) -> None:
        nonlocal sample_id
        rows.append(
            make_row(
                sample_id,
                source_kind=source_kind,
                document_type=document_type,
                scenario=scenario,
                old_text=old_text,
                new_text=new_text,
                change_type=change_type,
                extracted_entities=entities,
                importance_label=importance,
            )
        )
        sample_id += 1

    # ----------------------------
    # CRITICAL
    # ----------------------------
    services = [
        "предоставления государственной услуги",
        "рассмотрения заявления",
        "выдачи результата услуги",
    ]
    deadline_pairs = [
        ("5 рабочих дней", "10 рабочих дней"),
        ("3 рабочих дня", "7 рабочих дней"),
        ("1 рабочий день", "15 рабочих дней"),
    ]
    for service, (old_deadline, new_deadline) in product(services, deadline_pairs):
        add(
            document_type="регламент",
            scenario="deadline_changed",
            old_text=f"Срок {service} составляет {old_deadline}.",
            new_text=f"Срок {service} составляет {new_deadline}.",
            change_type="deadline",
            entities=[
                {"type": "service", "value": service},
                {"type": "deadline_old", "value": old_deadline},
                {"type": "deadline_new", "value": new_deadline},
            ],
            importance="critical",
        )

    doc_pairs = [
        ("паспорт гражданина Российской Федерации", "паспорт гражданина Российской Федерации, СНИЛС"),
        ("заявление и паспорт", "заявление, паспорт и документ, подтверждающий регистрацию"),
        ("паспорт", "паспорт и доверенность представителя"),
    ]
    for old_docs, new_docs in doc_pairs:
        add(
            document_type="административный регламент",
            scenario="required_documents_changed",
            old_text=f"Для получения услуги заявитель представляет {old_docs}.",
            new_text=f"Для получения услуги заявитель представляет {new_docs}.",
            change_type="document",
            entities=[
                {"type": "required_documents_old", "value": old_docs},
                {"type": "required_documents_new", "value": new_docs},
            ],
            importance="critical",
        )

    refusal_pairs = [
        (
            "Основанием для отказа является предоставление недостоверных сведений.",
            "Основанием для отказа является предоставление недостоверных сведений или непредставление СНИЛС.",
        ),
        (
            "Основания для отказа отсутствуют.",
            "Основанием для отказа является отсутствие регистрации по месту жительства.",
        ),
        (
            "В предоставлении услуги может быть отказано при отсутствии заявления.",
            "В предоставлении услуги может быть отказано при отсутствии заявления либо обязательного подтверждающего документа.",
        ),
    ]
    for old_text, new_text in refusal_pairs:
        add(
            document_type="регламент",
            scenario="refusal_ground_changed",
            old_text=old_text,
            new_text=new_text,
            change_type="refusal",
            entities=[{"type": "refusal_change", "value": "true"}],
            importance="critical",
        )

    obligation_pairs = [
        (
            "Сотрудник проверяет комплектность документов.",
            "Сотрудник обязан проверять комплектность документов и сверять сведения с реестром.",
        ),
        (
            "Сотрудник информирует заявителя устно по запросу.",
            "Сотрудник обязан информировать заявителя устно и письменно при выявлении оснований отказа.",
        ),
    ]
    for old_text, new_text in obligation_pairs:
        add(
            document_type="локальный акт",
            scenario="staff_obligation_changed",
            old_text=old_text,
            new_text=new_text,
            change_type="obligation",
            entities=[{"type": "staff_action", "value": "обязанность сотрудника"}],
            importance="critical",
        )

    responsibility_pairs = [
        (
            "Ответственность за нарушение порядка не установлена.",
            "За нарушение порядка предоставления услуги устанавливается дисциплинарная ответственность.",
        ),
        (
            "Сотрудник несёт ответственность в соответствии с законодательством.",
            "Сотрудник несёт дисциплинарную и материальную ответственность в соответствии с законодательством.",
        ),
    ]
    for old_text, new_text in responsibility_pairs:
        add(
            document_type="локальный акт",
            scenario="responsibility_changed",
            old_text=old_text,
            new_text=new_text,
            change_type="responsibility",
            entities=[{"type": "responsibility_change", "value": "true"}],
            importance="critical",
        )

    # ----------------------------
    # IMPORTANT
    # ----------------------------
    procedure_pairs = [
        (
            "Приём заявлений осуществляется в порядке живой очереди.",
            "Приём заявлений осуществляется по предварительной записи через региональный портал.",
        ),
        (
            "Документы принимаются в окне №1.",
            "Документы принимаются в окне №1 и через единое окно обслуживания.",
        ),
        (
            "Уведомление заявителя осуществляется по телефону.",
            "Уведомление заявителя осуществляется по телефону и через личный кабинет.",
        ),
        (
            "Заявление подаётся лично.",
            "Заявление подаётся лично либо через представителя.",
        ),
        (
            "Проверка заявления выполняется отделом приёма.",
            "Проверка заявления выполняется профильным отделом сопровождения.",
        ),
        (
            "Консультирование проводится с 9:00 до 18:00.",
            "Консультирование проводится с 8:00 до 20:00.",
        ),
    ]
    for old_text, new_text in procedure_pairs:
        add(
            document_type="регламент",
            scenario="procedure_changed",
            old_text=old_text,
            new_text=new_text,
            change_type="procedure",
            entities=[{"type": "procedure_change", "value": "true"}],
            importance="important",
        )

    condition_pairs = [
        (
            "Услуга предоставляется заявителям старше 18 лет.",
            "Услуга предоставляется заявителям старше 18 лет и их законным представителям.",
        ),
        (
            "Результат выдается по месту подачи заявления.",
            "Результат выдается по месту подачи заявления либо в выбранном МФЦ.",
        ),
        (
            "Для обращения требуется регистрация по месту жительства.",
            "Для обращения требуется регистрация по месту жительства или месту пребывания.",
        ),
    ]
    for old_text, new_text in condition_pairs:
        add(
            document_type="регламент",
            scenario="condition_changed",
            old_text=old_text,
            new_text=new_text,
            change_type="condition",
            entities=[{"type": "condition_change", "value": "true"}],
            importance="important",
        )

    # ----------------------------
    # INFORMATIONAL
    # ----------------------------
    info_pairs = [
        (
            "Консультации предоставляются в рабочее время.",
            "Консультации предоставляются в рабочее время. Дополнительно указан телефон горячей линии 8-800-100-00-00.",
        ),
        (
            "Подробная информация размещается на официальном сайте.",
            "Подробная информация размещается на официальном сайте и в информационных стендах в помещении МФЦ.",
        ),
        (
            "Порядок заполнения заявления определяется приложением.",
            "Порядок заполнения заявления определяется приложением, в котором приведён пример заполнения формы.",
        ),
        (
            "Информация о ходе рассмотрения заявления предоставляется заявителю.",
            "Информация о ходе рассмотрения заявления предоставляется заявителю, в том числе посредством справочного номера.",
        ),
        (
            "В тексте документа используются термины, установленные законодательством.",
            "В тексте документа используются термины, установленные законодательством, а также даны пояснения к отдельным сокращениям.",
        ),
    ]
    for old_text, new_text in info_pairs:
        add(
            document_type="памятка",
            scenario="informational_addition",
            old_text=old_text,
            new_text=new_text,
            change_type="informational",
            entities=[{"type": "info_change", "value": "true"}],
            importance="informational",
        )

    # ----------------------------
    # EDITORIAL
    # ----------------------------
    editorial_pairs = [
        (
            "Заявитель предоставляет документы лично.",
            "Заявитель предоставляет документы лично.",
        ),
        (
            "Прием документов осуществляется ежедневно.",
            "Приём документов осуществляется ежедневно.",
        ),
        (
            "Документ подписывается уполномоченным лицом.",
            "Документ подписывается уполномоченным лицом;",
        ),
        (
            "Раздел 3. Порядок предоставления услуги.",
            "РАЗДЕЛ 3. Порядок предоставления услуги.",
        ),
        (
            "Заявление регистрируется в течение 1 дня.",
            "Заявление регистрируется в течение одного дня.",
        ),
        (
            "Пункт 4.1. Общие положения.",
            "Пункт 4.1 Общие положения.",
        ),
        (
            "Информация размещается на сайте учреждения.",
            "Информация размещается на сайте организации.",
        ),
        (
            "Порядок предоставления услуги определяется настоящим регламентом.",
            "Порядок предоставления услуги определяется настоящим Регламентом.",
        ),
    ]
    for old_text, new_text in editorial_pairs:
        add(
            document_type="регламент",
            scenario="editorial_change",
            old_text=old_text,
            new_text=new_text,
            change_type="editorial",
            entities=[{"type": "editorial_change", "value": "true"}],
            importance="editorial",
        )

    # Добавим несколько явных structural/editorial кейсов
    structural_pairs = [
        (
            "Раздел II. Порядок предоставления услуги",
            "Глава 2. Порядок предоставления услуги",
        ),
        (
            "Пункт 5.2.",
            "Пункт 5.3.",
        ),
        (
            "Приложение 1",
            "Приложение № 1",
        ),
    ]
    for old_text, new_text in structural_pairs:
        add(
            document_type="регламент",
            scenario="structural_renumbering",
            old_text=old_text,
            new_text=new_text,
            change_type="structure",
            entities=[{"type": "structure_change", "value": "true"}],
            importance="editorial",
        )

    rnd = random.Random(42)
    rnd.shuffle(rows)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    label_counts = Counter(row["importance_label"] for row in rows)
    type_counts = Counter(row["change_type"] for row in rows)

    print(f"[OK] wrote: {OUT_PATH}")
    print(f"[OK] rows: {len(rows)}")
    print(f"[OK] labels: {dict(label_counts)}")
    print(f"[OK] change_types: {dict(type_counts)}")


if __name__ == "__main__":
    main()