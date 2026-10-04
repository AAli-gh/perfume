# راهنمای توسعه‌دهنده

این راهنما برای کسی است که روی کد کار می‌کند. مرجع کامل زیرسیستم‌ها (Theme Engine، استودیو، سئو، امنیت، …) در [architecture.md](architecture.md) است و دلیل تصمیم‌های اصلی در [adr/](adr/).

## ۱. شروع سریع

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                      # DATABASE_URL را به PostgreSQL محلی اشاره دهید
npm install && npm run build:css          # در حین کار: npm run watch:css
python manage.py migrate                  # پوسته پیش‌فرض با migration نصب می‌شود
python manage.py sync_themes              # ثبت همه پوسته‌های themes/ (پس از هر تغییر theme.json)
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

- **پیش‌نیازها:** Python 3.11 یا 3.12، Node 18+، PostgreSQL 14+ (SQLite پشتیبانی نمی‌شود، چون جستجو، `pg_trgm`، قفل ردیف و قیدهای CHECK به PostgreSQL وابسته‌اند).
- **Redis:** در توسعه لازم نیست. با `CELERY_TASK_ALWAYS_EAGER=True`، taskها همان لحظه و بدون worker اجرا می‌شوند.
- **درگاه پرداخت:** در `config.settings.dev` درگاه آزمایشی داخلی روشن است و خرید را کامل شبیه‌سازی می‌کند.
- **دستورها:** `make help` همه دستورها را نشان می‌دهد (`make test`، `make e2e`، `make lint`، `make css`، `make lock`، …).

## ۲. نقشه کد

```
config/settings/   base · dev · prod · test
apps/
  core/            Store (Tenant)، تنظیمات فروشگاه، امنیت، rate limit، audit، سلامت، لاگ، schema فرم‌ها
  accounts/ catalog/ reviews/ discounts/ cart/ wishlist/ orders/ payments/ blog/ marketing/   ← هسته (Domain)
  themes/ pages/ builder/ seo/ ai/                                                            ← نمایش و افزونه‌ها
themes/            قالب‌های فروشگاه: base/ (مشترک) و پوسته‌ها (luxury/ …)
static/            src/input.css ← css/app.css (Tailwind 3) · js/ · vendor/
tests/             معماری، بودجه کوئری، e2e/
deploy/            entrypoint، gunicorn، nginx، backup/restore، smoke test
```

### جهت وابستگی (با تست قفل شده)

```
   themes · pages · builder · seo · ai          (نمایش و افزونه‌ها)
                    │
                    ▼
 accounts catalog reviews discounts cart wishlist orders payments blog marketing   (هسته)
                    │
                    ▼
                  core
```

- هسته هرگز از لایه نمایش یا AI چیزی import نمی‌کند.
- وابستگی‌های مجاز بین اپ‌های هسته در `ALLOWED_DEPENDENCIES` فایل `tests/test_architecture.py` فهرست شده‌اند. اگر وابستگی جدیدی لازم شد، اول بپرسید آیا واقعاً لازم است، بعد آن را آگاهانه به فهرست اضافه کنید.
- وقتی اپ پایین‌تر به اپ بالاتر نیاز دارد، از **وارونگی وابستگی** استفاده کنید. نمونه: `orders` نباید `payments` را بشناسد. پس `payments` در `ready()` تابع خود را در `apps/orders/integration.py` ثبت می‌کند.
- viewهای یک اپ، viewهای اپ دیگر را import نمی‌کنند و چرخه وابستگی بین اپ‌ها ممنوع است.

### چرخه یک درخواست

ترتیب middlewareها در `config/settings/base.py` معنادار است:

1. `HealthCheckMiddleware`: `/healthz` و `/readyz`، پیش از ریدایرکت HTTPS و بررسی `ALLOWED_HOSTS`
2. `RequestIdMiddleware`: شناسه درخواست برای لاگ‌ها
3. `SecurityMiddleware` و `SecurityHeadersMiddleware`: CSP با nonce در `request.csp_nonce`
4. session، locale، CSRF، auth، messages
5. `StoreMiddleware`: `request.store` از روی دامنه
6. `PreviewMiddleware`: `request.is_preview` برای کارمند استودیو یا لینک امضاشده
7. `ThemeMiddleware`: پوسته و توکن‌ها (پیش‌نویس در حالت پیش‌نمایش)
8. `XFrameOptionsMiddleware` و `HtmxMiddleware`: `request.htmx`

## ۳. قواعد کد

### لایه‌ها

