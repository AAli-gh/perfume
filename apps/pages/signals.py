from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import Store

from .services import ensure_home_page


@receiver(post_save, sender=Store)
def _new_store_gets_home_page(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        ensure_home_page(instance)
