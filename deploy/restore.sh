#!/bin/sh
# بازگردانی پشتیبان (روی میزبان اجرا می‌شود):
#   deploy/restore.sh backups/db-20261003-020000.dump [backups/media-20261003-020000.tar.gz]
# پیش از اجرا سرویس‌های برنامه متوقف می‌شوند تا در حین بازگردانی چیزی نوشته نشود.
set -eu
DUMP=${1:?مسیر فایل db-*.dump}
MEDIA=${2:-}
COMPOSE="docker compose -f docker-compose.prod.yml"

$COMPOSE stop web worker beat
$COMPOSE exec -T db sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$DUMP"
if [ -n "$MEDIA" ]; then
    # با همان کاربر app (کانتینرها cap_drop: ALL دارند؛ chown ممکن نیست و لازم هم نیست)
    $COMPOSE run --rm --no-deps -T --entrypoint sh web -c 'find /app/media -mindepth 1 -delete && tar -xzf - -C /app/media --no-same-owner' < "$MEDIA"
fi
$COMPOSE up -d web worker beat
echo "بازگردانی کامل شد."