| لایه | کجا | قاعده |
|---|---|---|
| مدل | `models.py` | فقط داده و قیدها. مدل‌های متعلق به فروشگاه از `core.StoreOwned` ارث می‌برند و manager آن‌ها `StoreQuerySet` است. |
| خواندن | `selectors.py` | همه کوئری‌های خواندنی، همراه با `select_related` و `prefetch_related`. viewها و بخش‌های صفحه داده را فقط از selector می‌گیرند. |
| نوشتن | `services.py` | هر عملیاتی که چند مدل را تغییر می‌دهد، داخل `transaction.atomic`. قفل ردیف (`select_for_update`) برای موجودی و کد تخفیف. |
| view | `views.py` | نازک: ورودی ← فرم ← service یا selector ← قالب. اگر `request.htmx` باشد، partial برمی‌گردد. |
| قالب | `themes/` | بدون منطق تجاری. هیچ قالب فروشگاهی در `apps/` نیست. |

### چندفروشگاهی

- هر کوئری روی داده فروشگاه با `.for_store(request.store)` محدود می‌شود. یکتایی (slug، کد تخفیف) همیشه «در هر فروشگاه» است: `UniqueConstraint(fields=["store", …])`.
- کدی که `request` ندارد (task، command) فروشگاه را صریح می‌گیرد یا از `apps.core.stores.use_store(store)` استفاده می‌کند.
- تست‌ها fixture دوم `other_store` دارند. برای هر قابلیت جدید یک تست «داده فروشگاه دیگر دیده نمی‌شود» بنویسید.

### قالب و CSS

- **رنگ ثابت ممنوع:** هیچ رنگ hex در قالب یا CSS ننویسید. از کلاس‌های معنایی Tailwind (`bg-primary`، `text-muted`، …) استفاده کنید که به CSS Variables وصل‌اند. تست `test_built_css_has_no_hardcoded_store_colors` رنگ ثابت را در CSS ساخته‌شده رد می‌کند.
- **CSP:**
  - `<script>` inline، `onclick=` و `style="…"` در قالب‌های فروشگاه کار نمی‌کنند.
  - JS در `static/js/` و رفتار با `data-*` attributeها تعریف می‌شود.
  - اگر واقعاً `<style>` لازم است، `nonce="{{ request.csp_nonce }}"` بگذارید.
  - تنها استثنا `500.html` است که بدون فایل استاتیک نمایش داده می‌شود.
- **HTMX:**
  - `allowEval` و `allowScriptTags` خاموش‌اند. پاسخ HTMX اسکریپت اجرا نمی‌کند.
  - رویدادها را با `HX-Trigger` بفرستید و در `app.js` گوش کنید.
  - هر فرم HTMX باید بدون JS هم کار کند (`action` و `method` واقعی).
- **متن‌ها:** با `{% translate %}` و `gettext` علامت‌گذاری کنید. زبان پیش‌فرض فارسی است و جهت `rtl` از `theme.json` می‌آید.
- **Tailwind:** بعد از افزودن کلاس جدید `npm run build:css` را اجرا کنید. خروجی `static/css/app.css` در git نیست (`.gitignore`). Dockerfile و CI آن را خودشان می‌سازند.

### امنیت در کد جدید

| موضوع | ابزار |
|---|---|
| فرم عمومی (POST) | `@ratelimit("scope", "10/10m")` از `apps.core.ratelimit`. کلید پیش‌فرض IP است و `key="user"` یا تابع دلخواه هم ممکن است. |
| رویداد حساس | `apps.core.audit.record("app.action", request, target=…, **data)`. رمز یا توکن در `data` نگذارید. |
| فیلد تصویر | `validators=[ImageUploadValidator()]`. SVG ممنوع است. |
| پیوند کاربر | `LinkField` یا `validate_link` (فقط مسیر داخلی یا http/https) |
| JSON در قالب | `json_script` یا `json_dumps_safe`. هرگز `|safe` روی داده کاربر نگذارید. |
| دامنه خارجی در CSP | `apps.core.security.add_source(directive, origin)` در `AppConfig.ready()` (نمونه: `apps/payments/apps.py`) |
| Secret | فقط از متغیر محیطی (`env(...)` در settings). هرگز در کد، fixture یا migration ننویسید. |

### migration

