"""لاگ ساختاریافته (JSON) و شناسه درخواست (Request ID).

- RequestIdMiddleware: شناسه را از هدر X-Request-ID (که nginx می‌سازد) می‌گیرد یا خودش می‌سازد، در پاسخ
  برمی‌گرداند و به همه لاگ‌های همان درخواست اضافه می‌کند تا یک خطا در nginx، Django و Celery دنبال شود.
- JsonFormatter: هر لاگ یک خط JSON (برای Loki، ELK، CloudWatch و …). با LOG_FORMAT=json فعال می‌شود.
"""

import json
import logging
import re
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

_request_id = ContextVar("request_id", default="-")
VALID_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def get_request_id():
    return _request_id.get()


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get("HTTP_X_REQUEST_ID", "")
        request_id = incoming if VALID_ID.match(incoming) else uuid.uuid4().hex
        request.request_id = request_id
        token = _request_id.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            _request_id.reset(token)
        response["X-Request-ID"] = request_id
        return response


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    FIELDS = ("status_code", "method", "path")

    def format(self, record):
        payload = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        request = getattr(record, "request", None)
        if request is not None and hasattr(request, "path"):
            payload["path"], payload["method"] = request.path, request.method
        for field in self.FIELDS:
            if hasattr(record, field) and field not in payload:
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)
