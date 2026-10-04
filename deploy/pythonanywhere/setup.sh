#!/bin/bash
# نصب/به‌روزرسانی نسخه نمایشی روی PythonAnywhere (حساب رایگان، SQLite).
#   bash ~/majd_setup.sh            ← فایل ~/majd_release.tar.gz را باز و مستقر می‌کند
# داده‌ها (دیتابیس، تصاویر آپلودی، .env و رمز مدیر) در ~/majd-data می‌مانند و با هر استقرار حفظ می‌شوند.
set -euo pipefail
exec > >(tee -a "$HOME/majd_setup.log") 2>&1
echo "=== $(date -u +%FT%TZ) start"

APP="$HOME/majd"; DATA="$HOME/majd-data"; VENV="$HOME/.virtualenvs/majd"
HOST="${PA_HOST:-$(whoami).pythonanywhere.com}"
mkdir -p "$DATA/media"; chmod 700 "$DATA"

rm -rf "$APP.new"; mkdir -p "$APP.new"
tar -xzf "$HOME/majd_release.tar.gz" -C "$APP.new"

[ -x "$VENV/bin/python" ] || python3.11 -m venv "$VENV"
"$VENV/bin/pip" install -q --disable-pip-version-check -r "$APP.new/requirements.txt"

if [ ! -f "$DATA/.env" ]; then
  umask 077
  cat > "$DATA/.env" <<ENV
DJANGO_SETTINGS_MODULE=config.settings.pythonanywhere
SECRET_KEY=$("$VENV/bin/python" -c 'import secrets; print(secrets.token_urlsafe(50))')
ALLOWED_HOSTS=$HOST
CSRF_TRUSTED_ORIGINS=https://$HOST
DATABASE_URL=sqlite:///$DATA/db.sqlite3
ENV
fi
ln -sfn "$DATA/.env" "$APP.new/.env"
ln -sfn "$DATA/media" "$APP.new/media"

cd "$APP.new"
export DJANGO_SETTINGS_MODULE=config.settings.pythonanywhere
PY="$VENV/bin/python"
"$PY" manage.py migrate --noinput
"$PY" manage.py createcachetable
"$PY" manage.py sync_themes
"$PY" manage.py seed_demo
"$PY" manage.py collectstatic --noinput -v0
"$PY" manage.py check --deploy --fail-level WARNING

if [ ! -f "$DATA/admin_credentials.txt" ]; then
  umask 077
  ADMIN_PASSWORD=$("$PY" -c 'import secrets; print(secrets.token_urlsafe(14))')
  ADMIN_EMAIL="admin@$HOST" ADMIN_PASSWORD="$ADMIN_PASSWORD" "$PY" manage.py shell -c "
import os
from apps.accounts.models import User
email, password = os.environ['ADMIN_EMAIL'], os.environ['ADMIN_PASSWORD']
user = User.objects.filter(email=email).first() or User.objects.create_superuser(email=email, password=password)
user.set_password(password); user.is_staff = user.is_superuser = True; user.save()
"
  printf 'email: admin@%s\npassword: %s\n' "$HOST" "$ADMIN_PASSWORD" > "$DATA/admin_credentials.txt"
fi

cd "$HOME"
rm -rf "$APP.old"; [ -d "$APP" ] && mv "$APP" "$APP.old"
mv "$APP.new" "$APP"
echo "=== $(date -u +%FT%TZ) DONE"
