from django.urls import reverse

from apps.catalog.models import Brand, Product, ProductVariant
from apps.catalog.profile import Kind
from apps.core.tests.factories import ShopTestCase, img, make_product
from apps.orders.models import Order

from .test_checkout import VALID


def make_box(slug="box", capacity=2, price=500_000, stock=5):
    brand = Brand.objects.get_or_create(slug="b1", defaults={"name": "برند"})[0]
    box = Product.objects.create(slug=slug, name=f"باکس {slug}", brand=brand, kind=Kind.GIFT_BOX, gift_capacity=capacity,
                                 image=img(), short_description="باکس", description="باکس هدیه")
    return ProductVariant.objects.create(product=box, size_ml=0, price=price, stock=stock)


class GiftCatalogTests(ShopTestCase):
    def setUp(self):
        make_product()
        self.box = make_box()

    def test_gift_boxes_page_lists_boxes_only(self):
        resp = self.client.get(reverse("catalog:gift_boxes"))
        self.assertContains(resp, "باکس box")
        self.assertNotContains(resp, "عود تست")

    def test_shop_excludes_boxes_but_search_finds_them(self):
        names = [p.name for p in self.client.get(reverse("catalog:shop")).context["page"]]
        self.assertEqual(names, ["عود تست"])
        names = [p.name for p in self.client.get(reverse("catalog:shop"), {"q": "باکس"}).context["page"]]
        self.assertEqual(names, ["باکس box"])
        self.assertContains(self.client.get(reverse("catalog:product", args=["oud"])), "داخل باکس هدیه بفرستید")

    def test_box_product_page_has_no_compare_or_notes(self):
        resp = self.client.get(reverse("catalog:product", args=["box"]))
        self.assertContains(resp, "گنجایش")
        self.assertNotContains(resp, "compare-button")


class GiftCheckoutTests(ShopTestCase):
    def setUp(self):
        _, self.v50, _ = make_product(price=1_000_000, stock=5)
        self.small, self.big = make_box("small", capacity=1, price=300_000), make_box("big", capacity=3, price=700_000)
        self.client.post(reverse("cart:add"), {"variant": self.v50.pk, "quantity": 2})

    def checkout(self, **overrides):
        return self.client.post(reverse("orders:checkout"), {**VALID, **overrides})

    def test_default_is_plain_packaging(self):
        self.assertRedirects(self.checkout(), Order.objects.get().get_absolute_url())
        order = Order.objects.get()
        self.assertEqual(order.packaging, Order.Packaging.NONE)
        self.assertFalse(order.is_gift)
        self.assertEqual(order.items.count(), 1)

    def test_box_chosen_at_checkout_is_added_and_reserved(self):
        resp = self.checkout(packaging="in_box", gift_box=self.big.pk, gift_message="تولدت مبارک", gift_from="سارا",
                             hide_prices="on")
        order = Order.objects.get()
        self.assertRedirects(resp, order.get_absolute_url())
        self.assertEqual(order.packaging, Order.Packaging.IN_BOX)
        self.assertEqual(order.subtotal, 2_000_000 + 700_000)
        self.assertEqual(sorted(order.items.values_list("product_name", flat=True)), ["باکس big", "عود تست"])
        self.assertEqual(ProductVariant.objects.get(pk=self.big.pk).stock, 4)
        page = self.client.get(order.get_absolute_url())
        self.assertContains(page, "تولدت مبارک")
        self.assertContains(page, "از طرف سارا")
        self.assertContains(page, "فاکتور قیمت داخل بسته قرار نمی‌گیرد")

    def test_capacity_too_small(self):
        resp = self.checkout(packaging="in_box", gift_box=self.small.pk)
        self.assertContains(resp, "گنجایش باکس‌ها 1 شیشه", status_code=422)
        self.assertFalse(Order.objects.exists())

    def test_box_required_for_in_box_and_separate(self):
        for packaging in ["in_box", "separate"]:
            resp = self.checkout(packaging=packaging)
            self.assertContains(resp, "یک باکس هدیه انتخاب کنید", status_code=422)

    def test_separate_box_is_added_without_capacity_check(self):
        self.checkout(packaging="separate", gift_box=self.small.pk)
        self.assertEqual(Order.objects.get().packaging, Order.Packaging.SEPARATE)
        self.assertEqual(Order.objects.get().items.count(), 2)

    def test_custom_needs_note_and_needs_no_box(self):
        self.assertContains(self.checkout(packaging="custom"), "توضیح دهید", status_code=422)
        self.checkout(packaging="custom", packaging_note="یکی در باکس، یکی جدا")
        order = Order.objects.get()
        self.assertEqual((order.packaging, order.packaging_note), ("custom", "یکی در باکس، یکی جدا"))
        self.assertEqual(order.items.count(), 1)

    def test_box_ignored_with_plain_packaging(self):
        self.checkout(packaging="none", gift_box=self.big.pk)
        self.assertEqual(Order.objects.get().items.count(), 1)

    def test_box_already_in_cart(self):
        self.client.post(reverse("cart:add"), {"variant": self.big.pk, "quantity": 1})
        page = self.client.get(reverse("cart:detail"))
        self.assertContains(page, "باکس هدیه در سبد شما")
        self.assertNotContains(page, 'name="gift_box"')
        self.checkout(packaging="in_box")
        order = Order.objects.get()
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(ProductVariant.objects.get(pk=self.big.pk).stock, 4)

    def test_only_box_in_cart_cannot_be_in_box(self):
        self.client.post(reverse("cart:remove", args=[self.v50.pk]))
        self.client.post(reverse("cart:add"), {"variant": self.small.pk, "quantity": 1})
        self.assertContains(self.checkout(packaging="in_box"), "عطری ندارد", status_code=422)
        self.checkout(packaging="separate")
        self.assertEqual(Order.objects.get().packaging, Order.Packaging.SEPARATE)

    def test_checkout_page_shows_box_picker(self):
        resp = self.client.get(reverse("cart:detail"))
        self.assertContains(resp, "بسته‌بندی و هدیه")
        self.assertContains(resp, "باکس big")
        self.assertContains(resp, "change from:[name=gift_box]")

    def test_quote_includes_chosen_box(self):
        data = {**VALID, "packaging": "in_box", "gift_box": self.big.pk}
        resp = self.htmx("post", reverse("orders:quote"), data)
        self.assertContains(resp, "باکس هدیه انتخاب‌شده")
        self.assertEqual(resp.context["quote"].subtotal, 2_700_000)
        resp = self.htmx("post", reverse("orders:quote"), {**data, "packaging": "none"})
        self.assertNotContains(resp, "باکس هدیه انتخاب‌شده")
        self.assertEqual(resp.context["quote"].subtotal, 2_000_000)
