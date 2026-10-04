from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def shorten_staff_session(sender, request, user, **kwargs):
    """نشست کارکنان (دسترسی به پنل مدیریت و استودیو) کوتاه‌تر است؛ نشست مشتریان دست نمی‌خورد."""
    if user.is_staff and request is not None and hasattr(request, "session"):
        expiry = request.session.get_expiry_age()
        request.session.set_expiry(min(expiry, settings.STAFF_SESSION_AGE) if expiry else settings.STAFF_SESSION_AGE)
