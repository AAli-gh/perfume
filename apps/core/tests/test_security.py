import os
import re
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.core.ratelimit import client_ip, parse_rate
from apps.core.validators import ImageUploadValidator, favicon_upload, image_upload

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parents[3]


def csp(response):
    return dict(
        (part.split(" ", 1) + [""])[:2]
        for part in (p.strip() for p in response["Content-Security-Policy"].split(";")) if part
    )


def make_user(email="u@example.com", password="Strong-pass-123", **extra):
    return User.objects.create_user(email=email, password=password, **extra)


# ---------- هدرهای امنیتی و CSP ----------

def test_csp_header_and_nonce(client, store):
    r1, r2 = client.get("/"), client.get("/")
    policy = csp(r1)
    assert policy["script-src"] == "'self'" and "unsafe" not in policy["script-src"]
    assert policy["object-src"] == "'none'" and policy["frame-ancestors"] == "'none'"
    assert policy["base-uri"] == "'self'"
    nonce = re.search(r"'nonce-([\w-]+)'", policy["style-src"]).group(1)
    assert f'<style id="theme-tokens" nonce="{nonce}">' in r1.content.decode()
    assert nonce != re.search(r"'nonce-([\w-]+)'", csp(r2)["style-src"]).group(1)  # هر درخواست nonce تازه
    assert "https://payment.zarinpal.com" in policy["form-action"]  # ثبت‌شده توسط اپ پرداخت
    assert policy["frame-src"].split()[0] == "'self'"  # iframe پیش‌نمایش استودیو
    assert r1["Permissions-Policy"].startswith("camera=()")
    assert r1["X-Content-Type-Options"] == "nosniff" and r1["X-Frame-Options"] == "DENY"


def test_no_inline_scripts_or_handlers_in_templates():
    """CSP اسکریپت inline را مسدود می‌کند؛ هیچ قالبی نباید به آن وابسته باشد."""
    offenders = []
    for path in list((ROOT / "themes").rglob("*.html")) + list((ROOT / "apps").rglob("templates/**/*.html")):
        text = path.read_text()
        for m in re.finditer(r"<script(?![^>]*\bsrc=)([^>]*)>", text):
            if "application/ld+json" not in m.group(1):
                offenders.append(f"{path.name}: inline <script>")
        if re.search(r"\son[a-z]+\s*=\s*[\"']", text) or "javascript:" in text:
            offenders.append(f"{path.name}: inline handler")
        if re.search(r"<style(?![^>]*nonce)", text) and path.name != "500.html":
            offenders.append(f"{path.name}: <style> without nonce")
    assert not offenders, offenders


def test_htmx_hardened(client, store):
    body = client.get("/").content.decode()
    assert '"allowEval":false' in body and '"allowScriptTags":false' in body and '"includeIndicatorStyles":false' in body


def test_studio_head_has_nonce(client, store):
    client.force_login(make_user(is_staff=True, is_superuser=True))
    r = client.get(reverse("builder:dashboard"))
    nonce = re.search(r"'nonce-([\w-]+)'", csp(r)["style-src"]).group(1)
    assert f'<style id="studio-tokens" nonce="{nonce}">' in r.content.decode()


def test_preview_allows_same_origin_framing_only(client, store):
    client.force_login(make_user(is_staff=True, is_superuser=True))
    client.get(reverse("builder:preview"))
    r = client.get("/")
    assert csp(r)["frame-ancestors"] == "'self'" and r["X-Frame-Options"] == "SAMEORIGIN"


@override_settings(CSP_REPORT_ONLY=True)
def test_csp_report_only_mode(client, store):
    r = client.get("/")
    assert "Content-Security-Policy-Report-Only" in r and "Content-Security-Policy" not in r


def test_500_page_works_under_csp():
    html = (ROOT / "themes/base/templates/500.html").read_text()
    assert "<style" not in html and "{% load" not in html


