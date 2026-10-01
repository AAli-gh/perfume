# عطر مجد — Majd Perfume

فروشگاه اینترنتی عطر، فارسی و راست‌به‌چپ، با طراحی تیره و طلایی.

**معماری:** Modular Monolith — Django 5.2 · PostgreSQL · Celery + Redis · Django Templates · HTMX 2 · Tailwind CSS 3

> این پروژه در حال تبدیل شدن به یک پلتفرم فروشگاهی White-Label است. نقشه راه مرحله‌ای در `docs/` (Phase 13) مستند می‌شود.

## ساختار پروژه

```
config/
  settings/     base.py (مشترک) · dev.py · prod.py · test.py
  celery.py     پیکربندی Celery (کشف خودکار tasks.py هر اپ)
apps/
  core/         Store (Tenant)، تنظیمات فروشگاه، StoreMiddleware، فیلترهای قالب، اعتبارسنج‌ها، seed_demo
  accounts/     کاربر سفارشی (ورود با ایمیل)، آدرس‌های ذخیره‌شده، ورود/ثبت‌نام، سفارش‌های من
  catalog/      برند، خانواده رایحه، کالکشن، محصول، حجم/قیمت، گالری
                selectors.py (کوئری‌های خواندنی) · services.py (عملیات نوشتنی)
  reviews/      نظرات محصول (با تأیید مدیر)
  discounts/    کدهای تخفیف
  cart/         سبد خرید مبتنی بر session · services.py (اعمال کد تخفیف)
  orders/       سفارش، ثبت سفارش (services.py)، درگاه زرین‌پال
  blog/         دسته‌بندی و مقاله
  marketing/    خبرنامه
  pages/        صفحه اصلی، درباره ما، تماس و پیام‌های تماس (لایه نمایش)
  ai/           اسکلت لایه هوش مصنوعی (غیرفعال؛ هسته به آن وابسته نیست)
templates/      قالب پایه و کامپوننت‌های مشترک
static/         src/input.css → css/app.css (Tailwind) · js/app.js · vendor/htmx.min.js
tests/          تست‌های معماری (جهت وابستگی ماژول‌ها) و لایه AI
seed/images/    تصاویر داده‌های نمایشی
```

### قواعد معماری

- **View نازک است:** کوئری‌های خواندنی در `selectors.py` و عملیات نوشتنی در `services.py` هر اپ قرار دارند.
- **جهت وابستگی:** `themes / pages / ai → هسته (catalog، orders، …) → core`. هسته هرگز از لایه نمایش یا AI چیزی import نمی‌کند. این قاعده با `tests/test_architecture.py` قفل شده است.
- **Multi-Tenant آماده:** همه داده‌های اصلی (محصول، برند، کالکشن، سفارش، کد تخفیف، مقاله، خبرنامه، پیام تماس) به یک `Store` تعلق دارند. `StoreMiddleware` فروشگاه را از روی دامنه (`StoreDomain`) تشخیص می‌دهد و در `request.store` قرار می‌دهد. اگر دامنه ثبت نشده باشد، فروشگاه پیش‌فرض استفاده می‌شود. همه کوئری‌ها با `.for_store(store)` محدود می‌شوند و slugها در هر فروشگاه یکتا هستند.
- **app label:** اپ‌ها در `apps/` هستند، اما `label` هر اپ (مثلاً `catalog`) ثابت مانده تا جدول‌ها و migrationها تغییر نکنند.

### HTMX کجا استفاده شده است

| بخش | رفتار |
|---|---|
| فیلترهای فروشگاه، مرتب‌سازی، صفحه‌بندی | فقط `#results` جایگزین می‌شود و آدرس صفحه به‌روز می‌شود (`hx-push-url`) |
| افزودن به سبد | `hx-swap="none"` و شمارنده سبد و اعلان به‌صورت out-of-band به‌روز می‌شوند |
| تغییر تعداد / حذف / کد تخفیف | بخش سبد و خلاصه سفارش با هم به‌روز می‌شوند |
| ثبت نظر، فرم تماس، خبرنامه | فقط خود فرم جایگزین می‌شود |
| جستجو و دسته‌بندی مجله | فقط لیست مقالات جایگزین می‌شود |

