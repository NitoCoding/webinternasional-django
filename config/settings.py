"""
Django settings for config project (International Office - Unhas).

Konfigurasi dibaca dari file .env di root proyek.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.accounts",
    "apps.academic",
    "apps.international",
    "apps.content",
    "apps.website",
    "apps.dashboard",
]

# Tool pengembangan (runserver_plus, shell_plus, show_urls) hanya aktif saat DEBUG=True.
if DEBUG:
    INSTALLED_APPS += ["django_extensions"]

# User model kustom harus diset sebelum migration pertama
AUTH_USER_MODEL = "accounts.User"

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
                "apps.website.context_processors.site_footer",
                "apps.accounts.context_processors.role_flags",
                "apps.accounts.context_processors.registration_flag",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ---------------------------------------------------------------------------
# Database (MariaDB)
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_DATABASE"),
        "USER": env("DB_USERNAME"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="127.0.0.1"),
        "PORT": env("DB_PORT", default="3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Makassar"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files (CSS Tailwind/DaisyUI di static/css, library npm di static/vendor)
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# WhiteNoise melayani static di DEBUG=True maupun DEBUG=False.
# DEBUG=True : file dibaca langsung dari STATICFILES_DIRS dan app (finders), tanpa collectstatic.
# DEBUG=False: file dibaca dari STATIC_ROOT, jadi jalankan `manage.py collectstatic` setelah static berubah.
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# Sertifikat mahasiswa disimpan di luar MEDIA_ROOT dan hanya dibuka lewat view yang memeriksa hak akses.
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"

# Login / logout
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "website:home"


# ---------------------------------------------------------------------------
# Email (reset password). Default: tampil di console.
# ---------------------------------------------------------------------------

EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="internationalClassUH@gmail.com")

# API SIPAKAMASE (data mahasiswa). Diisi di .env; tanpa nilai, fitur impor mahasiswa menampilkan error.
SIPAKAMASE_URL = env("SIPAKAMASE_URL", default="")
SIPAKAMASE_USERNAME = env("SIPAKAMASE_USERNAME", default="")
SIPAKAMASE_PASSWORD = env("SIPAKAMASE_PASSWORD", default="")
SIPAKAMASE_TIMEOUT = env.float("SIPAKAMASE_TIMEOUT", default=15.0)
# Verifikasi TLS ke server SIPAKAMASE. Dimatikan atas keputusan pemilik proyek, karena server
# hanya mengirim sertifikat leaf tanpa intermediate CA. Hanya berlaku untuk klien SIPAKAMASE.
# Nyalakan (True) setelah server mengirim rantai sertifikat lengkap.
SIPAKAMASE_VERIFY_TLS = env.bool("SIPAKAMASE_VERIFY_TLS", default=False)
# Jeda antar baris saat impor CSV, untuk menghindari rate limit API (Laravel memakai 0.5 detik).
CSV_IMPORT_DELAY_SECONDS = env.float("CSV_IMPORT_DELAY_SECONDS", default=0.5)
# Masa studi maksimal (semester), sama dengan config/academic.php di Laravel.
ACADEMIC_MAX_STUDY_PERIOD_DEFAULT = 14  # angkatan <= ACADEMIC_POLICY_CHANGE_YEAR
ACADEMIC_MAX_STUDY_PERIOD_FROM_2023 = 10
ACADEMIC_POLICY_CHANGE_YEAR = 2022


# ---------------------------------------------------------------------------
# Frontend: tanpa bundler. CSS Tailwind/DaisyUI dibangun oleh Tailwind CLI
# (npm run build:css) ke static/css/app.css. Library JS dari npm disalin
# ke static/vendor oleh script npm.
# ---------------------------------------------------------------------------
