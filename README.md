# عطر مجد — Majd Perfume

فروشگاه اینترنتی عطر، فارسی و راست‌به‌چپ، که روی یک **پلتفرم فروشگاهی White-Label** ساخته شده است. ظاهر و صفحه اصلی بدون کدنویسی از استودیو تغییر می‌کنند و داده‌ها آماده چندفروشگاهی‌اند.

**معماری:** Modular Monolith — Django 5.2 · PostgreSQL 16 · Celery + Redis · Django Templates · HTMX 2 · Tailwind CSS 3 · Docker

## امکانات

- **فروشگاه:**
  - کاتالوگ با دسته‌بندی درختی، کالکشن، برند، نت رایحه و ویژگی‌های قابل فیلتر.
  - جستجوی فارسی.
  - سبد خرید، کد تخفیف و علاقه‌مندی‌ها.
  - تسویه با پرداخت آنلاین (زرین‌پال)، کارت به کارت یا پرداخت در محل.
  - نظرات با تأیید مدیر، مجله و خبرنامه.
- **پلتفرم:**
  - Theme Engine با پوسته و پیش‌تنظیم.
  - Design Token‌ها به‌صورت CSS Variables.
  - سازنده صفحه با ۱۱ نوع بخش.
  - استودیو (`/studio/`) با پیش‌نمایش زنده، لینک پیش‌نمایش، انتشار و تاریخچه نسخه‌ها.
- **کیفیت و عملیات:**
  - سئوی کامل (JSON-LD، sitemap و canonical).
  - CSP اعمال‌شده با nonce، rate limit و گزارش امنیتی.
  - پوشش تست ۹۷٪ همراه با E2E در مرورگر.
  - image امن، با پشتیبان‌گیری، پایش و CI.

## تصاویر

<table>
<tr><td align="center" valign="top"><img src="docs/screenshots/home-hero.jpg" alt="صفحه اصلی"><br><sub>صفحه اصلی</sub></td><td align="center" valign="top"><img src="docs/screenshots/product.jpg" alt="صفحه محصول"><br><sub>صفحه محصول</sub></td></tr>
<tr><td align="center" valign="top"><img src="docs/screenshots/studio-colors.jpg" alt="استودیو: رنگ‌ها با پیش‌نمایش زنده"><br><sub>استودیو: رنگ‌ها با پیش‌نمایش زنده</sub></td><td align="center" valign="top"><img src="docs/screenshots/studio-page-editor.jpg" alt="استودیو: سازنده صفحه"><br><sub>استودیو: سازنده صفحه</sub></td></tr>
</table>

<table>
<tr><td align="center" valign="top"><img src="docs/screenshots/preset-gold.jpg" alt="طلایی لوکس"><br><sub>طلایی لوکس</sub></td><td align="center" valign="top"><img src="docs/screenshots/preset-emerald.jpg" alt="زمرد لوکس"><br><sub>زمرد لوکس</sub></td><td align="center" valign="top"><img src="docs/screenshots/preset-pearl.jpg" alt="مروارید"><br><sub>مروارید</sub></td><td align="center" valign="top"><img src="docs/screenshots/preset-minimal.jpg" alt="مینیمال روشن"><br><sub>مینیمال روشن</sub></td></tr>
</table>

<table>
<tr><td align="center" valign="top"><img src="docs/screenshots/m-home.jpg" alt="موبایل"><br><sub>موبایل</sub></td><td align="center" valign="top"><img src="docs/screenshots/m-product.jpg" alt="محصول"><br><sub>محصول</sub></td><td align="center" valign="top"><img src="docs/screenshots/m-cart.jpg" alt="سبد"><br><sub>سبد</sub></td><td align="center" valign="top"><img src="docs/screenshots/m-menu.jpg" alt="منو"><br><sub>منو</sub></td></tr>
</table>

همه تصاویر (فروشگاه، خرید، موبایل، پیش‌تنظیم‌ها، استودیو و پنل مدیریت): [docs/screenshots.md](docs/screenshots.md)

## مستندات

| سند | محتوا |
|---|---|
| [راهنمای مدیر فروشگاه](docs/admin-guide.md) | کار با پنل مدیریت و استودیو، بدون کدنویسی |
| [راهنمای توسعه‌دهنده](docs/developer-guide.md) | راه‌اندازی، قواعد کد، افزودن بخش، پوسته و درگاه، تست‌ها |
| [معماری و مرجع زیرسیستم‌ها](docs/architecture.md) | هر بخش پلتفرم چطور کار می‌کند و کدش کجاست |
| [تصمیم‌های معماری (ADR)](docs/adr/README.md) | چرا این‌طور طراحی شده است |
| [نقشه راه](docs/roadmap.md) | چندفروشگاهی واقعی، لایه AI و بهبودها |
| [اتصال سرویس‌ها](docs/integrations.md) | پیامک، ایمیل سفارش، ورود با کد، روش‌های ارسال و گزارش فروش |
| [راهنمای استقرار](DEPLOY.md) | production با Docker، TLS، پشتیبان‌گیری، پایش |
| [پوسته‌ها](themes/README.md) | ساخت و تغییر پوسته |
| [تصاویر](docs/screenshots.md) | همه بخش‌های سایت، استودیو و پنل مدیریت |