- migrationی که روی production اجرا شده، **هرگز** ویرایش نمی‌شود. برای اصلاح، migration جدید بسازید.
- داده‌ای که قبلاً در کد ثابت بود، با data migration به دیتابیس منتقل شود (نمونه: `core/0006_store_seo_settings`).
- migration داده باید با `apps.get_model` کار کند، نه با import مستقیم مدل، و در صورت امکان `reverse_code` داشته باشد.
- CI بررسی می‌کند که migrationی جا نمانده باشد (`makemigrations --check`).

## ۴. کارهای رایج

### افزودن نوع بخش صفحه

1. در `apps/pages/sections/types.py` یک `SectionForm` با فیلدهای تنظیمات بسازید. هر فیلد `label` و `initial` دارد. پیش‌فرض‌ها همان چیزی است که کاربر در اولین افزودن می‌بیند.
2. یک `SectionType` با `key`، `label`، `icon` و `form_class` بسازید و با `@register` ثبت کنید.
3. اگر بخش داده لازم دارد، `get_context(self, settings, *, request, section=None)` را بازنویسی کنید و داده را **فقط از selector** بگیرید. `is_visible` بخش خالی را پنهان می‌کند.
4. قالب را در `themes/base/templates/sections/<key>.html` بگذارید. متغیرها `section` (تنظیمات و داده) و `spacing` هستند.
5. فرم ویرایش استودیو خودکار از `form_class` ساخته می‌شود. برای فهرست تکرارشونده از `ListOfDictsField` (`apps/core/schema.py`) استفاده کنید.
6. تست: رندر با تنظیمات پیش‌فرض، رد تنظیمات نامعتبر، و یک بودجه کوئری اگر بخش داده می‌خواند.

### افزودن پوسته

1. پوشه `themes/<code>/` را با `theme.json` بسازید: `code`، `name`، `version`، `extends: "base"`، `direction` و `presets` (حداقل یکی با `"default": true`).
2. فقط قالب‌هایی را که متفاوت‌اند با همان مسیر در `themes/<code>/templates/` بگذارید. بقیه از `base` خوانده می‌شوند.
3. اگر هدر یا فوتر را override می‌کنید، از `THEME_HEADER` و `THEME_FOOTER` استفاده کنید تا تنظیمات استودیو اثر داشته باشد.
4. قالب‌های `builder/` و `admin/` قابل override نیستند (`PROTECTED_PREFIXES`).
5. `python manage.py sync_themes` را اجرا کنید (در production، حالت `migrate` در `deploy/entrypoint.sh` این کار را انجام می‌دهد).
6. تست کنتراست WCAG در `apps/themes/tests/` همه پیش‌تنظیم‌ها را بررسی می‌کند. پالت با کنتراست ضعیف رد می‌شود.

جزئیات بیشتر: [themes/README.md](../themes/README.md).

### افزودن پیش‌تنظیم رنگ

یک شیء به `presets` در `theme.json` اضافه کنید. فقط توکن‌هایی را بنویسید که با `DEFAULT_TOKENS` (`apps/themes/tokens.py`) فرق دارند. بعد `sync_themes` را اجرا کنید.

### افزودن درگاه پرداخت

1. در `apps/payments/gateways/<code>.py` یک زیرکلاس `PaymentGateway` بسازید و `initiate`، `parse_callback` و `verify` را پیاده کنید.
2. `redirect_origins` را با دامنه صفحه پرداخت درگاه پر کنید تا به CSP `form-action` اضافه شود.
3. با `@register` ثبت کنید و ماژول را در `apps/payments/gateways/__init__.py` import کنید.
4. اعتبارنامه‌ها در `GatewayAccount` هر فروشگاه ذخیره می‌شوند، نه در settings.
5. تست: پاسخ‌های درگاه را mock کنید (نمونه: `apps/payments/tests/`). بازگشت تکراری، انصراف، مبلغ نامطابق و قطع ارتباط را پوشش دهید.

سفارش‌ها و سرویس پرداخت تغییری لازم ندارند.

### افزودن ارائه‌دهنده AI

1. در `apps/ai/providers/` یک زیرکلاس `AIProvider` با `code` و `generate(AIRequest) -> AIResponse` بسازید و با `register` ثبت کنید.
2. کلید API را از متغیر محیطی بخوانید.
3. `AI_PROVIDER=<code>` را تنظیم کنید.
4. قابلیت‌ها در `apps/ai/features/` قرار می‌گیرند و خروجی آن‌ها همیشه پیش‌نویس است (ADR-0010).

### افزودن task زمان‌بندی‌شده

