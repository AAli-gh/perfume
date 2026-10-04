"""ارائه‌دهنده توسعه: پیامک‌ها فقط در لاگ و حافظه ثبت می‌شوند (outbox برای تست‌ها)."""

import logging

from .base import SMSProvider, SMSResult
from .registry import register

log = logging.getLogger("apps.notifications.sms")
outbox = []


@register
class ConsoleProvider(SMSProvider):
    code = "console"
    label = "کنسول (توسعه)"

    def send(self, to, text):
        outbox.append({"to": to, "text": text})
        log.info("SMS to %s: %s", to, text)
        return SMSResult(message_id=f"console-{len(outbox)}")

    def send_template(self, to, template, params):
        outbox.append({"to": to, "template": template, "params": dict(params)})
        log.info("SMS template %s to %s: %s", template, to, params)
        return SMSResult(message_id=f"console-{len(outbox)}")
