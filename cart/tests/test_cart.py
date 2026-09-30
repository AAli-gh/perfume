from django.urls import reverse

from core.tests.factories import ShopTestCase, make_product
from orders.models import Coupon


class CartTests(ShopTestCase):
    def setUp(self):
        self.product, self.v50, self.v100 = make_product(price=1_000_000, stock=3)

    def add(self, variant, qty=1):
        return self.htmx("post", reverse("cart:add"), {"variant": variant.pk, "quantity": qty})

    def cart(self):
        return self.client.get(reverse("cart:detail")).context["cart"]

    def test_add_returns_oob_badge_and_toast(self):
        resp = self.add(self.v50, 2)
        self.assertContains(resp, 'id="cart-badge" hx-swap-oob="true"')
        self.assertContains(resp, "به سبد خرید اضافه شد")
        self.assertEqual(len(self.cart()), 2)

    def test_quantity_is_capped_by_stock(self):
        self.add(self.v50, 10)
        self.assertEqual(len(self.cart()), 3)

    def test_out_of_stock_not_added(self):
        self.v50.stock = 0
        self.v50.save()
        resp = self.add(self.v50)
        self.assertContains(resp, "موجود نیست")
        self.assertTrue(self.cart().is_empty)

    def test_update_and_remove(self):
        self.add(self.v50)
        self.htmx("post", reverse("cart:update", args=[self.v50.pk]), {"delta": "1"})
        self.assertEqual(len(self.cart()), 2)
        self.htmx("post", reverse("cart:update", args=[self.v50.pk]), {"quantity": "۳"})
        self.assertEqual(len(self.cart()), 3)
        resp = self.htmx("post", reverse("cart:remove", args=[self.v50.pk]))
        self.assertContains(resp, "سبد خرید شما خالی است")
        self.assertTrue(self.cart().is_empty)

    def test_totals_with_coupon_and_shipping(self):
        Coupon.objects.create(code="off20", percent=20, max_discount=300_000)
        self.add(self.v100, 1)  # 2,000,000
        resp = self.htmx("post", reverse("cart:coupon"), {"code": "OFF20"})
        self.assertContains(resp, "اعمال شد")
        cart = self.cart()
        self.assertEqual(cart.subtotal, 2_000_000)
        self.assertEqual(cart.discount, 300_000)  # سقف تخفیف
        self.assertEqual(cart.shipping, 100_000)
        self.assertEqual(cart.total, 1_800_000)

    def test_invalid_coupon(self):
        self.add(self.v50)
        Coupon.objects.create(code="MIN", percent=10, min_subtotal=5_000_000)
        self.assertContains(self.htmx("post", reverse("cart:coupon"), {"code": "nope"}), "معتبر نیست")
        self.assertContains(self.htmx("post", reverse("cart:coupon"), {"code": "min"}), "کافی نیست")
        self.assertIsNone(self.cart().coupon)
