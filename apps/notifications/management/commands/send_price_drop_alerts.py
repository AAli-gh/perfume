"""خبر کاهش قیمت محصولات علاقه‌مندی‌ها (برای میزبان بدون Celery beat؛ مثلاً هر ساعت در Scheduled task)."""

from django.core.management.base import BaseCommand

from apps.notifications.tasks import send_price_drop_alerts_task


class Command(BaseCommand):
    help = "پیامک/ایمیل کاهش قیمت به مشتریانی که محصول را در علاقه‌مندی‌ها دارند"

    def handle(self, *args, **options):
        count = send_price_drop_alerts_task()
        self.stdout.write(self.style.SUCCESS(f"{count} خبر کاهش قیمت ارسال شد."))
