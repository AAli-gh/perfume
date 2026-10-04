"""کشف پوسته‌های نصب‌شده روی دیسک (themes/<code>/theme.json) و همگام‌سازی با دیتابیس."""

import json
import re
from pathlib import Path

from django.conf import settings
from django.db import transaction

CODE_RE = re.compile(r"^[a-z][a-z0-9_-]{1,39}$")
BASE_THEME = "base"  # لایه مشترک قالب‌ها؛ پوسته قابل انتخاب نیست


def themes_dir() -> Path:
    return Path(settings.THEMES_DIR)


def is_valid_code(code) -> bool:
    return bool(code) and bool(CODE_RE.match(code))


def theme_path(code) -> Path | None:
    """مسیر پوشه پوسته؛ کد نامعتبر (مثلاً ../) هرگز به مسیری بیرون از THEMES_DIR نمی‌رسد."""
    if not is_valid_code(code):  # فقط [a-z0-9_-]: «/» و «..» ممکن نیست ← خروج از THEMES_DIR ممکن نیست
        return None
    path = themes_dir() / code
    return path if path.is_dir() else None


def read_manifest(code) -> dict | None:
    path = theme_path(code)
    if path is None or not (path / "theme.json").exists():
        return None
    data = json.loads((path / "theme.json").read_text(encoding="utf-8"))
    if data.get("code") != code:
        raise ValueError(f"themes/{code}/theme.json: کد پوسته ({data.get('code')}) با نام پوشه یکی نیست")
    return data


def discover():
    """همه پوسته‌های قابل انتخاب روی دیسک: [manifest, …]"""
    found = []
    for child in sorted(themes_dir().iterdir()) if themes_dir().is_dir() else []:
        if child.is_dir() and child.name != BASE_THEME:
            manifest = read_manifest(child.name)
            if manifest:
                found.append(manifest)
    return found


@transaction.atomic
def sync(Theme=None, ThemePreset=None):
    """ثبت/به‌روزرسانی پوسته‌ها و پیش‌تنظیم‌هایشان از روی دیسک (قابل استفاده در migration با مدل‌های تاریخی)."""
    if Theme is None:
        from .models import Theme, ThemePreset
    result = []
    for manifest in discover():
        theme, _ = Theme.objects.update_or_create(
            code=manifest["code"],
            defaults={
                "name": manifest.get("name", manifest["code"]),
                "description": manifest.get("description", ""),
                "version": manifest.get("version", "1.0.0"),
                "manifest": {k: v for k, v in manifest.items() if k != "presets"},
                "is_available": True,
            },
        )
        for order, preset in enumerate(manifest.get("presets", [])):
            ThemePreset.objects.update_or_create(
                theme=theme, code=preset["code"],
                defaults={"name": preset["name"], "tokens": preset.get("tokens", {}),
                          "is_default": preset.get("default", order == 0), "order": order},
            )
        result.append(theme)
    return result
