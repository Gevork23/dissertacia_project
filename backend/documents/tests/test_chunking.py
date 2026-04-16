import shutil
import tempfile

from django.test import SimpleTestCase, TestCase, override_settings

from ..domain.diff import build_version_diff
from ..domain.text_processing import (
    FRAGMENT_TYPE_ARTICLE,
    FRAGMENT_TYPE_FALLBACK_BLOCK,
    FRAGMENT_TYPE_POINT,
    FRAGMENT_TYPE_PREAMBLE,
    FRAGMENT_TYPE_SUBPOINT,
    FRAGMENT_TYPE_TITLE,
    chunk_by_structure_ru,
    sha256_hex,
)
from ..models import Chunk, Document, VersionComparison
from ..services.ingestion import rebuild_version_chunks
from ..services.versioning import create_text_document_version
from ..services.workflows import materialize_comparison

TEST_MEDIA_ROOT = tempfile.mkdtemp()


class StructuralChunkingUnitTests(SimpleTestCase):
    def test_chunk_by_structure_ru_splits_points_and_lettered_subpoints(self):
        text = (
            "ПОЛОЖЕНИЕ О ПРЕДОСТАВЛЕНИИ УСЛУГИ\n\n"
            "Раздел I Общие положения\n\n"
            "Статья 1 Порядок приема\n"
            "1. Прием заявлений осуществляется по графику.\n"
            "2. Для получения услуги представляются:\n"
            "а) заявление;\n"
            "б) паспорт."
        )

        chunks = chunk_by_structure_ru(text)

        self.assertEqual(chunks[0].fragment_type, FRAGMENT_TYPE_TITLE)
        self.assertEqual(chunks[1].fragment_type, FRAGMENT_TYPE_POINT)
        self.assertEqual(chunks[1].canonical_label, "Пункт 1")
        self.assertEqual(chunks[2].fragment_type, FRAGMENT_TYPE_POINT)
        self.assertIn("article:1/point:2", chunks[2].path_key)
        self.assertEqual(chunks[3].fragment_type, FRAGMENT_TYPE_SUBPOINT)
        self.assertEqual(chunks[3].canonical_label, "Подпункт а")
        self.assertIn("point:2/subpoint:а", chunks[3].path_key)
        self.assertEqual(chunks[4].fragment_type, FRAGMENT_TYPE_SUBPOINT)
        self.assertEqual(chunks[4].canonical_label, "Подпункт б")

    def test_chunk_by_structure_ru_keeps_article_body_when_no_points(self):
        text = (
            "Раздел I Общие положения\n\n"
            "Статья 3 Результат предоставления услуги\n"
            "Результатом является выдача документа либо мотивированного отказа."
        )

        chunks = chunk_by_structure_ru(text)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].fragment_type, FRAGMENT_TYPE_ARTICLE)
        self.assertEqual(chunks[0].canonical_label, "Статья 3")
        self.assertEqual(
            chunks[0].section_path,
            "Раздел I: Общие положения > Статья 3: Результат предоставления услуги",
        )

    def test_chunk_by_structure_ru_materializes_title_and_preamble(self):
        text = (
            "АДМИНИСТРАТИВНЫЙ РЕГЛАМЕНТ\n\n"
            "Настоящий регламент определяет общий порядок предоставления услуги.\n\n"
            "Статья 1 Предмет регулирования\n"
            "Регламент применяется при подаче заявления."
        )

        chunks = chunk_by_structure_ru(text)

        self.assertEqual(chunks[0].fragment_type, FRAGMENT_TYPE_TITLE)
        self.assertEqual(chunks[1].fragment_type, FRAGMENT_TYPE_PREAMBLE)
        self.assertEqual(chunks[2].fragment_type, FRAGMENT_TYPE_ARTICLE)

    def test_chunk_by_structure_ru_supports_hierarchical_numeric_subpoints(self):
        text = (
            "Статья 5 Основания проверки\n"
            "1. Проверка проводится в следующих случаях:\n"
            "1.1. при поступлении заявления;\n"
            "1.2. при уточнении сведений."
        )

        chunks = chunk_by_structure_ru(text)

        self.assertEqual(
            [chunk.fragment_type for chunk in chunks],
            [
                FRAGMENT_TYPE_POINT,
                FRAGMENT_TYPE_SUBPOINT,
                FRAGMENT_TYPE_SUBPOINT,
            ],
        )
        self.assertEqual(chunks[1].canonical_label, "Подпункт 1.1")
        self.assertIn("subpoint:1.1", chunks[1].path_key)

    def test_chunk_by_structure_ru_falls_back_for_unstructured_text(self):
        text = "Первый абзац без формальной структуры.\n\nВторой абзац без разметки."

        chunks = chunk_by_structure_ru(text)

        self.assertGreaterEqual(len(chunks), 1)
        self.assertTrue(
            all(chunk.fragment_type == FRAGMENT_TYPE_FALLBACK_BLOCK for chunk in chunks)
        )
        self.assertTrue(all(chunk.path_key.startswith("fallback:") for chunk in chunks))


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class StructuralChunkingIntegrationTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def test_create_text_document_version_materializes_structural_metadata(self):
        document = Document.objects.create(title="Регламент")
        version = create_text_document_version(
            document=document,
            source_filename="reglament.txt",
            raw_text=(
                "АДМИНИСТРАТИВНЫЙ РЕГЛАМЕНТ\n\n"
                "Статья 1 Срок предоставления услуги\n"
                "1. Общий срок составляет 7 рабочих дней.\n"
                "2. При межведомственном запросе срок продлевается на 2 дня."
            ),
        )

        chunks = list(version.chunks.order_by("chunk_index"))

        self.assertEqual(
            [chunk.fragment_type for chunk in chunks],
            [
                FRAGMENT_TYPE_TITLE,
                FRAGMENT_TYPE_POINT,
                FRAGMENT_TYPE_POINT,
            ],
        )
        self.assertEqual(chunks[1].canonical_label, "Пункт 1")
        self.assertEqual(chunks[1].structure_level, 4)
        self.assertTrue(chunks[1].path_key.endswith("article:1/point:1"))
        self.assertIn("Статья 1: Срок предоставления услуги", chunks[1].heading)

    def test_rebuild_version_chunks_invalidates_materialized_comparisons(self):
        document = Document.objects.create(title="Изменяемый регламент")
        version_one = create_text_document_version(
            document=document,
            source_filename="v1.txt",
            raw_text="Статья 1 Срок\n1. Срок составляет 10 дней.",
        )
        version_two = create_text_document_version(
            document=document,
            source_filename="v2.txt",
            raw_text="Статья 1 Срок\n1. Срок составляет 7 дней.",
        )

        materialize_comparison(from_version=version_one, to_version=version_two)
        self.assertEqual(VersionComparison.objects.count(), 1)

        rebuild_version_chunks(version_one)

        self.assertEqual(VersionComparison.objects.count(), 0)

    def test_diff_uses_path_key_for_modified_pairing(self):
        document = Document.objects.create(title="Diff by path")
        version_one = create_text_document_version(
            document=document,
            source_filename="v1.txt",
            raw_text="Статья 1 Срок\n1. Срок составляет 10 дней.",
        )
        version_two = create_text_document_version(
            document=document,
            source_filename="v2.txt",
            raw_text="Статья 1 Срок\n1. Срок составляет 7 дней.",
        )
        # Перестраховываемся: проверяем именно структурный контур, а не только parser.
        old_chunk = version_one.chunks.get(chunk_index=1)
        new_chunk = version_two.chunks.get(chunk_index=1)
        old_chunk.path_key = "article:1/point:1"
        old_chunk.canonical_label = "Пункт 1"
        old_chunk.heading = "Статья 1: Срок · Пункт 1"
        old_chunk.text_hash = sha256_hex(old_chunk.text)
        old_chunk.save(
            update_fields=["path_key", "canonical_label", "heading", "text_hash"]
        )
        new_chunk.path_key = "article:1/point:1"
        new_chunk.canonical_label = "Пункт 1"
        new_chunk.heading = "Статья 1: Срок · Пункт 1"
        new_chunk.text_hash = sha256_hex(new_chunk.text)
        new_chunk.save(
            update_fields=["path_key", "canonical_label", "heading", "text_hash"]
        )

        diff_payload = build_version_diff(version_one, version_two)

        self.assertEqual(diff_payload["summary"]["modified"], 1)
        self.assertEqual(diff_payload["modified"][0]["match_reason"], "path_key")

    def test_manual_chunk_supports_new_structural_fields(self):
        document = Document.objects.create(title="Ручной чанк")
        version = create_text_document_version(
            document=document,
            source_filename="manual.txt",
            raw_text="Просто текст",
        )

        chunk = Chunk.objects.create(
            version=version,
            chunk_index=99,
            fragment_type=Chunk.FragmentType.SUBPOINT,
            structure_level=5,
            raw_label="а)",
            canonical_label="Подпункт а",
            path_key="article:1/point:1/subpoint:а",
            heading="Статья 1 · Пункт 1 · Подпункт а",
            section_path="Статья 1 > Пункт 1 > Подпункт а",
            text="Дополнительное условие.",
            text_hash=sha256_hex("Дополнительное условие."),
        )

        self.assertEqual(chunk.fragment_type, Chunk.FragmentType.SUBPOINT)
        self.assertEqual(chunk.structure_level, 5)
        self.assertEqual(chunk.path_key, "article:1/point:1/subpoint:а")
