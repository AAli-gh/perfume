# عطر مجد — Majd Perfume

فروشگاه اینترنتی عطر، فارسی و راست‌به‌چپ، با طراحی تیره و طلایی.

**معماری:** Django 5.2 · PostgreSQL · Django Templates · HTMX 2 · Tailwind CSS 3

## ساختار پروژه

```
config/        تنظیمات، urls، wsgi
core/          صفحه اصلی، درباره ما، تماس، خبرنامه، فیلترهای قالب (اعداد فارسی، تومان، تاریخ شمسی)، seed_demo
catalog/       برند، خانواده رایحه، کالکشن، محصول، حجم/قیمت (Variant)، گالری، نظرات
cart/          سبد خرید مبتنی بر session + کد تخفیف
orders/        کد تخفیف، سفارش، اقلام سفارش، ثبت سفارش، درگاه زرین‌پال
accounts/      کاربر سفارشی (ورود با ایمیل)، ورود/ثبت‌نام، سفارش‌های من
blog/          دسته‌بندی و مقاله
templates/     قالب پایه و کامپوننت‌های مشترک (کارت محصول، هیرو، صفحه‌بندی، …)
static/src/    ورودی Tailwind  →  static/css/app.css (ساخته می‌شود)
static/js/     app.js (تعاملات کوچک: منو، گالری، اسلایدر، تب‌ها)
static/vendor/ htmx.min.js
seed/images/   تصاویر داده‌های نمایشی
```

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
pip install -r requirements.txt
cp .env.example .env          # در صورت نیاز DATABASE_URL را تغییر دهید

# ۳. Tailwind
npm install
npm run build:css             # یا در حین توسعه: npm run watch:css

# ۴. دیتابیس و داده نمایشی
python manage.py migrate
python manage.py seed_demo    # ۱۲ محصول، ۵ کالکشن، ۶ مقاله، کدهای تخفیف MAJD10 و YALDA50
python manage.py createsuperuser

python manage.py runserver
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

سایت روی http://localhost:8080 بالا می‌آید. nginx فایل‌های static و media را سرو می‌کند.

## تست‌ها

```bash
python manage.py test
```

تست‌ها روی PostgreSQL اجرا می‌شوند و این موارد را پوشش می‌دهند: فیلترها و جستجو، پاسخ‌های partial در HTMX، سبد خرید و کد تخفیف، ثبت سفارش و کم شدن موجودی، اعتبارسنجی فرم‌ها، پرداخت، ورود و ثبت‌نام.

## پرداخت

- **زرین‌پال:** `ZARINPAL_MERCHANT_ID` را در `.env` تنظیم کنید. برای محیط آزمایشی زرین‌پال `ZARINPAL_SANDBOX=True` و برای پرداخت واقعی `False` بگذارید.
- **بدون مرچنت و با `DEBUG=True`:** یک درگاه آزمایشی داخلی فعال می‌شود.
- **بدون مرچنت و در حالت production:** گزینه پرداخت آنلاین نمایش داده نمی‌شود.
- موجودی کالا هنگام ثبت سفارش کم می‌شود. اگر سفارش در پنل مدیریت «لغو شده» شود، موجودی برمی‌گردد.

## تنظیمات (`.env`)

| متغیر | توضیح |
|---|---|
| `DEBUG` | حالت توسعه |
| `SECRET_KEY` | در production الزامی است |
| `ALLOWED_HOSTS` | دامنه‌های مجاز، جدا شده با کاما |
| `CSRF_TRUSTED_ORIGINS` | آدرس‌های مجاز برای CSRF، جدا شده با کاما |
| `DATABASE_URL` | مثلاً `postgres://user:pass@host:5432/db` |
| `ZARINPAL_MERCHANT_ID` / `ZARINPAL_SANDBOX` | درگاه پرداخت |
| `SHIPPING_COST` | هزینه ارسال به تومان |
| `FREE_SHIPPING_OVER` | حداقل مبلغ سفارش برای ارسال رایگان؛ مقدار ۰ یعنی ارسال رایگان غیرفعال است |
| `SECURE_SSL_REDIRECT` / `SECURE_HSTS_SECONDS` | تنظیمات امنیتی HTTPS در production |

اطلاعات تماس فروشگاه (تلفن، ایمیل، آدرس، شبکه‌های اجتماعی) در `SITE_INFO` داخل `config/settings.py` قرار دارد.
