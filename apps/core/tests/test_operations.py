"""سلامت سرویس، شناسه درخواست، لاگ JSON و بررسی‌های استقرار."""

import json
import logging
import runpy
from pathlib import Path
from unittest import mock

import pytest
from django.core.checks import run_checks
from django.test import override_settings

from apps.core.logging import JsonFormatter, RequestIdFilter, get_request_id

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parents[3]


@override_settings(SECURE_SSL_REDIRECT=True, ALLOWED_HOSTS=["shop.example.com"])
def test_healthz_bypasses_https_redirect_and_host_check(client):
    """healthcheck کانتینر با http://127.0.0.1 درخواست می‌دهد."""
    r = client.get("/healthz", HTTP_HOST="127.0.0.1:8000")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert r["Cache-Control"] == "no-store"
    # بقیه مسیرها همچنان ریدایرکت/رد می‌شوند
    assert client.get("/", HTTP_HOST="127.0.0.1:8000").status_code == 400


def test_readyz_reports_dependencies(client):
    r = client.get("/readyz")
    body = r.json()
    assert r.status_code == 200 and body["checks"]["database"]["ok"] and body["checks"]["cache"]["ok"]


def test_readyz_returns_503_when_database_down(client):
    from apps.core import health

    def broken():
        raise ConnectionError("db down")

    with mock.patch.dict(health.CHECKS, {"database": broken}):
        r = client.get("/readyz")
    assert r.status_code == 503 and r.json()["checks"]["database"] == {"ok": False}
    assert "db down" not in r.content.decode()  # جزئیات خطا بیرون داده نمی‌شود


def test_request_id_generated_and_propagated(client, store):
    r = client.get("/")
    assert len(r["X-Request-ID"]) == 32
    r = client.get("/", HTTP_X_REQUEST_ID="nginx-abc123def456")
    assert r["X-Request-ID"] == "nginx-abc123def456"
    r = client.get("/", HTTP_X_REQUEST_ID="<script>bad</script>")  # مقدار نامعتبر جایگزین می‌شود
    assert "<" not in r["X-Request-ID"] and len(r["X-Request-ID"]) == 32
    assert get_request_id() == "-"  # بعد از درخواست پاک می‌شود


def test_json_formatter():
    record = logging.LogRecord("apps.audit", logging.WARNING, __file__, 1, "سلام %s", ("دنیا",), None)
    RequestIdFilter().filter(record)
    data = json.loads(JsonFormatter().format(record))
    assert data["message"] == "سلام دنیا" and data["level"] == "WARNING" and data["request_id"] == "-"
    assert data["time"].endswith("+00:00")
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record.exc_info = sys.exc_info()
    assert "ValueError: boom" in json.loads(JsonFormatter().format(record))["exception"]


def test_deploy_check_warns_without_shared_cache():
    ids = [m.id for m in run_checks(include_deployment_checks=True)]
    assert "majd.W001" in ids  # تنظیمات تست cache حافظه‌ای دارد
    with override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache",
                                               "LOCATION": "redis://x"}}):
        assert "majd.W001" not in [m.id for m in run_checks(include_deployment_checks=True)]


def test_gunicorn_config(monkeypatch):
    monkeypatch.setenv("WEB_CONCURRENCY", "5")
    conf = runpy.run_path(str(ROOT / "deploy" / "gunicorn.conf.py"))
    assert conf["workers"] == 5 and conf["bind"] == "0.0.0.0:8000" and conf["worker_class"] == "gthread"
    assert conf["max_requests"] > 0 and conf["timeout"] == 30


def test_lockfile_pins_every_requirement_with_hashes():
    lock = (ROOT / "requirements.lock").read_text()
    names = [line.split("==")[0] for line in lock.splitlines() if "==" in line and not line.startswith(" ")]
    for req in (ROOT / "requirements.txt").read_text().splitlines():
        name = req.split("#")[0].strip().split(">")[0].split("<")[0].split("[")[0].strip().lower()
        if name:
            assert name in names, f"{name} در requirements.lock نیست (make lock)"
    assert lock.count("--hash=sha256:") >= len(names)
