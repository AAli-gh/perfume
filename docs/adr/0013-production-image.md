# ADR-0013: image production: lock با hash، کاربر غیر root، فایل‌سیستم فقط‌خواندنی، migrate جدا

**وضعیت:** پذیرفته‌شده

## زمینه
استقرار باید تکرارپذیر، امن و بدون downtime طولانی باشد. Kubernetes در brief کنار گذاشته شده است.

## تصمیم
- **image:**
  - Dockerfile چندمرحله‌ای است و Node وارد image نهایی نمی‌شود.
  - وابستگی‌ها فقط از `requirements.lock` و با `--require-hashes` نصب می‌شوند.
  - برنامه با کاربر `app` (uid 10001) اجرا می‌شود.
- **کانتینرها:** `read_only`، `cap_drop: ALL` و `no-new-privileges`. فقط volume فایل‌های media و `/tmp` قابل نوشتن‌اند.
- **ترتیب استقرار در docker compose:**
  - `migrate` یک سرویس یک‌باره است: migrate، `sync_themes` و `check --deploy --fail-level WARNING`. web فقط پس از موفقیت آن بالا می‌آید.
  - `init-media` مالکیت volume را درست می‌کند.
- **nginx:** آدرس web را با `resolve` از DNS داخلی Docker می‌گیرد، تا IP قدیمی بعد از redeploy خطای 502 ندهد.
- **سلامت و لاگ:** `/healthz` (زنده بودن) و `/readyz` (آمادگی)، لاگ JSON با `request_id`، و پشتیبان‌گیری روزانه دیتابیس و media.

## پیامدها
- تنظیمات ناامن، استقرار را متوقف می‌کنند، نه اینکه بی‌صدا اجرا شوند.
- مقیاس افقی (چند سرور) به ذخیره‌ساز media مشترک (S3) نیاز دارد که هنوز پیاده نشده است ([roadmap](../roadmap.md)).
