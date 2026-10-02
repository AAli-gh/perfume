# پوسته‌ها (Themes)

```
themes/
  base/templates/     ← لایه مشترک: همه قالب‌ها و کامپوننت‌های فروشگاه (پوسته قابل انتخاب نیست)
  luxury/
    theme.json        ← مشخصات پوسته + پیش‌تنظیم‌ها (Presets)
    templates/        ← فقط قالب‌هایی که این پوسته با base متفاوت می‌خواهد (override)
```

- Template Loader ابتدا `themes/<پوسته فعال>/templates/` و سپس `themes/base/templates/` را جستجو می‌کند.
- برای تغییر یک بخش در یک پوسته، **فقط همان فایل** را با همان مسیر در پوشه پوسته بسازید (مثلاً
  `themes/minimal/templates/components/product_card.html`). بقیه قالب‌ها از base خوانده می‌شوند.
- بعد از افزودن یا تغییر `theme.json`: `python manage.py sync_themes`
- کد پوسته: فقط حروف کوچک انگلیسی، رقم، `-` و `_`.
