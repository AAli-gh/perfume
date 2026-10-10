from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .cart import restore


@receiver(user_logged_in)
def _restore_saved_cart(sender, request, user, **kwargs):
    if request is not None and hasattr(request, "session"):
        restore(request, user)
