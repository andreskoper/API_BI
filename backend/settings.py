#Configuración global del proyecto (apps instaladas, templates, middleware, base de datos)
import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-test"

DEBUG = True

ALLOWED_HOSTS = ["*"]

ROOT_URLCONF = "backend.urls"


load_dotenv()

PBI_CLIENT_ID = os.getenv("PBI_CLIENT_ID")
PBI_CLIENT_SECRET = os.getenv("PBI_CLIENT_SECRET")
PBI_TENANT_ID = os.getenv("PBI_TENANT_ID")

PBI_GROUP_ID = os.getenv("PBI_GROUP_ID")
PBI_DATASET_ID = os.getenv("PBI_DATASET_ID")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True




INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    'powerbi.apps.PowerbiConfig',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    'whitenoise.middleware.WhiteNoiseMiddleware',
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    BASE_DIR / "static",
]
def validar_env(var, nombre):
    if not var:
        raise Exception(f"Falta variable de entorno: {nombre}")
    return var

PBI_CLIENT_ID = validar_env(os.getenv("PBI_CLIENT_ID"), "PBI_CLIENT_ID")
PBI_CLIENT_SECRET = validar_env(os.getenv("PBI_CLIENT_SECRET"), "PBI_CLIENT_SECRET")
PBI_TENANT_ID = validar_env(os.getenv("PBI_TENANT_ID"), "PBI_TENANT_ID")

EMAIL_HOST_USER = validar_env(os.getenv("EMAIL_HOST_USER"), "EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = validar_env(os.getenv("EMAIL_HOST_PASSWORD"), "EMAIL_HOST_PASSWORD")
ADMIN_EMAIL = validar_env(os.getenv("ADMIN_EMAIL"), "ADMIN_EMAIL")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER