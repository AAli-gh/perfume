"""رابط مشترک سرویس‌های پیامک (Adapter).

ارائه‌دهنده با SMS_PROVIDER انتخاب می‌شود و اعتبارنامه‌ها از متغیرهای محیطی می‌آیند:
    SMS_PROVIDER=kavenegar | smsir | console      (خالی = پیامک خاموش)
    SMS_API_KEY=...                               کلید API پنل پیامک
    SMS_SENDER=...                                شماره خط ارسال (برای پیامک متنی)

دو نوع ارسال:
- send():          پیامک متنی آزاد از خط اختصاصی
- send_template(): پیامک «الگو/خدماتی» (Pattern/Verify) که متنش در پنل سرویس‌دهنده تأیید شده است.
  برای ارسال به شماره‌های در لیست سیاه مخابرات و کد یک‌بارمصرف، الگو لازم است.

ارائه‌دهنده جدید: زیرکلاس SMSProvider + @register در یک ماژول این پوشه + import در sms/__init__.py.
"""

from dataclasses import dataclass, field


class SMSError(Exception):
    """ارسال انجام نشد (خطای شبکه، کلید نامعتبر، اعتبار ناکافی، …)."""


@dataclass
class SMSResult:
    message_id: str = ""
    raw: dict = field(default_factory=dict)


class SMSProvider:
    code = ""
    label = ""
    TIMEOUT = 10

    def __init__(self, api_key="", sender=""):
        self.api_key = api_key
        self.sender = sender

    def send(self, to, text) -> SMSResult:
        raise NotImplementedError

    def send_template(self, to, template, params) -> SMSResult:
        """template: کد/شناسه الگو در پنل؛ params: dict نام ← مقدار به ترتیب تعریف در الگو."""
        raise NotImplementedError
