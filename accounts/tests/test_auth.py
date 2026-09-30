from django.contrib.auth import get_user_model
from django.urls import reverse

from core.tests.factories import ShopTestCase

User = get_user_model()


class AuthTests(ShopTestCase):
    def test_register_logs_in(self):
        resp = self.client.post(reverse("accounts:register"), {
            "first_name": "مهسا", "last_name": "احمدی", "email": "Mahsa@Example.com",
            "password1": "Atr-Majd-2026!", "password2": "Atr-Majd-2026!",
        })
        self.assertRedirects(resp, reverse("accounts:profile"))
        self.assertTrue(User.objects.filter(email="mahsa@example.com").exists())

    def test_duplicate_email_rejected(self):
        User.objects.create_user("a@b.ir", "x")
        resp = self.client.post(reverse("accounts:register"), {
            "first_name": "a", "last_name": "b", "email": "A@b.ir", "password1": "Atr-Majd-2026!", "password2": "Atr-Majd-2026!",
        })
        self.assertContains(resp, "قبلاً ثبت‌نام", status_code=422)

    def test_login_with_email(self):
        User.objects.create_user("a@b.ir", "Atr-Majd-2026!")
        resp = self.client.post(reverse("accounts:login"), {"username": "A@B.ir", "password": "Atr-Majd-2026!"})
        self.assertRedirects(resp, reverse("accounts:profile"))
        bad = self.client_class().post(reverse("accounts:login"), {"username": "a@b.ir", "password": "wrong"})
        self.assertContains(bad, "اشتباه است")

    def test_profile_requires_login(self):
        resp = self.client.get(reverse("accounts:profile"))
        self.assertRedirects(resp, reverse("accounts:login") + "?next=" + reverse("accounts:profile"))
