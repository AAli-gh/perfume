"""بازگردانی از snapshotهای قدیمی یا خراب نباید پیش‌نویس را خراب کند."""

import pytest

from apps.builder import services as builder
from apps.builder.models import Revision
from apps.pages.models import Page, PageSection
from apps.pages.services import page_sections
from apps.themes.services import draft_settings

pytestmark = pytest.mark.django_db


def test_restore_skips_invalid_parts(store):
    home = Page.objects.get(store=store, is_home=True)
    revision = Revision.objects.create(store=store, number=1, snapshot={
        "theme": {
            "theme": "deleted-theme", "preset": "nope",
            "overrides": {"colors": {"primary": "red;}"}},  # نامعتبر
            "header": {"menu": [{"label": "x", "url": "javascript:alert(1)"}]},  # نامعتبر
            "footer": {"hours": "۹ تا ۲۱"}, "logo": "", "favicon": "",
        },
        "pages": {
            "home": {"sections": [
                {"type": "hero", "enabled": True, "settings": {}, "image": ""},
                {"type": "removed-type", "settings": {}},  # نوع حذف‌شده
                {"type": "best_sellers", "settings": {"limit": 9999}},  # تنظیمات نامعتبر
                {"type": "newsletter", "enabled": False, "settings": {"title": "خبرنامه"}},
            ]},
            "no-such-page": {"sections": []},
        },
    })
    builder.restore(store, revision)
    draft = draft_settings(store)
    assert draft.theme.code == "luxury" and draft.preset is None
    assert draft.overrides == {} and draft.header == {} and draft.footer == {"hours": "۹ تا ۲۱"}
    rows = list(page_sections(Page.objects.get(pk=home.pk), PageSection.Status.DRAFT).values_list("type", "is_enabled"))
    assert rows == [("hero", True), ("newsletter", False)]


def test_restore_rejects_foreign_revision(store, other_store):
    revision = Revision.objects.create(store=other_store, number=1, snapshot={})
    with pytest.raises(ValueError):
        builder.restore(store, revision)


def test_restore_with_empty_snapshot_keeps_draft(store):
    draft = draft_settings(store)
    draft.overrides = {"colors": {"primary": "#123456"}}
    draft.save()
    builder.restore(store, Revision.objects.create(store=store, number=1, snapshot={}))
    assert draft_settings(store).overrides == {"colors": {"primary": "#123456"}}
