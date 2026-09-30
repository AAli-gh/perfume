from django.urls import reverse

from core.models import ContactMessage, NewsletterSubscriber
from core.templatetags.majd import article, fa_int, toman

from .factories import ShopTestCase


class PageTests(ShopTestCase):
    def test_static_pages_render(self):
        for name in ["core:home", "core:about", "core:contact", "catalog:collections", "blog:list", "cart:detail", "accounts:login"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_contact_form_htmx(self):
        resp = self.htmx("post", reverse("core:contact"), {"name": "رضا", "email": "r@x.ir", "subject": "order", "message": "سلام، سفارشم کجاست؟"})
        self.assertContains(resp, "پیام شما دریافت شد")
        self.assertEqual(ContactMessage.objects.count(), 1)
        bad = self.htmx("post", reverse("core:contact"), {"name": "", "email": "x", "subject": "order", "message": "کوتاه"})
        self.assertContains(bad, "field-error")

    def test_newsletter_is_idempotent(self):
        for _ in range(2):
            self.htmx("post", reverse("core:newsletter"), {"email": "A@x.ir"})
        self.assertEqual(NewsletterSubscriber.objects.count(), 1)

    def test_filters(self):
        self.assertEqual(fa_int(1234567), "۱٬۲۳۴٬۵۶۷")
        self.assertEqual(toman(5000), "۵٬۰۰۰ تومان")
        html = article("سلام <b>\n\n## تیتر\n\nپاراگراف")
        self.assertIn("<h2>تیتر</h2>", html)
        self.assertIn("&lt;b&gt;", html)
