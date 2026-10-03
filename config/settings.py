import os
from pathlib import Path

from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or (
    "insecure-dev-key" if DEBUG else None
)
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off")

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,adredirector.loc").split(",")
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "src.redirect",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

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
            ],
        },
    },
]

# PostgreSQL when POSTGRES_HOST is set (Docker), SQLite otherwise (local dev/tests).
if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "NAME": os.environ.get("POSTGRES_DB", "ad_redirector"),
            "USER": os.environ.get("POSTGRES_USER", "ad_redirector"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Where /go/ sends visitors; {code} is replaced with the URL-encoded JuicyAds code.
JUICYADS_REDIRECT_URL = os.environ.get(
    "JUICYADS_REDIRECT_URL",
    "http://xapi.juicyads.com/d90c4c222228b7bdc2781ce358ae1ab3ce7072ef.php"
    "?juicy_code={code}&u=http%3A%2F%2Fwww.juicyads.rocks",
)

# Only enable behind exactly one reverse proxy you control (nginx-proxy in production);
# the last X-Forwarded-For entry is then the address that proxy saw. Without a proxy,
# visitors could spoof the IP that gets logged.
USE_X_FORWARDED_FOR = env_bool("USE_X_FORWARDED_FOR")

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_TIMEZONE = TIME_ZONE
# Periodic tasks run by the celery-beat service.
CELERY_BEAT_SCHEDULE = {
    "download-geoip-database": {
        "task": "src.redirect.tasks.download_geoip_database",
        "schedule": crontab(hour=3, minute=0),
    },
    "download-tor-exit-nodes": {
        "task": "src.redirect.tasks.download_tor_exit_nodes",
        "schedule": crontab(minute=15),
    },
    "clean-up-clicks": {
        "task": "src.redirect.tasks.clean_up_clicks",
        "schedule": crontab(hour=4, minute=0),
    },
}

# MaxMind GeoLite2 download (account ID and license key from maxmind.com → Manage License Keys).
MAXMIND_ACCOUNT_ID = os.environ.get("MAXMIND_ACCOUNT_ID", "")
MAXMIND_LICENSE_KEY = os.environ.get("MAXMIND_LICENSE_KEY", "")
# Databases to download. Add GeoIP2-Anonymous-IP (paid) to enable the VPN/proxy filter.
MAXMIND_EDITION_IDS = env_list("MAXMIND_EDITION_IDS", "GeoLite2-Country,GeoLite2-ASN")
MAXMIND_DATABASE_DIR = Path(os.environ.get("MAXMIND_DATABASE_DIR", BASE_DIR / "geoip"))
TOR_EXIT_NODES_PATH = MAXMIND_DATABASE_DIR / "tor-exit-nodes.txt"

# Traffic filtering for /go/<code>/ (see src/redirect/services/filtering).
# Log-only: record what would be blocked in Click.blocked_reason, but let every visit through.
TRAFFIC_FILTER_LOG_ONLY = env_bool("TRAFFIC_FILTER_LOG_ONLY")
# Where blocked visits are sent.
TRAFFIC_FILTER_BLOCKED_URL = os.environ.get("TRAFFIC_FILTER_BLOCKED_URL", "/")
# ISO country codes, e.g. "US,GB,DE". Empty allowed list = all countries allowed.
TRAFFIC_FILTER_ALLOWED_COUNTRIES = frozenset(
    c.upper() for c in env_list("TRAFFIC_FILTER_ALLOWED_COUNTRIES")
)
TRAFFIC_FILTER_BLOCKED_COUNTRIES = frozenset(
    c.upper() for c in env_list("TRAFFIC_FILTER_BLOCKED_COUNTRIES")
)
# ASNs to block on top of the built-in hosting provider list.
TRAFFIC_FILTER_EXTRA_BLOCKED_ASNS = frozenset(
    int(asn) for asn in env_list("TRAFFIC_FILTER_EXTRA_BLOCKED_ASNS")
)
# Block an IP that already went through the same link within this many hours (0 = off).
TRAFFIC_FILTER_REPEAT_CLICK_HOURS = int(os.environ.get("TRAFFIC_FILTER_REPEAT_CLICK_HOURS", "24"))
# JavaScript check page before the first redirect.
TRAFFIC_FILTER_CHALLENGE = env_bool("TRAFFIC_FILTER_CHALLENGE", True)

# Data retention (GDPR), applied daily by the clean_up_clicks task. 0 = keep forever.
# Full visitor IPs are cleared after this many days; a keyed hash stays for the repeat-click check.
CLICK_IP_RETENTION_DAYS = int(os.environ.get("CLICK_IP_RETENTION_DAYS", "7"))
BLOCKED_CLICK_RETENTION_DAYS = int(os.environ.get("BLOCKED_CLICK_RETENTION_DAYS", "30"))
CLICK_RETENTION_DAYS = int(os.environ.get("CLICK_RETENTION_DAYS", "365"))

# Shown on the privacy page (/privacy/).
PRIVACY_OPERATOR_NAME = os.environ.get("PRIVACY_OPERATOR_NAME", "")
PRIVACY_CONTACT_EMAIL = os.environ.get("PRIVACY_CONTACT_EMAIL", "")
