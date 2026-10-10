"""ورود/خروج Excel و CSV محصولات و تغییر گروهی قیمت."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.catalog import bulk
from apps.catalog.models import PriceChangeBatch, Product, ProductVariant, StockMovement
from apps.catalog.tests.factories import BrandFactory, ProductFactory, VariantFactory
from apps.core import spreadsheet

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())


@pytest.fixture
def staff(client):
    user = User.objects.create_user(email="stock@example.com", password="x-Strong-123", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="change_product"))
    client.force_login(user)
    return user


@pytest.fixture
def catalog(store):
    royal = BrandFactory(name="رویال عود", slug="royal")
    oud = ProductFactory(name="عود رازآلود", slug="mystic-oud", brand=royal)
    VariantFactory(product=oud, size_ml=50, price=5_200_000, stock=4)
    VariantFactory(product=oud, size_ml=100, price=8_300_000, stock=2)
    rose = ProductFactory(name="شکوفه", slug="rose")
    VariantFactory(product=rose, size_ml=50, price=3_200_000, stock=9)
    return {"oud": oud, "rose": rose, "royal": royal}


def test_xlsx_roundtrip_with_persian_text_and_formula_guard():
    rows = [["نام", "قیمت", "یادداشت"], ["عود رازآلود", 5200000, "=HYPERLINK(1)"], ["شکوفه", 3200000, ""]]
    table = spreadsheet.read_table("x.xlsx", spreadsheet.write_xlsx(rows))
    assert table[0] == ["نام", "قیمت", "یادداشت"]
    assert table[1] == ["عود رازآلود", "5200000", "=HYPERLINK(1)"]  # ذخیره با ' و خواندن بدون آن
    assert table[2][:2] == ["شکوفه", "3200000"]


def test_csv_reading_with_bom_and_semicolon():
    data = "﻿شناسه محصول;حجم (میل);قیمت (تومان)\nrose;50;۳٬۵۰۰٬۰۰۰\n".encode()
    assert spreadsheet.read_table("p.csv", data) == [["شناسه محصول", "حجم (میل)", "قیمت (تومان)"],
                                                     ["rose", "50", "۳٬۵۰۰٬۰۰۰"]]


def test_reject_bad_files():
    with pytest.raises(spreadsheet.SpreadsheetError):
        spreadsheet.read_table("x.pdf", b"%PDF")
    with pytest.raises(spreadsheet.SpreadsheetError):
        spreadsheet.read_table("x.xlsx", b"PK not a zip")


def test_import_plan_and_apply(store, catalog, staff):
    header = [label for _, label in bulk.COLUMNS]
    table = [header,
             ["mystic-oud", "", "", "", "", "50", "۵٬۵۰۰٬۰۰۰", "10", "", ""],       # قیمت و موجودی
             ["mystic-oud", "", "", "", "", "100", "8300000", "2", "", ""],          # بدون تغییر
             ["mystic-oud", "", "", "", "", "30", "2900000", "5", "", ""],           # حجم جدید
             ["new-musk", "مشک سفید", "عطر", "برند تازه", "گلی", "50", "3100000", "7", "بله", "نرم و تمیز"],
             ["new-musk", "", "", "", "", "100", "4900000", "", "", ""],             # حجم دوم محصول جدید
             ["ghost", "", "", "", "", "50", "1000", "", "", ""],                    # محصول جدید ناقص
             ["rose", "", "", "", "", "50", "abc", "", "", ""]]                      # عدد نامعتبر
    plan = bulk.plan_import(store, table)
    assert [r.action for r in plan.rows] == ["update", "unchanged", "new_variant", "new_product", "new_variant",
                                             "error", "error"]
    counts = bulk.apply_import(store, plan, user=staff)
    assert counts == {"updated": 1, "new_products": 1, "new_variants": 2, "stock": 1, "prices": 1}
    v50 = ProductVariant.objects.get(product=catalog["oud"], size_ml=50)
    assert (v50.price, v50.stock) == (5_500_000, 10)
    assert v50.movements.latest("pk").reason == StockMovement.Reason.IMPORT
    assert ProductVariant.objects.get(product=catalog["oud"], size_ml=30).stock == 5
    musk = Product.objects.get(slug="new-musk")
    assert not musk.is_active and musk.brand.name == "برند تازه" and musk.scent.name == "گلی" and musk.image
    assert sorted(musk.variants.values_list("size_ml", "price")) == [(50, 3_100_000), (100, 4_900_000)]
    batch = PriceChangeBatch.objects.get()
    assert batch.changes == [[v50.pk, 5_200_000, 5_500_000]]


def test_export_contains_all_variants(client, store, catalog, staff):
    response = client.get(reverse("builder:products_export"))
    assert response["Content-Type"].startswith("application/vnd.openxmlformats")
    table = spreadsheet.read_table("p.xlsx", response.content)
    assert table[0][0] == "شناسه محصول" and len(table) == 4
    assert ["mystic-oud", "عود رازآلود", "عطر", "رویال عود"] == next(r for r in table if r[0] == "mystic-oud")[:4]
    csv_response = client.get(reverse("builder:products_export"), {"format": "csv"})
    assert csv_response.content.startswith("﻿".encode())


def test_import_views_preview_then_confirm(client, store, catalog, staff):
    rows = list(bulk.export_rows(store))
    next(r for r in rows if r[0] == "mystic-oud" and r[5] == 50)[6] = 6_000_000
    upload = SimpleUploadedFile("p.xlsx", spreadsheet.write_xlsx(rows))
    preview = client.post(reverse("builder:products_import"), {"file": upload})
    assert preview.status_code == 200 and preview.context["counts"]["update"] == 1
    assert ProductVariant.objects.get(product=catalog["oud"], size_ml=50).price == 5_200_000  # هنوز اعمال نشده
    client.post(reverse("builder:products_import_confirm"), {"token": preview.context["token"]})
    assert ProductVariant.objects.get(product=catalog["oud"], size_ml=50).price == 6_000_000
    again = client.post(reverse("builder:products_import_confirm"), {"token": preview.context["token"]})
    assert again.status_code == 302  # توکن یک‌بارمصرف


def test_price_rule():
    assert bulk.PriceRule("percent", Decimal(15), 10_000).apply(5_200_000) == 5_980_000
    assert bulk.PriceRule("percent", Decimal(-10), 0).apply(3_333_333) == 3_000_000
    assert bulk.PriceRule("amount", Decimal(250_000), 100_000).apply(3_200_000) == 3_500_000
    assert bulk.PriceRule("percent", Decimal(-99), 0).apply(1_500) == 1000  # کف قیمت


def test_bulk_price_preview_apply_and_revert(client, store, catalog, staff):
    params = {"direction": "up", "mode": "percent", "value": "۱۵", "rounding": "10000", "brands": [catalog["royal"].pk]}
    preview = client.get(reverse("builder:products_prices"), params)
    assert preview.status_code == 200 and preview.context["total"] == 2  # فقط برند رویال
    assert ProductVariant.objects.get(product=catalog["oud"], size_ml=50).price == 5_200_000
    client.post(reverse("builder:products_prices"), {**params, "confirm": "1"})
    assert ProductVariant.objects.get(product=catalog["oud"], size_ml=50).price == 5_980_000
    assert ProductVariant.objects.get(product=catalog["rose"]).price == 3_200_000
    batch = PriceChangeBatch.objects.get()
    assert "رویال عود" in batch.description and "+15٪" in batch.description
    # یک حجم بعداً دستی عوض شده: بازگرداندن آن را دست نمی‌زند
    ProductVariant.objects.filter(product=catalog["oud"], size_ml=100).update(price=9_999_000)
    client.post(reverse("builder:products_price_revert", args=[batch.pk]))
    assert ProductVariant.objects.get(product=catalog["oud"], size_ml=50).price == 5_200_000
    assert ProductVariant.objects.get(product=catalog["oud"], size_ml=100).price == 9_999_000
    batch.refresh_from_db()
    assert batch.reverted_at is not None


def test_bulk_price_validation(client, store, catalog, staff):
    response = client.get(reverse("builder:products_prices"), {"direction": "down", "mode": "percent", "value": "100",
                                                                "rounding": "0"})
    assert response.status_code == 422
