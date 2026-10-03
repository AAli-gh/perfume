# راهنمای استقرار (production)

این راهنما برای اجرای عطر مجد روی یک سرور لینوکس با Docker است. سرویس‌ها همه در `docker-compose.prod.yml` تعریف شده‌اند.

## معماری

```
اینترنت ──► nginx (80→443، TLS، gzip، cache استاتیک، محدودیت سیل درخواست، سرو امن media)
              │
              ▼
            web (gunicorn، کاربر غیر root، فایل‌سیستم فقط‌خواندنی) ──► PostgreSQL 16
              │                                                    ──► Redis 7 (cache + صف Celery)
            worker (Celery) · beat (زمان‌بندی) · backup (pg_dump روزانه + media)
init-media و migrate: پیش از web یک بار اجرا می‌شوند (مالکیت media، migrate، ثبت پوسته‌ها، check --deploy)
```

- **پورت‌ها:** فقط nginx پورت منتشر می‌کند (۸۰ و ۴۴۳). دیتابیس، Redis و gunicorn از بیرون در دسترس نیستند.
- **image:**
  - دو مرحله ساخت دارد و ابزار ساخت CSS (Node) وارد image نهایی نمی‌شود.
  - وابستگی‌های Python از `requirements.lock` با بررسی hash نصب می‌شوند.
  - برنامه با کاربر `app` (uid 10001) اجرا می‌شود.
- **کانتینرهای برنامه:**
  - `read_only` و `cap_drop: ALL` هستند و `no-new-privileges` دارند.
  - فقط volume فایل‌های media و `/tmp` قابل نوشتن‌اند.
- **فایل‌های استاتیک:**
  - داخل image هستند و whitenoise آن‌ها را با نام hash‌دار، brotli یا gzip و cache یک‌ساله می‌دهد.
  - nginx هم آن‌ها را cache می‌کند.
  - پس از هر به‌روزرسانی، فایل قدیمی‌ای باقی نمی‌ماند.

## نصب اول

```bash
git clone <repo> majd && cd majd
cp .env.example .env
```

`.env` را ویرایش کنید. کمترین موارد لازم:

| متغیر | مقدار |
|---|---|
| `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `ALLOWED_HOSTS` | `shop.example.com,www.shop.example.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://shop.example.com,https://www.shop.example.com` |
| `POSTGRES_PASSWORD` و `REDIS_PASSWORD` | رمزهای تصادفی جدا (همان دستور بالا با 24) |
| `ADMIN_URL` | آدرس غیرقابل حدس پنل مدیریت، مثلاً `manage-k8x2/` |
| `EMAIL_URL` | `smtp+tls://user:pass@smtp.example.com:587` |
| `DEFAULT_FROM_EMAIL`، `ADMINS` | فرستنده ایمیل‌ها و گیرنده گزارش خطاهای ۵۰۰ (`نام:email`) |
| `ZARINPAL_MERCHANT_ID` | پس از ساخت حساب درگاه در پنل مدیریت |

> `.env` را هرگز commit نکنید (در `.gitignore` هست). دسترسی فایل را محدود کنید: `chmod 600 .env`.

### گواهی TLS

nginx گواهی را از `deploy/certs/fullchain.pem` و `deploy/certs/privkey.pem` می‌خواند.

**Let's Encrypt** (پیشنهادی؛ درخواست تأیید روی پورت ۸۰ از مسیر `/.well-known/acme-challenge/` جواب داده می‌شود):

