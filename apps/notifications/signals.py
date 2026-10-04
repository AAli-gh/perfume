from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import Store


@receiver(post_save, sender=Store)
def _new_store_gets_notification_settings(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        from .services import settings_for

        settings_for(instance)
