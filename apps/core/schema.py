"""فیلدهای فرم امن برای تنظیمات JSON (بخش‌های صفحه، هدر و فوتر پوسته و …).

مقادیری که مدیر فروشگاه وارد می‌کند همیشه از این فیلدها رد می‌شوند:
- پیوندها فقط مسیر داخلی، http(s) یا لنگر (#)؛ javascript: و data: رد می‌شوند.
- فهرست‌ها تعداد، کلید و طول متن محدود دارند.
"""

import json
import re

from django import forms
from django.core.exceptions import ValidationError

SAFE_URL = re.compile(r"^(/[^\s]*|https?://[^\s]+|#[\w-]*)$")


def validate_link(value):
    """فقط مسیر داخلی (/…)، http(s) یا لنگر (#…) — javascript: و مشابه رد می‌شوند."""
    if value and (not SAFE_URL.match(value) or value.startswith("//")):
        raise ValidationError("پیوند باید با / یا https:// شروع شود.")


class LinkField(forms.CharField):
    default_validators = [validate_link]

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 300)
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)


class ListOfDictsWidget(forms.Widget):
    """ویرایشگر ردیفی فهرست (بدون جاوااسکریپت): هر ردیف یک آیتم، ردیف خالی نادیده گرفته می‌شود.

    نام ورودی‌ها: <name>-<i>-<key> ؛ اگر داده خام (لیست یا JSON) با نام خود فیلد برسد همان استفاده می‌شود
    (برای اعتبارسنجی تنظیمات ذخیره‌شده).
    """

    template_name = "core/widgets/list_of_dicts.html"
    extra_rows = 2

    def __init__(self, attrs=None):
        super().__init__(attrs)
        self.keys, self.labels, self.max_items, self.key_choices, self.textareas = (), {}, 12, {}, set()

    def value_from_datadict(self, data, files, name):
        if f"{name}-rows" not in data:
            raw = data.get(name)
            return raw if raw is None or isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
        rows = []
        for i in range(self.max_items + self.extra_rows):
            row = {key: (data.get(f"{name}-{i}-{key}") or "").strip() for key in self.keys}
            if any(row[k] for k in self.keys if k not in self.key_choices):
                rows.append(row)
        return json.dumps(rows, ensure_ascii=False)

    def value_omitted_from_data(self, data, files, name):
        return f"{name}-rows" not in data and name not in data

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        try:
            items = json.loads(value) if isinstance(value, str) else (value or [])
        except (TypeError, ValueError):
            items = []
        if not isinstance(items, list):
            items = []
        count = min(len(items) + self.extra_rows, self.max_items) if len(items) < self.max_items else len(items)
        rows = []
        for i in range(count):
            item = items[i] if i < len(items) and isinstance(items[i], dict) else {}
            rows.append({
                "index": i,
                "cells": [
                    {
                        "key": key,
                        "name": f"{name}-{i}-{key}",
                        "label": self.labels.get(key, key),
                        "value": item.get(key, ""),
                        "choices": sorted(self.key_choices.get(key, ())),
                        "textarea": key in self.textareas,
                    }
                    for key in self.keys
                ],
            })
        context["widget"].update(rows=rows, max_items=self.max_items)
        return context


class ListOfDictsField(forms.JSONField):
    """فهرست آیتم‌ها با کلیدهای مشخص و متن کوتاه (مثلاً ویژگی‌ها، پرسش‌ها یا پیوندهای منو)."""

    widget = ListOfDictsWidget

    def __init__(self, *, keys, max_items=12, choices=None, labels=None, validators_by_key=None,
                 textareas=(), **kwargs):
        self.keys, self.max_items, self.key_choices = tuple(keys), max_items, choices or {}
        self.validators_by_key = validators_by_key or {}
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)
        if isinstance(self.widget, ListOfDictsWidget):
            self.widget.keys, self.widget.max_items = self.keys, max_items
            self.widget.labels, self.widget.key_choices = labels or {}, self.key_choices
            self.widget.textareas = set(textareas)

    def clean(self, value):
        value = super().clean(value) or []
        if not isinstance(value, list) or len(value) > self.max_items:
            raise ValidationError(f"فهرستی با حداکثر {self.max_items} آیتم")
        cleaned = []
        for item in value:
            if not isinstance(item, dict):
                raise ValidationError("هر آیتم باید یک شیء باشد")
            row = {}
            for key in self.keys:
                text = item.get(key, "")
                if not isinstance(text, str) or len(text) > 600:
                    raise ValidationError(f"مقدار «{key}» نامعتبر است")
                text = text.strip()
                if key in self.key_choices and text not in self.key_choices[key]:
                    raise ValidationError(f"«{text}» برای {key} مجاز نیست")
                for validator in self.validators_by_key.get(key, ()):
                    validator(text)
                row[key] = text
            cleaned.append(row)
        return cleaned
