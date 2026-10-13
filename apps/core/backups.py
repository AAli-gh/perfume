"""پشتیبان‌گیری دیتابیس و فایل‌های آپلودی (SQLite روی PythonAnywhere، PostgreSQL روی سرور اصلی).

خروجی‌ها در BACKUP_DIR: db-YYYYmmdd-HHMMSS.sqlite3.gz | .dump (pg_dump custom) | .json.gz و media-….tar.gz.
هر فایل اول با پسوند .partial نوشته و بعد تغییر نام داده می‌شود؛ فایل ناقص هرگز «نسخه معتبر» به نظر نمی‌رسد.
"""

import gzip
import logging
import os
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connection

log = logging.getLogger(__name__)
PATTERNS = ("db-*", "media-*")


@dataclass
class BackupResult:
    files: list = field(default_factory=list)
    pruned: list = field(default_factory=list)


def _publish(partial: Path) -> Path:
    final = partial.with_name(partial.name.removesuffix(".partial"))
    partial.replace(final)
    return final


def _gzip_file(src, dest):
    with open(src, "rb") as fin, gzip.open(dest, "wb", compresslevel=6) as fout:
        shutil.copyfileobj(fin, fout)


def backup_sqlite(dest_dir: Path, stamp: str, source=None) -> Path:
    """نسخه سازگار با API پشتیبان SQLite (در حین کار سایت امن است) + بررسی سلامت، سپس gzip."""
    source = source or settings.DATABASES["default"]["NAME"]
    with tempfile.TemporaryDirectory(dir=dest_dir) as tmp:
        copy = Path(tmp) / "db.sqlite3"
        src, dst = sqlite3.connect(source), sqlite3.connect(copy)
        try:
            src.backup(dst)
            status = dst.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            dst.close()
            src.close()
        if status != "ok":
            raise RuntimeError(f"نسخه پشتیبان SQLite سالم نیست: {status}")
        partial = dest_dir / f"db-{stamp}.sqlite3.gz.partial"
        _gzip_file(copy, partial)
    return _publish(partial)


def backup_postgres(dest_dir: Path, stamp: str) -> Path:
    db = settings.DATABASES["default"]
    partial = dest_dir / f"db-{stamp}.dump.partial"
    env = {**os.environ, "PGPASSWORD": str(db.get("PASSWORD") or "")}
    cmd = ["pg_dump", "--format=custom", "--no-owner", "--file", str(partial), "--dbname", db["NAME"]]
    for flag, key in (("--host", "HOST"), ("--port", "PORT"), ("--username", "USER")):
        if db.get(key):
            cmd += [flag, str(db[key])]
    subprocess.run(cmd, env=env, check=True, capture_output=True, timeout=1800)
    return _publish(partial)


def backup_json(dest_dir: Path, stamp: str) -> Path:
    """جایگزین وقتی pg_dump در دسترس نیست: dumpdata کامل (بازگردانی با loaddata)."""
    partial = dest_dir / f"db-{stamp}.json.gz.partial"
    with gzip.open(partial, "wt", encoding="utf-8") as out:
        call_command("dumpdata", "--natural-foreign", "--exclude=contenttypes", "--exclude=auth.permission",
                     "--exclude=sessions", "--exclude=admin.logentry", stdout=out)
    return _publish(partial)


def backup_media(dest_dir: Path, stamp: str) -> Path | None:
    root = Path(os.path.realpath(settings.MEDIA_ROOT))  # روی PythonAnywhere پوشه media یک symlink است
    if not root.is_dir():
        return None
    partial = dest_dir / f"media-{stamp}.tar.gz.partial"
    with tarfile.open(partial, "w:gz") as tar:
        tar.add(root, arcname=".")
    return _publish(partial)


def prune(dest_dir: Path, keep_days: int) -> list:
    """حذف نسخه‌های قدیمی‌تر از keep_days روز؛ تازه‌ترین نسخه هر نوع همیشه می‌ماند."""
    cutoff = time.time() - keep_days * 86400
    removed = []
    for pattern in PATTERNS:
        files = sorted((p for p in dest_dir.glob(pattern) if not p.name.endswith(".partial")),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[1:]:
            if old.stat().st_mtime < cutoff:
                old.unlink()
                removed.append(old.name)
    for stale in dest_dir.glob("*.partial"):  # باقی‌مانده اجرای ناموفق قبلی
        if stale.stat().st_mtime < time.time() - 86400:
            stale.unlink()
    return removed


def run_backup(*, dest=None, keep_days=None, media=True) -> BackupResult:
    dest_dir = Path(dest or settings.BACKUP_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(dest_dir, 0o700)  # شامل اطلاعات مشتریان است
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    result = BackupResult()
    if connection.vendor == "sqlite":
        result.files.append(backup_sqlite(dest_dir, stamp))
    elif connection.vendor == "postgresql" and shutil.which("pg_dump"):
        result.files.append(backup_postgres(dest_dir, stamp))
    else:
        result.files.append(backup_json(dest_dir, stamp))
    if media and (archive := backup_media(dest_dir, stamp)):
        result.files.append(archive)
    days = settings.BACKUP_RETENTION_DAYS if keep_days is None else keep_days
    result.pruned = prune(dest_dir, days)
    log.info("backup ok: %s (pruned %d)", ", ".join(p.name for p in result.files), len(result.pruned))
    return result
