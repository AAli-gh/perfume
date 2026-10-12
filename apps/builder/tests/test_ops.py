"""پیشخوان عملیات، فهرست سفارش‌ها، چاپ گروهی، رهگیری گروهی و موجودی."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.builder.ops_views import parse_tracking_lines
from apps.catalog.models import ProductVariant, StockMovement
from apps.catalog.tests.factories import VariantFactory
from apps.notifications.sms import console
from apps.orders.models import Order, OrderItem

pytestmark = pytest.mark.django_db
User = get_user_model()
S, P = Order.Status, Order.PaymentMethod


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())
    console.outbox.clear()


def make_order(store, *, status=S.PENDING, method=P.COD, total=1_000_000, **extra):
    order = Order.objects.create(store=store, first_name="سارا", last_name="محمدی", phone="09121112233",
                                 province="تهران", city="تهران", address="خیابان ولیعصر", postal_code="1234567890",
                                 subtotal=total, total=total, status=status, payment_method=method, **extra)
    OrderItem.objects.create(order=order, product_name="عود رازآلود", size_ml=50, unit_price=total, quantity=1)
    return order


@pytest.fixture
def staff(client):
    user = User.objects.create_user(email="ops@example.com", password="x-Strong-123", is_staff=True)
    for codename in ("view_order", "change_order", "change_product"):
        user.user_permissions.add(Permission.objects.get(codename=codename))
    client.force_login(user)
    return user


def test_dashboard_shows_todays_work(client, store, staff):
    make_order(store, method=P.CARD)                       # کارت به کارت منتظر تأیید
    make_order(store, status=S.PAID, method=P.ONLINE, paid_at="2026-01-01T00:00Z")  # آماده‌سازی
    make_order(store)                                       # پرداخت در محل ← آماده‌سازی
    make_order(store, status=S.PROCESSING)                  # ارسال
    make_order(store, method=P.ONLINE)                      # آنلاینِ پرداخت‌نشده: کاری نیست
    VariantFactory(stock=1)                                 # رو به اتمام (آستانه پیش‌فرض ۳)
    VariantFactory(stock=50)
    body = client.get(reverse("builder:dashboard")).content.decode()
    assert "کارت به کارت منتظر تأیید" in body and "رو به اتمام: ۱" in body
    ctx = client.get(reverse("builder:dashboard")).context["ops"]
    assert (ctx["awaiting_card"], ctx["to_prepare"], ctx["to_ship"]) == (1, 2, 1)
    assert len(ctx["orders"]) == 4 and ctx["low_stock_count"] == 1


def test_dashboard_hides_ops_without_order_permission(client, store):
    user = User.objects.create_user(email="designer@example.com", password="x-Strong-123", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="change_themesettings"))
    client.force_login(user)
    assert client.get(reverse("builder:dashboard")).context["ops"] is None


def test_orders_list_tabs_and_search(client, store, staff):
    a = make_order(store, method=P.CARD)
    make_order(store, status=S.PROCESSING)
    page = client.get(reverse("builder:orders"), {"q": "card"}).context["page"]
    assert [o.pk for o in page] == [a.pk]
    assert [o.pk for o in client.get(reverse("builder:orders"), {"q": "all", "s": a.number}).context["page"]] == [a.pk]


def test_print_invoice_hides_prices_when_requested_and_packing_has_gift_card(client, store, staff):
    plain = make_order(store, total=2_500_000)
    gift = make_order(store, total=3_700_000, hide_prices=True, packaging=Order.Packaging.IN_BOX,
                      gift_message="تولدت مبارک", gift_from="مریم")
    invoice = client.get(reverse("builder:print_orders"), {"doc": "invoice", "ids": [plain.pk, gift.pk]})
    body = invoice.content.decode()
    assert body.count('class="page invoice"') == 2 and "فاکتور فروش" in body
    assert "۲٬۵۰۰٬۰۰۰" in body and "۳٬۷۰۰٬۰۰۰" not in body and "قیمت‌ها در این فاکتور چاپ نشده" in body
    packing = client.get(reverse("builder:print_orders"), {"doc": "packing", "ids": [gift.pk]}).content.decode()
    assert "تولدت مبارک" in packing and "از طرف مریم" in packing and "فاکتور قیمت داخل بسته قرار نگیرد" in packing
    labels = client.get(reverse("builder:print_orders"), {"doc": "labels", "ids": [plain.pk, gift.pk]}).content.decode()
    assert labels.count('class="label"') == 2 and "۱۲۳۴۵۶۷۸۹۰" in labels


def test_print_only_own_store_orders(client, store, other_store, staff):
    foreign = make_order(other_store)
    response = client.get(reverse("builder:print_orders"), {"doc": "invoice", "ids": [foreign.pk]})
    assert response.status_code == 302  # «هیچ سفارشی انتخاب نشده»


def test_print_requires_permission(client, store):
    user = User.objects.create_user(email="x@example.com", password="x-Strong-123", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="change_themesettings"))
    client.force_login(user)
    assert client.get(reverse("builder:print_orders"), {"doc": "invoice"}).status_code == 403


def test_parse_tracking_lines():
    pairs, bad = parse_tracking_lines("MJ2610A1B2C3  123456789012\nmj2610d4e5f6, ۹۸۷۶۵۴۳۲\nسلام\n\n")
    assert pairs == {"MJ2610A1B2C3": "123456789012", "MJ2610D4E5F6": "98765432"}
    assert bad == ["سلام"]


def test_bulk_tracking_marks_shipped_and_sends_sms(client, store, staff):
    a = make_order(store, status=S.PROCESSING)
    b = make_order(store, status=S.PAID, method=P.ONLINE, paid_at="2026-01-01T00:00Z")
    response = client.post(reverse("builder:tracking"), {
        f"code-{a.pk}": "TRK-111", "bulk": f"{b.number} 222333444\nMJBAD 1234", "ship": "on"})
    assert response.status_code == 302
    a.refresh_from_db()
    b.refresh_from_db()
    assert (a.tracking_code, a.status) == ("TRK-111", S.SHIPPED)
    assert (b.tracking_code, b.status) == ("222333444", S.SHIPPED)  # پرداخت‌شده ← آماده‌سازی ← ارسال
    assert any("TRK-111" in m["text"] for m in console.outbox)


def test_bulk_status_change(client, store, staff):
    card = make_order(store, method=P.CARD)
    shipped = make_order(store, status=S.SHIPPED)
    client.post(reverse("builder:orders_status"), {"ids": [card.pk, shipped.pk], "to": "paid"})
    card.refresh_from_db()
    shipped.refresh_from_db()
    assert card.status == S.PAID and card.paid_at and shipped.status == S.SHIPPED


def test_stock_page_restock_and_threshold(client, store, staff):
    variant = VariantFactory(stock=0)
    page = client.get(reverse("builder:stock"))
    assert variant in list(page.context["page"])
    client.post(reverse("builder:stock"), {"variant": variant.pk, "add": "12", "threshold": "5"})
    variant.refresh_from_db()
    assert (variant.stock, variant.low_stock_threshold) == (12, 5)
    movement = variant.movements.latest("pk")
    assert movement.reason == StockMovement.Reason.RESTOCK and movement.change == 12
    assert variant not in list(client.get(reverse("builder:stock")).context["page"])


def test_stock_page_requires_product_permission(client, store):
    user = User.objects.create_user(email="o@example.com", password="x-Strong-123", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="view_order"))
    client.force_login(user)
    assert client.get(reverse("builder:stock")).status_code == 403
    assert ProductVariant.objects.count() == 0


def test_section_list_explains_why_section_is_hidden(client, store, staff):
    from apps.pages import services as page_services

    staff.user_permissions.add(Permission.objects.get(codename="change_pagesection"),
                               Permission.objects.get(codename="add_pagesection"))
    page = page_services.ensure_home_page(store)
    client.post(reverse("builder:section_add", args=[page.pk]), {"type": "faq"})
    body = client.get(reverse("builder:page", args=[page.pk])).content.decode()
    assert "فعلاً در سایت دیده نمی‌شود" in body and "پرسش" in body
