"""
Django settings for the CoreSDK django-app example.
"""

import os
import tomllib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY", "dev-only-insecure-secret-key-change-in-prod"
)

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "api",
]

# ── CoreSDK middleware first, then standard Django middleware ──────────────────
MIDDLEWARE = [
    "coresdk.middleware.django.CoreSDKMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "api.urls"

WSGI_APPLICATION = "api.wsgi.application"

# No database — in-memory store only
DATABASES = {}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Load coresdk.toml ─────────────────────────────────────────────────────────


def _load_coresdk_config() -> dict:
    config_path = BASE_DIR / "coresdk.toml"
    with open(config_path, "rb") as f:
        cfg = tomllib.load(f)
    sdk = cfg["sdk"]
    sdk["sidecar_addr"] = os.getenv("CORESDK_SIDECAR_ADDR", sdk["sidecar_addr"])
    sdk["tenant_id"] = os.getenv("CORESDK_TENANT_ID", sdk["tenant_id"])
    sdk["service_name"] = os.getenv("CORESDK_SERVICE_NAME", sdk["service_name"])
    sdk["fail_mode"] = os.getenv("CORESDK_FAIL_MODE", sdk["fail_mode"])
    sdk["dev_mode"] = (
        os.getenv("CORESDK_DEV_MODE", str(sdk["dev_mode"])).lower() == "true"
    )
    return cfg


CORESDK = _load_coresdk_config()

# ── Django REST Framework ─────────────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "UNAUTHENTICATED_USER": None,
}