def test_production_deploy_check_passes():
    """manage.py check --deploy با تنظیمات production هیچ هشداری نمی‌دهد."""
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.prod", "SECRET_KEY": "k3Y-q9Z_" * 8,
           "ALLOWED_HOSTS": "shop.example.com", "REDIS_URL": "redis://localhost:6379/0"}
    result = subprocess.run([sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
                            cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("key", ["", "short-key", "django-insecure-" + "a" * 50, "x" * 60])
def test_production_rejects_weak_secret_key(key):
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.prod", "SECRET_KEY": key}
    result = subprocess.run([sys.executable, "-c", "import django; django.setup()"], cwd=ROOT, env=env,
                            capture_output=True, text=True)
    assert result.returncode != 0 and "SECRET_KEY" in result.stderr


def test_production_settings_values():
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.prod", "SECRET_KEY": "k3Y-q9Z_" * 8}
    code = ("import django;django.setup();from django.conf import settings as s;"
            "print(s.SECURE_HSTS_SECONDS, s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, s.CSRF_COOKIE_HTTPONLY,"
            " s.SECURE_SSL_REDIRECT, s.CSP_UPGRADE_INSECURE, s.TRUSTED_PROXY_COUNT, s.PAYMENT_TEST_GATEWAY_ENABLED)")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True).stdout
    assert out.split() == ["31536000", "True", "True", "True", "True", "True", "1", "False"]


# ---------- محدودیت درخواست ----------

def test_parse_rate():
    assert parse_rate("5/15m") == (5, 900) and parse_rate("10/h") == (10, 3600)
    with pytest.raises(ValueError):
        parse_rate("five per minute")


def test_login_limited_per_account_across_ips(client, store):
    make_user()
    url = reverse("accounts:login")
    for i in range(5):
        r = client.post(url, {"username": "u@example.com", "password": "wrong"}, REMOTE_ADDR=f"10.0.0.{i}")
        assert r.status_code == 200
    r = client.post(url, {"username": "U@example.com ", "password": "wrong"}, REMOTE_ADDR="10.0.0.99")
    assert r.status_code == 429 and int(r["Retry-After"]) > 0
    assert "تعداد درخواست‌ها بیش از حد مجاز است" in r.content.decode()
    # حتی رمز درست تا پایان پنجره پذیرفته نمی‌شود
    r = client.post(url, {"username": "u@example.com", "password": "Strong-pass-123"}, REMOTE_ADDR="10.0.0.98")
    assert r.status_code == 429
    assert AuditLog.objects.filter(action="ratelimit.blocked", target="login-account").count() == 2
    # حساب دیگر محدود نیست
    make_user("other@example.com")
    r = client.post(url, {"username": "other@example.com", "password": "Strong-pass-123"}, REMOTE_ADDR="10.0.0.97")
    assert r.status_code == 302


def test_login_limited_per_ip(client, store):
    url = reverse("accounts:login")
    codes = [client.post(url, {"username": f"x{i}@example.com", "password": "x"}).status_code for i in range(21)]
    assert codes[:20] == [200] * 20 and codes[20] == 429


@pytest.mark.parametrize("url_name,data,limit", [
    ("pages:contact", {"name": "a", "email": "a@example.com", "subject": "other", "message": "سلام"}, 5),
    ("marketing:newsletter", {"email": "n@example.com"}, 10),
    ("cart:coupon", {"code": "NOPE"}, 10),
    ("accounts:register", {"email": "r@example.com"}, 5),
])
def test_forms_rate_limited(client, store, url_name, data, limit):
    url = reverse(url_name)
    codes = [client.post(url, data).status_code for _ in range(limit + 1)]
    assert 429 not in codes[:limit] and codes[limit] == 429


def test_htmx_request_gets_429_status(client, store):
    url = reverse("cart:coupon")
    for _ in range(10):
        client.post(url, {"code": "X"}, HTTP_HX_REQUEST="true")
    assert client.post(url, {"code": "X"}, HTTP_HX_REQUEST="true").status_code == 429


def test_get_requests_not_limited_unless_configured(client, store):
    assert all(client.get(reverse("pages:contact")).status_code == 200 for _ in range(8))


def test_admin_login_rate_limited(client, store):
    url = reverse("admin:login")
    codes = [client.post(url, {"username": "a@example.com", "password": "x"}).status_code for _ in range(11)]
    assert codes[10] == 429 and 429 not in codes[:10]


def test_preview_share_links_rate_limited(client, store):
    url = reverse("builder:preview_share", args=["bogus"])
    codes = [client.get(url).status_code for _ in range(31)]
    assert codes[:30] == [404] * 30 and codes[30] == 429


def test_forwarded_for_ignored_without_trusted_proxy(rf, settings):
    settings.TRUSTED_PROXY_COUNT = 0
    request = rf.get("/", HTTP_X_FORWARDED_FOR="1.2.3.4", REMOTE_ADDR="10.0.0.1")
    assert client_ip(request) == "10.0.0.1"
    settings.TRUSTED_PROXY_COUNT = 1
    request = rf.get("/", HTTP_X_FORWARDED_FOR="6.6.6.6, 1.2.3.4", REMOTE_ADDR="172.18.0.2")
    assert client_ip(request) == "1.2.3.4"  # جعل اولین مقدار فایده‌ای ندارد


def test_spoofed_forwarded_for_does_not_bypass_limit(client, store, settings):
    settings.TRUSTED_PROXY_COUNT = 0
    url = reverse("pages:contact")
    data = {"name": "a", "email": "a@example.com", "subject": "other", "message": "x"}
    codes = [client.post(url, data, HTTP_X_FORWARDED_FOR=f"9.9.9.{i}").status_code for i in range(6)]
    assert codes[5] == 429


# ---------- گزارش رویدادهای امنیتی ----------

def test_auth_events_audited(client, store):
    make_user()
    url = reverse("accounts:login")
    client.post(url, {"username": "u@example.com", "password": "bad-password"}, REMOTE_ADDR="10.1.1.1")
    client.post(url, {"username": "u@example.com", "password": "Strong-pass-123"}, REMOTE_ADDR="10.1.1.1")
    client.post(reverse("accounts:logout"))
    actions = list(AuditLog.objects.order_by("created_at").values_list("action", flat=True))
    assert actions == ["auth.login_failed", "auth.login", "auth.logout"]
    failed = AuditLog.objects.get(action="auth.login_failed")
    assert failed.target == "u@example.com" and failed.ip == "10.1.1.1" and failed.store == store
    assert "bad-password" not in str(AuditLog.objects.values_list("data", "target"))


def test_register_audited(client, store):
    client.post(reverse("accounts:register"), {
        "first_name": "م", "last_name": "ا", "email": "new@example.com",
        "password1": "Strong-pass-123", "password2": "Strong-pass-123",
    })
    assert AuditLog.objects.filter(action="auth.register", target="new@example.com").exists()


def test_studio_publish_audited(client, store):
    from apps.themes.services import draft_settings

    boss = make_user(is_staff=True, is_superuser=True)
    client.force_login(boss)
    ts = draft_settings(store)
    ts.overrides = {"colors": {"primary": "#123456"}}
    ts.save()
    client.post(reverse("builder:publish"))
    entry = AuditLog.objects.get(action="studio.publish")
    assert entry.user == boss and "رنگ‌ها" in entry.data["changes"]


def test_audit_failure_never_breaks_request(client, store, monkeypatch):
    from apps.core import models

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(models.AuditLog.objects, "create", boom)
    make_user()
    r = client.post(reverse("accounts:login"), {"username": "u@example.com", "password": "Strong-pass-123"})
    assert r.status_code == 302


def test_prune_audit_log(store):
    old = AuditLog.objects.create(action="auth.login")
    AuditLog.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=200))
    fresh = AuditLog.objects.create(action="auth.login")
    call_command("prune_audit_log")
    assert list(AuditLog.objects.values_list("pk", flat=True)) == [fresh.pk]


