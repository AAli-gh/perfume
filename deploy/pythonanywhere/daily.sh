#!/bin/bash
# کار روزانه PythonAnywhere (Tasks → Scheduled tasks؛ حساب رایگان فقط یک کار روزانه دارد):
#   bash ~/majd/deploy/pythonanywhere/daily.sh
# پشتیبان دیتابیس و تصاویر در ~/majd-data/backups، سپس پیام‌های زمان‌بندی‌شده (روی این هاست Celery beat نیست).
# هر مرحله جدا اجرا می‌شود تا خطای یکی بقیه را متوقف نکند؛ خروجی در ~/majd-data/daily.log
set -uo pipefail
APP="$HOME/majd"; PY="$HOME/.virtualenvs/majd/bin/python"
export DJANGO_SETTINGS_MODULE=config.settings.pythonanywhere
cd "$APP" || exit 1
exec >> "$HOME/majd-data/daily.log" 2>&1
echo "=== $(date -u +%FT%TZ)"
status=0
for cmd in backup_site send_price_drop_alerts send_cart_reminders prune_audit_log; do
    "$PY" manage.py "$cmd" || { echo "!! $cmd FAILED"; status=1; }
done
exit $status
