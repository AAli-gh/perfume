from django.urls import reverse

from catalog.models import Brand, Review, ScentFamily
from core.tests.factories import ShopTestCase, make_product


class ShopViewTests(ShopTestCase):
    def setUp(self):
        self.floral = ScentFamily.objects.create(slug="floral", name="گلی")
        self.other_brand = Brand.objects.create(slug="b2", name="برند دو")
        self.oud, *_ = make_product("oud", "عود شب", price=4_000_000)
        self.rose, *_ = make_product("rose", "گل سرخ", price=2_000_000, scent=self.floral, brand=self.other_brand)
        make_product("hidden", "مخفی", is_active=False)

    def names(self, resp):
        return [p.name for p in resp.context["page"].object_list]

    def test_lists_only_active_products(self):
        resp = self.client.get(reverse("catalog:shop"))
        self.assertEqual(resp.status_code, 200)
        self.assertCountEqual(self.names(resp), ["عود شب", "گل سرخ"])

    def test_filters_and_search(self):
        url = reverse("catalog:shop")
        self.assertEqual(self.names(self.client.get(url, {"scent": "floral"})), ["گل سرخ"])
        self.assertEqual(self.names(self.client.get(url, {"brand": "b2"})), ["گل سرخ"])
        self.assertEqual(self.names(self.client.get(url, {"q": "عود"})), ["عود شب"])
        self.assertEqual(self.names(self.client.get(url, {"max_price": 3_000_000})), ["گل سرخ"])
        self.assertEqual(self.names(self.client.get(url, {"sort": "price"})), ["گل سرخ", "عود شب"])

    def test_htmx_returns_partial(self):
        resp = self.htmx("get", reverse("catalog:shop"), {"scent": "floral"})
        self.assertTemplateUsed(resp, "catalog/partials/results.html")
        self.assertTemplateNotUsed(resp, "base.html")

    def test_product_page_hides_unapproved_reviews(self):
        Review.objects.create(product=self.oud, name="الف", rating=5, text="عالی بود", is_approved=True)
        Review.objects.create(product=self.oud, name="ب", rating=1, text="اسپم اسپم", is_approved=False)
        resp = self.client.get(self.oud.get_absolute_url())
        self.assertContains(resp, "عالی بود")
        self.assertNotContains(resp, "اسپم اسپم")

    def test_review_submission_needs_approval(self):
        resp = self.htmx("post", reverse("catalog:review", args=["oud"]), {"name": "سارا", "rating": 5, "text": "خیلی خوب است"})
        self.assertContains(resp, "پس از تأیید")
        review = Review.objects.get()
        self.assertFalse(review.is_approved)

    def test_inactive_product_404(self):
        self.assertEqual(self.client.get(reverse("catalog:product", args=["hidden"])).status_code, 404)
