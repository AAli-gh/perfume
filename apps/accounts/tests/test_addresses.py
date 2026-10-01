import pytest
from django.urls import reverse

from apps.accounts.models import Address, User
from apps.accounts.services import default_address, remember_address
from apps.catalog.tests.factories import VariantFactory
from apps.orders.forms import checkout_initial

pytestmark = pytest.mark.django_db

DATA = {"first_name": "علی", "last_name": "رضایی", "phone": "09121234567", "province": "تهران",
        "city": "تهران", "address": "خیابان آزادی", "postal_code": "1234567890"}


@pytest.fixture
def user():
    return User.objects.create_user("a@b.ir", "Atr-Majd-2026!", first_name="علی")


def test_remember_address_deduplicates_and_sets_default(user):
    first = remember_address(user, DATA)
    again = remember_address(user, DATA)
    assert first.pk == again.pk and Address.objects.count() == 1
    second = remember_address(user, {**DATA, "city": "کرج"})
    assert Address.objects.count() == 2
    assert default_address(user) == second
    assert Address.objects.filter(user=user, is_default=True).count() == 1


def test_anonymous_user_not_saved():
    from django.contrib.auth.models import AnonymousUser

    assert remember_address(AnonymousUser(), DATA) is None
    assert not Address.objects.exists()


def test_checkout_saves_and_prefills_address(client, user):
    client.force_login(user)
    variant = VariantFactory(stock=5)
    client.post(reverse("cart:add"), {"variant": variant.pk})
    client.post(reverse("orders:checkout"), {**DATA, "phone": "۰۹۱۲۱۲۳۴۵۶۷", "payment_method": "cod", "accept_terms": "on"})
    address = Address.objects.get(user=user)
    assert address.phone == "09121234567" and address.is_default
    initial = checkout_initial(user)
    assert initial["address"] == "خیابان آزادی" and initial["postal_code"] == "1234567890"


def test_profile_lists_addresses(client, user):
    remember_address(user, DATA)
    client.force_login(user)
    assert "خیابان آزادی" in client.get(reverse("accounts:profile")).content.decode()
