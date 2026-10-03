"""تنظیمات پایه (مشترک) پروژه.

ماژول‌های محیطی:  dev.py · prod.py · test.py
همه مقادیر حساس از متغیرهای محیطی خوانده می‌شوند.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY", default="")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.postgres",
    "django.contrib.sitemaps",
    "django_htmx",
    "apps.accounts",
    "apps.core",
    "apps.catalog",
    "apps.reviews",
    "apps.discounts",
    "apps.cart",
    "apps.wishlist",
    "apps.orders",
    "apps.payments",
    "apps.blog",
    "apps.marketing",
    "apps.pages",
    "apps.themes",
    "apps.builder",
    "apps.seo",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.core.stores.StoreMiddleware",
    "apps.builder.preview.PreviewMiddleware",  # حالت پیش‌نمایش پیش‌نویس (قبل از ThemeMiddleware)
    "apps.themes.runtime.ThemeMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"

# ---------- Theme Engine ----------
THEMES_DIR = BASE_DIR / "themes"
DEFAULT_THEME = env("DEFAULT_THEME", default="luxury")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": False,
        "OPTIONS": {
            # پوسته فعال ← themes/base ← قالب‌های اپ‌ها (Admin و …)؛ cache به تفکیک پوسته
            "loaders": [
                ("apps.themes.loaders.ThemeCachedLoader", [
                    "apps.themes.loaders.ThemeLoader",
                    "django.template.loaders.app_directories.Loader",
                ]),
            ],
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
                "apps.cart.context_processors.cart",
                "apps.themes.context_processors.theme",
            ],
            "builtins": ["apps.core.templatetags.majd"],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://majd:majd@localhost:5432/majd"),
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:profile"
LOGOUT_REDIRECT_URL = "pages:home"

LANGUAGE_CODE = "fa"
LANGUAGES = [("fa", "فارسی")]
# متن‌های رابط کاربری با {% translate %} علامت‌گذاری می‌شوند (msgid فارسی است).
# برای افزودن زبان: makemessages -l en (نیاز به gettext) ← ترجمه در locale/ ← compilemessages
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # سبد خرید تا ۳۰ روز می‌ماند

# ---------- تنظیمات فروشگاه ----------
# درگاه‌های پرداخت هر فروشگاه در پنل مدیریت ← «حساب‌های درگاه پرداخت» تنظیم می‌شوند.
# درگاه آزمایشی داخلی فقط با این پرچم فعال می‌شود (در prod همیشه خاموش است):
PAYMENT_TEST_GATEWAY_ENABLED = env.bool("PAYMENT_TEST_GATEWAY_ENABLED", default=False)

# اطلاعات فروشگاه (نام، تماس، هزینه ارسال، …) در دیتابیس و پنل مدیریت ← «فروشگاه‌ها» قرار دارد.

# ---------- Cache / Celery (Redis) ----------
REDIS_URL = env("REDIS_URL", default="")
CACHES = {
    "default": (
        {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}
        if REDIS_URL
        else {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    )
}
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL or "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="") or None
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_TIME_LIMIT = 300
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "release-expired-reservations": {"task": "apps.orders.tasks.release_expired_reservations", "schedule": 300.0},
}

# ---------- سئو ----------
# برای محیط‌های آزمایشی (staging): همه صفحه‌ها noindex و robots.txt همه چیز را Disallow می‌کند.
SEO_NOINDEX = env.bool("SEO_NOINDEX", default=False)

# ---------- لایه هوش مصنوعی (اختیاری؛ apps/ai) ----------
AI_PROVIDER = env("AI_PROVIDER", default="")  # خالی = غیرفعال

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
