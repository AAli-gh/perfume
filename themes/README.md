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

## Design Tokens و رنگ‌ها

- **منبع رنگ‌ها:** همه رنگ‌ها، فونت‌ها، گردی گوشه‌ها و سبک کامپوننت‌ها از توکن‌ها می‌آیند (`apps/themes/tokens.py`). هیچ رنگی در CSS یا قالب‌ها ثابت نوشته نشده است و این قاعده با تست قفل شده است.
- **ترتیب ترکیب:** `DEFAULT_TOKENS` ← `ThemePreset.tokens` ← `ThemeSettings.overrides` (شخصی‌سازی هر فروشگاه).
- **تبدیل به CSS:** تگ `{% theme_head %}` در `base.html` توکن‌ها را به این شکل تولید می‌کند:
  `<style id="theme-tokens">:root{--color-primary:196 122 69;…}</style>`
  رنگ‌ها به‌صورت کانال RGB نوشته می‌شوند تا شفافیت Tailwind (`bg-primary/20`) کار کند.
- **کلاس‌های Tailwind:** در `tailwind.config.js` کلاس‌ها به متغیرها وصل شده‌اند:
  - نام‌های معنایی: `primary`، `accent`، `surface`، `panel`، `text`، …
  - نام‌های قبلی پوسته لوکس (`gold`، `copper`، `ink`، …) هم برای سازگاری حفظ شده‌اند.
  - **تغییر پالت نیازی به build دوباره CSS ندارد.**
- **گونه‌های کامپوننت:** ویژگی‌های `data-*` روی `<html>` تعیین می‌شوند و CSS بر اساس آن‌ها رفتار می‌کند:
  - `data-button`: gradient / solid / outline
  - `data-card`: gradient / flat / outline
  - `data-header`: blur / solid
  - `data-background`: glow / plain
  - `data-texture`: noise / none
  - `data-shadow`: strong / soft / none
- **امنیت:** رنگ فقط با قالب `#RRGGBB` پذیرفته می‌شود، فونت فقط از فهرست مجاز، اعداد فقط در بازه تعریف‌شده و گونه‌ها فقط از گزینه‌های بالا. به این ترتیب تزریق CSS ممکن نیست.
- **پیش‌تنظیم‌های پوسته لوکس:** «طلایی لوکس» (طراحی فعلی)، «زمرد لوکس»، «مشکی لوکس»، «مروارید» (روشن) و «مینیمال روشن». کنتراست متن همه آن‌ها با تست WCAG AA بررسی می‌شود.
