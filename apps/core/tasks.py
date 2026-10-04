from celery import shared_task

from .audit import prune


@shared_task
def prune_audit_log():
    return prune()
