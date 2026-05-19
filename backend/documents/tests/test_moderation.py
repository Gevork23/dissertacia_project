import json
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from ..api.serializers import VersionDiffSerializer
from ..domain.change_enrichment import enrich_compare_payload
from ..domain.text_processing import sha256_hex
from ..models import Document, DocumentVersion, ModeratedChange
from ..services.moderation import annotate_diff_for_moderation
from ..services.workflows import build_comparison_payload, create_quiz_from_versions

TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ModeratedChangeModelTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.admin_user = User.objects.get(username="admin")
        self.document = Document.objects.create(title="Moderation doc")
        self.version_one = self._make_version(
            version_number=1,
            filename="v1.txt",
            text="Статья 1\nСрок рассмотрения составляет 10 рабочих дней.",
        )
        self.version_two = self._make_version(
            version_number=2,
            filename="v2.txt",
            text="Статья 1\nСрок рассмотрения составляет 7 рабочих дней.",
        )

    def _make_version(self, *, version_number: int, filename: str, text: str):
        uploaded_file = SimpleUploadedFile(
            filename,
            text.encode("utf-8"),
            content_type="text/plain",
        )
        return DocumentVersion.objects.create(
            document=self.document,
            version_number=version_number,
            source_filename=filename,
            file=uploaded_file,
            extracted_text=text,
            normalized_text=text,
            content_hash=sha256_hex(text),
        )

    def test_moderated_change_enforces_uniqueness(self):
        ModeratedChange.objects.create(
            from_version=self.version_one,
            to_version=self.version_two,
            change_id="abc",
            original_label=ModeratedChange.Label.CRITICAL,
            corrected_label=ModeratedChange.Label.IMPORTANT,
            moderated_by=self.admin_user,
        )
        with self.assertRaises(IntegrityError):
            ModeratedChange.objects.create(
                from_version=self.version_one,
                to_version=self.version_two,
                change_id="abc",
                original_label=ModeratedChange.Label.CRITICAL,
                corrected_label=ModeratedChange.Label.MINOR,
                moderated_by=self.admin_user,
            )


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ModerationViewsTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.admin_user = User.objects.get(username="admin")
        self.employee_user = User.objects.get(username="user")
        self.document = Document.objects.create(title="Moderation flow doc")
        self.version_one = self._make_version(
            version_number=1,
            filename="v1.txt",
            text=(
                "Раздел I Общие положения\n\n"
                "Статья 1 Срок\n"
                "1. Срок составляет 10 рабочих дней."
            ),
        )
        self.version_two = self._make_version(
            version_number=2,
            filename="v2.txt",
            text=(
                "Раздел I Общие положения\n\n"
                "Статья 1 Срок\n"
                "1. Срок составляет 7 рабочих дней."
            ),
        )

    def _make_version(self, *, version_number: int, filename: str, text: str):
        uploaded_file = SimpleUploadedFile(
            filename,
            text.encode("utf-8"),
            content_type="text/plain",
        )
        return DocumentVersion.objects.create(
            document=self.document,
            version_number=version_number,
            source_filename=filename,
            file=uploaded_file,
            extracted_text=text,
            normalized_text=text,
            content_hash=sha256_hex(text),
        )

    def _first_moderation_row(self):
        raw_diff = VersionDiffSerializer(
            build_comparison_payload(
                from_version=self.version_one,
                to_version=self.version_two,
            )
        ).data
        enriched = enrich_compare_payload(raw_diff)
        _, rows = annotate_diff_for_moderation(
            enriched,
            from_version=self.version_one,
            to_version=self.version_two,
            apply_corrections=False,
        )
        return rows[0]

    def test_moderate_page_is_admin_only(self):
        self.client.force_login(self.employee_user)

        response = self.client.get(
            reverse("demo-moderate"),
            {"from_version": self.version_one.id, "to_version": self.version_two.id},
        )

        self.assertEqual(response.status_code, 403)

    def test_moderate_page_renders_changes_for_admin(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("demo-moderate"),
            {"from_version": self.version_one.id, "to_version": self.version_two.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Модерация изменений")
        self.assertContains(response, "Сохранить все изменения")

    def test_moderate_page_without_pair_shows_document_selector(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("demo-moderate"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Выберите документ")
        self.assertContains(response, self.document.title)

    def test_moderate_api_saves_corrections(self):
        row = self._first_moderation_row()
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("demo-moderate-api"),
            content_type="application/json",
            data=(
                "{"
                f"\"from_version\":{self.version_one.id},"
                f"\"to_version\":{self.version_two.id},"
                "\"changes\":["
                "{"
                f"\"change_id\":\"{row['change_id']}\","
                "\"corrected_label\":\"important\","
                "\"comment\":\"Эксперт повысил значимость.\""
                "}"
                "]}"
            ),
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["saved"], 1)
        moderated = ModeratedChange.objects.get(change_id=row["change_id"])
        self.assertEqual(moderated.corrected_label, ModeratedChange.Label.IMPORTANT)
        self.assertEqual(moderated.comment, "Эксперт повысил значимость.")

    def test_moderate_api_is_admin_only(self):
        row = self._first_moderation_row()
        self.client.force_login(self.employee_user)

        response = self.client.post(
            reverse("demo-moderate-api"),
            content_type="application/json",
            data=(
                "{"
                f"\"from_version\":{self.version_one.id},"
                f"\"to_version\":{self.version_two.id},"
                "\"changes\":["
                "{"
                f"\"change_id\":\"{row['change_id']}\","
                "\"corrected_label\":\"ignored\""
                "}"
                "]}"
            ),
        )

        self.assertEqual(response.status_code, 403)

    def test_create_quiz_can_use_moderated_labels(self):
        row = self._first_moderation_row()
        ModeratedChange.objects.create(
            from_version=self.version_one,
            to_version=self.version_two,
            change_id=row["change_id"],
            original_label=row["original_label"],
            corrected_label=ModeratedChange.Label.IMPORTANT,
            comment="Понижено до important.",
            moderated_by=self.admin_user,
        )

        quiz = create_quiz_from_versions(
            from_version=self.version_one,
            to_version=self.version_two,
            title="Moderated quiz",
            max_questions=3,
            use_moderation=True,
        )

        self.assertEqual(quiz.questions.first().source_change_item.significance_label, "important")
