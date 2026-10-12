"""صفحه‌های خطا با طرح سایت، پنهان بودن پنل مدیریت/استودیو و منوی مدیریت کارکنان در هدر."""

import pytest
from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db
User = get_user_model()


def user(email, **extra):
    return User.objects.create_user(email=email, password="Strong-pass-123", **extra)


@pytest.mark.parametrize("path", ["/studio/", "/studio/orders/", "/admin/", "/admin/login/", "/admin/orders/order/"])
def test_backoffice_is_indistinguishable_from_missing_page(client, store, path):
    missing = client.get("/no-such-page/")
    r = client.get(path)
    assert r.status_code == 404 and r.templates[0].name == missing.templates[0].name == "404.html"
    client.force_login(user("shopper@example.com"))
    assert client.get(path).status_code == 404


def test_staff_reach_backoffice(client, store):
    client.force_login(user("boss@example.com", is_staff=True, is_superuser=True))
    assert client.get(reverse("builder:dashboard")).status_code == 200
    assert client.get(reverse("admin:index")).status_code == 200


def test_inactive_staff_session_is_blocked(client, store):
    staff = user("old@example.com", is_staff=True, is_superuser=True)
    client.force_login(staff)
    User.objects.filter(pk=staff.pk).update(is_active=False)
    assert client.get(reverse("admin:index")).status_code in (302, 404)  # نشست غیرفعال اعتبار ندارد


def test_custom_admin_url_also_hidden(settings):
    from apps.core.backoffice import is_backoffice_path

    settings.ADMIN_URL = "manage-x7/"
    assert is_backoffice_path("/manage-x7/") and not is_backoffice_path("/admin-like/")


def test_staff_menu_only_for_staff(client, store):
    assert "data-staff-menu" not in client.get("/").content.decode()
    client.force_login(user("c@example.com"))
    assert "data-staff-menu" not in client.get("/").content.decode()
    client.force_login(user("s@example.com", is_staff=True))
    body = client.get("/").content.decode()
    assert "data-staff-menu" in body and reverse("builder:dashboard") in body and reverse("admin:index") in body


def test_404_page_has_search_and_links(client, store):
    r = client.get("/no-such-page/")
    body = r.content.decode()
    assert r.status_code == 404 and "خطای ۴۰۴" in body and 'name="q"' in body and reverse("catalog:shop") in body


def test_403_page(client, store):
    client.force_login(user("s2@example.com", is_staff=True))  # کارمند بدون مجوز
    r = client.get(reverse("builder:orders"))
    assert r.status_code == 403 and "اجازه دسترسی به این صفحه را ندارید" in r.content.decode()


def test_405_page_for_browsers_only(client, store):
    r = client.get(reverse("accounts:logout"))
    assert r.status_code == 405 and "خطای ۴۰۵" in r.content.decode() and r["Allow"]
    htmx = client.get(reverse("accounts:logout"), HTTP_HX_REQUEST="true")
    assert htmx.status_code == 405 and not htmx.content


def test_csrf_failure_page(store):
    csrf_client = Client(enforce_csrf_checks=True)
    r = csrf_client.post(reverse("accounts:login"), {"username": "a@b.ir", "password": "x"})
    assert r.status_code == 403 and "نشست فرم منقضی شده است" in r.content.decode()


def test_400_page_renders_without_session(client):
    r = client.get("/", HTTP_HOST="evil.example")
    assert r.status_code == 400 and "درخواست نامعتبر است" in r.content.decode()


def test_429_page(client, store):
    url = reverse("accounts:login")
    for _ in range(20):
        client.post(url, {"username": "x@example.com", "password": "x"})
    r = client.post(url, {"username": "x@example.com", "password": "x"})
    assert r.status_code == 429 and "خطای ۴۲۹" in r.content.decode()


def test_standalone_500_and_400_templates():
    for name, text in (("500.html", "مشکلی پیش آمد"), ("400.html", "درخواست نامعتبر")):
        html = get_template(name).render({})
        assert text in html and "{%" not in html and "<style" not in html
