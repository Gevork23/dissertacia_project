# backend/config/apps.py
from __future__ import annotations

import logging

from django.apps import AppConfig

logger = logging.getLogger("core.startup")


class ConfigConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "config"

    def ready(self) -> None:
        logger.info("Startup: logging is configured and Django app is ready.")
