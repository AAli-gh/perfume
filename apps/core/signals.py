from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .audit import record


@receiver(user_logged_in)
def _logged_in(sender, request, user, **kwargs):
    record("auth.login", request, user=user, target=user.get_username(), staff=user.is_staff)


@receiver(user_logged_out)
def _logged_out(sender, request, user, **kwargs):
    if user is not None:
        record("auth.logout", request, user=user, target=user.get_username())


@receiver(user_login_failed)
def _login_failed(sender, credentials, request=None, **kwargs):
    # رمز عبور هرگز ثبت نمی‌شود؛ Django خودش credentials را پاک‌سازی می‌کند، اینجا فقط شناسه برداشته می‌شود
    identifier = (credentials or {}).get("username") or (credentials or {}).get("email") or ""
    record("auth.login_failed", request, target=str(identifier)[:120])
