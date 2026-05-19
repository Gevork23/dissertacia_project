from __future__ import annotations

import json
import sys
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from documents.models import RusLawODDocument
from documents.ruslawod.build_test_cases import build_regression_pairs
from documents.ruslawod.data_loader import download_ruslawod, extract_metadata_and_text
from documents.ruslawod.process_dataset import import_ruslawod_documents


class RusLawODDataLoaderTests(SimpleTestCase):
    def test_extract_metadata_and_text_parses_document(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            xml_path = Path(temp_dir) / "sample.xml"
            xml_path.write_text(
                """
                <act>
                  <meta>
                    <identification>
                      <pravogovruNd val="123456789" />
                      <issuedByIPS val="Правительство РФ" />
                      <docdateIPS val="17.05.2026" />
                      <docNumberIPS val="42" />
                      <headingIPS>О внесении изменений</headingIPS>
                      <doc_typeIPS val="Постановление" />
                      <signedIPS val="И.И. Иванов" />
                      <statusIPS val="действует" />
                    </identification>
                  </meta>
                  <text>
                    <textIPS>
                      <p>Первый абзац.</p>
                      <p>Второй  абзац.</p>
                    </textIPS>
                  </text>
                  <keywords>
                    <keywordsByIPS val="изменения; регламент" />
                  </keywords>
                  <reference>
                    <classifierByIPS val="02.01" />
                  </reference>
                </act>
                """,
                encoding="utf-8",
            )

            payload = extract_metadata_and_text(xml_path)

        self.assertEqual(payload["pravo_gov_ru_nd"], "123456789")
        self.assertEqual(payload["heading"], "О внесении изменений")
        self.assertEqual(payload["document_date"], date(2026, 5, 17))
        self.assertEqual(payload["cleaned_text"], "Первый абзац. Второй абзац.")
        self.assertIn("правительство рф", payload["version_family_key"])
        self.assertEqual(payload["metadata"]["classifier"], "02.01")
        self.assertEqual(payload["metadata"]["keywords"], "изменения; регламент")

    def test_download_ruslawod_streams_and_uses_cache(self):
        rows = [
            {
                "pravogovruNd": "000000001",
                "issuedByIPS": "Правительство РФ",
                "docdateIPS": "17.05.2026",
                "docNumberIPS": "1",
                "headingIPS": "Документ 1",
                "doc_typeIPS": "Постановление",
                "textIPS": "Текст 1",
            },
            {
                "pravogovruNd": "000000002",
                "issuedByIPS": "Правительство РФ",
                "docdateIPS": "18.05.2026",
                "docNumberIPS": "2",
                "headingIPS": "Документ 2",
                "doc_typeIPS": "Постановление",
                "textIPS": "Текст 2",
            },
        ]
        calls = {"count": 0}

        def fake_load_dataset(name, split, streaming, cache_dir):
            calls["count"] += 1
            self.assertEqual(name, "irlspbru/RusLawOD")
            self.assertEqual(split, "train")
            self.assertTrue(streaming)
            self.assertTrue(str(cache_dir).endswith("hf"))
            return iter(rows)

        fake_datasets = SimpleNamespace(load_dataset=fake_load_dataset)
        fake_tqdm = SimpleNamespace(tqdm=lambda iterable, **kwargs: iterable)

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                sys.modules,
                {"datasets": fake_datasets, "tqdm": fake_tqdm},
            ):
                paths = download_ruslawod(cache_dir=temp_dir, limit=2)
                cached_paths = download_ruslawod(cache_dir=temp_dir, limit=2)

            manifest = json.loads(
                (Path(temp_dir) / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(calls["count"], 1)
        self.assertEqual(len(paths), 2)
        self.assertEqual(paths, cached_paths)
        self.assertEqual(manifest["count"], 2)
        self.assertEqual(manifest["dataset"], "irlspbru/RusLawOD")


class RusLawODModelTests(TestCase):
    def test_ruslawod_document_requires_identifier_and_text(self):
        document = RusLawODDocument(
            pravo_gov_ru_nd="",
            source_xml="",
            cleaned_text="",
        )

        with self.assertRaises(ValidationError):
            document.full_clean()

    def test_ruslawod_document_normalizes_fields(self):
        document = RusLawODDocument.objects.create(
            pravo_gov_ru_nd=" 123456789 ",
            heading="  О   внесении   изменений ",
            source_xml="<act />",
            cleaned_text="  Первый   второй  ",
            version_family_key="  Family ",
        )

        self.assertEqual(document.pravo_gov_ru_nd, "123456789")
        self.assertEqual(document.heading, "О внесении изменений")
        self.assertEqual(document.cleaned_text, "Первый второй")
        self.assertEqual(document.version_family_key, "Family")


class RusLawODServiceTests(TestCase):
    def test_import_ruslawod_documents_upserts_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            xml_path = Path(temp_dir) / "123456789.xml"
            xml_path.write_text(
                """
                <act>
                  <meta><identification>
                    <pravogovruNd val="123456789" />
                    <docdateIPS val="01.01.2026" />
                    <headingIPS>Заголовок</headingIPS>
                  </identification></meta>
                  <text><textIPS>Первая редакция</textIPS></text>
                </act>
                """,
                encoding="utf-8",
            )
            with patch(
                "documents.ruslawod.process_dataset.download_ruslawod",
                return_value=[xml_path],
            ):
                first_stats = import_ruslawod_documents(cache_dir=temp_dir)

            xml_path.write_text(
                """
                <act>
                  <meta><identification>
                    <pravogovruNd val="123456789" />
                    <docdateIPS val="01.01.2026" />
                    <headingIPS>Заголовок</headingIPS>
                  </identification></meta>
                  <text><textIPS>Вторая редакция</textIPS></text>
                </act>
                """,
                encoding="utf-8",
            )
            with patch(
                "documents.ruslawod.process_dataset.download_ruslawod",
                return_value=[xml_path],
            ):
                second_stats = import_ruslawod_documents(cache_dir=temp_dir)

        document = RusLawODDocument.objects.get(pravo_gov_ru_nd="123456789")
        self.assertEqual(first_stats, {"processed": 1, "created": 1, "updated": 0})
        self.assertEqual(second_stats, {"processed": 1, "created": 0, "updated": 1})
        self.assertEqual(document.cleaned_text, "Вторая редакция")

    def test_build_regression_pairs_writes_consecutive_versions(self):
        first = RusLawODDocument.objects.create(
            pravo_gov_ru_nd="111111111",
            heading="Регламент",
            document_date=date(2026, 1, 1),
            source_xml="<act />",
            cleaned_text="Первая редакция",
            version_family_key="family-1",
        )
        second = RusLawODDocument.objects.create(
            pravo_gov_ru_nd="222222222",
            heading="Регламент",
            document_date=date(2026, 2, 1),
            source_xml="<act />",
            cleaned_text="Вторая редакция",
            version_family_key="family-1",
        )
        third = RusLawODDocument.objects.create(
            pravo_gov_ru_nd="333333333",
            heading="Регламент",
            document_date=date(2026, 3, 1),
            source_xml="<act />",
            cleaned_text="Третья редакция",
            version_family_key="family-1",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "pairs.json"
            export_dir = Path(temp_dir) / "pairs"
            pairs = build_regression_pairs(
                limit=10,
                output_path=output_path,
                export_dir=export_dir,
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            first_old_path = Path(payload[0]["v1_path"])
            first_new_path = Path(payload[0]["v2_path"])
            self.assertTrue(first_old_path.exists())
            self.assertTrue(first_new_path.exists())

        self.assertEqual(len(pairs), 2)
        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]["v1_document_id"], first.id)
        self.assertEqual(payload[0]["v2_document_id"], second.id)
        self.assertEqual(payload[1]["v1_document_id"], second.id)
        self.assertEqual(payload[1]["v2_document_id"], third.id)
        self.assertEqual(payload[0]["annotation_status"], "pending")


class RusLawODCommandTests(TestCase):
    def test_import_ruslawod_command_outputs_stats(self):
        with patch(
            "documents.management.commands.import_ruslawod.import_ruslawod_documents",
            return_value={"processed": 3, "created": 2, "updated": 1},
        ):
            with tempfile.TemporaryFile(mode="w+") as stdout:
                call_command("import_ruslawod", limit=3, stdout=stdout)
                stdout.seek(0)
                output = stdout.read()

        self.assertIn("processed=3", output)
        self.assertIn("created=2", output)
        self.assertIn("updated=1", output)

    def test_generate_regression_pairs_command_outputs_result(self):
        with patch(
            "documents.management.commands.generate_regression_pairs.build_regression_pairs",
            return_value=[{"id": "pair-1"}, {"id": "pair-2"}],
        ):
            with tempfile.TemporaryFile(mode="w+") as stdout:
                call_command(
                    "generate_regression_pairs",
                    limit=2,
                    output="ruslawod.json",
                    export_dir="ruslawod_pairs",
                    stdout=stdout,
                )
                stdout.seek(0)
                output = stdout.read()

        self.assertIn("Generated 2 RusLawOD regression pairs", output)