## ساختار پروژه

```
config/
  settings/     base.py (مشترک) · dev.py · prod.py · test.py
  celery.py     پیکربندی Celery (کشف خودکار tasks.py هر اپ)
apps/
  core/         Store (Tenant)، تنظیمات فروشگاه، StoreMiddleware، فیلترهای قالب، اعتبارسنج‌ها، seed_demo
  accounts/     کاربر سفارشی (ورود با ایمیل)، آدرس‌های ذخیره‌شده، ورود/ثبت‌نام، سفارش‌های من
  catalog/      برند، دسته‌بندی درختی، برچسب، کالکشن، ویژگی، نت رایحه (هرم TOP/HEART/BASE)، محصول، حجم/قیمت، گالری
                selectors.py (کوئری‌ها و فیلترها) · services.py · search.py (جستجوی PostgreSQL)
                inventory.py (رزرو/آزادسازی موجودی + دفتر StockMovement)
  reviews/      نظرات محصول (با تأیید مدیر)
  discounts/    کدهای تخفیف
  cart/         سبد خرید مبتنی بر session · pricing.py (تنها نقطه محاسبه قیمت)
  wishlist/     علاقه‌مندی‌ها
  orders/       سفارش، ثبت سفارش (services.py)، چرخه وضعیت (workflow.py)، تاریخچه وضعیت، لغو خودکار سفارش پرداخت‌نشده
  payments/     پرداخت (Payment)، حساب درگاه هر فروشگاه، آداپتورهای درگاه (gateways/: zarinpal، test)
  blog/         دسته‌بندی و مقاله
  marketing/    خبرنامه
  pages/        صفحه اصلی و بخش‌های آن (سازنده صفحه)، درباره ما، تماس و پیام‌های تماس (لایه نمایش)
  themes/       Theme Engine: پوسته، پیش‌تنظیم، تنظیمات ظاهر هر فروشگاه، Template Loader
  builder/      استودیو: ویرایشگر ظاهر و صفحه، پیش‌نویس، پیش‌نمایش، انتشار و تاریخچه
  seo/          متاتگ‌ها، JSON-LD، sitemap و robots
  ai/           اسکلت لایه هوش مصنوعی (غیرفعال؛ هسته به آن وابسته نیست)
themes/         لایه نمایش (Presentation)
  base/templates/   همه قالب‌ها و کامپوننت‌های فروشگاه (مشترک بین پوسته‌ها)
  luxury/           پوسته شماره ۱: theme.json (پیش‌تنظیم «طلایی لوکس») + overrideها
deploy/         entrypoint، gunicorn، nginx، پشتیبان‌گیری و بازگردانی، smoke test
docs/           مستندات
locale/         ترجمه‌ها (متن‌ها با {% translate %} علامت‌گذاری می‌شوند)
static/         src/input.css → css/app.css (Tailwind) · js/app.js · vendor/htmx.min.js
tests/          تست‌های معماری، بودجه کوئری و E2E (tests/e2e/)
seed/images/    تصاویر داده‌های نمایشی
```

