from django.core.management.base import BaseCommand

from apps.themes.registry import sync


class Command(BaseCommand):
    help = "ثبت پوسته‌های پوشه themes/ و پیش‌تنظیم‌هایشان در دیتابیس"

    def handle(self, *args, **options):
        for theme in sync():
            self.stdout.write(self.style.SUCCESS(f"✓ {theme.code} ({theme.presets.count()} پیش‌تنظیم)"))
