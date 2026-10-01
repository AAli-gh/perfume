"""درگاه پرداخت: زرین‌پال (API نسخه ۴) و درگاه آزمایشی برای توسعه."""

import logging
import secrets
from dataclasses import dataclass

import requests
from django.conf import settings
from django.urls import reverse

log = logging.getLogger(__name__)


class PaymentError(Exception):
    pass


@dataclass
class VerifyResult:
    ok: bool
    ref_id: str = ""
    message: str = ""


class ZarinpalGateway:
    TIMEOUT = 15

    def __init__(self, merchant_id, sandbox=False):
        self.merchant_id = merchant_id
        host = "sandbox.zarinpal.com" if sandbox else "payment.zarinpal.com"
        self.api = f"https://{host}/pg/v4/payment"
        self.start_url = f"https://{host}/pg/StartPay/"

    def _post(self, endpoint, payload):
        try:
            resp = requests.post(f"{self.api}/{endpoint}.json", json=payload, timeout=self.TIMEOUT)
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            log.exception("Zarinpal %s failed", endpoint)
            raise PaymentError("ارتباط با درگاه پرداخت برقرار نشد. لطفاً دوباره تلاش کنید.") from exc

    def request(self, order, callback_url):
        """ایجاد تراکنش؛ شناسه (authority) و آدرس انتقال به درگاه را برمی‌گرداند."""
        data = self._post("request", {
            "merchant_id": self.merchant_id,
            "amount": order.total * 10,  # ریال
            "callback_url": callback_url,
            "description": f"سفارش {order.number} — عطر مجد",
            "metadata": {"mobile": order.phone, "email": order.email or None, "order_id": order.number},
        })
        body = data.get("data") or {}
        if body.get("code") != 100:
            log.warning("Zarinpal request rejected: %s", data.get("errors"))
            raise PaymentError("درگاه پرداخت درخواست را نپذیرفت.")
        authority = body["authority"]
        return authority, self.start_url + authority

    def verify(self, order, authority):
        data = self._post("verify", {"merchant_id": self.merchant_id, "amount": order.total * 10, "authority": authority})
        body = data.get("data") or {}
        if body.get("code") in (100, 101):
            return VerifyResult(True, str(body.get("ref_id", "")))
        return VerifyResult(False, message="پرداخت تأیید نشد.")


class FakeGateway:
    """درگاه آزمایشی داخلی — فقط در حالت DEBUG."""

    def request(self, order, callback_url):
        authority = "FAKE" + secrets.token_hex(8).upper()
        return authority, reverse("orders:fake_gateway", args=[authority])

    def verify(self, order, authority):
        return VerifyResult(True, ref_id=str(secrets.randbelow(10**9)).zfill(9))


def get_gateway():
    if settings.ZARINPAL_MERCHANT_ID:
        return ZarinpalGateway(settings.ZARINPAL_MERCHANT_ID, settings.ZARINPAL_SANDBOX)
    if settings.DEBUG:
        return FakeGateway()
    raise PaymentError("درگاه پرداخت پیکربندی نشده است.")
