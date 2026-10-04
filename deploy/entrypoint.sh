#!/bin/sh
# نقطه ورود کانتینر:  web | worker | beat | migrate | manage <args…> | <هر دستور دیگر>
set -eu

case "${1:-web}" in
  web)
    exec gunicorn config.wsgi:application -c /app/deploy/gunicorn.conf.py
    ;;
  worker)
    exec celery -A config worker --loglevel "${LOG_LEVEL:-INFO}" --concurrency "${CELERY_CONCURRENCY:-2}"
    ;;
  beat)
    # فایل زمان‌بندی در /tmp (کد برنامه برای کاربر app فقط‌خواندنی است)
    exec celery -A config beat --loglevel "${LOG_LEVEL:-INFO}" --schedule /tmp/celerybeat-schedule
    ;;
  migrate)
    # یک بار در هر استقرار (سرویس جدا)، نه در شروع هر web؛ چند replica هم‌زمان migrate نمی‌کنند
    python manage.py migrate --noinput
    python manage.py sync_themes
    # در production هر هشدار امنیتی استقرار را متوقف می‌کند (برای اجرای محلی روی http: DEPLOY_CHECK=0)
    if [ "${DEPLOY_CHECK:-1}" = "1" ]; then
        python manage.py check --deploy --fail-level WARNING
    fi
    ;;
  manage)
    shift
    exec python manage.py "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
