import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.catalog.models import SearchLog
from apps.catalog.search_log import report
from apps.catalog.tests.factories import ScentFactory, VariantFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def fresh(store):
    VariantFactory(price=3_400_000, product__scent=ScentFactory(slug="fresh", name="خنک و تازه"))


def test_searches_are_logged_grouped_and_deduped(client, store, fresh):
    client.get(reverse("catalog:shop"), {"q": "عطر خنک زیر سه تومن"})
    client.get(reverse("catalog:shop"), {"q": "عطر خنک زیر سه تومن"})        # همان نفر ← یک بار
    client.get(reverse("catalog:shop"), {"q": "عطر خنک زیر سه تومن", "page": 2})
    from django.test import Client

    Client(REMOTE_ADDR="10.0.0.2").get(reverse("catalog:shop"), {"q": "خنک کمتر از ۳ میلیون"})  # نفر دوم، همان خواسته
    client.get(reverse("catalog:shop"), {"q": "خنک"})                         # یک واژه، نتیجه دقیق
    assert SearchLog.objects.count() == 3
    log = SearchLog.objects.filter(raw="عطر خنک زیر سه تومن").get()
    assert not log.exact and log.results == 1 and "قیمت" in log.relaxed
    data = report(store)
    unmet = data["unmet"][0]
    assert unmet["people"] == 2 and "خنک و تازه" in unmet["intent"] and "۳ میلیون" in unmet["intent"]


def test_suggest_does_not_log(client, store, fresh):
    client.get(reverse("catalog:search_suggest"), {"q": "خنک"})
    assert not SearchLog.objects.exists()


def test_studio_search_report(client, store, fresh):
    client.get(reverse("catalog:shop"), {"q": "عطر خنک زیر سه تومن"})
    user = get_user_model().objects.create_user(email="an@example.com", password="x-Strong-123", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="view_order"))
    client.force_login(user)
    body = client.get(reverse("builder:searches")).content.decode()
    assert "۱ نفر" in body and "خنک و تازه" in body and "تقاضای بی‌پاسخ" in body
