"""Factoryهای factory-boy برای تست‌های جدید (تست‌های قدیمی از core.tests.factories استفاده می‌کنند)."""

import factory
from factory.django import DjangoModelFactory

from apps.catalog.models import Brand, Collection, Product, ProductVariant, ScentFamily
from apps.reviews.models import Review

GIF = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"


class BrandFactory(DjangoModelFactory):
    class Meta:
        model = Brand
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"برند {n}")
    slug = factory.Sequence(lambda n: f"brand-{n}")


class ScentFactory(DjangoModelFactory):
    class Meta:
        model = ScentFamily
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"رایحه {n}")
    slug = factory.Sequence(lambda n: f"scent-{n}")


class CollectionFactory(DjangoModelFactory):
    class Meta:
        model = Collection

    name = factory.Sequence(lambda n: f"کالکشن {n}")
    slug = factory.Sequence(lambda n: f"col-{n}")
    image = factory.django.ImageField(from_func=lambda **kw: __import__("io").BytesIO(GIF), filename="c.gif")


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Sequence(lambda n: f"عطر {n}")
    slug = factory.Sequence(lambda n: f"perfume-{n}")
    brand = factory.SubFactory(BrandFactory)
    scent = factory.SubFactory(ScentFactory)
    short_description = "توضیح کوتاه"
    description = "توضیح کامل"
    notes_top = "برگاموت"
    notes_middle = "رز"
    notes_base = "مشک"
    image = factory.django.ImageField(from_func=lambda **kw: __import__("io").BytesIO(GIF), filename="p.gif")


class VariantFactory(DjangoModelFactory):
    class Meta:
        model = ProductVariant

    product = factory.SubFactory(ProductFactory)
    size_ml = 50
    price = 1_000_000
    stock = 10


class ReviewFactory(DjangoModelFactory):
    class Meta:
        model = Review

    product = factory.SubFactory(ProductFactory)
    name = "کاربر"
    rating = 5
    text = "عالی"
    is_approved = True
