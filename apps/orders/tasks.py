from celery import shared_task

from .workflow import expire_unpaid_orders


@shared_task
def release_expired_reservations():
    """هر چند دقیقه: آزادسازی موجودی سفارش‌های پرداخت‌نشده‌ای که مهلتشان تمام شده."""
    return expire_unpaid_orders()