# ---------- نشست کارکنان ----------

def test_staff_session_shorter_than_customer(store, settings):
    staff, customer = Client(), Client()
    make_user("s@example.com", is_staff=True)
    make_user("c@example.com")
    for c, email in ((staff, "s@example.com"), (customer, "c@example.com")):
        c.post(reverse("accounts:login"), {"username": email, "password": "Strong-pass-123", "remember": "on"})
    assert staff.session.get_expiry_age() == settings.STAFF_SESSION_AGE == 12 * 3600
    assert customer.session.get_expiry_age() == settings.SESSION_COOKIE_AGE


# ---------- پنل مدیریت ----------

def test_published_theme_read_only_in_admin(client, store):
    from apps.themes.models import ThemeSettings
    from apps.themes.services import draft_settings

    client.force_login(make_user(is_staff=True, is_superuser=True))
    published = ThemeSettings.objects.get(store=store, status="published")
    draft = draft_settings(store)
    page = client.get(reverse("admin:themes_themesettings_change", args=[published.pk])).content.decode()
    assert 'name="overrides"' not in page  # فقط نمایش
    r = client.post(reverse("admin:themes_themesettings_change", args=[published.pk]), {"overrides": '{"colors":{"primary":"#000000"}}'})
    assert r.status_code == 403
    assert client.post(reverse("admin:themes_themesettings_delete", args=[published.pk]), {"post": "yes"}).status_code == 403
    assert 'name="overrides"' in client.get(reverse("admin:themes_themesettings_change", args=[draft.pk])).content.decode()
    assert client.get(reverse("admin:themes_themesettings_add")).status_code == 403


