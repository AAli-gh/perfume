"""کاوه‌نگار — https://kavenegar.com/rest.html

- متنی:  GET  https://api.kavenegar.com/v1/{API-KEY}/sms/send.json?receptor=&sender=&message=
- الگو:   GET  https://api.kavenegar.com/v1/{API-KEY}/verify/lookup.json?receptor=&template=&token=&token2=&token3=
  مقادیر الگو به ترتیب در token، token2، token3، token10 و token20 قرار می‌گیرند
  (token تا token3 نباید فاصله داشته باشند؛ فاصله‌ها با نیم‌فاصله جایگزین می‌شوند).
"""

import requests

from .base import SMSError, SMSProvider, SMSResult
from .registry import register

TOKEN_KEYS = ("token", "token2", "token3", "token10", "token20")


@register
class KavenegarProvider(SMSProvider):
    code = "kavenegar"
    label = "کاوه‌نگار"
    BASE = "https://api.kavenegar.com/v1"

    def _call(self, endpoint, params):
        if not self.api_key:
            raise SMSError("SMS_API_KEY تنظیم نشده است.")
        try:
            response = requests.get(f"{self.BASE}/{self.api_key}/{endpoint}.json", params=params, timeout=self.TIMEOUT)
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise SMSError(f"ارتباط با کاوه‌نگار برقرار نشد: {exc.__class__.__name__}") from exc
        status = (data.get("return") or {}).get("status")
        if status != 200:
            raise SMSError(f"کاوه‌نگار: {(data.get('return') or {}).get('message') or status}")
        entries = data.get("entries") or [{}]
        return SMSResult(message_id=str(entries[0].get("messageid", "")), raw=data)

    def send(self, to, text):
        return self._call("sms/send", {"receptor": to, "sender": self.sender, "message": text})

    def send_template(self, to, template, params):
        values = list(params.values())
        if len(values) > len(TOKEN_KEYS):
            raise SMSError("الگوی کاوه‌نگار حداکثر ۵ متغیر دارد.")
        query = {"receptor": to, "template": template}
        for key, value in zip(TOKEN_KEYS, values, strict=False):
            value = str(value)
            query[key] = value if key in ("token10", "token20") else value.replace(" ", "\u200c")
        return self._call("verify/lookup", query)
