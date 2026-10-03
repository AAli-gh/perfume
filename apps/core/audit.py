"""ثبت رویدادهای امنیتی در AuditLog. ثبت گزارش هرگز نباید درخواست اصلی را از کار بیندازد."""

import logging

from .ratelimit import client_ip

log = logging.getLogger("apps.audit")


def record(action, request=None, *, user=None, target="", store=None, **data):
    from .models import AuditLog

    try:
        if request is not None:
            user = user if user is not None else getattr(request, "user", None)
            store = store if store is not None else getattr(request, "store", None)
        if user is not None and not getattr(user, "is_authenticated", False):
            user = None
        ip = client_ip(request) if request is not None else None
        entry = AuditLog.objects.create(
            action=action[:60],
            target=str(target)[:200],
            user=user,
            store=store if getattr(store, "pk", None) else None,
            ip=ip or None,
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request is not None else "")[:200],
            data={k: (str(v)[:300] if not isinstance(v, (int, float, bool, type(None))) else v) for k, v in data.items()},
        )
        log.info("audit %s user=%s ip=%s target=%s", action, getattr(user, "pk", None), ip, target)
        return entry
    except Exception:  # noqa: BLE001
        log.exception("Could not write audit log for %s", action)
        return None


def prune(days=None):
    """حذف رویدادهای قدیمی‌تر از AUDIT_LOG_RETENTION_DAYS (پیش‌فرض ۱۸۰ روز)."""
    from datetime import timedelta

    from django.conf import settings
    from django.utils import timezone

    from .models import AuditLog

    days = days or getattr(settings, "AUDIT_LOG_RETENTION_DAYS", 180)
    deleted, _ = AuditLog.objects.filter(created_at__lt=timezone.now() - timedelta(days=days)).delete()
    return deleted
