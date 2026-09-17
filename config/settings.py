"""Django settings for the Truck Parts AI Data Center MVP."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.postgres",
    "django_q",
    "import_export",
    "apps.core",
    "apps.catalog",
    "apps.suppliers",
    "apps.ai",
    "apps.inquiry",
    "apps.ingest",
    "apps.quality",
    "apps.listing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://truckparts:truckparts@localhost:5440/truckparts"),
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

# --- Background tasks (django-q2, ORM broker; see DESIGN.md ADR-04) ---
Q_CLUSTER = {
    "name": "truckparts",
    "workers": 2,
    "timeout": 600,
    "retry": 900,
    "orm": "default",
    "sync": env.bool("Q_SYNC", default=False),
}

# --- AI (OpenAI-compatible API; see DESIGN.md ADR-05) ---
LLM_BASE_URL = env("LLM_BASE_URL", default="https://api.deepseek.com/v1")
LLM_API_KEY = env("LLM_API_KEY", default="")
LLM_MODEL = env("LLM_MODEL", default="deepseek-chat")
VISION_BASE_URL = env("VISION_BASE_URL", default="") or LLM_BASE_URL
VISION_API_KEY = env("VISION_API_KEY", default="") or LLM_API_KEY
VISION_MODEL = env("VISION_MODEL", default="")
EMBEDDING_BASE_URL = env("EMBEDDING_BASE_URL", default="") or LLM_BASE_URL
EMBEDDING_API_KEY = env("EMBEDDING_API_KEY", default="") or LLM_API_KEY
EMBEDDING_MODEL = env("EMBEDDING_MODEL", default="")
EMBEDDING_DIM = 1024  # fixed by the Product.embedding column
AI_TIMEOUT = env.int("AI_TIMEOUT", default=60)
# Mock when explicitly requested or when no key is configured.
AI_MOCK = env.bool("AI_MOCK", default=False) or not LLM_API_KEY

# --- Pricing (see DESIGN.md §6) ---
FX_TO_USD = {"USD": 1.0, "CNY": 0.14, "EUR": 1.08}
OFFER_FRESH_DAYS = 180
