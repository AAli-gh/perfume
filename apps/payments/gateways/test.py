"""درگاه آزمایشی داخلی — فقط وقتی PAYMENT_TEST_GATEWAY_ENABLED=True (هرگز در production)."""

import secrets

from django.urls import reverse

from .base import CallbackData, InitiateResult, PaymentGateway, VerifyResult
from .registry import register


@register
class TestGateway(PaymentGateway):
    code = "test"
    label = "درگاه آزمایشی"

    def initiate(self, payment, callback_url):
        authority = "TEST" + secrets.token_hex(8).upper()
        return InitiateResult(authority, reverse("payments:test_gateway", args=[authority]))

    def parse_callback(self, params):
        return CallbackData(params.get("Authority", ""), params.get("Status") == "OK", raw=dict(params.items()))

    def verify(self, payment, callback):
        return VerifyResult(True, ref_id=str(secrets.randbelow(10**9)).zfill(9), card_pan="6037-99**-****-1234")