همه فرم‌ها بدون جاوااسکریپت هم کار می‌کنند؛ HTMX فقط تجربه کاربری را بهتر می‌کند.
در هر view، `request.htmx` (از django-htmx) مشخص می‌کند که partial برگردد یا صفحه کامل.

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

```bash
cp .env.example .env
docker compose up --build
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py createsuperuser
```

سایت روی http://localhost:8080 بالا می‌آید. سرویس‌ها: `db`، `redis`، `web` (gunicorn)، `worker` و `beat` (Celery)، `nginx` (فایل‌های static و media).
کانتینرها با `config.settings.prod` اجرا می‌شوند. در `docker-compose.yml`، کوکی امن و ریدایرکت HTTPS برای اجرای محلی روی http خاموش شده‌اند. پشت TLS واقعی آن‌ها را فعال کنید.

## تست‌ها

```bash
pytest                    # با تنظیمات config.settings.test
pytest --cov              # همراه با گزارش پوشش کد
```

تست‌ها روی PostgreSQL اجرا می‌شوند و این موارد را پوشش می‌دهند: قواعد معماری، selectorها و سرویس‌ها، فیلترها و جستجو، پاسخ‌های partial در HTMX، سبد خرید و کد تخفیف، ثبت سفارش و کم شدن موجودی، اعتبارسنجی فرم‌ها، پرداخت، ورود و ثبت‌نام.

## پرداخت

- **زرین‌پال:** `ZARINPAL_MERCHANT_ID` را در `.env` تنظیم کنید. برای محیط آزمایشی زرین‌پال `ZARINPAL_SANDBOX=True` و برای پرداخت واقعی `False` بگذارید.
- **بدون مرچنت و با `DEBUG=True`:** یک درگاه آزمایشی داخلی فعال می‌شود.
- **بدون مرچنت و در حالت production:** گزینه پرداخت آنلاین نمایش داده نمی‌شود.
- موجودی کالا هنگام ثبت سفارش کم می‌شود. اگر سفارش در پنل مدیریت «لغو شده» شود، موجودی برمی‌گردد.

## تنظیمات (`.env`)

| متغیر | توضیح |
|---|---|
| `DJANGO_SETTINGS_MODULE` | پیش‌فرض: `config.settings.dev` (manage.py) و `config.settings.prod` (wsgi و Docker) |
| `DEBUG` | حالت توسعه (در prod همیشه False است) |
| `SECRET_KEY` | در production الزامی است |
| `ALLOWED_HOSTS` | دامنه‌های مجاز، جدا شده با کاما |
| `CSRF_TRUSTED_ORIGINS` | آدرس‌های مجاز برای CSRF، جدا شده با کاما |
| `DATABASE_URL` | مثلاً `postgres://user:pass@host:5432/db` |
| `REDIS_URL` | cache و broker مربوط به Celery؛ اگر خالی باشد cache در حافظه است |
| `CELERY_TASK_ALWAYS_EAGER` | اجرای taskها بدون worker (برای توسعه) |
| `AI_PROVIDER` | ارائه‌دهنده AI؛ خالی یعنی غیرفعال |
| `ZARINPAL_MERCHANT_ID` / `ZARINPAL_SANDBOX` | درگاه پرداخت |
| `SECURE_SSL_REDIRECT` / `SECURE_HSTS_SECONDS` | تنظیمات امنیتی HTTPS در production |

### تنظیمات فروشگاه (پنل مدیریت)

نام فروشگاه، شعار، تلفن، ایمیل، آدرس، شبکه‌های اجتماعی، هزینه ارسال، حد ارسال رایگان و شماره کارت در
**پنل مدیریت ← هسته ← فروشگاه‌ها** تنظیم می‌شوند و نیازی به تغییر کد یا deploy ندارند.

برای راه‌اندازی فروشگاه دوم روی دامنه دیگر، یک Store جدید با دامنه آن بسازید، دامنه را به `ALLOWED_HOSTS` اضافه کنید و
در صورت نیاز با `python manage.py seed_demo --store=CODE` داده نمایشی بسازید.
