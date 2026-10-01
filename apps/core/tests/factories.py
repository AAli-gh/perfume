"""ساخت داده‌های آزمایشی کمینه برای تست‌ها."""

import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.catalog.models import Brand, Product, ProductVariant, ScentFamily
from apps.core.stores import get_default_store

GIF = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
MEDIA = tempfile.mkdtemp()


def img(name="x.gif"):
    return SimpleUploadedFile(name, GIF, content_type="image/gif")


def make_product(slug="oud", name="عود تست", price=1_000_000, stock=5, brand=None, scent=None, **extra):
    brand = brand or Brand.objects.get_or_create(slug="b1", defaults={"name": "برند"})[0]
    scent = scent or ScentFamily.objects.get_or_create(slug="woody", defaults={"name": "چوبی"})[0]
    p = Product.objects.create(
        slug=slug, name=name, brand=brand, scent=scent, image=img(),
        short_description="توضیح", description="توضیح کامل", notes_top="a", notes_middle="b", notes_base="c", **extra,
    )
    v50 = ProductVariant.objects.create(product=p, size_ml=50, price=price, stock=stock)
    v100 = ProductVariant.objects.create(product=p, size_ml=100, price=price * 2, stock=stock)
    return p, v50, v100


@override_settings(MEDIA_ROOT=MEDIA, DEBUG=True, ZARINPAL_MERCHANT_ID="")
class ShopTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # هزینه ارسال از Phase 2 در تنظیمات فروشگاه (دیتابیس) است، نه settings
        config = get_default_store().config
        config.shipping_cost, config.free_shipping_over = 100_000, 0
        config.save()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def htmx(self, method, url, data=None):
        return getattr(self.client, method)(url, data or {}, HTTP_HX_REQUEST="true")
