"""دستورهای مدیریتی و taskهای Celery (اجرای eager در تست)."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.blog.models import Post
from apps.catalog.models import Collection, Product, ProductVariant, StockMovement
from apps.discounts.models import Coupon
from apps.reviews.models import Review

pytestmark = pytest.mark.django_db


def run(*args):
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def test_seed_demo_builds_full_store(store):
    output = run("seed_demo")
    assert "12 محصول، 3 باکس هدیه و 6 مقاله" in output
    assert Product.objects.for_store(store).perfumes().count() == 12
    assert Product.objects.for_store(store).gift_boxes().filter(gift_capacity__gte=1).count() == 3
    assert Collection.objects.for_store(store).count() == 5
    assert Post.objects.for_store(store).published().count() == 6
    assert Coupon.objects.filter(code="MAJD10").exists()
    assert Review.objects.filter(is_approved=True).exists()
    # موجودی اولیه در دفتر انبار ثبت می‌شود
    assert StockMovement.objects.count() == ProductVariant.objects.count()
    # جستجو برای داده بذر هم کار می‌کند
    assert Product.objects.exclude(search_document="").count() == 15


def test_seed_demo_is_idempotent_and_reset_rebuilds(store):
    run("seed_demo")
    first_ids = set(Product.objects.values_list("pk", flat=True))
    run("seed_demo")
    assert set(Product.objects.values_list("pk", flat=True)) == first_ids  # تکرار، چیزی تکراری نمی‌سازد
    run("seed_demo", "--reset")
    assert Product.objects.count() == 15 and not first_ids & set(Product.objects.values_list("pk", flat=True))


def test_seed_demo_for_another_store(store, other_store):
    run("seed_demo", f"--store={other_store.code}")
    assert Product.objects.for_store(other_store).count() == 15
    assert Product.objects.for_store(store).count() == 0


def test_sync_themes_command_is_idempotent():
    from apps.themes.models import Theme, ThemePreset

    output = run("sync_themes")
    assert "luxury" in output
    count = ThemePreset.objects.count()
    run("sync_themes")
    assert Theme.objects.filter(code="luxury").count() == 1 and ThemePreset.objects.count() == count


def test_prune_audit_log_task(store):
    from datetime import timedelta

    from django.utils import timezone

    from apps.core.models import AuditLog
    from apps.core.tasks import prune_audit_log

    old = AuditLog.objects.create(action="x")
    AuditLog.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=400))
    assert prune_audit_log.delay().get() == 1


def test_reindex_tasks(store):
    from apps.catalog.tasks import reindex_products_task, reindex_store_task
    from apps.catalog.tests.factories import ProductFactory

    product = ProductFactory(name="عطر آزمایشی")
    Product.objects.filter(pk=product.pk).update(search_document="")
    reindex_products_task.delay([product.pk])
    assert Product.objects.get(pk=product.pk).search_document
    Product.objects.filter(pk=product.pk).update(search_document="")
    reindex_store_task.delay(store.pk)
    assert Product.objects.get(pk=product.pk).search_document
