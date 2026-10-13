import logging

from django.core.management.base import BaseCommand, CommandError

from apps.core.backups import run_backup
from apps.core.templatetags.majd import fa

log = logging.getLogger("apps.core.backups")


class Command(BaseCommand):
    help = "پشتیبان دیتابیس و تصاویر آپلودی در BACKUP_DIR و حذف نسخه‌های قدیمی‌تر از BACKUP_RETENTION_DAYS روز"

    def add_arguments(self, parser):
        parser.add_argument("--dir", dest="dest", default=None, help="پوشه مقصد (پیش‌فرض BACKUP_DIR)")
        parser.add_argument("--keep-days", type=int, default=None)
        parser.add_argument("--no-media", action="store_true", help="فقط دیتابیس")

    def handle(self, *args, dest=None, keep_days=None, no_media=False, **options):
        try:
            result = run_backup(dest=dest, keep_days=keep_days, media=not no_media)
        except Exception as exc:
            log.exception("backup FAILED")  # با Sentry فعال، خطا گزارش می‌شود
            raise CommandError(f"پشتیبان‌گیری ناموفق بود: {exc}") from exc
        for path in result.files:
            self.stdout.write(f"✓ {path} ({fa(round(path.stat().st_size / 1024))} KB)")
        if result.pruned:
            self.stdout.write(f"{fa(len(result.pruned))} نسخه قدیمی حذف شد.")
