"""پیش‌نویس، انتشار، بازگشت به نسخه قبلی و لینک پیش‌نمایش.

جریان کار:
    ویرایش در استودیو  →  پیش‌نویس (ThemeSettings[draft] + PageSection[draft])
    پیش‌نمایش         →  فروشگاه با پیش‌نویس (فقط برای کارکنان یا دارنده لینک امضاشده)
    انتشار            →  پیش‌نویس روی نسخه منتشرشده کپی و یک Revision ثبت می‌شود
    بازگشت            →  محتوای یک Revision در پیش‌نویس بارگذاری می‌شود (بعد از پیش‌نمایش، انتشار)
"""

import logging
import uuid

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from apps.pages import sections
from apps.pages import services as page_services
from apps.pages.models import Page, PageSection
from apps.themes import chrome
from apps.themes import services as theme_services
from apps.themes import tokens as T
from apps.themes.models import Theme, ThemePreset, ThemeSettings

from .models import Revision, Workspace

log = logging.getLogger(__name__)

KEEP_REVISIONS = 50
PREVIEW_SALT = "majd.builder.preview"
PREVIEW_LINK_HOURS = 72


class NothingToPublish(Exception):
    pass


# ---------- پیش‌نویس ----------

def workspace(store):
    ws, _ = Workspace.objects.get_or_create(store=store)
    return ws


def touch(store, user=None):
    """ثبت آخرین ویرایشگر پیش‌نویس (پس از هر تغییر در استودیو)."""
    ws = workspace(store)
    ws.updated_by = user if user is not None and user.is_authenticated else None
    ws.save(update_fields=["updated_by", "updated_at"])
    return ws


def editable_page(page):
    """صفحه‌ای که ویرایش می‌شود همیشه پیش‌نویس دارد."""
    return page_services.ensure_draft(page)


# ---------- Snapshot ----------

def _theme_snapshot(ts):
    if ts is None:
        return {}
    return {
        "theme": ts.theme.code,
        "preset": ts.preset.code if ts.preset_id else None,
        "overrides": ts.overrides or {},
        "header": ts.header or {},
        "footer": ts.footer or {},
        "logo": ts.logo.name or "",
        "favicon": ts.favicon.name or "",
    }


def _page_snapshot(page, status):
    return {
        "title": page.title,
        "sections": [
            {"type": s.type, "enabled": s.is_enabled, "settings": s.settings or {}, "image": s.image.name or ""}
            for s in page_services.page_sections(page, status)
        ],
    }


def snapshot(store, *, draft):
    """عکس کامل ظاهر و صفحه‌ها؛ draft=True ← آنچه پس از انتشار دیده خواهد شد."""
    ts = theme_services.draft_settings(store, create=False) if draft else None
    ts = ts or theme_services.ensure_store_theme(store)
    pages = {}
    for page in Page.objects.for_store(store).order_by("pk"):
        status = PageSection.Status.DRAFT if draft and page.has_draft else PageSection.Status.PUBLISHED
        pages[page.slug] = _page_snapshot(page, status)
    return {"version": 1, "theme": _theme_snapshot(ts), "pages": pages}


TOKEN_AREAS = [
    ("colors", "رنگ‌ها"),
    ("typography,radius,spacing", "فونت، اندازه و فاصله"),
    ("components", "سبک اجزا"),
]
BRANDING_HEADER_KEYS = {"logo_height", "monogram"}


def diff(before, after):
    """فهرست بخش‌هایی که بین دو snapshot فرق دارند (برای نمایش به مدیر)."""
    a, b = before.get("theme", {}), after.get("theme", {})
    out = []
    if (a.get("theme"), a.get("preset")) != (b.get("theme"), b.get("preset")):
        out.append("پوسته و پیش‌تنظیم")
    for groups, label in TOKEN_AREAS:
        keys = groups.split(",")
        if any((a.get("overrides") or {}).get(k) != (b.get("overrides") or {}).get(k) for k in keys):
            out.append(label)
    ha, hb = a.get("header") or {}, b.get("header") or {}
    branding = (a.get("logo"), a.get("favicon")) != (b.get("logo"), b.get("favicon"))
    if branding or any(ha.get(k) != hb.get(k) for k in BRANDING_HEADER_KEYS):
        out.append("لوگو و فاوآیکون")
    if {k: v for k, v in ha.items() if k not in BRANDING_HEADER_KEYS} != {
        k: v for k, v in hb.items() if k not in BRANDING_HEADER_KEYS
    }:
        out.append("هدر و منو")
    if (a.get("footer") or {}) != (b.get("footer") or {}):
        out.append("فوتر")
    pa, pb = before.get("pages", {}), after.get("pages", {})
    for slug in sorted(set(pa) | set(pb)):
        if pa.get(slug, {}).get("sections") != pb.get(slug, {}).get("sections"):
            title = (pb.get(slug) or pa.get(slug) or {}).get("title", slug)
            out.append(f"صفحه «{title}»")
    return out


