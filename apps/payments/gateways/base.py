"""رابط مشترک درگاه‌های پرداخت (Adapter).

برای افزودن درگاه جدید: یک زیرکلاس PaymentGateway بسازید، initiate/verify/parse_callback را پیاده کنید
و با @register ثبت کنید. سیستم سفارش و سرویس پرداخت بدون تغییر از آن استفاده می‌کنند.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class PaymentError(Exception):
    """خطای قابل نمایش به کاربر (ارتباط با درگاه، رد درخواست، …)."""


@dataclass
class InitiateResult:
    authority: str
    redirect_url: str
    raw: dict = field(default_factory=dict)


@dataclass
class CallbackData:
    authority: str
    success: bool  # کاربر پرداخت را کامل کرده (نه انصراف)
    raw: dict = field(default_factory=dict)


@dataclass
class VerifyResult:
    ok: bool
    ref_id: str = ""
    card_pan: str = ""
    message: str = ""
    raw: dict = field(default_factory=dict)


class PaymentGateway(ABC):
    code: str = ""
    label: str = ""
    # دامنه‌هایی که کاربر برای پرداخت به آن‌ها منتقل می‌شود (برای CSP form-action)
    redirect_origins: tuple = ()

    def __init__(self, account=None):
        self.account = account  # GatewayAccount یا None

    @abstractmethod
    def initiate(self, payment, callback_url) -> InitiateResult:
        """ایجاد تراکنش در درگاه و برگرداندن آدرس انتقال کاربر."""

    @abstractmethod
    def parse_callback(self, params) -> CallbackData:
        """خواندن پارامترهای بازگشت از درگاه (GET/POST)."""

    @abstractmethod
    def verify(self, payment, callback: CallbackData) -> VerifyResult:
        """تأیید نهایی تراکنش نزد درگاه (تا زمانی که verify نشود پول نهایی نمی‌شود)."""
