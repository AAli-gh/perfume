"""Fixtureهای مشترک pytest."""

import pytest


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture(autouse=True)
def _clear_cache():
    """cache (sitemap، توکن‌های پوسته، …) بین تست‌ها مشترک نماند."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def store(db):
    """فروشگاه پیش‌فرض (توسط migration ساخته می‌شود)."""
    from apps.core.stores import get_default_store

    return get_default_store()


@pytest.fixture
def other_store(db):
    """یک فروشگاه دوم برای تست جداسازی داده‌ها (Multi-Tenant)."""
    from apps.core.models import Store, StoreDomain, StoreSettings

    s = Store.objects.create(name="فروشگاه دوم", code="second")
    StoreSettings.objects.create(store=s, shipping_cost=50_000)
    StoreDomain.objects.create(store=s, domain="second.test")
    return s
