from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


def split_csv(raw: str) -> list[str]:
    cleaned = raw.replace(";", ",").replace(" ", ",")
    return [item.strip() for item in cleaned.split(",") if item.strip()]


SECRET_KEY = env_str("DJANGO_SECRET_KEY", "change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)


env_hosts = split_csv(env_str("DJANGO_ALLOWED_HOSTS"))
dev_hosts = ["localhost", "127.0.0.1", "0.0.0.0"]
if DEBUG:
    ALLOWED_HOSTS = sorted(set(env_hosts + dev_hosts))
else:
    ALLOWED_HOSTS = env_hosts or ["localhost"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
    "documents",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.RequestLogMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

DB_ENGINE = env_str("DB_ENGINE", "postgres").lower()
if DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env_str("POSTGRES_DB", "dissertacia"),
            "USER": env_str("POSTGRES_USER", "dissertacia"),
            "PASSWORD": env_str("POSTGRES_PASSWORD", "dissertacia"),
            "HOST": env_str("POSTGRES_HOST", "db"),
            "PORT": env_str("POSTGRES_PORT", "5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        )
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
}

QDRANT_ENABLED = env_bool("QDRANT_ENABLED", False)
QDRANT_HOST = env_str("QDRANT_HOST", "qdrant")
QDRANT_PORT = env_int("QDRANT_PORT", 6333)
QDRANT_TIMEOUT_SECONDS = float(env_str("QDRANT_TIMEOUT_SECONDS", "3"))

ENTITY_LLM_API_URL = env_str("ENTITY_LLM_API_URL")
ENTITY_LLM_API_KEY = env_str("ENTITY_LLM_API_KEY")
ENTITY_LLM_MODEL = env_str("ENTITY_LLM_MODEL")
ENTITY_LLM_TIMEOUT_SECONDS = env_int("ENTITY_LLM_TIMEOUT_SECONDS", 60)

LOG_LEVEL = env_str("DJANGO_LOG_LEVEL", "INFO").upper()
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "core.logging.RequestIdFilter",
        },
    },
    "formatters": {
        "standard": {
            "format": (
                "%(asctime)s %(levelname)s [%(name)s] "
                "[rid=%(request_id)s] %(message)s"
            ),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "standard",
            "level": LOG_LEVEL,
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filters": ["request_id"],
            "formatter": "standard",
            "level": LOG_LEVEL,
            "filename": str(LOG_DIR / "backend.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
        },
    },
    "root": {"handlers": ["console", "file"], "level": LOG_LEVEL},
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "core": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "documents": {
            "handlers": ["console", "file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