1. task را در `apps/<app>/tasks.py` با `@shared_task` بنویسید. Celery آن را خودکار کشف می‌کند.
2. اگر دوره‌ای است، آن را به `CELERY_BEAT_SCHEDULE` در `config/settings/base.py` اضافه کنید.
3. task باید idempotent باشد، چون `acks_late` فعال است و ممکن است دوباره اجرا شود.

### افزودن اپ جدید

1. پوشه `apps/<name>/` را با `AppConfig` بسازید (`name = "apps.<name>"`، `label = "<name>"`، `verbose_name` فارسی).
2. آن را به `INSTALLED_APPS` اضافه کنید.
3. اپ را در `DOMAIN_APPS` یا `PRESENTATION_AND_EXTENSIONS` فایل `tests/test_architecture.py` قرار دهید و وابستگی‌های مجازش را بنویسید.

## ۵. تست‌ها

```bash
pytest                        # واحد و یکپارچگی (بیش از ۵۰۰ تست، بدون مرورگر)
pytest --cov                  # پوشش کد؛ کمتر از ۹۵٪ = شکست
pytest apps/catalog -k search # بخشی از تست‌ها
pytest -m e2e                 # ۱۰ سناریوی سرتاسری با Chromium (نیاز به npm run build:css)
ruff check .
```

- **تنظیمات:** `config.settings.test`، روی PostgreSQL واقعی، با cache حافظه‌ای. cache و `MEDIA_ROOT` پیش از هر تست پاک یا جدا می‌شوند (`conftest.py`).
- **fixtureها:** `store` و `other_store` (ریشه)، و `site`، `page`، `probe`، `new_probe` و `staff_credentials` برای E2E (`tests/e2e/conftest.py`).
- **E2E:**
  - هر خطای JS یا نقض CSP، تست را شکست می‌دهد (`PageProbe`).
  - `wait_for_function` و `evaluate` با رشته پیچیده را به کار نبرید، چون CSP جلوی eval را می‌گیرد. منتظر بودن را با `expect(...)` یا `expect_response` انجام دهید.
- **همزمانی:** تست‌هایی که thread می‌سازند `@pytest.mark.django_db(transaction=True, serialized_rollback=True)` دارند (`apps/orders/tests/test_concurrency.py`).
- **بودجه کوئری:** `tests/test_query_budgets.py`. اگر صفحه‌ای کوئری اضافه گرفت، اول N+1 را رفع کنید و فقط در صورت توجیه، سقف را بالا ببرید.
- **قاعده:** هر باگ اول یک تست شکست‌خورنده می‌گیرد و بعد رفع می‌شود.

## ۶. وابستگی‌ها و CI

- **Python:**
  - `requirements.txt` بازه‌های مجاز نسخه را دارد.
  - `requirements.lock` نسخه دقیق همراه با hash را دارد. image production فقط از lock و با `--require-hashes` نصب می‌کند.
  - پس از تغییر `requirements.txt`، دستور `make lock` را اجرا کنید و هر دو فایل را commit کنید. تستی هست که lock ناقص را رد می‌کند.
- **Node:** فقط برای ساخت CSS است و وارد image نهایی نمی‌شود. Tailwind عمداً روی نسخه 3 مانده است (ADR-0008).
- **CI** (`.github/workflows/ci.yml`، روی هر push و PR):
  - lint
  - تست روی 3.11 و 3.12 (3.12 از lock نصب می‌کند)، همراه با پوشش کد و `makemigrations --check`
  - e2e
  - ساخت image، اجرای کامل stack و smoke test
  - `pip-audit` و `npm audit`

  پیش از push، `make lint test` را اجرا کنید.

## ۷. اشکال‌یابی

| نشانه | علت رایج |
|---|---|
| صفحه بدون استایل در `runserver` | `npm run build:css` اجرا نشده است |
| قالب پوسته جدید دیده نمی‌شود | `sync_themes` اجرا نشده، یا پوسته در `ThemeSettings` منتشرشده انتخاب نشده است |
| کنسول مرورگر: `Refused to execute inline script` | CSP. کد را به `static/js/` منتقل کنید. |
| تغییر استودیو در سایت دیده نمی‌شود | تغییرات هنوز پیش‌نویس‌اند و باید منتشر شوند |
| `429` در تست‌ها | cache بین تست‌ها پاک می‌شود. اگر یک تست بیش از سقف درخواست می‌دهد، `settings.RATELIMIT_ENABLED = False` بگذارید. |
| `SynchronousOnlyOperation` در E2E | کد ORM خارج از fixtureهای `tests/e2e/conftest.py` در حلقه async Playwright اجرا شده است |
