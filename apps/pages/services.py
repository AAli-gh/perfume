"""ساخت صفحه از روی بخش‌ها (Homepage Builder)."""

import logging
from dataclasses import dataclass

from django.db import transaction

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