قواعد معماری (جهت وابستگی، چندفروشگاهی و لایه‌ها) در [راهنمای توسعه‌دهنده](docs/developer-guide.md#۲-نقشه-کد) آمده است.

## راه‌اندازی محلی

پیش‌نیازها: Python 3.11+، Node 18+، PostgreSQL 14+

```bash
# ۱. پایگاه داده
createuser -P majd            # رمز: majd
createdb -O majd majd

# ۲. پایتون
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt     # در production فقط requirements.txt
cp .env.example .env          # در صورت نیاز DATABASE_URL را تغییر دهید

# ۳. Tailwind
npm install
npm run build:css             # یا در حین توسعه: npm run watch:css

# ۴. دیتابیس و داده نمایشی
python manage.py migrate
python manage.py seed_demo    # ۱۲ محصول، ۵ کالکشن، ۶ مقاله، کدهای تخفیف MAJD10 و YALDA50
python manage.py createsuperuser

python manage.py runserver

# (اختیاری) Celery — نیاز به Redis و REDIS_URL در .env دارد
celery -A config worker -l info
```

- سایت: http://localhost:8000
- پنل مدیریت: http://localhost:8000/admin

## اجرا با Docker

**استقرار production:** راهنمای کامل در [DEPLOY.md](DEPLOY.md). خلاصه:

```bash
cp .env.example .env          # SECRET_KEY، رمزها، دامنه‌ها
# گواهی TLS در deploy/certs/  (Let's Encrypt؛ یا برای آزمایش: sh deploy/selfsigned-cert.sh)
make build && make up         # docker-compose.prod.yml
make smoke URL=https://shop.example.com
```

**اجرای محلی یا نمایشی** (همان image، بدون TLS، روی http://localhost:8080):

```bash
cp .env.example .env          # SECRET_KEY قوی لازم است (تنظیمات production)
docker compose up -d --build
docker compose run --rm web manage seed_demo
docker compose run --rm web manage createsuperuser
```

`make help` فهرست همه دستورها (تست، lint، ساخت، پشتیبان‌گیری، تست بار و …) را نشان می‌دهد.

## تست‌ها

```bash
pytest                         # تست‌های واحد و یکپارچگی (بدون مرورگر) با config.settings.test
pytest --cov                   # همراه با پوشش کد؛ کمتر از ۹۵٪ = شکست
npm run build:css && pytest -m e2e    # تست‌های سرتاسری با مرورگر واقعی (Playwright)
pytest -m ""                   # همه تست‌ها
ruff check .                   # lint
```

| لایه | محل | چه چیزی را تضمین می‌کند |
|---|---|---|
| واحد و یکپارچگی | `apps/*/tests/` | سرویس‌ها، selectorها، viewها و پاسخ‌های HTMX، فرم‌ها، پرداخت، پوسته و توکن‌ها، استودیو، سئو و امنیت |
| معماری | `tests/test_architecture.py` | جهت وابستگی ماژول‌ها، نبود چرخه، قالب‌های فروشگاه فقط در `themes/` |
| همزمانی | `apps/orders/tests/test_concurrency.py` | چند خریدار هم‌زمان (thread با اتصال جدا): آخرین واحد فقط یک بار فروخته می‌شود، بازنده‌ها پیام «ناموجود» می‌گیرند و هیچ خطای ۵۰۰ رخ نمی‌دهد. سقف کد تخفیف هم رعایت می‌شود. |
| بودجه کوئری | `tests/test_query_budgets.py` | سقف تعداد کوئری صفحه‌های اصلی. اگر تعداد کوئری با بیشتر شدن محصولات و مقاله‌ها رشد کند (N+1)، تست شکست می‌خورد. |
| سرتاسری (E2E) | `tests/e2e/` | این سناریوها در Chromium واقعی روی سرور زنده و داده `seed_demo` اجرا می‌شوند:<br>- خرید کامل (فیلتر، سبد، کد تخفیف، تسویه و درگاه آزمایشی)<br>- نظر، تماس، مجله، ثبت‌نام، علاقه‌مندی و جستجو<br>- صفحه کالکشن و ۴۰۴<br>- اعلان ۴۲۹<br>- موبایل بدون اسکرول افقی<br>- استودیو: پیش‌نمایش زنده رنگ، کشیدن و رها کردن، لینک پیش‌نمایش، انتشار و بازگردانی<br>**هر خطای جاوااسکریپت یا نقض CSP در مرورگر، تست را شکست می‌دهد.** |

- **دیتابیس:** تست‌ها روی PostgreSQL اجرا می‌شوند، همان پایگاه production (جستجو، قفل ردیف و قیدهای CHECK).
- **CI:** فایل `.github/workflows/ci.yml` این مراحل را روی هر push و pull request اجرا می‌کند:
  - lint
  - تست‌ها روی Python 3.11 و 3.12 با پوشش کد
  - بررسی به‌روز بودن migrationها
  - E2E
  - ساخت image، اجرای کامل stack production و smoke test
  - `pip-audit` و `npm audit`

## تنظیمات (`.env`)

همه تنظیمات حساس از متغیرهای محیطی خوانده می‌شوند و هیچ کلید یا رمزی در کد نیست. نمونه کامل در `.env.example` است.

**پایه**

| متغیر | توضیح |
|---|---|
| `DJANGO_SETTINGS_MODULE` | پیش‌فرض: `config.settings.dev` (manage.py) و `config.settings.prod` (wsgi و Docker) |
| `DEBUG` | حالت توسعه (در prod همیشه False است) |
| `SECRET_KEY` | در production الزامی است: حداقل ۵۰ نویسه تصادفی (`python -c "import secrets; print(secrets.token_urlsafe(50))"`). کلید ضعیف یا پیش‌فرض پذیرفته نمی‌شود. |
| `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` | دامنه‌ها و آدرس‌های مجاز، جدا شده با کاما |
| `DATABASE_URL` / `CONN_MAX_AGE` | مثلاً `postgres://user:pass@host:5432/db` و عمر اتصال دیتابیس |
| `REDIS_URL` | cache، rate limit و broker مربوط به Celery. اگر خالی باشد، cache در حافظه است (فقط برای توسعه). |
| `CELERY_TASK_ALWAYS_EAGER` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | اجرای taskها بدون worker (توسعه) و آدرس‌های جایگزین Celery |
| `DEFAULT_THEME` | پوسته پیش‌فرض (`luxury`) |
| `AI_PROVIDER` | ارائه‌دهنده AI. خالی یعنی غیرفعال. |
| `SMS_PROVIDER` / `SMS_API_KEY` / `SMS_SENDER` | سرویس پیامک (`kavenegar`، `smsir` یا `console` برای توسعه)، کلید API و شماره خط. خالی یعنی پیامک خاموش. راهنما: [docs/integrations.md](docs/integrations.md) |
| `PAYMENT_TEST_GATEWAY_ENABLED` | درگاه آزمایشی داخلی (در prod همیشه خاموش). درگاه واقعی از پنل مدیریت تنظیم می‌شود. |
| `SEO_NOINDEX` | `true` در staging: جلوگیری از index شدن کل سایت |

**امنیت (production)**

| متغیر | توضیح |
|---|---|
| `ADMIN_URL` | آدرس پنل مدیریت (پیش‌فرض `admin/`؛ در production آن را تغییر دهید) |
| `CSP_ENABLED` / `CSP_REPORT_ONLY` | فعال بودن CSP (در production همیشه روشن) و حالت فقط‌گزارش برای آزمایش |
| `SECURE_SSL_REDIRECT` / `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` | پیش‌فرض روشن. فقط برای اجرای محلی بدون TLS خاموش شوند. |
| `SECURE_HSTS_SECONDS` / `SECURE_HSTS_INCLUDE_SUBDOMAINS` / `SECURE_HSTS_PRELOAD` | پیش‌فرض یک سال. includeSubDomains و preload فقط وقتی که همه زیردامنه‌ها HTTPS هستند. |
| `TRUSTED_PROXY_COUNT` | تعداد پراکسی‌های مطمئن جلوی برنامه (پیش‌فرض production: ۱) |
| `STAFF_SESSION_AGE` | حداکثر عمر نشست کارکنان به ثانیه (پیش‌فرض ۱۲ ساعت) |
| `AUDIT_LOG_RETENTION_DAYS` | مدت نگهداری گزارش امنیتی (پیش‌فرض ۱۸۰ روز) |

**ایمیل، لاگ و استقرار**

| متغیر | توضیح |
|---|---|
| `EMAIL_URL` / `DEFAULT_FROM_EMAIL` / `SERVER_EMAIL` | سرور SMTP (مثلاً `smtp+tls://user:pass@host:587`) و فرستنده‌ها |
| `ADMINS` | گیرندگان گزارش خطای ۵۰۰ (`نام:email`، جدا شده با کاما) |
| `LOG_FORMAT` / `LOG_LEVEL` | `json` برای لاگ ساخت‌یافته؛ سطح لاگ |
| `POSTGRES_PASSWORD` / `REDIS_PASSWORD` (و `POSTGRES_USER`، `POSTGRES_DB`) | رمزهای سرویس‌ها در `docker-compose.prod.yml` |
| `WEB_CONCURRENCY` / `GUNICORN_THREADS` / `GUNICORN_TIMEOUT` / `CELERY_CONCURRENCY` | تعداد worker و thread، و timeout |
| `DEPLOY_CHECK` | `0` فقط برای اجرای محلی: رد شدن از `check --deploy` در حالت migrate |
| `BACKUP_INTERVAL_SECONDS` / `BACKUP_RETENTION_DAYS` | دوره پشتیبان‌گیری و مدت نگهداری |
| `APP_IMAGE` / `HTTP_PORT` / `HTTPS_PORT` | image مورد استفاده (برای برگشت به نسخه قبل) و پورت‌های nginx |

### تنظیمات فروشگاه (پنل مدیریت)

نام فروشگاه، شعار، تلفن، ایمیل، آدرس، شبکه‌های اجتماعی، هزینه ارسال، حد ارسال رایگان و شماره کارت در
**پنل مدیریت ← هسته ← فروشگاه‌ها** تنظیم می‌شوند و نیازی به تغییر کد یا deploy ندارند.

برای راه‌اندازی فروشگاه دوم روی دامنه دیگر، یک Store جدید با دامنه آن بسازید، دامنه را به `ALLOWED_HOSTS` اضافه کنید و
در صورت نیاز با `python manage.py seed_demo --store=CODE` داده نمایشی بسازید.

