"""ساخت صفحه از روی بخش‌ها (Homepage Builder)."""

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from . import sections
from .defaults import DEFAULT_HOME_SECTIONS
from .models import Page, PageSection

log = logging.getLogger(__name__)

SPACING_AFTER_HERO = "pt-14"
SPACING_DEFAULT = "pt-14 lg:pt-[var(--space-section)]"


@dataclass
class Block:
    section: PageSection
    template: str
    context: dict
    spacing: str


@transaction.atomic
def ensure_home_page(store):
    """صفحه اصلی فروشگاه را (در صورت نبود) با چیدمان پیش‌فرض می‌سازد."""
    page = Page.objects.filter(store=store, is_home=True).first()
    if page:
        return page
    page = Page.objects.create(store=store, title="صفحه اصلی", slug="home", is_home=True)
    PageSection.objects.bulk_create([
        PageSection(page=page, type=key, order=i * 10, settings=sections.get(key).clean_settings({}))
        for i, key in enumerate(DEFAULT_HOME_SECTIONS)
    ])
    return page


def build_blocks(page, request, status=PageSection.Status.PUBLISHED):
    """بخش‌های فعال صفحه ← فهرست Block آماده رندر.

    خطای یک بخش (مثلاً تنظیمات خراب یا داده ناموجود) فقط همان بخش را حذف می‌کند، نه کل صفحه را.
    """
    blocks, after_hero = [], True
    for section in page.sections.filter(status=status, is_enabled=True).order_by("order", "id"):
        section_type = section.section_type
        if section_type is None:
            log.warning("Unknown section type %r on page %s", section.type, page.pk)
            continue
        try:
            settings = section_type.clean_settings(section.settings)
            context = section_type.get_context(settings, request=request, section=section)
        except Exception:  # noqa: BLE001 — یک بخش خراب نباید کل صفحه را از کار بیندازد
            log.exception("Section %s (%s) failed to render", section.pk, section.type)
            continue
        if not section_type.is_visible(context):
            continue
        if section_type.full_bleed:
            spacing, after_hero = "", True
        else:
            spacing, after_hero = (SPACING_AFTER_HERO if after_hero else SPACING_DEFAULT), False
        blocks.append(Block(section, section_type.template, context, spacing))
    return blocks


# ---------- مدیریت بخش‌ها (سازنده صفحه) ----------
# استودیو بخش‌های «پیش‌نویس» را ویرایش می‌کند؛ با انتشار، پیش‌نویس جایگزین نسخه منتشرشده می‌شود.
# تصاویر بخش‌ها بین دو نسخه مشترک‌اند و حذف نمی‌شوند.

ORDER_STEP = 10
DRAFT, PUBLISHED = PageSection.Status.DRAFT, PageSection.Status.PUBLISHED


def page_sections(page, status=PUBLISHED):
    return page.sections.filter(status=status).order_by("order", "id")


def _clone_sections(page, source_status, target_status):
    page.sections.filter(status=target_status).delete()
    PageSection.objects.bulk_create([
        PageSection(page=page, type=s.type, status=target_status, order=s.order, is_enabled=s.is_enabled,
                    settings=dict(s.settings or {}), image=s.image.name)
        for s in page_sections(page, source_status)
    ])


@transaction.atomic
def ensure_draft(page):
    """پیش‌نویس صفحه را (در صورت نبود) از روی نسخه منتشرشده می‌سازد."""
    page = Page.objects.select_for_update().get(pk=page.pk)
    if not page.has_draft:
        _clone_sections(page, PUBLISHED, DRAFT)
        page.has_draft = True
        page.save(update_fields=["has_draft", "updated_at"])
    return page


@transaction.atomic
def publish_page(page):
    page = Page.objects.select_for_update().get(pk=page.pk)
    if page.has_draft:
        _clone_sections(page, DRAFT, PUBLISHED)
    return page


@transaction.atomic
def reset_page_draft(page):
    page = Page.objects.select_for_update().get(pk=page.pk)
    if page.has_draft:
        _clone_sections(page, PUBLISHED, DRAFT)
    return page


def rendered_status(page, request):
    """فروشگاه نسخه منتشرشده را نشان می‌دهد؛ در حالت پیش‌نمایش، پیش‌نویس را."""
    return DRAFT if getattr(request, "is_preview", False) and page.has_draft else PUBLISHED


@transaction.atomic
def reorder_sections(page, ids, status=DRAFT):
    """ترتیب جدید بر اساس فهرست شناسه‌ها؛ شناسه‌های ناشناخته نادیده و بخش‌های جاافتاده به انتها می‌روند."""
    sections = list(page_sections(page, status).select_for_update())
    by_id = {s.pk: s for s in sections}
    ordered = list(dict.fromkeys(pk for pk in ids if pk in by_id))
    ordered += [s.pk for s in sections if s.pk not in ordered]
    for index, pk in enumerate(ordered):
        by_id[pk].order = index * ORDER_STEP
    PageSection.objects.bulk_update(sections, ["order"])
    Page.objects.filter(pk=page.pk).update(updated_at=timezone.now())


def move_section(section, delta):
    """جابه‌جایی یک بخش به بالا (-۱) یا پایین (+۱)."""
    ids = list(page_sections(section.page, section.status).values_list("pk", flat=True))
    i = ids.index(section.pk)
    j = max(0, min(len(ids) - 1, i + delta))
    ids[i], ids[j] = ids[j], ids[i]
    reorder_sections(section.page, ids, section.status)


def add_section(page, type_key, status=DRAFT):
    section_type = sections.get(type_key)
    if section_type is None:
        raise ValueError(f"unknown section type {type_key!r}")
    last = page_sections(page, status).last()
    return PageSection.objects.create(
        page=page, type=type_key, status=status, order=(last.order + ORDER_STEP) if last else 0,
        settings=section_type.clean_settings({}),
    )


def toggle_section(section):
    section.is_enabled = not section.is_enabled
    section.save(update_fields=["is_enabled", "updated_at"])


def delete_section(section):
    section.delete()


def update_section(section, settings, *, image=None, clear_image=False):
    """settings باید از فرم همان نوع بخش اعتبارسنجی شده باشد؛ اینجا دوباره پاک‌سازی می‌شود."""
    section.settings = section.section_type.clean_settings(settings)
    if image:
        section.image = image
    elif clear_image:
        section.image = ""
    section.save()
