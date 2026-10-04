"""بررسی سلامت برای Docker، load balancer و مانیتورینگ.

- /healthz  ← فرایند زنده است (بدون دیتابیس؛ برای HEALTHCHECK کانتینر)
- /readyz   ← آماده سرویس‌دهی: دیتابیس و cache پاسخ می‌دهند؛ در غیر این صورت 503

این middleware اولین middleware است: قبل از ریدایرکت HTTPS و بررسی ALLOWED_HOSTS، چون healthcheck داخل
کانتینر با http://127.0.0.1 درخواست می‌دهد. هیچ اطلاعات حساسی برنمی‌گرداند.
"""

import json
import logging
import time

from django.core.cache import cache
from django.db import connections
from django.http import HttpResponse

log = logging.getLogger(__name__)


def _check_database():
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def _check_cache():
    key = "health:ping"
    cache.set(key, "1", 10)
    if cache.get(key) != "1":
        raise RuntimeError("cache read-back failed")


CHECKS = {"database": _check_database, "cache": _check_cache}


def readiness():
    results, ok = {}, True
    for name, check in CHECKS.items():
        started = time.monotonic()
        try:
            check()
            results[name] = {"ok": True, "ms": round((time.monotonic() - started) * 1000, 1)}
        except Exception as exc:  # noqa: BLE001
            ok = False
            results[name] = {"ok": False}
            log.error("Readiness check %s failed: %s", name, exc.__class__.__name__)
    return ok, results


class HealthCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/healthz":
            return self._respond({"status": "ok"}, 200)
        if request.path == "/readyz":
            ok, results = readiness()
            return self._respond({"status": "ok" if ok else "unavailable", "checks": results}, 200 if ok else 503)
        return self.get_response(request)

    @staticmethod
    def _respond(payload, status):
        response = HttpResponse(json.dumps(payload), status=status, content_type="application/json")
        response["Cache-Control"] = "no-store"
        return response
