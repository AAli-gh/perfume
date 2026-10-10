"""ورود دومرحله‌ای کارکنان با کد پیامکی."""

import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.notifications.services import settings_for
from apps.notifications.sms import console

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def enabled(store):
    conf = settings_for(store)
    conf.staff_2fa_enabled = True
    conf.save()
    console.outbox.clear()
    return conf


@pytest.fixture
def staff(client):
    user = User.objects.create_user(email="st@example.com", password="x-Strong-123", is_staff=True,
                                    phone="09127778899")
    user.user_permissions.add(Permission.objects.get(codename="view_order"))
    client.force_login(user)
    return user


def test_studio_requires_code_when_enabled(client, store, enabled, staff):
    response = client.get(reverse("builder:dashboard"))
    assert response.status_code == 302 and reverse("notifications:staff_2fa") in response["Location"]
    page = client.get(response["Location"])
    assert "۸۸۹۹" in page.content.decode()
    client.post(reverse("notifications:staff_2fa"), {"action": "send", "next": "/studio/"})
    code = re.search(r"\b(\d{6})\b", console.outbox[-1]["text"]).group(1)
    assert console.outbox[-1]["to"] == "09127778899" and "پنل مدیریت" in console.outbox[-1]["text"]
    wrong = client.post(reverse("notifications:staff_2fa"), {"action": "verify", "code": "000000", "next": "/studio/"})
    assert wrong.status_code == 302 and client.get(reverse("builder:dashboard")).status_code == 302
    ok = client.post(reverse("notifications:staff_2fa"), {"action": "verify",
                                                          "code": code.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")),
                                                          "next": "/studio/"})
    assert ok["Location"] == "/studio/"
    assert client.get(reverse("builder:dashboard")).status_code == 200


def test_admin_is_protected_too(client, store, enabled, staff):
    assert client.get(reverse("admin:index")).status_code == 302


def test_disabled_by_default_and_storefront_unaffected(client, store, staff):
    assert client.get(reverse("builder:dashboard")).status_code == 200
    conf = settings_for(store)
    conf.staff_2fa_enabled = True
    conf.save()
    assert client.get(reverse("catalog:shop")).status_code == 200


def test_staff_without_phone_is_blocked_but_superuser_warned(client, store, enabled):
    user = User.objects.create_user(email="np@example.com", password="x-Strong-123", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="view_order"))
    client.force_login(user)
    page = client.get(reverse("builder:dashboard"), follow=True)
    assert "موبایل حساب شما ثبت نشده" in page.content.decode()
    boss = User.objects.create_superuser(email="boss@example.com", password="x-Strong-123")
    client.force_login(boss)
    assert client.get(reverse("builder:dashboard")).status_code == 200


def test_htmx_requests_get_hx_redirect(client, store, enabled, staff):
    response = client.get(reverse("builder:dashboard"), HTTP_HX_REQUEST="true")
    assert response.status_code == 204 and reverse("notifications:staff_2fa") in response["HX-Redirect"]
