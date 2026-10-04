#!/bin/sh
# پشتیبان‌گیری دیتابیس و media.  اجرا: backup.sh once | loop
#   خروجی: /backups/db-YYYYmmdd-HHMMSS.dump (فرمت custom، قابل pg_restore) و media-….tar.gz
set -eu
BACKUP_DIR=${BACKUP_DIR:-/backups}
RETENTION=${BACKUP_RETENTION_DAYS:-14}
INTERVAL=${BACKUP_INTERVAL_SECONDS:-86400}

backup_once() {
    stamp=$(date -u +%Y%m%d-%H%M%S)
    mkdir -p "$BACKUP_DIR"
    pg_dump --format=custom --no-owner --file "$BACKUP_DIR/db-$stamp.dump.partial"
    mv "$BACKUP_DIR/db-$stamp.dump.partial" "$BACKUP_DIR/db-$stamp.dump"   # فایل ناقص هرگز «نسخه معتبر» به نظر نمی‌رسد
    if [ -d /media ]; then
        tar -czf "$BACKUP_DIR/media-$stamp.tar.gz.partial" -C /media .
        mv "$BACKUP_DIR/media-$stamp.tar.gz.partial" "$BACKUP_DIR/media-$stamp.tar.gz"
    fi
    find "$BACKUP_DIR" -name 'db-*.dump' -mtime "+$RETENTION" -delete
    find "$BACKUP_DIR" -name 'media-*.tar.gz' -mtime "+$RETENTION" -delete
    echo "$(date -u +%FT%TZ) backup ok: db-$stamp.dump ($(du -h "$BACKUP_DIR/db-$stamp.dump" | cut -f1))"
}

case "${1:-once}" in
    once) backup_once ;;
    loop)
        while true; do
            backup_once || echo "$(date -u +%FT%TZ) backup FAILED" >&2
            sleep "$INTERVAL"
        done ;;
    *) echo "usage: backup.sh once|loop" >&2; exit 2 ;;
esac
