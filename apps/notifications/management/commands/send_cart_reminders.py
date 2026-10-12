"""ارسال پیامک یادآوری سبدهای رهاشده (برای میزبان بدون Celery beat؛ مثلاً هر ساعت در Scheduled task)."""

from django.core.management.base import BaseCommand

from apps.notifications.tasks import send_cart_reminders_task


class Command(BaseCommand):
    help = "یادآوری پیامکی سبدهای خرید رهاشده"

    def handle(self, *args, **options):
        count = send_cart_reminders_task()
        self.stdout.write(self.style.SUCCESS(f"{count} یادآوری ارسال شد."))
