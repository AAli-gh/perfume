# syntax=docker/dockerfile:1.7
# ---- مرحله ۱: ساخت CSS با Tailwind (ابزار ساخت وارد image نهایی نمی‌شود) ----
FROM node:22-alpine AS assets
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY tailwind.config.js ./
COPY static ./static
COPY themes ./themes
COPY apps ./apps
RUN npm run build:css

# ---- مرحله ۲: برنامه Django ----
FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod
WORKDIR /app

# کاربر بدون دسترسی root؛ کد برنامه متعلق به root و برای این کاربر فقط‌خواندنی است
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app

# وابستگی‌ها از فایل قفل با بررسی hash (هر بسته دقیقاً همان نسخه تست‌شده)
COPY requirements.lock .
RUN pip install --require-hashes -r requirements.lock

COPY . .
COPY --from=assets /app/static/css/app.css ./static/css/app.css
# کلید موقت و تصادفی فقط برای collectstatic (تنظیمات production کلید ضعیف را نمی‌پذیرد)
RUN SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')" \
    python manage.py collectstatic --noinput \
 && mkdir -p /app/media \
 && chown app:app /app/media \
 && chmod +x /app/deploy/entrypoint.sh

USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)" || exit 1
ENTRYPOINT ["/app/deploy/entrypoint.sh"]
CMD ["web"]
