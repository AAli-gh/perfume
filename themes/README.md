# پوسته‌ها (Themes)

> مرور کلی Theme Engine در [docs/architecture.md](../docs/architecture.md#theme-engine) و گام‌های افزودن پوسته در [راهنمای توسعه‌دهنده](../docs/developer-guide.md#افزودن-پوسته) آمده است.

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
  - `data-ui`: classic / system (قواعد Design System: وزن فونت، حالت‌های دکمه، فوکوس، بج و چیپ، کارت و فیلد)
  - `data-mode`: main / alt (حالت شب و روز؛ با `data-scheme`: dark / light)
- **حالت شب و روز:**
  - توکن `colors_alt` پالت حالت مقابل `colors` است. فقط رنگ‌های تغییرکرده ذخیره می‌شوند و بقیه از `DAY_COLORS` می‌آیند (اگر پالت اصلی تیره است) یا از «طلایی لوکس» (اگر روشن است).
  - توکن `mode` دو کلید دارد: `toggle` برای نمایش دکمه و `default` برای حالت پیش‌فرض (`main` / `alt` / `system`).
  - `to_css` یک بلوک `html[data-mode="alt"]` می‌سازد، و برای `system` یک media query با `prefers-color-scheme`.
  - انتخاب بازدیدکننده در کوکی `majd_mode` ذخیره می‌شود و سرور هنگام رندر `data-mode` را از آن می‌گذارد، پس رنگ صفحه پرش نمی‌کند.
- **امنیت:** رنگ فقط با قالب `#RRGGBB` پذیرفته می‌شود، فونت فقط از فهرست مجاز، اعداد فقط در بازه تعریف‌شده و گونه‌ها فقط از گزینه‌های بالا. به این ترتیب تزریق CSS ممکن نیست.
- **پیش‌تنظیم‌های پوسته لوکس:** «طلایی لوکس» (طراحی فعلی)، «زمرد لوکس»، «مشکی لوکس»، «مروارید» (روشن) و «مینیمال روشن». کنتراست متن همه آن‌ها با تست WCAG AA بررسی می‌شود.
- **پوسته «استاندارد (Design System)»** (`themes/standard/`): بر اساس [Design System فیگما](https://www.figma.com/community/file/1267195373409722424).
  - فونت Inter؛ چون Inter حروف فارسی ندارد، وزیرمتن همراهش بارگذاری می‌شود (کلید `with` در `FONTS`).
  - پالت ایندیگو ۵۰۰ (`#4E61F6`) با خاکستری‌های ۹۰۰ تا ۵۰.
  - گردی گوشه ۶ / ۸ / ۱۶ پیکسل و فاصله بخش‌ها ۶۴ پیکسل (شبکه ۸).
  - حالت‌های دکمه: عادی، hover (تیره‌تر)، فشرده، فوکوس (حلقه ۴px) و غیرفعال (خاکستری).
  - پیش‌تنظیم‌ها: «ایندیگو» (پیش‌فرض)، «سبز» و «تیره».

## بخش‌های صفحه (Sections)

- قالب هر بخش سازنده صفحه در `themes/base/templates/sections/<key>.html` است. یک پوسته می‌تواند ظاهر یک بخش را با ساختن همان مسیر در پوشه خودش تغییر دهد (مثلاً `themes/minimal/templates/sections/hero.html`).
- **متغیرهای قالب بخش:**
  - `section`: تنظیمات اعتبارسنجی‌شده همراه با داده‌های آماده، مثلاً `section.products` یا `section.posts`.
  - `spacing`: کلاس فاصله بالای بخش.
- فاصله بین بخش‌ها از توکن `spacing.section` می‌آید. اگر بخش‌ها جابه‌جا شوند، فاصله‌ها یکدست می‌مانند.

## هدر و فوتر

- متن‌ها، منو و گزینه‌های هدر/فوتر در `THEME_HEADER` و `THEME_FOOTER` به قالب‌ها داده می‌شوند. schema آن‌ها در `apps/themes/chrome.py` تعریف شده و از استودیو ویرایش می‌شوند.
- پوسته‌ای که `components/header.html` یا `components/footer.html` را override می‌کند، باید از همین متغیرها استفاده کند تا تنظیمات استودیو روی آن هم اثر داشته باشد.
- قالب‌های `builder/` (استودیو) و `admin/` قابل override نیستند.
