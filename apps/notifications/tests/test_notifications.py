from unittest import mock

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.catalog.tests.factories import VariantFactory
from apps.notifications import events as E
from apps.notifications.models import NotificationLog, NotificationRule
from apps.notifications.services import notify_order, settings_for
from apps.notifications.sms import SMSError, console
from apps.notifications.sms.kavenegar import KavenegarProvider
from apps.notifications.sms.smsir import SmsIrProvider
from apps.orders.models import Order
from apps.orders.workflow import transition
from apps.shipping.models import ShippingMethod

pytestmark = pytest.mark.django_db

CHECKOUT = {
    "first_name": "علی", "last_name": "رضایی", "phone": "09121234567", "email": "ali@example.com",
    "province": "تهران", "city": "تهران", "address": "خیابان آزادی", "postal_code": "1234567890", "note": "",
    "payment_method": "cod", "accept_terms": "on",
}


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    """سیگنال‌های سفارش پس از commit ارسال می‌شوند؛ در تست (تراکنش rollback‌شونده) همان لحظه اجرا شوند."""
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())


@pytest.fixture(autouse=True)
def _outbox():
    console.outbox.clear()
    yield
    console.outbox.clear()


@pytest.fixture
def place_order(client, store):
    def place(**overrides):
        variant = VariantFactory(price=1_000_000, stock=10)
        client.post(reverse("cart:add"), {"variant": variant.pk, "quantity": 1})
        response = client.post(reverse("orders:checkout"), {**CHECKOUT, **overrides})
        assert response.status_code == 302, response.content[:300]
        return Order.objects.latest("pk")
    return place


def test_order_placed_sends_customer_sms_and_email_and_staff_alerts(place_order, store):
    conf = settings_for(store)
    conf.staff_phones, conf.staff_emails = "09130000000", "boss@example.com"
    conf.save()
    order = place_order()
    texts = {m["to"]: m["text"] for m in console.outbox}
    assert order.number in texts["09121234567"] and "علی عزیز" in texts["09121234567"]
    assert "سفارش جدید" in texts["09130000000"]
    assert sorted(m.to[0] for m in mail.outbox) == ["ali@example.com", "boss@example.com"]
    customer_mail = next(m for m in mail.outbox if m.to == ["ali@example.com"])
    assert order.number in customer_mail.subject and customer_mail.alternatives[0][1] == "text/html"
    assert NotificationLog.objects.filter(order=order, status=NotificationLog.SENT).count() == 4


def test_shipped_sms_includes_tracking_code_and_url(place_order, store):
    method = ShippingMethod.objects.create(store=store, name="تیپاکس", cost=0,
                                           tracking_url_template="https://track.example/{code}")
    order = place_order(shipping_method=method.pk)
    console.outbox.clear()
    order.tracking_code = "TPX-9"
    order.save()
    transition(order, Order.Status.PROCESSING)  # پیامک آماده‌سازی به‌طور پیش‌فرض خاموش است
    assert console.outbox == []
    transition(order, Order.Status.SHIPPED)
    text = console.outbox[-1]["text"]
    assert "تیپاکس" in text and "TPX-9" in text and "https://track.example/TPX-9" in text


def test_notifications_are_idempotent(place_order):
    order = place_order()
    count = len(console.outbox)
    notify_order(order, E.ORDER_PLACED)  # اجرای دوباره task (acks_late)
    assert len(console.outbox) == count
    assert NotificationLog.objects.filter(order=order, event=E.ORDER_PLACED, channel=E.SMS).count() == 1


def test_disabled_channel_and_rule_are_skipped(place_order, store):
    conf = settings_for(store)
    conf.sms_enabled = False
    conf.save()
    assert NotificationRule.objects.filter(store=store).count() == len(E.DEFAULT_RULES)  # قبل از اولین سفارش
    NotificationRule.objects.filter(store=store, event=E.ORDER_PLACED, channel=E.EMAIL).update(is_active=False)
    order = place_order()
    assert console.outbox == [] and mail.outbox == []
    assert NotificationLog.objects.get(order=order, channel=E.SMS).status == NotificationLog.SKIPPED


def test_provider_failure_is_logged_and_retried_without_breaking_checkout(place_order):
    with mock.patch.object(console.ConsoleProvider, "send", side_effect=SMSError("اعتبار کافی نیست")):
        order = place_order()
    entry = NotificationLog.objects.get(order=order, channel=E.SMS, recipient="09121234567")
    assert entry.status == NotificationLog.FAILED and "اعتبار" in entry.error
    notify_order(order, E.ORDER_PLACED)  # تلاش دوباره موفق
    entry.refresh_from_db()
    assert entry.status == NotificationLog.SENT and entry.attempts == 2


