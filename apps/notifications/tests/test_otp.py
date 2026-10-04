import re

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.core.models import AuditLog
from apps.notifications import otp
from apps.notifications.services import settings_for
from apps.notifications.sms import console

pytestmark = pytest.mark.django_db
User = get_user_model()
PHONE = "09121234567"


@pytest.fixture(autouse=True)
def enabled(store):
    console.outbox.clear()
    conf = settings_for(store)
    conf.otp_login_enabled = True
    conf.save()
    return conf


def _request_code(client, phone=PHONE, **extra):
    response = client.post(reverse("notifications:otp_login"), {"phone": phone, **extra})
    code = re.search(r"\d{6}", console.outbox[-1]["text"]).group() if console.outbox else None
    return response, code


def test_disabled_by_default_and_without_provider(client, enabled, settings):
    enabled.otp_login_enabled = False
    enabled.save()
    assert client.get(reverse("notifications:otp_login")).status_code == 404
    assert "ورود با کد پیامکی" not in client.get(reverse("accounts:login")).content.decode()
    enabled.otp_login_enabled = True
    enabled.save()
    assert "ورود با کد پیامکی" in client.get(reverse("accounts:login")).content.decode()
    settings.SMS_PROVIDER = ""
    assert client.get(reverse("notifications:otp_login")).status_code == 404


def test_new_phone_creates_account_and_logs_in(client):
    response, code = _request_code(client, phone="۰۹۱۲۱۲۳۴۵۶۷")  # ارقام فارسی
    assert response.status_code == 200 and "پیامک شد" in response.content.decode()
    assert console.outbox[-1]["to"] == PHONE and "کد ورود" in console.outbox[-1]["text"]
    response = client.post(reverse("notifications:otp_verify"), {"phone": PHONE, "code": code, "next": "/cart/"})
    assert response.status_code == 302 and response["Location"] == "/cart/"
    user = User.objects.get(phone=PHONE)
    assert not user.has_real_email and not user.has_usable_password() and user.contact_label == PHONE
    assert client.get(reverse("accounts:profile")).status_code == 200
    assert AuditLog.objects.filter(action="auth.otp_register").exists()


def test_existing_user_is_logged_in_and_code_is_single_use(client):
    user = User.objects.create_user(email="ali@example.com", password="x-Strong-123", phone=PHONE)
    _, code = _request_code(client)
    client.post(reverse("notifications:otp_verify"), {"phone": PHONE, "code": code})
    assert int(client.session["_auth_user_id"]) == user.pk
    client.logout()
    response = client.post(reverse("notifications:otp_verify"), {"phone": PHONE, "code": code})
    assert response.status_code == 422 and "منقضی" in response.content.decode()


def test_wrong_codes_lock_after_max_attempts(client):
    _, code = _request_code(client)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(otp.MAX_ATTEMPTS - 1):
        assert "درست نیست" in client.post(reverse("notifications:otp_verify"),
                                         {"phone": PHONE, "code": wrong}).content.decode()
    client.post(reverse("notifications:otp_verify"), {"phone": PHONE, "code": wrong})
    response = client.post(reverse("notifications:otp_verify"), {"phone": PHONE, "code": code})
    assert response.status_code == 422 and not User.objects.filter(phone=PHONE).exists()


def test_code_is_stored_hashed_and_bound_to_phone(client, store):
    from django.core.cache import cache

    _, code = _request_code(client)
    stored = cache.get(f"otp:{store.pk}:{PHONE}")
    assert code not in str(stored)
    response = client.post(reverse("notifications:otp_verify"), {"phone": "09120000000", "code": code})
    assert response.status_code == 422


def test_send_is_rate_limited_per_phone(client):
    for _ in range(3):
        _request_code(client)
    response, _ = _request_code(client)
    assert response.status_code == 429


def test_ambiguous_phone_asks_for_email_login(client):
    User.objects.create_user(email="a@example.com", phone=PHONE)
    User.objects.create_user(email="b@example.com", phone=PHONE)
    _, code = _request_code(client)
    response = client.post(reverse("notifications:otp_verify"), {"phone": PHONE, "code": code})
    assert response.status_code == 422 and "با ایمیل وارد شوید" in response.content.decode()


def test_invalid_phone_and_failed_sms(client, settings):
    response = client.post(reverse("notifications:otp_login"), {"phone": "12345"})
    assert response.status_code == 422 and console.outbox == []
    settings.SMS_PROVIDER = "kavenegar"
    settings.SMS_API_KEY = ""  # ارسال شکست می‌خورد (کلید خالی، بدون شبکه)
    response = client.post(reverse("notifications:otp_login"), {"phone": PHONE})
    assert response.status_code == 422 and "ارسال پیامک انجام نشد" in response.content.decode()


def test_otp_message_body_is_never_logged(client):
    from apps.notifications.models import NotificationLog

    _, code = _request_code(client)
    entry = NotificationLog.objects.get(event="otp")
    assert entry.status == NotificationLog.SENT and code not in entry.body
