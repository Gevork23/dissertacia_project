from django.test import SimpleTestCase

from documents.change_enrichment import enrich_change


class ChangeEnrichmentTests(SimpleTestCase):
    def test_deadline_change_gets_importance(self) -> None:
        change = {
            "old_text": "Срок рассмотрения заявления составляет 5 рабочих дней.",
            "new_text": "Срок рассмотрения заявления составляет 10 рабочих дней.",
        }

        enriched = enrich_change(change)

        self.assertEqual(enriched["change_type"], "deadline")
        self.assertEqual(enriched["importance_label"], "critical")
        self.assertTrue(enriched["importance_confidence"] >= 0.9)

    def test_document_change_gets_importance(self) -> None:
        change = {
            "old_text": "Для получения услуги заявитель представляет паспорт.",
            "new_text": "Для получения услуги заявитель представляет паспорт и СНИЛС.",
        }

        enriched = enrich_change(change)

        self.assertEqual(enriched["change_type"], "document")
        self.assertEqual(enriched["importance_label"], "critical")

    def test_editorial_change_gets_importance(self) -> None:
        change = {
            "old_text": "Прием документов осуществляется ежедневно.",
            "new_text": "Приём документов осуществляется ежедневно.",
        }

        enriched = enrich_change(change)

        self.assertEqual(enriched["change_type"], "editorial")
        self.assertEqual(enriched["importance_label"], "editorial")

    def test_procedure_change_gets_importance(self) -> None:
        change = {
            "old_text": "Приём заявлений осуществляется в порядке живой очереди.",
            "new_text": "Приём заявлений осуществляется по предварительной записи через региональный портал.",
        }

        enriched = enrich_change(change)

        self.assertEqual(enriched["change_type"], "procedure")
        self.assertEqual(enriched["importance_label"], "important")