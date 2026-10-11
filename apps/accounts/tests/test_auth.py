from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.core.tests.factories import ShopTestCase

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

    def test_login_and_register_are_separate_pages(self):
        login_page = self.client.get(reverse("accounts:login") + "?next=/cart/")
        self.assertContains(login_page, 'name="username"')
        self.assertNotContains(login_page, 'name="password1"')
        self.assertContains(login_page, reverse("accounts:register") + "?next=/cart/")
        register_page = self.client.get(reverse("accounts:register") + "?next=/cart/")
        self.assertContains(register_page, 'name="password1"')
        self.assertNotContains(register_page, 'name="username"')
        self.assertContains(register_page, 'name="next" value="/cart/"')
        self.assertContains(register_page, reverse("accounts:login") + "?next=/cart/")

    def test_register_keeps_next_and_ignores_foreign_next(self):
        data = {"first_name": "a", "last_name": "b", "password1": "Atr-Majd-2026!", "password2": "Atr-Majd-2026!"}
        resp = self.client.post(reverse("accounts:register"), {**data, "email": "n1@b.ir", "next": "/cart/"})
        self.assertRedirects(resp, "/cart/", fetch_redirect_response=False)
        self.client.logout()
        page = self.client.get(reverse("accounts:register") + "?next=https://evil.example/")
        self.assertNotContains(page, "evil.example")

    def test_register_page_redirects_signed_in_user(self):
        User.objects.create_user("a@b.ir", "Atr-Majd-2026!")
        self.client.login(username="a@b.ir", password="Atr-Majd-2026!")
        self.assertRedirects(self.client.get(reverse("accounts:register")), reverse("accounts:profile"))
