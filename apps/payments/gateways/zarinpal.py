"""درگاه زرین‌پال — API نسخه ۴."""

import logging

import requests

from .base import CallbackData, InitiateResult, PaymentError, PaymentGateway, VerifyResult
from .registry import register

log = logging.getLogger(__name__)


@register
class ZarinpalGateway(PaymentGateway):
    code = "zarinpal"
    label = "زرین‌پال"
    TIMEOUT = 15

    @property
    def _host(self):
        return "sandbox.zarinpal.com" if self.account.sandbox else "payment.zarinpal.com"

    def _post(self, endpoint, payload):
        url = f"https://{self._host}/pg/v4/payment/{endpoint}.json"
        try:
            return requests.post(url, json=payload, timeout=self.TIMEOUT).json()
        except (requests.RequestException, ValueError) as exc:
            log.exception("Zarinpal %s failed", endpoint)
            raise PaymentError("ارتباط با درگاه پرداخت برقرار نشد. لطفاً دوباره تلاش کنید.") from exc

    def initiate(self, payment, callback_url):
        order = payment.order
        data = self._post("request", {
            "merchant_id": self.account.merchant_id,
            "amount": payment.amount * 10,  # ریال
            "callback_url": callback_url,
            "description": f"سفارش {order.number}",
            "metadata": {"mobile": order.phone, "email": order.email or None, "order_id": order.number},
        })
        body = data.get("data") or {}
        if body.get("code") != 100:
            log.warning("Zarinpal request rejected: %s", data.get("errors"))
            raise PaymentError("درگاه پرداخت درخواست را نپذیرفت.")
        authority = body["authority"]
        return InitiateResult(authority, f"https://{self._host}/pg/StartPay/{authority}", raw={"request": data})

    def parse_callback(self, params):
        return CallbackData(params.get("Authority", ""), params.get("Status") == "OK", raw=dict(params.items()))

    def verify(self, payment, callback):
        data = self._post("verify", {
            "merchant_id": self.account.merchant_id, "amount": payment.amount * 10, "authority": payment.authority,
        })
        body = data.get("data") or {}
        if body.get("code") in (100, 101):  # 101 = قبلاً تأیید شده
            return VerifyResult(True, str(body.get("ref_id", "")), body.get("card_pan", ""), raw={"verify": data})
        return VerifyResult(False, message="پرداخت توسط درگاه تأیید نشد.", raw={"verify": data})