```bash
docker compose -f docker-compose.prod.yml up -d nginx   # (اولین بار با گواهی موقت، پایین)
docker run --rm -v majd_acme:/var/www/acme -v "$PWD/deploy/certs-le:/etc/letsencrypt" certbot/certbot \
  certonly --webroot -w /var/www/acme -d shop.example.com --agree-tos -m you@example.com -n
cp deploy/certs-le/live/shop.example.com/fullchain.pem deploy/certs-le/live/shop.example.com/privkey.pem deploy/certs/
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

تمدید (cron هفتگی): همان دستور certbot با `renew`، کپی فایل‌ها و `nginx -s reload`.

**گواهی موقت** (فقط برای آزمایش؛ مرورگر هشدار می‌دهد): `sh deploy/selfsigned-cert.sh shop.example.com`

### اجرا

```bash
make build                      # یا: docker build -t majd:latest .
make up                         # docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps        # همه healthy؛ init-media و migrate با کد 0 تمام شده باشند
docker compose -f docker-compose.prod.yml run --rm web manage createsuperuser
make smoke URL=https://shop.example.com
```

`migrate` با `check --deploy --fail-level WARNING` تمام می‌شود. اگر تنظیمات امنیتی ناقص باشد (مثلاً Redis تنظیم نشده یا کلید ضعیف است)، web بالا نمی‌آید و دلیل در `docker compose logs migrate` نوشته می‌شود.

پس از ورود به پنل مدیریت:
1. اطلاعات فروشگاه، دامنه اصلی (`StoreDomain` با «دامنه اصلی») و حساب درگاه پرداخت را تنظیم کنید.
2. در استودیو (`/studio/`) ظاهر را بسازید و منتشر کنید.

## به‌روزرسانی

```bash
git pull
make build
docker compose -f docker-compose.prod.yml up -d     # migrate دوباره اجرا می‌شود و سپس web/worker/beat تازه
make smoke URL=https://shop.example.com
```

- nginx آدرس جدید web را خودکار از DNS داخلی Docker می‌گیرد (`resolve`)؛ ری‌استارت nginx لازم نیست.
- **بازگشت به نسخه قبل:** image قبلی را با برچسب نگه دارید و آن را اجرا کنید:

  ```bash
  docker tag majd:latest majd:2026-10-03          # پیش از هر build
  APP_IMAGE=majd:2026-10-03 docker compose -f docker-compose.prod.yml up -d
  ```

  migrationها رو به جلو هستند. اگر نسخه جدید migration داشت و برگشت لازم شد، پیش از برگشت پشتیبان بگیرید (`make backup`).

## پشتیبان‌گیری و بازگردانی

- **خودکار:** سرویس `backup` هر `BACKUP_INTERVAL_SECONDS` (پیش‌فرض ۲۴ ساعت) این دو فایل را در `./backups/` می‌سازد:
  - `db-<زمان>.dump` (pg_dump)
  - `media-<زمان>.tar.gz`
  
  نسخه‌های قدیمی‌تر از `BACKUP_RETENTION_DAYS` (پیش‌فرض ۱۴ روز) پاک می‌شوند.
- **فوری:** `make backup`
- **خارج از سرور:** پوشه `backups/` را روزانه به فضای دیگری (مثلاً S3 یا سرور دوم) منتقل کنید. پشتیبانی که فقط روی همان سرور باشد با خرابی سرور از بین می‌رود.

**بازگردانی:**

```bash
sh deploy/restore.sh backups/db-20261003-020000.dump backups/media-20261003-020000.tar.gz
```

این اسکریپت:
1. web، worker و beat را متوقف می‌کند.
2. دیتابیس را با `pg_restore --clean` بازمی‌گرداند و media را جایگزین می‌کند.
3. سرویس‌ها را دوباره راه می‌اندازد.

این روند در فاز ۱۲ عملاً آزمایش شد: حذف همه محصولات، سپس بازگردانی کامل.

## پایش

| آدرس | کاربرد |
|---|---|
| `/healthz` | زنده بودن فرایند (HEALTHCHECK کانتینر، بدون دیتابیس) |
| `/readyz` | آمادگی: دیتابیس و Redis؛ در صورت مشکل 503 |
| `/nginx-health` (روی پورت ۸۰) | سلامت nginx |

- **لاگ‌ها:**
  - هر خط یک JSON است، همراه با `request_id`. nginx این شناسه را می‌سازد و Django، gunicorn و Celery همان را ثبت می‌کنند.
  - هدر `X-Request-ID` در پاسخ هم هست، پس شکایت یک کاربر را می‌شود تا لاگ دقیق دنبال کرد.
  - چرخش لاگ Docker: ۵ فایل ۱۰ مگابایتی برای هر سرویس.
- **رویدادهای امنیتی:** پنل مدیریت ← «گزارش رویدادهای امنیتی». این رویدادها با logger `apps.audit` در لاگ هم نوشته می‌شوند.

## ظرفیت (اندازه‌گیری فاز ۱۲)

روی یک ماشین ۴ هسته‌ای (تست بار روی همان ماشین اجرا شد):

| سناریو | درخواست در ثانیه | p50 | p95 | p99 | خطا |
|---|---|---|---|---|---|
| ۱۰ کاربر هم‌زمان (مستقیم به gunicorn) | ۱۲۱ | ۷۷ms | ۱۵۸ms | ۲۲۹ms | ۰ |
| ۳۰ کاربر هم‌زمان | ۱۲۴ | ۱۹۹ms | ۵۶۲ms | ۷۱۶ms | ۰ |

- اجرای دوباره روی سرور خودتان: `make loadtest USERS=20 DURATION=30`
- تعداد worker با `WEB_CONCURRENCY` تنظیم می‌شود (پیش‌فرض: ۲×CPU+۱).
- nginx از هر IP بیش از ۲۰ درخواست در ثانیه (با ظرفیت انفجاری ۴۰) را با 429 رد می‌کند. اگر پشت CDN یا load balancer هستید:
  - IP واقعی را در nginx تنظیم کنید (`set_real_ip_from`).
  - `TRUSTED_PROXY_COUNT` را یکی بیشتر کنید.

## اجرای محلی با Docker

`docker compose up -d --build` (فایل `docker-compose.yml`) همان image را روی `http://localhost:8080` و بدون TLS اجرا می‌کند. فقط برای آزمایش است؛ در این حالت HTTPS، HSTS و `check --deploy` خاموش‌اند.
