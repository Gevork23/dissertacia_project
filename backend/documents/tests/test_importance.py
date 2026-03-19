from django.test import SimpleTestCase
from documents.services.importance import classify_change_importance


class ImportanceRulesTests(SimpleTestCase):
    def test_deadline_change_is_critical(self) -> None:
        prediction = classify_change_importance(
            old_text="Срок рассмотрения заявления составляет 5 рабочих дней.",
            new_text="Срок рассмотрения заявления составляет 10 рабочих дней.",
            change_type="deadline",
        )
        self.assertEqual(prediction.label, "critical")

    def test_refusal_change_is_critical(self) -> None:
        prediction = classify_change_importance(
            old_text="Основания для отказа отсутствуют.",
            new_text="Основанием для отказа является отсутствие регистрации по месту жительства.",
            change_type="refusal",
        )
        self.assertEqual(prediction.label, "critical")

    def test_procedure_change_is_important(self) -> None:
        prediction = classify_change_importance(
            old_text="Приём заявлений осуществляется в порядке живой очереди.",
            new_text="Приём заявлений осуществляется по предварительной записи через региональный портал.",
            change_type="procedure",
        )
        self.assertEqual(prediction.label, "important")

    def test_informational_addition_is_informational(self) -> None:
        prediction = classify_change_importance(
            old_text="Консультации предоставляются в рабочее время.",
            new_text="Консультации предоставляются в рабочее время. Дополнительно указан телефон горячей линии 8-800-100-00-00.",
            change_type="informational",
        )
        self.assertEqual(prediction.label, "informational")

    def test_editorial_change_is_editorial(self) -> None:
        prediction = classify_change_importance(
            old_text="Прием документов осуществляется ежедневно.",
            new_text="Приём документов осуществляется ежедневно.",
            change_type="editorial",
        )
        self.assertEqual(prediction.label, "editorial")