def test_pattern_rule_sends_template_with_ordered_params(place_order, store):
    place_order()  # ساخت پیام‌های پیش‌فرض
    NotificationRule.objects.filter(store=store, event=E.ORDER_PLACED, channel=E.SMS, audience=E.CUSTOMER).update(
        sms_template="order-placed", template_params="number,total")
    console.outbox.clear()
    order = place_order()
    sent = next(m for m in console.outbox if m.get("template"))
    assert sent["template"] == "order-placed" and list(sent["params"]) == ["number", "total"]
    assert sent["params"]["number"] == order.number


def test_rule_validation_rejects_unknown_placeholders(store):
    rule = NotificationRule(store=store, event=E.ORDER_SHIPPED, channel=E.SMS, text="سلام {password}",
                            sms_template="x", template_params="number,secret")
    with pytest.raises(ValidationError) as exc:
        rule.full_clean()
    assert {"text", "template_params"} <= set(exc.value.message_dict)
    with pytest.raises(ValidationError):
        E.validate_text(E.ORDER_PAID, "{number")
    assert E.render_text("{number} {unknown_ok}", {"number": "MJ1"}) == "MJ1"


def test_store_without_sms_provider_logs_failure(place_order, settings):
    settings.SMS_PROVIDER = ""
    order = place_order()
    entry = NotificationLog.objects.get(order=order, channel=E.SMS, recipient="09121234567")
    assert entry.status == NotificationLog.FAILED and "SMS_PROVIDER" in entry.error


# ---------- آداپتورهای سرویس پیامک (بدون شبکه) ----------

def _response(payload):
    response = mock.Mock()
    response.json.return_value = payload
    return response


def test_kavenegar_send_and_lookup_requests():
    provider = KavenegarProvider(api_key="KEY", sender="10004346")
    ok = {"return": {"status": 200}, "entries": [{"messageid": 77}]}
    with mock.patch("requests.get", return_value=_response(ok)) as get:
        assert provider.send("09121234567", "سلام").message_id == "77"
        url, kwargs = get.call_args[0][0], get.call_args[1]
        assert url == "https://api.kavenegar.com/v1/KEY/sms/send.json"
        assert kwargs["params"] == {"receptor": "09121234567", "sender": "10004346", "message": "سلام"}
        provider.send_template("09121234567", "verify", {"code": "123456", "store": "عطر مجد"})
        params = get.call_args[1]["params"]
        assert get.call_args[0][0].endswith("/verify/lookup.json")
        assert params["template"] == "verify" and params["token"] == "123456" and " " not in params["token2"]
    with mock.patch("requests.get", return_value=_response({"return": {"status": 418, "message": "bad key"}})):
        with pytest.raises(SMSError, match="bad key"):
            provider.send("09121234567", "x")
    with pytest.raises(SMSError):
        KavenegarProvider(api_key="").send("09121234567", "x")


def test_smsir_bulk_and_verify_requests():
    provider = SmsIrProvider(api_key="KEY", sender="30007732")
    with mock.patch("requests.post", return_value=_response({"status": 1, "data": {"messageIds": [5]}})) as post:
        assert provider.send("09121234567", "سلام").message_id == "5"
        assert post.call_args[0][0] == "https://api.sms.ir/v1/send/bulk"
        assert post.call_args[1]["json"] == {"lineNumber": 30007732, "messageText": "سلام", "mobiles": ["09121234567"]}
        assert post.call_args[1]["headers"]["X-API-KEY"] == "KEY"
        provider.send_template("09121234567", "100", {"code": "123456"})
        assert post.call_args[1]["json"] == {"mobile": "09121234567", "templateId": 100,
                                              "parameters": [{"name": "CODE", "value": "123456"}]}
    with mock.patch("requests.post", return_value=_response({"status": 0, "message": "اعتبار کافی نیست"})):
        with pytest.raises(SMSError, match="اعتبار"):
            provider.send("09121234567", "x")
    with pytest.raises(SMSError):
        SmsIrProvider(api_key="KEY", sender="abc").send("09121234567", "x")


def test_unknown_provider_is_reported(settings):
    from apps.notifications.sms import get_provider

    settings.SMS_PROVIDER = "nope"
    with pytest.raises(LookupError, match="kavenegar"):
        get_provider()


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_signals_fire_only_after_commit(store, monkeypatch):
    """بدون جایگزینی on_commit: سفارش rollback‌شده پیامکی ندارد، سفارش commit‌شده دارد."""
    from django.db import transaction

    from apps.orders.signals import order_placed

    monkeypatch.undo()  # on_commit واقعی
    order = Order.objects.create(store=store, first_name="a", last_name="b", phone="09121234567", province="تهران",
                                 city="تهران", address="x", postal_code="1234567890", total=1)
    with pytest.raises(RuntimeError), transaction.atomic():
        transaction.on_commit(lambda: order_placed.send(sender=Order, order=order))
        raise RuntimeError
    assert console.outbox == []
    with transaction.atomic():
        transaction.on_commit(lambda: order_placed.send(sender=Order, order=order))
        assert console.outbox == []
    assert any(m["to"] == "09121234567" for m in console.outbox)
