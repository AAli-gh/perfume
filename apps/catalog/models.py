from django.db import models
from django.db.models import Avg, Count, Min, Q
from django.urls import reverse

from apps.core.models import StoreOwned, StoreQuerySet


class Brand(StoreOwned):
    name = models.CharField("نام", max_length=100)
    slug = models.SlugField("نامک", allow_unicode=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        verbose_name = "برند"
        verbose_name_plural = "برندها"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="catalog_brand_unique_slug_per_store"),
        ]

    def __str__(self):
        return self.name


class ScentFamily(StoreOwned):
    name = models.CharField("نام", max_length=100)
    slug = models.SlugField("نامک", allow_unicode=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["id"]
        verbose_name = "خانواده رایحه"
        verbose_name_plural = "خانواده‌های رایحه"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="catalog_scentfamily_unique_slug_per_store"),
        ]

    def __str__(self):
        return self.name


class Collection(StoreOwned):
    name = models.CharField("نام", max_length=150)
    slug = models.SlugField("نامک", allow_unicode=True)
    tagline = models.CharField("شعار", max_length=250, blank=True)
    image = models.ImageField("تصویر", upload_to="collections/")
    is_wide = models.BooleanField("نمایش عریض", default=False)
    order = models.PositiveSmallIntegerField("ترتیب", default=0)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "کالکشن"
        verbose_name_plural = "کالکشن‌ها"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="catalog_collection_unique_slug_per_store"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"{reverse('catalog:shop')}?collection={self.slug}"


class ProductQuerySet(StoreQuerySet):
    def active(self):
        return self.filter(is_active=True)

    def with_stats(self):
        """قیمت پایه (کمترین قیمت حجم‌ها)، میانگین امتیاز و تعداد نظرات تأییدشده."""
        approved = Q(reviews__is_approved=True)
        return self.annotate(
            min_price=Min("variants__price"),
            rating_avg=Avg("reviews__rating", filter=approved),
            review_count=Count("reviews", filter=approved, distinct=True),
        )


class Product(StoreOwned):
    name = models.CharField("نام", max_length=150)
    slug = models.SlugField("نامک", allow_unicode=True, max_length=160)
    brand = models.ForeignKey(Brand, verbose_name="برند", on_delete=models.PROTECT, related_name="products")
    scent = models.ForeignKey(ScentFamily, verbose_name="خانواده رایحه", on_delete=models.PROTECT, related_name="products")
    collection = models.ForeignKey(
        Collection, verbose_name="کالکشن", on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    short_description = models.CharField("توضیح کوتاه", max_length=400)
    description = models.TextField("توضیحات کامل")
    notes_top = models.CharField("نت آغازین", max_length=200)
    notes_middle = models.CharField("نت میانی", max_length=200)
    notes_base = models.CharField("نت پایه", max_length=200)
    image = models.ImageField("تصویر اصلی", upload_to="products/")
    is_active = models.BooleanField("فعال", default=True)
    is_featured = models.BooleanField("ویژه", default=False)
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="catalog_product_unique_slug_per_store"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:product", args=[self.slug])

    @property
    def default_variant(self):
        variants = [v for v in self.variants.all() if v.stock > 0] or list(self.variants.all())
        return min(variants, key=lambda v: v.price) if variants else None

    @property
    def in_stock(self):
        return any(v.stock > 0 for v in self.variants.all())


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants", verbose_name="محصول")
    size_ml = models.PositiveSmallIntegerField("حجم (میلی‌لیتر)")
    price = models.PositiveIntegerField("قیمت (تومان)")
    stock = models.PositiveIntegerField("موجودی", default=0)

    class Meta:
        ordering = ["size_ml"]
        unique_together = [("product", "size_ml")]
        verbose_name = "حجم / قیمت"
        verbose_name_plural = "حجم‌ها و قیمت‌ها"

    def __str__(self):
        return f"{self.product.name} — {self.size_ml} میل"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images", verbose_name="محصول")
    image = models.ImageField("تصویر", upload_to="products/gallery/")
    order = models.PositiveSmallIntegerField("ترتیب", default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "تصویر گالری"
        verbose_name_plural = "گالری تصاویر"
