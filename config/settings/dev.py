"""تنظیمات توسعه محلی."""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = env.bool("DEBUG", default=True)
SECRET_KEY = SECRET_KEY or "django-insecure-dev-only-key"  # noqa: F405
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
PAYMENT_TEST_GATEWAY_ENABLED = env.bool("PAYMENT_TEST_GATEWAY_ENABLED", default=True)
