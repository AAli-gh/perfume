# ---- مرحله ۱: ساخت CSS با Tailwind ----
FROM node:22-alpine AS assets
WORKDIR /app
COPY package.json package-lock.json tailwind.config.js ./
RUN npm ci
COPY . .
RUN npm run build:css

# ---- مرحله ۲: برنامه Django ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=config.settings.prod
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=assets /app/static/css/app.css ./static/css/app.css
# کلید موقت و تصادفی فقط برای collectstatic (تنظیمات production کلید ضعیف را نمی‌پذیرد)
RUN SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')" python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
