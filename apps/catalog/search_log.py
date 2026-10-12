"""ثبت جستجوهای مشتریان و گزارش آن برای استودیو.

هر جستجو با «برداشت» آن ذخیره می‌شود؛ جستجوهای «خنک زیر سه تومن» و «عطر خنک تا ۳ میلیون» برداشت یکسان دارند
و با هم شمرده می‌شوند. یک بازدیدکننده که همان عبارت را در ۳۰ دقیقه چند بار جستجو کند یک بار شمرده می‌شود.
"""

import hashlib
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, Max, Q
from django.utils import timezone

from .models import SearchLog
from .search import normalize

DEDUPE_SECONDS = 1800
RETENTION_DAYS = 365


def intent_of(result):
    parsed = result.parsed
    if parsed is not None and parsed.is_smart:
        return " · ".join(c.label for c in parsed.criteria if c.kind != "sort")[:300]
    return normalize(parsed.raw if parsed is not None else "")[:300]


def record_search(request, q, result, count):
    q = (q or "").strip()
    if not q or len(q) > 200:
        return None
    session_key = request.session.session_key or ""
    visitor = hashlib.sha256(f"{session_key}:{request.META.get('REMOTE_ADDR', '')}".encode()).hexdigest()[:16]
    normalized = normalize(q)
    key = f"searchlog:{request.store.pk}:{visitor}:{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"
    if not cache.add(key, 1, DEDUPE_SECONDS):
        return None
    intent = intent_of(result) if result.parsed is not None else normalized
    return SearchLog.objects.create(
        store=request.store, query=normalized, raw=q[:200], intent=intent or normalized, results=count,
        exact=result.exact and count > 0, relaxed=" · ".join(c.label for c in result.relaxed)[:200], visitor=visitor)


def report(store, days=7, limit=30):
    since = timezone.now() - timedelta(days=days)
    logs = SearchLog.objects.for_store(store).filter(created_at__gte=since)
    groups = (logs.values("intent")
              .annotate(searches=Count("id"), people=Count("visitor", distinct=True), avg_results=Avg("results"),
                        missed=Count("id", filter=Q(exact=False)), last=Max("created_at"), sample=Max("raw"))
              .order_by("-people", "-searches"))
    return {
        "total": logs.count(),
        "people": logs.values("visitor").distinct().count(),
        "missed_total": logs.filter(exact=False).count(),
        "top": list(groups[:limit]),
        "unmet": list(groups.filter(missed__gt=0).order_by("-missed", "-people")[:limit]),
        "recent": list(logs.order_by("-created_at")[:30]),
    }


def prune(days=RETENTION_DAYS):
    return SearchLog.objects.filter(created_at__lt=timezone.now() - timedelta(days=days)).delete()[0]
