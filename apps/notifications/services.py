"""ارسال پیامک و ایمیل رویدادهای سفارش و کد ورود.

هر ارسال یک ردیف NotificationLog دارد. خطای سرویس پیامک یا ایمیل هرگز سفارش را خراب نمی‌کند:
ارسال در Celery انجام می‌شود و فقط وضعیت «ناموفق» در گزارش ثبت می‌شود.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse

from apps.core.templatetags.majd import toman

from . import events as E
from .models import NotificationLog, NotificationRule, NotificationSettings
from .sms import SMSError, get_provider

log = logging.getLogger(__name__)


# ---------- تنظیمات و قواعد ----------

def settings_for(store):
    obj, created = NotificationSettings.objects.get_or_create(store=store)
    if created:
        ensure_rules(store)
    return obj


def ensure_rules(store):
    """پیام‌های پیش‌فرض فروشگاه را (فقط موارد نبود) می‌سازد تا در پنل قابل ویرایش باشند."""
    NotificationRule.objects.bulk_create(
        [NotificationRule(store=store, event=r.event, channel=r.channel, audience=r.audience, is_active=r.is_active,
                          text=r.text, subject=r.subject) for r in E.DEFAULT_RULES],
        ignore_conflicts=True,
    )


def rules_for(store, event):
    rules = NotificationRule.objects.filter(store=store, event=event)
    if not rules.exists():
        ensure_rules(store)
    return [r for r in rules.filter(is_active=True)]


def sms_available():
    return bool(getattr(settings, "SMS_PROVIDER", ""))


# ---------- متن پیام ----------

def order_context(order):
    store = order.store
    base = store.base_url
    return {
        "store": store.name,
        "name": order.first_name,
        "number": order.number,
        "total": toman(order.total),
        "status": order.get_status_display(),
        "payment_method": order.get_payment_method_display(),
        "shipping_method": order.shipping_method_name or "پست",
        "tracking_code": order.tracking_code,
        "tracking_url": order.tracking_url,
        "order_url": base + reverse("orders:detail", args=[order.number]),
        "phone": order.phone,
    }


def _recipients(rule, order, conf):
    if rule.audience == E.STAFF:
        return conf.staff_phone_list if rule.channel == E.SMS else conf.staff_email_list
    target = order.phone if rule.channel == E.SMS else order.email
    return [target] if target else []


# ---------- ارسال ----------

def _deliver_sms(rule, to, context):
    """(provider_code, message_id, body)؛ در صورت خطا SMSError."""
    provider = get_provider()
    if provider is None:
        raise SMSError("سرویس پیامک تنظیم نشده است (SMS_PROVIDER).")
    if rule.sms_template:
        params = {name: context.get(name, "") for name in rule.param_names}
        result = provider.send_template(to, rule.sms_template, params)
        body = f"[الگو {rule.sms_template}] " + "، ".join(f"{k}={v}" for k, v in params.items())
    else:
        body = E.render_text(rule.text, context)
        if not body:
            raise SMSError("متن پیامک خالی است.")
        result = provider.send(to, body)
    return provider.code, result.message_id, body


def _deliver_email(rule, to, context, order):
    subject = E.render_text(rule.subject, context) or f"{context['store']} — سفارش {context['number']}"
    template_context = {**context, "order": order, "event": rule.event, "audience": rule.audience, "subject": subject}
    text = render_to_string("emails/order_event.txt", template_context)
    html = render_to_string("emails/order_event.html", template_context)
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to])
    message.attach_alternative(html, "text/html")
    message.send()
    return "email", "", subject


def notify_order(order, event):
    """همه پیام‌های فعال یک رویداد سفارش؛ خروجی: فهرست NotificationLog."""
    conf = settings_for(order.store)
    context = order_context(order)
    logs = []
    for rule in rules_for(order.store, event):
        enabled = conf.sms_enabled if rule.channel == E.SMS else conf.email_enabled
        for to in _recipients(rule, order, conf):
            logs.append(_send_once(rule, order, to, context, enabled))
    return logs


def _send_once(rule, order, to, context, enabled):
    key = {"order": order, "event": rule.event, "channel": rule.channel, "recipient": to}
    try:
        with transaction.atomic():
            NotificationLog.objects.get_or_create(**key, defaults={"store": order.store, "status": NotificationLog.SKIPPED})
    except IntegrityError:  # اجرای هم‌زمان دیگری همین ردیف را ساخت
        pass
    # قفل ردیف تا پایان ارسال: دو worker هم‌زمان یک پیام را دو بار نمی‌فرستند
    with transaction.atomic():
        entry = NotificationLog.objects.select_for_update().get(**key)
        if entry.status == NotificationLog.SENT:
            return entry
        if entry.error:  # تلاش قبلی ناموفق بوده
            entry.attempts += 1
        if not enabled:
            entry.status, entry.error = NotificationLog.SKIPPED, "این کانال در تنظیمات اطلاع‌رسانی خاموش است."
            entry.save()
            return entry
        try:
            if rule.channel == E.SMS:
                entry.provider, entry.message_id, entry.body = _deliver_sms(rule, to, context)
            else:
                entry.provider, entry.message_id, entry.body = _deliver_email(rule, to, context, order)
            entry.status, entry.error = NotificationLog.SENT, ""
        except Exception as exc:  # سرویس پیامک/SMTP — خطا ثبت می‌شود، سفارش تحت تأثیر نیست
            log.warning("Notification %s/%s to %s failed: %s", rule.event, rule.channel, to, exc)
            entry.status, entry.error = NotificationLog.FAILED, str(exc)[:300] or exc.__class__.__name__
        entry.save()
        return entry


def send_otp(store, phone, code, minutes, event=E.OTP):
    """پیامک کد ورود (همگام؛ کاربر منتظر کد است). خروجی: True در صورت ارسال."""
    rule = next(iter(rules_for(store, event)), None)
    if rule is None or not settings_for(store).sms_enabled:
        return False
    context = {"store": store.name, "code": code, "minutes": minutes}
    entry = NotificationLog(store=store, event=event, channel=E.SMS, recipient=phone)
    try:
        entry.provider, entry.message_id, _ = _deliver_sms(rule, phone, context)
        entry.status = NotificationLog.SENT
    except SMSError as exc:
        log.warning("OTP SMS to %s failed: %s", phone, exc)
        entry.status, entry.error = NotificationLog.FAILED, str(exc)[:300]
    entry.body = "(کد ورود — برای امنیت ذخیره نمی‌شود)"
    entry.save()
    return entry.status == NotificationLog.SENT


# ---------- رویدادهای غیرسفارشی (موجودی، یادآوری سبد، پیامک گروهی، کارت هدیه) ----------

def notify_event(store, event, context, *, phone="", email="", audiences=(E.CUSTOMER, E.STAFF)):
    """ارسال همه پیام‌های فعال یک رویداد غیرسفارشی؛ مشتری با phone/email و مدیران از تنظیمات اطلاع‌رسانی.

    خروجی: فهرست NotificationLog (هر ارسال یک ردیف؛ خطای سرویس فقط ثبت می‌شود).
    """
    conf = settings_for(store)
    context = {"store": store.name, **context}
    logs = []
    for rule in rules_for(store, event):
        if rule.audience not in audiences:
            continue
        if rule.audience == E.STAFF:
            targets = conf.staff_phone_list if rule.channel == E.SMS else conf.staff_email_list
        else:
            targets = [phone] if rule.channel == E.SMS and phone else [email] if rule.channel == E.EMAIL and email else []
        enabled = conf.sms_enabled if rule.channel == E.SMS else conf.email_enabled
        for to in targets:
            entry = NotificationLog(store=store, event=event, channel=rule.channel, recipient=to)
            if not enabled:
                entry.status, entry.error = NotificationLog.SKIPPED, "این کانال در تنظیمات اطلاع‌رسانی خاموش است."
            else:
                try:
                    if rule.channel == E.SMS:
                        entry.provider, entry.message_id, entry.body = _deliver_sms(rule, to, context)
                    else:
                        entry.provider, entry.message_id, entry.body = _deliver_simple_email(rule, to, context)
                    entry.status = NotificationLog.SENT
                except Exception as exc:  # سرویس پیامک/SMTP
                    log.warning("Notification %s/%s to %s failed: %s", event, rule.channel, to, exc)
                    entry.status, entry.error = NotificationLog.FAILED, str(exc)[:300] or exc.__class__.__name__
            entry.save()
            logs.append(entry)
    return logs


def _deliver_simple_email(rule, to, context):
    subject = E.render_text(rule.subject, context) or context["store"]
    body = E.render_text(rule.text, context) or subject
    text = render_to_string("emails/simple.txt", {**context, "subject": subject, "body": body})
    html = render_to_string("emails/simple.html", {**context, "subject": subject, "body": body})
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to])
    message.attach_alternative(html, "text/html")
    message.send()
    return "email", "", subject


def send_sms_text(store, event, phone, text):
    """یک پیامک متنی آزاد (پیامک گروهی کارزار)؛ خروجی NotificationLog."""
    conf = settings_for(store)
    entry = NotificationLog(store=store, event=event, channel=E.SMS, recipient=phone, body=text)
    if not conf.sms_enabled:
        entry.status, entry.error = NotificationLog.SKIPPED, "پیامک در تنظیمات اطلاع‌رسانی خاموش است."
    else:
        provider = get_provider()
        try:
            if provider is None:
                raise SMSError("سرویس پیامک تنظیم نشده است (SMS_PROVIDER).")
            entry.provider, entry.message_id = provider.code, provider.send(phone, text).message_id
            entry.status = NotificationLog.SENT
        except SMSError as exc:
            entry.status, entry.error = NotificationLog.FAILED, str(exc)[:300]
    entry.save()
    return entry