def pending_changes(store):
    """بخش‌هایی که در پیش‌نویس تغییر کرده‌اند و هنوز منتشر نشده‌اند."""
    return diff(snapshot(store, draft=False), snapshot(store, draft=True))


# ---------- انتشار / کنار گذاشتن ----------

def _rotate_key(ws):
    ws.preview_key = uuid.uuid4()
    ws.save(update_fields=["preview_key", "updated_at"])


def _next_number(store):
    return (Revision.objects.filter(store=store).aggregate(n=Max("number"))["n"] or 0) + 1


@transaction.atomic
def publish(store, user=None, label=""):
    ws = Workspace.objects.select_for_update().get(pk=workspace(store).pk)  # انتشارهای هم‌زمان پشت سر هم
    before, after = snapshot(store, draft=False), snapshot(store, draft=True)
    changes = diff(before, after)
    if not changes:
        raise NothingToPublish
    by = user if user is not None and user.is_authenticated else None
    if not Revision.objects.filter(store=store).exists():
        Revision.objects.create(store=store, number=1, kind=Revision.Kind.BASELINE,
                                label="پیش از اولین انتشار", snapshot=before)
    theme_services.publish_draft(store)
    for page in Page.objects.for_store(store).filter(has_draft=True):
        page_services.publish_page(page)
    revision = Revision.objects.create(store=store, number=_next_number(store), label=label[:120],
                                       snapshot=after, changes=changes, created_by=by)
    stale = Revision.objects.filter(store=store).order_by("-number")[KEEP_REVISIONS:]
    Revision.objects.filter(pk__in=[r.pk for r in stale]).delete()
    _rotate_key(ws)
    return revision


@transaction.atomic
def discard(store):
    ws = Workspace.objects.select_for_update().get(pk=workspace(store).pk)
    theme_services.reset_draft(store)
    for page in Page.objects.for_store(store).filter(has_draft=True):
        page_services.reset_page_draft(page)
    _rotate_key(ws)


# ---------- بازگشت به نسخه قبلی ----------

def _restore_theme(store, data):
    draft = theme_services.draft_settings(store)
    if draft is None or not data:
        return
    theme = Theme.objects.filter(code=data.get("theme"), is_available=True).first() or draft.theme
    preset = ThemePreset.objects.filter(theme=theme, code=data.get("preset")).first() if data.get("preset") else None
    draft.theme, draft.preset = theme, preset
    try:
        draft.overrides = T.validate(data.get("overrides") or {}, partial=True)
    except ValidationError:
        draft.overrides = {}
    for part in ("header", "footer"):
        value = data.get(part) or {}
        try:
            chrome.clean(part, value)
        except ValidationError:
            value = {}
        setattr(draft, part, value)
    draft.logo, draft.favicon = data.get("logo") or "", data.get("favicon") or ""
    draft.save()


def _restore_page(page, data):
    page = page_services.ensure_draft(page)
    page.sections.filter(status=PageSection.Status.DRAFT).delete()
    rows = []
    for index, item in enumerate(data.get("sections", [])):
        section_type = sections.get(item.get("type"))
        if section_type is None:
            continue
        try:
            settings = section_type.clean_settings(item.get("settings") or {})
        except ValidationError:
            log.warning("Skipping invalid section %r while restoring", item.get("type"))
            continue
        rows.append(PageSection(page=page, type=item["type"], status=PageSection.Status.DRAFT,
                                order=index * page_services.ORDER_STEP, is_enabled=bool(item.get("enabled", True)),
                                settings=settings, image=item.get("image") or ""))
    PageSection.objects.bulk_create(rows)


@transaction.atomic
def restore(store, revision, user=None):
    """محتوای یک نسخه در پیش‌نویس بارگذاری می‌شود؛ فروشگاه تا انتشار بعدی تغییری نمی‌کند."""
    if revision.store_id != store.pk:
        raise ValueError("revision belongs to another store")
    data = revision.snapshot or {}
    _restore_theme(store, data.get("theme"))
    pages = {p.slug: p for p in Page.objects.for_store(store)}
    for slug, page_data in (data.get("pages") or {}).items():
        if slug in pages:
            _restore_page(pages[slug], page_data)
    touch(store, user)


# ---------- لینک پیش‌نمایش ----------

def preview_link_token(store):
    return signing.dumps({"s": store.pk, "k": workspace(store).preview_key.hex}, salt=PREVIEW_SALT, compress=True)


def check_preview_token(token, store):
    """True اگر لینک امضاشده، تاریخ‌نگذشته، برای همین فروشگاه و مربوط به پیش‌نویس فعلی باشد."""
    try:
        data = signing.loads(token, salt=PREVIEW_SALT, max_age=PREVIEW_LINK_HOURS * 3600)
    except signing.BadSignature:
        return False
    if not isinstance(data, dict) or data.get("s") != getattr(store, "pk", None):
        return False
    key = Workspace.objects.filter(store=store).values_list("preview_key", flat=True).first()
    return key is not None and data.get("k") == key.hex


def theme_draft_exists(store):
    return ThemeSettings.objects.filter(store=store, status=ThemeSettings.Status.DRAFT).exists()
