"""
Django settings for the Muranga e-Citizen backend.

Deployed on Render (https://citizen-muranga-portal.onrender.com)
Frontend on Vercel (https://muranga-ecitizen-frontend-final.vercel.app)
"""
import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# The project package name (the folder that holds this file), detected
# automatically so ROOT_URLCONF / WSGI_APPLICATION are always correct.
PROJECT_PACKAGE = __name__.rsplit(".", 1)[0]

# ---------------------------------------------------------------- Core
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
DEBUG = os.getenv("DEBUG", "False") == "True"

ALLOWED_HOSTS = [
    "citizen-muranga-portal.onrender.com",
    "localhost",
    "127.0.0.1",
]
# Render also injects its hostname; allow it automatically.
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Public URL of the frontend. Used to build the links inside verification
# and password-reset emails. No trailing slash.
FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "https://muranga-ecitizen-frontend-final.vercel.app",
).rstrip("/")

# How long a verification / reset code stays valid (minutes).
OTP_TTL_MINUTES = int(os.getenv("OTP_TTL_MINUTES", "15"))

# ---------------------------------------------------------------- Apps
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "auditlog",
]

# All Django apps live under apps/. Each apps.py must have name = "apps.<folder>".
LOCAL_APPS = [
    "apps.users",
    "apps.categories",
    "apps.service_requests",
    "apps.announcements",
    "apps.notifications",
    "apps.audit_logs",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------- Middleware
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # MUST be first
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
]

# ---------------------------------------------------------------- CORS / CSRF
CORS_ALLOWED_ORIGINS = [
    "https://muranga-ecitizen-frontend-final.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Vercel preview deployments (remove if you don't want them allowed)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://muranga-ecitizen-frontend-final-.*\.vercel\.app$",
]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "https://muranga-ecitizen-frontend-final.vercel.app",
    "https://citizen-muranga-portal.onrender.com",
]

# ---------------------------------------------------------------- URLs / WSGI
ROOT_URLCONF = f"{PROJECT_PACKAGE}.urls"
WSGI_APPLICATION = f"{PROJECT_PACKAGE}.wsgi.application"

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
    },
]

# ---------------------------------------------------------------- Database
# On Render, set DATABASE_URL to your Postgres connection string (Neon).
# Without it Django falls back to SQLite, which is wiped on every deploy.
#
# conn_health_checks=True makes Django test a reused connection before using
# it. Neon closes idle connections, which caused
# "SSL connection has been closed unexpectedly" (500) on the first request
# after a quiet period. With the check, Django opens a fresh connection instead.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# ---------------------------------------------------------------- Auth
AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------- DRF / JWT
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}
# In production return JSON only (no browsable HTML API, which needs
# collected static files and can itself cause 500s).
if not DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (
        "rest_framework.renderers.JSONRenderer",
    )

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# ---------------------------------------------------------------- Celery / Redis
# If REDIS_URL is NOT set (e.g. Render free tier with no Redis), tasks run
# immediately inside the request instead of trying to reach localhost:6379.
# That connection attempt is a common cause of 500s on register.
REDIS_URL = os.getenv("REDIS_URL", "")
CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_RESULT_BACKEND = REDIS_URL or "cache+memory://"
CELERY_TIMEZONE = "Africa/Nairobi"
CELERY_TASK_ALWAYS_EAGER = not REDIS_URL
CELERY_TASK_EAGER_PROPAGATES = False  # a failing task must not crash the request

# ---------------------------------------------------------------- Africa's Talking (SMS)
AFRICASTALKING_USERNAME = os.getenv("AFRICASTALKING_USERNAME", "sandbox")
AFRICASTALKING_API_KEY = os.getenv("AFRICASTALKING_API_KEY", "")

# Aliases so older code that reads AT_* keeps working.
AT_USERNAME = AFRICASTALKING_USERNAME
AT_API_KEY = AFRICASTALKING_API_KEY

# ---------------------------------------------------------------- Email (verification codes)
# Production delivery uses HTTPS providers in apps.users.otp. In DEBUG, Django's
# console backend is available for local development only.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------- i18n
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Non-manifest storage: does not 500 if collectstatic hasn't run.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- Render / HTTPS proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------- Logging
# Sends full tracebacks to the Render logs so 500 errors are visible.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}