"""هشدار موجودی کم به مدیران و «موجود شد خبرم کن» به مشتریان."""

import pytest
from django.urls import reverse

from apps.catalog import inventory
from apps.catalog.models import BackInStockRequest
from apps.catalog.tests.factories import VariantFactory
from apps.notifications.models import NotificationLog
from apps.notifications.services import settings_for
from apps.notifications.sms import console

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())
    console.outbox.clear()


@pytest.fixture
def staff_phone(store):
    conf = settings_for(store)
    conf.staff_phones = "09130000000"
    conf.save()
    return "09130000000"


def texts_to(phone):
    return [m["text"] for m in console.outbox if m["to"] == phone]


def test_low_stock_alert_once_per_crossing(store, staff_phone):
    variant = VariantFactory(stock=5, product__name="عود رازآلود")
    inventory.reserve([inventory.StockLine(variant.pk, 1)], "MJ1")   # ۵ ← ۴: هنوز بالای آستانه ۳
    assert texts_to(staff_phone) == []
    inventory.reserve([inventory.StockLine(variant.pk, 2)], "MJ2")   # ۴ ← ۲: عبور از آستانه
    assert len(texts_to(staff_phone)) == 1 and "عود رازآلود" in texts_to(staff_phone)[0] and "2" in texts_to(staff_phone)[0]
    inventory.reserve([inventory.StockLine(variant.pk, 1)], "MJ3")   # ۲ ← ۱: دوباره نه
    assert len(texts_to(staff_phone)) == 1
    inventory.set_stock(variant, 10)
    inventory.set_stock(variant, 3)                                  # عبور دوباره
    assert len(texts_to(staff_phone)) == 2


def test_variant_threshold_overrides_store_default(store, staff_phone):
    variant = VariantFactory(stock=12, low_stock_threshold=10)
    inventory.set_stock(variant, 9)
    assert len(texts_to(staff_phone)) == 1


def test_notify_me_form_and_sms_when_back_in_stock(client, store):
    variant = VariantFactory(stock=0, product__name="کسوف سیاه")
    product = variant.product
    page = client.get(product.get_absolute_url())
    assert page.context["notify_form"] is not None and "خبرم کن" in page.content.decode()
    url = reverse("catalog:notify_me", args=[product.slug])
    response = client.post(url, {"variant": variant.pk, "phone": "۰۹۱۲۳۴۵۶۷۸۹"}, HTTP_HX_REQUEST="true")
    assert "ثبت شد" in response.content.decode()
    client.post(url, {"variant": variant.pk, "phone": "09123456789"})  # تکراری
    assert BackInStockRequest.objects.count() == 1
    bad = client.post(url, {"variant": variant.pk, "phone": "123"})
    assert "۱۱ رقم" in bad.content.decode()

    inventory.set_stock(variant, 4)
    assert any("کسوف سیاه" in t and product.get_absolute_url() in t for t in texts_to("09123456789"))
    request = BackInStockRequest.objects.get()
    assert request.notified_at is not None
    assert NotificationLog.objects.filter(event="back_in_stock", status=NotificationLog.SENT).count() == 1
    # موجود بودن دوباره پیامک تکراری نمی‌فرستد؛ درخواست جدید پس از اطلاع‌رسانی مجاز است
    inventory.set_stock(variant, 0)
    inventory.set_stock(variant, 2)
    assert len(texts_to("09123456789")) == 1


def test_no_notify_form_when_everything_in_stock(client, store):
    variant = VariantFactory(stock=3)
    assert client.get(variant.product.get_absolute_url()).context["notify_form"] is None
