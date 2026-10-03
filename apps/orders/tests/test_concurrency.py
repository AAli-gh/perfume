"""هم‌زمانی واقعی (چند thread با اتصال جدا به PostgreSQL): موجودی هرگز منفی یا بیش‌فروش نمی‌شود.

دو لایه محافظت دارد: قفل ردیف (select_for_update) در سرویس انبار، و قید CHECK (stock >= 0) در دیتابیس.
بدون قفل هم بیش‌فروش رخ نمی‌دهد، اما خریدار بازنده به‌جای پیام «ناموجود» خطای ۵۰۰ می‌گیرد؛ این تست هر دو را
بررسی می‌کند.
"""

import threading

import pytest
from django.db import connection
from django.test import Client
from django.urls import reverse

from apps.catalog.inventory import record_initial
from apps.catalog.models import ProductVariant
from apps.catalog.tests.factories import VariantFactory
from apps.orders.models import Order

from .test_workflow_inventory import CHECKOUT, ledger

pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)


def race(clients, action):
    """همه clientها هم‌زمان action را اجرا می‌کنند؛ خروجی: کد وضعیت پاسخ‌ها (یا نام استثنا)."""
    barrier = threading.Barrier(len(clients))
    results = []

    def run(client):
        barrier.wait()
        try:
            results.append(action(client).status_code)
        except Exception as exc:  # noqa: BLE001 — خطای سرور هم نتیجه است
            results.append(type(exc).__name__)
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(c,)) for c in clients]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return results


@pytest.mark.parametrize("buyers", [2, 5])
def test_last_unit_sold_once(store, buyers):
    variant = VariantFactory(stock=1)
    record_initial(variant)
    clients = [Client() for _ in range(buyers)]
    for c in clients:
        c.post(reverse("cart:add"), {"variant": variant.pk})
    results = race(clients, lambda c: c.post(reverse("orders:checkout"), CHECKOUT))
    variant.refresh_from_db()
    assert all(code in (200, 302) for code in results), results  # بازنده‌ها پیام «ناموجود» می‌گیرند، نه خطا
    assert Order.objects.count() == 1
    assert variant.stock == 0 == ledger(variant)


def test_parallel_orders_reserve_exact_stock(store):
    variant = VariantFactory(stock=6)
    record_initial(variant)
    clients = [Client() for _ in range(4)]
    for c in clients:
        c.post(reverse("cart:add"), {"variant": variant.pk, "quantity": 2})
    results = race(clients, lambda c: c.post(reverse("orders:checkout"), CHECKOUT))
    assert all(code in (200, 302) for code in results), results
    assert Order.objects.count() == 3  # ۳ × ۲ = ۶؛ چهارمی موجودی کافی ندارد
    assert ProductVariant.objects.get(pk=variant.pk).stock == 0 == ledger(variant)
