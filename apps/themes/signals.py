from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import Store

from .services import ensure_store_theme


@receiver(post_save, sender=Store)
def _new_store_gets_default_theme(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        ensure_store_theme(instance)
