from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from .views import api_root, health, live


class ApiRootTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_api_root_returns_service_description(self):
        request = self.factory.get("/api/")
        response = api_root(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertIn("health", response.data["api"])
        self.assertIn("documents", response.data["api"])

    def test_live_returns_200(self):
        request = self.factory.get("/api/health/live/")
        response = live(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")


class HealthEndpointTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @override_settings(QDRANT_ENABLED=False)
    @patch("core.views._check_database")
    def test_health_returns_200_when_db_is_ok_and_qdrant_is_disabled(
        self,
        mock_check_database,
    ):
        mock_check_database.return_value = {
            "status": "ok",
            "engine": "sqlite",
            "result": 1,
        }

        request = self.factory.get("/api/health")
        response = health(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["checks"]["database"]["status"], "ok")
        self.assertEqual(response.data["checks"]["qdrant"]["status"], "disabled")

    @override_settings(QDRANT_ENABLED=True)
    @patch("core.views._check_qdrant")
    @patch("core.views._check_database")
    def test_health_returns_200_when_all_enabled_checks_are_ok(
        self,
        mock_check_database,
        mock_check_qdrant,
    ):
        mock_check_database.return_value = {
            "status": "ok",
            "engine": "sqlite",
            "result": 1,
        }
        mock_check_qdrant.return_value = {
            "status": "ok",
            "host": "qdrant",
            "port": 6333,
            "collections_count": 0,
        }

        request = self.factory.get("/api/health")
        response = health(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["checks"]["database"]["status"], "ok")
        self.assertEqual(response.data["checks"]["qdrant"]["status"], "ok")

    @override_settings(QDRANT_ENABLED=True)
    @patch("core.views._check_qdrant", side_effect=RuntimeError("qdrant down"))
    @patch("core.views._check_database")
    def test_health_returns_503_when_enabled_qdrant_is_unavailable(
        self,
        mock_check_database,
        mock_check_qdrant,
    ):
        mock_check_database.return_value = {
            "status": "ok",
            "engine": "sqlite",
            "result": 1,
        }

        request = self.factory.get("/api/health")
        response = health(request)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["checks"]["database"]["status"], "ok")
        self.assertEqual(response.data["checks"]["qdrant"]["status"], "error")
        self.assertIn("qdrant down", response.data["checks"]["qdrant"]["error"])
