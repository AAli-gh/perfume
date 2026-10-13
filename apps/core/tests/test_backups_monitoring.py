"""پشتیبان روزانه و گزارش خطا به Sentry."""

import gzip
import os
import sqlite3
import tarfile
import time
from unittest import mock

import environ
import pytest
from django.core.management import CommandError, call_command

from apps.core import backups, monitoring

pytestmark = pytest.mark.django_db


def test_backup_command_db_and_media(settings, tmp_path, store):
    (tmp_path / "media").mkdir()
    settings.MEDIA_ROOT = str(tmp_path / "media")
    (tmp_path / "media" / "a.jpg").write_bytes(b"img")
    dest = tmp_path / "b"
    with mock.patch("apps.core.backups.shutil.which", return_value=None):  # نسخه pg_dump محیط CI مهم نباشد
        call_command("backup_site", "--dir", str(dest), stdout=open(os.devnull, "w"))
    names = sorted(p.name for p in dest.iterdir())
    assert len(names) == 2 and names[0].startswith("db-") and names[1].startswith("media-")
    assert oct(dest.stat().st_mode)[-3:] == "700"
    with tarfile.open(dest / names[1]) as tar:
        assert "./a.jpg" in tar.getnames()


def test_json_fallback_when_pg_dump_missing(tmp_path, store):
    with mock.patch("apps.core.backups.shutil.which", return_value=None):
        result = backups.run_backup(dest=tmp_path, media=False)
    (dump,) = result.files
    assert dump.name.endswith(".json.gz")
    assert b'"core.store"' in gzip.open(dump).read()


def test_postgres_dump_uses_pg_dump(tmp_path):
    def fake_run(cmd, **kwargs):
        open(cmd[cmd.index("--file") + 1], "wb").write(b"PGDMP")
        assert kwargs["env"]["PGPASSWORD"] is not None and "--dbname" in cmd

    with mock.patch("apps.core.backups.subprocess.run", side_effect=fake_run):
        path = backups.backup_postgres(tmp_path, "20260101-000000")
    assert path.name == "db-20260101-000000.dump" and path.read_bytes() == b"PGDMP"


def test_sqlite_backup_is_consistent(tmp_path):
    source = tmp_path / "live.sqlite3"
    con = sqlite3.connect(source)
    con.execute("create table t (x)")
    con.execute("insert into t values (42)")
    con.commit()
    con.close()
    path = backups.backup_sqlite(tmp_path, "20260101-000000", source=str(source))
    restored = tmp_path / "restored.sqlite3"
    restored.write_bytes(gzip.open(path).read())
    assert sqlite3.connect(restored).execute("select x from t").fetchone() == (42,)
    assert not list(tmp_path.glob("*.partial"))


def test_prune_keeps_newest_of_each_kind(tmp_path):
    old = time.time() - 30 * 86400
    for name, age in [("db-1.dump", old), ("db-2.dump", old - 10), ("media-1.tar.gz", old), ("x.partial", old)]:
        (tmp_path / name).write_text("x")
        os.utime(tmp_path / name, (age, age))
    (tmp_path / "db-3.dump").write_text("x")  # تازه
    removed = backups.prune(tmp_path, keep_days=14)
    assert sorted(removed) == ["db-1.dump", "db-2.dump"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["db-3.dump", "media-1.tar.gz"]


def test_backup_failure_is_logged_and_raises(tmp_path, caplog):
    with mock.patch("apps.core.management.commands.backup_site.run_backup", side_effect=OSError("disk full")):
        with pytest.raises(CommandError, match="disk full"):
            call_command("backup_site", "--dir", str(tmp_path))
    assert "backup FAILED" in caplog.text


def test_sentry_disabled_without_dsn():
    assert monitoring.init_sentry(environ.Env()) is False


def test_sentry_init_with_dsn(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://public@o0.ingest.sentry.io/1")
    with mock.patch("sentry_sdk.init") as init:
        assert monitoring.init_sentry(environ.Env()) is True
    kwargs = init.call_args.kwargs
    assert kwargs["send_default_pii"] is False and kwargs["before_send"] is monitoring.before_send
    assert kwargs["traces_sample_rate"] == 0.0 and kwargs["environment"] == "production"


def test_before_send_scrubs_pii():
    event = {
        "user": {"id": 7, "email": "a@b.com", "ip_address": "1.2.3.4"},
        "request": {"url": "https://x.ir/track/?phone=09121234567", "cookies": {"sessionid": "s"}, "data": {"p": 1},
                    "headers": {"Cookie": "s", "User-Agent": "UA", "Authorization": "t"},
                    "query_string": "phone=09121234567"},
        "exception": {"values": [{"value": "SMS to 09121234567 / ali@example.com failed"}]},
        "extra": {"phone": "09121234567", "order": "MJ-1"},
    }
    out = monitoring.before_send(event)
    assert out["user"] == {"id": 7}
    assert "cookies" not in out["request"] and "data" not in out["request"]
    assert out["request"]["headers"] == {"User-Agent": "UA"}
    flat = str(out)
    assert "09121234567" not in flat and "ali@example.com" not in flat
    assert out["extra"] == {"phone": monitoring.FILTERED, "order": "MJ-1"}
    assert monitoring.before_send({"user": {}})["user"] == {}
