"""SMS.ir (نسخه ۱ API) — https://app.sms.ir/developer

- متنی:  POST https://api.sms.ir/v1/send/bulk    {"lineNumber", "messageText", "mobiles": [...]}
- الگو:   POST https://api.sms.ir/v1/send/verify  {"mobile", "templateId", "parameters": [{"name", "value"}]}
  هدر X-API-KEY؛ نام پارامترها همان نام‌هایی است که در قالب پنل تعریف کرده‌اید (مثلاً CODE یا NUMBER).
"""

import requests

from .base import SMSError, SMSProvider, SMSResult
from .registry import register


@register
class SmsIrProvider(SMSProvider):
    code = "smsir"
    label = "SMS.ir"
    BASE = "https://api.sms.ir/v1"

    def _post(self, endpoint, payload):
        if not self.api_key:
            raise SMSError("SMS_API_KEY تنظیم نشده است.")
        headers = {"X-API-KEY": self.api_key, "Accept": "application/json"}
        try:
            data = requests.post(f"{self.BASE}/{endpoint}", json=payload, headers=headers, timeout=self.TIMEOUT).json()
        except (requests.RequestException, ValueError) as exc:
            raise SMSError(f"ارتباط با SMS.ir برقرار نشد: {exc.__class__.__name__}") from exc
        if data.get("status") != 1:
            raise SMSError(f"SMS.ir: {data.get('message') or data.get('status')}")
        body = data.get("data") or {}
        message_id = body.get("messageId") or (body.get("messageIds") or [""])[0]
        return SMSResult(message_id=str(message_id), raw=data)

    def send(self, to, text):
        try:
            line = int(self.sender)
        except ValueError as exc:
            raise SMSError("SMS_SENDER (شماره خط) برای SMS.ir باید عدد باشد.") from exc
        return self._post("send/bulk", {"lineNumber": line, "messageText": text, "mobiles": [to]})

    def send_template(self, to, template, params):
        try:
            template_id = int(template)
        except ValueError as exc:
            raise SMSError("شناسه قالب SMS.ir باید عدد باشد.") from exc
        parameters = [{"name": name.upper(), "value": str(value)} for name, value in params.items()]
        return self._post("send/verify", {"mobile": to, "templateId": template_id, "parameters": parameters})