def test_page_sections_read_only_in_admin(client, store):
    from apps.pages.models import Page

    client.force_login(make_user(is_staff=True, is_superuser=True))
    page = Page.objects.get(store=store, is_home=True)
    body = client.get(reverse("admin:pages_page_change", args=[page.pk])).content.decode()
    assert "ویرایش از استودیو" in body and 'name="sections-0-settings"' not in body


def test_audit_and_revisions_read_only_in_admin(client, store):
    client.force_login(make_user(is_staff=True, is_superuser=True))
    entry = AuditLog.objects.create(action="auth.login")
    assert client.get(reverse("admin:core_auditlog_changelist")).status_code == 200
    assert client.get(reverse("admin:core_auditlog_add")).status_code == 403
    assert client.post(reverse("admin:core_auditlog_delete", args=[entry.pk]), {"post": "yes"}).status_code == 403
    assert client.get(reverse("admin:builder_revision_add")).status_code == 403


# ---------- آپلود فایل ----------

@pytest.mark.parametrize("name,size,ok", [
    ("a.jpg", 1000, True), ("a.PNG", 1000, True), ("a.gif", 1000, True), ("a.webp", 1000, True),
    ("a.svg", 1000, False), ("a.html", 1000, False), ("a.php.jpg.exe", 1000, False), ("noext", 1000, False),
    ("big.jpg", 5 * 1024 * 1024 + 1, False),
])
def test_image_upload_validator(name, size, ok):
    upload = SimpleUploadedFile(name, b"x" * size)
    if ok:
        image_upload(upload)
    else:
        with pytest.raises(ValidationError):
            image_upload(upload)


def test_favicon_validator_is_stricter():
    with pytest.raises(ValidationError):
        favicon_upload(SimpleUploadedFile("f.jpg", b"x"))
    favicon_upload(SimpleUploadedFile("f.ico", b"x"))
    assert ImageUploadValidator() == image_upload  # قابل سریال‌سازی در migration


def test_admin_rejects_svg_product_image(client, store):
    from apps.catalog.models import Product

    client.force_login(make_user(is_staff=True, is_superuser=True))
    svg = SimpleUploadedFile("evil.svg", b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>",
                             content_type="image/svg+xml")
    count = Product.objects.count()
    r = client.post(reverse("admin:catalog_product_add"), {"name": "x", "image": svg})
    assert r.status_code == 200 and Product.objects.count() == count


# ---------- آدرس پنل مدیریت ----------

def test_custom_admin_url_not_in_robots(client, store, settings):
    settings.ADMIN_URL = "manage-x7/"
    assert "manage-x7" not in client.get("/robots.txt").content.decode()


def test_rate_limit_cannot_be_doubled_across_window_boundary(store):
    """با پنجره ثابت، ۵ درخواست قبل و ۵ درخواست بعد از مرز پنجره همه مجاز می‌شدند."""
    from unittest import mock

    from apps.core import ratelimit

    period = 600
    boundary = (int(1_800_000_000 // period) + 1) * period
    with mock.patch.object(ratelimit.time, "time", return_value=boundary - 1):
        assert all(ratelimit.hit("t", "ip", 5, period)[0] for _ in range(5))
    with mock.patch.object(ratelimit.time, "time", return_value=boundary + 1):
        assert not ratelimit.hit("t", "ip", 5, period)[0]  # پنجره قبلی هنوز حساب می‌شود
    # یک پنجره کامل بعد، دوباره آزاد است
    with mock.patch.object(ratelimit.time, "time", return_value=boundary + period + 1):
        assert ratelimit.hit("t", "ip", 5, period)[0]
