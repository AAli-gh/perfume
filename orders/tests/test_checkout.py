from django.test import override_settings
from django.urls import reverse

from catalog.models import ProductVariant
from core.tests.factories import ShopTestCase, make_product
from orders.models import Coupon, Order

VALID = {
    "first_name": "علی", "last_name": "رضایی", "phone": "۰۹۱۲۱۲۳۴۵۶۷", "email": "", "province": "تهران",
    "city": "تهران", "address": "خیابان آزادی", "postal_code": "1234567890", "note": "",
    "payment_method": "cod", "accept_terms": "on",
}


class CheckoutTests(ShopTestCase):
    def setUp(self):
        self.product, self.v50, _ = make_product(price=1_000_000, stock=5)
        self.client.post(reverse("cart:add"), {"variant": self.v50.pk, "quantity": 2})

    def checkout(self, **overrides):
        return self.client.post(reverse("orders:checkout"), {**VALID, **overrides})

    def test_creates_order_and_reduces_stock(self):
        Coupon.objects.create(code="MAJD10", percent=10)
        self.client.post(reverse("cart:coupon"), {"code": "MAJD10"})
        resp = self.checkout()
        order = Order.objects.get()
        self.assertRedirects(resp, order.get_absolute_url())
        self.assertEqual(order.phone, "09121234567")  # ارقام فارسی تبدیل شد
        self.assertEqual((order.subtotal, order.discount, order.shipping, order.total), (2_000_000, 200_000, 100_000, 1_900_000))
        self.assertEqual(order.items.get().quantity, 2)
        self.assertEqual(ProductVariant.objects.get(pk=self.v50.pk).stock, 3)
        self.assertEqual(Coupon.objects.get().used_count, 1)
        self.assertTrue(self.client.get(reverse("cart:detail")).context["cart"].is_empty)

    def test_validation_errors(self):
        resp = self.checkout(phone="12345", postal_code="12", accept_terms="")
        self.assertEqual(resp.status_code, 422)
        self.assertContains(resp, "شماره موبایل باید", status_code=422)
        self.assertContains(resp, "کد پستی باید", status_code=422)
        self.assertFalse(Order.objects.exists())

    def test_out_of_stock_at_checkout(self):
        ProductVariant.objects.filter(pk=self.v50.pk).update(stock=1)
        self.checkout()
        self.assertFalse(Order.objects.exists())

    def test_order_page_is_private(self):
        self.checkout()
        order = Order.objects.get()
        self.assertEqual(self.client.get(order.get_absolute_url()).status_code, 200)
        self.client.session.flush()
        self.client.logout()
        other = self.client_class()
        self.assertEqual(other.get(order.get_absolute_url()).status_code, 404)

    def test_online_payment_with_test_gateway(self):
        resp = self.checkout(payment_method="online")
        order = Order.objects.get()
        self.assertRedirects(resp, reverse("orders:pay", args=[order.number]), fetch_redirect_response=False)
        resp = self.client.get(reverse("orders:pay", args=[order.number]))
        order.refresh_from_db()
        self.assertTrue(order.payment_authority.startswith("FAKE"))
        cb = reverse("orders:callback")
        self.client.get(cb, {"Authority": order.payment_authority, "Status": "NOK"})
        order.refresh_from_db()
        self.assertFalse(order.is_paid)
        self.client.get(cb, {"Authority": order.payment_authority, "Status": "OK"})
        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertEqual(order.status, Order.Status.PAID)

    @override_settings(DEBUG=False)
    def test_test_gateway_disabled_in_production(self):
        from orders.forms import CheckoutForm

        self.assertNotIn("online", dict(CheckoutForm().fields["payment_method"].choices))
        self.assertEqual(self.client.get(reverse("orders:fake_gateway", args=["FAKE1"])).status_code, 404)
