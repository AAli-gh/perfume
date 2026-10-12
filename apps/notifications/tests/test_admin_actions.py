"""اکشن‌های پنل مدیریت تنظیمات اطلاع‌رسانی: پیامک آزمایشی و ساخت پیام‌های پیش‌فرض."""

import pytest
from django.contrib.admin.sites import site
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from apps.notifications.admin import NotificationSettingsAdmin
from apps.notifications.models import NotificationRule, NotificationSettings
from apps.notifications.sms import SMSError, console

pytestmark = pytest.mark.django_db


def _request():
    request = RequestFactory().post("/")
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def _texts(request):
    return [str(m) for m in request._messages]


def test_send_test_sms(store, settings, monkeypatch):
    conf, _ = NotificationSettings.objects.get_or_create(store=store)
    conf.staff_phones = "09121234567"
    conf.save()
    model_admin = NotificationSettingsAdmin(NotificationSettings, site)
    console.outbox.clear()
    request = _request()
    model_admin.send_test_sms(request, NotificationSettings.objects.filter(pk=conf.pk))
    assert any("09121234567" in t for t in _texts(request)) and console.outbox

    def fail(self, phone, text):
        raise SMSError("اعتبار پنل تمام شده")

    monkeypatch.setattr(console.ConsoleProvider, "send", fail)
    request = _request()
    model_admin.send_test_sms(request, NotificationSettings.objects.filter(pk=conf.pk))
    assert any("اعتبار پنل تمام شده" in t for t in _texts(request))

    NotificationSettings.objects.filter(pk=conf.pk).update(staff_phones="")
    request = _request()
    model_admin.send_test_sms(request, NotificationSettings.objects.filter(pk=conf.pk))
    assert any("خالی است" in t for t in _texts(request))

    settings.SMS_PROVIDER = ""
    request = _request()
    model_admin.send_test_sms(request, NotificationSettings.objects.filter(pk=conf.pk))
    assert any("تنظیم نشده" in t for t in _texts(request))


def test_create_default_messages(store):
    conf, _ = NotificationSettings.objects.get_or_create(store=store)
    NotificationRule.objects.filter(store=store).delete()
    request = _request()
    NotificationSettingsAdmin(NotificationSettings, site).create_default_messages(
        request, NotificationSettings.objects.filter(pk=conf.pk))
    assert NotificationRule.objects.filter(store=store).exists() and "ساخته شد" in _texts(request)[0]
