from django.core.management.base import BaseCommand

from apps.core.audit import prune


class Command(BaseCommand):
    help = "حذف رویدادهای امنیتی قدیمی (پیش‌فرض: قدیمی‌تر از AUDIT_LOG_RETENTION_DAYS روز)"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None)

    def handle(self, *args, days=None, **options):
        self.stdout.write(f"{prune(days)} رویداد حذف شد.")
