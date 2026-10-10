from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Case, Count, F, Min, Q, When
from django.urls import reverse
from django.utils import timezone

from apps.core.db import ListField
from apps.core.validators import image_upload
from apps.core.models import SeoFields, StoreOwned, StoreQuerySet

from .profile import Concentration, Gender, Kind, Occasion, Season, labels


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


class Collection(StoreOwned, SeoFields):
    name = models.CharField("نام", max_length=150)
    slug = models.SlugField("نامک", allow_unicode=True)
    tagline = models.CharField("شعار", max_length=250, blank=True)
    image = models.ImageField("تصویر", upload_to="collections/", validators=[image_upload])
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
        return reverse("catalog:collection", args=[self.slug])


class Category(StoreOwned, SeoFields):
    """دسته‌بندی درختی محصولات (مثلاً عطر ← عطر زنانه ← ادوپرفیوم)."""

    name = models.CharField("نام", max_length=120)
    slug = models.SlugField("نامک", allow_unicode=True, max_length=140)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children", verbose_name="دسته والد"
    )
    description = models.TextField("توضیحات", blank=True)
    order = models.PositiveSmallIntegerField("ترتیب", default=0)
    is_active = models.BooleanField("فعال", default=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="catalog_category_unique_slug_per_store"),
        ]

    def __str__(self):
        return " › ".join(c.name for c in self.ancestors(include_self=True))

    def get_absolute_url(self):
        return reverse("catalog:category", args=[self.slug])

    def ancestors(self, include_self=False):
        node, chain = (self if include_self else self.parent), []
        while node is not None and len(chain) < 20:  # محافظت در برابر حلقه
            chain.insert(0, node)
            node = node.parent
        return chain

    def descendant_ids(self):
        """شناسه خودش و همه زیرشاخه‌ها (برای فیلتر «همه محصولات این دسته»)."""
        ids, frontier = {self.pk}, [self.pk]
        while frontier:
            frontier = list(Category.objects.filter(parent_id__in=frontier).values_list("pk", flat=True))
            frontier = [i for i in frontier if i not in ids]
            ids.update(frontier)
        return ids

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.parent_id and self.pk and self.pk in {c.pk for c in self.parent.ancestors(include_self=True)}:
            raise ValidationError({"parent": "دسته نمی‌تواند زیرمجموعه خودش باشد."})
        if self.parent_id and self.parent.store_id != self.store_id:
            raise ValidationError({"parent": "دسته والد باید متعلق به همین فروشگاه باشد."})


class Tag(StoreOwned):
    name = models.CharField("نام", max_length=80)
    slug = models.SlugField("نامک", allow_unicode=True, max_length=100)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        verbose_name = "برچسب"
        verbose_name_plural = "برچسب‌ها"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="catalog_tag_unique_slug_per_store"),
        ]

    def __str__(self):
        return self.name


class FragranceNote(StoreOwned):
    """یک نت رایحه (مثلاً برگاموت، عود، مشک) — قابل استفاده در جستجو، فیلتر و پیشنهاد محصول."""

    name = models.CharField("نام", max_length=80)
    slug = models.SlugField("نامک", allow_unicode=True, max_length=100)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        verbose_name = "نت رایحه"
        verbose_name_plural = "نت‌های رایحه"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="catalog_fragrancenote_unique_slug_per_store"),
        ]

    def __str__(self):
        return self.name


class Attribute(StoreOwned):
    """ویژگی قابل فیلتر (مثلاً غلظت: ادوپرفیوم/ادوتویلت، جنسیت: زنانه/مردانه/یونیسکس)."""

    name = models.CharField("نام", max_length=80)
    slug = models.SlugField("نامک", allow_unicode=True, max_length=100)
    is_filterable = models.BooleanField("قابل فیلتر در فروشگاه", default=True)
    order = models.PositiveSmallIntegerField("ترتیب", default=0)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "ویژگی"
        verbose_name_plural = "ویژگی‌ها"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="catalog_attribute_unique_slug_per_store"),
        ]

    def __str__(self):
        return self.name


class AttributeValue(models.Model):
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE, related_name="values", verbose_name="ویژگی")
    value = models.CharField("مقدار", max_length=80)
    slug = models.SlugField("نامک", allow_unicode=True, max_length=100)
    order = models.PositiveSmallIntegerField("ترتیب", default=0)

    class Meta:
        ordering = ["attribute__order", "order", "value"]
        verbose_name = "مقدار ویژگی"
        verbose_name_plural = "مقادیر ویژگی"
        constraints = [
            models.UniqueConstraint(fields=["attribute", "slug"], name="catalog_attributevalue_unique_slug"),
        ]

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class ProductQuerySet(StoreQuerySet):
    def active(self):
        return self.filter(is_active=True)

    def perfumes(self):
        return self.filter(kind=Kind.PERFUME)

    def gift_boxes(self):
        return self.filter(kind=Kind.GIFT_BOX)

    def with_stats(self):
        """قیمت پایه (کمترین قیمت فعلی حجم‌ها، با احتساب حراج)، قیمت پیش از حراج، امتیاز و تعداد نظرات."""
        approved = Q(reviews__is_approved=True)
        return self.annotate(
            min_price=Min(effective_price("variants__")),
            min_regular_price=Min("variants__price"),
            rating_avg=Avg("reviews__rating", filter=approved),
            review_count=Count("reviews", filter=approved, distinct=True),
        )


class Product(StoreOwned, SeoFields):
    name = models.CharField("نام", max_length=150)
    slug = models.SlugField("نامک", allow_unicode=True, max_length=160)
    brand = models.ForeignKey(Brand, verbose_name="برند", on_delete=models.PROTECT, related_name="products")
    kind = models.CharField("نوع محصول", max_length=10, choices=Kind.choices, default=Kind.PERFUME, db_index=True)
    scent = models.ForeignKey(ScentFamily, verbose_name="خانواده رایحه", on_delete=models.PROTECT, related_name="products",
                              null=True, blank=True, help_text="برای عطرها الزامی است")
    collection = models.ForeignKey(
        Collection, verbose_name="کالکشن", on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    categories = models.ManyToManyField(Category, blank=True, related_name="products", verbose_name="دسته‌بندی‌ها")
    tags = models.ManyToManyField(Tag, blank=True, related_name="products", verbose_name="برچسب‌ها")
    attribute_values = models.ManyToManyField(
        AttributeValue, blank=True, related_name="products", verbose_name="ویژگی‌ها"
    )
    short_description = models.CharField("توضیح کوتاه", max_length=400)
    description = models.TextField("توضیحات کامل")
    image = models.ImageField("تصویر اصلی", upload_to="products/", validators=[image_upload])
    # مشخصات رایحه (اختیاری؛ برای مقایسه، «عطر مناسب من» و پیشنهادها)
    gift_capacity = models.PositiveSmallIntegerField(
        "گنجایش (تعداد شیشه عطر)", null=True, blank=True,
        help_text="فقط برای باکس هدیه؛ چند شیشه عطر داخل یک باکس جا می‌شود",
    )
    gender = models.CharField("مناسب برای", max_length=10, choices=Gender.choices, blank=True)
    concentration = models.CharField("غلظت", max_length=10, choices=Concentration.choices, blank=True)
    longevity = models.PositiveSmallIntegerField(
        "ماندگاری", null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="۱ (کمتر از ۲ ساعت) تا ۵ (بیش از ۸ ساعت)",
    )
    sillage = models.PositiveSmallIntegerField(
        "پخش بو", null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="۱ (نزدیک به پوست) تا ۵ (بسیار قوی)",
    )
    seasons = ListField(models.CharField(max_length=10, choices=Season.choices), verbose_name="فصل مناسب",
                         default=list, blank=True)
    occasions = ListField(models.CharField(max_length=10, choices=Occasion.choices), verbose_name="موقعیت مناسب",
                           default=list, blank=True)
    is_active = models.BooleanField("فعال", default=True)
    is_featured = models.BooleanField("ویژه", default=False)
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True)
    # ستون‌های جستجو (به‌صورت خودکار توسط catalog.search به‌روز می‌شوند)
    search_document = models.TextField(blank=True, default="", editable=False)
    search_vector = SearchVectorField(null=True, editable=False)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="catalog_product_unique_slug_per_store"),
        ]
        indexes = [
            GinIndex(fields=["search_vector"], name="catalog_product_search_vec"),
            GinIndex(fields=["search_document"], name="catalog_product_search_trgm", opclasses=["gin_trgm_ops"]),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:product", args=[self.slug])

    @property
    def default_variant(self):
        variants = [v for v in self.variants.all() if v.stock > 0] or list(self.variants.all())
        return min(variants, key=lambda v: v.current_price) if variants else None

    @property
    def in_stock(self):
        return any(v.stock > 0 for v in self.variants.all())

    @property
    def is_gift_box(self):
        return self.kind == Kind.GIFT_BOX

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.kind == Kind.PERFUME and not self.scent_id:
            raise ValidationError({"scent": "خانواده رایحه برای عطر الزامی است."})
        if self.kind == Kind.GIFT_BOX and not self.gift_capacity:
            raise ValidationError({"gift_capacity": "گنجایش باکس هدیه را وارد کنید."})

    @property
    def season_labels(self):
        return labels(Season, self.seasons)

    @property
    def occasion_labels(self):
        return labels(Occasion, self.occasions)

    @property
    def has_profile(self):
        return bool(self.gender or self.concentration or self.longevity or self.sillage or self.seasons or self.occasions)

    def notes_by_layer(self):
        """{"top": [نت‌ها], "heart": [...], "base": [...]} — با prefetch روی notes__note بدون کوئری اضافه."""
        layers = {layer: [] for layer in ProductNote.Layer.values}
        for link in sorted(self.notes.all(), key=lambda n: (n.order, n.pk)):
            layers[link.layer].append(link.note.name)
        return layers


class ProductNote(models.Model):
    """اتصال محصول به نت رایحه در یکی از سه لایه هرم بویایی."""

    class Layer(models.TextChoices):
        TOP = "top", "نت آغازین"
        HEART = "heart", "نت میانی"
        BASE = "base", "نت پایه"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="notes", verbose_name="محصول")
    note = models.ForeignKey(FragranceNote, on_delete=models.PROTECT, related_name="product_links", verbose_name="نت")
    layer = models.CharField("لایه", max_length=5, choices=Layer.choices)
    order = models.PositiveSmallIntegerField("ترتیب", default=0)

    class Meta:
        ordering = ["layer", "order", "id"]
        verbose_name = "نت محصول"
        verbose_name_plural = "هرم بویایی (نت‌ها)"
        constraints = [
            models.UniqueConstraint(fields=["product", "note", "layer"], name="catalog_productnote_unique"),
        ]

    def __str__(self):
        return f"{self.get_layer_display()}: {self.note}"


def sale_active(prefix="", now=None):
    """Q حجم‌هایی که همین الان حراج فعال دارند (قیمت حراج کمتر از قیمت اصلی و در بازه زمانی)."""
    now = now or timezone.now()
    return (Q(**{f"{prefix}sale_price__isnull": False}) & Q(**{f"{prefix}sale_price__lt": F(f"{prefix}price")})
            & (Q(**{f"{prefix}sale_starts_at__isnull": True}) | Q(**{f"{prefix}sale_starts_at__lte": now}))
            & (Q(**{f"{prefix}sale_ends_at__isnull": True}) | Q(**{f"{prefix}sale_ends_at__gt": now})))


def effective_price(prefix="", now=None):
    """قیمت فعلی در کوئری: قیمت حراج اگر فعال است، وگرنه قیمت اصلی."""
    return Case(When(sale_active(prefix, now), then=F(f"{prefix}sale_price")), default=F(f"{prefix}price"),
                output_field=models.PositiveIntegerField())


class SaleCampaign(StoreOwned):
    """حراج زمان‌دار گروهی از حجم‌ها (مثلاً «۲۰٪ تخفیف برند X تا پایان مهر»)."""

    name = models.CharField("عنوان حراج", max_length=100)
    percent = models.PositiveSmallIntegerField("درصد تخفیف", validators=[MinValueValidator(1), MaxValueValidator(90)])
    starts_at = models.DateTimeField("شروع", null=True, blank=True)
    ends_at = models.DateTimeField("پایان", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+", verbose_name="کاربر")
    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True)
    ended_at = models.DateTimeField("پایان دستی", null=True, blank=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "حراج زمان‌دار"
        verbose_name_plural = "حراج‌های زمان‌دار"

    def __str__(self):
        return self.name

    def status(self, now=None):
        now = now or timezone.now()
        if self.ended_at or (self.ends_at and self.ends_at <= now):
            return "ended"
        if self.starts_at and self.starts_at > now:
            return "scheduled"
        return "active"

    def get_status_display(self):
        return {"ended": "پایان‌یافته", "scheduled": "زمان‌بندی‌شده", "active": "فعال"}[self.status()]


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants", verbose_name="محصول")
    size_ml = models.PositiveSmallIntegerField("حجم (میلی‌لیتر)")
    price = models.PositiveIntegerField("قیمت (تومان)")
    stock = models.PositiveIntegerField("موجودی", default=0)
    low_stock_threshold = models.PositiveSmallIntegerField(
        "آستانه موجودی کم", null=True, blank=True,
        help_text="خالی = آستانه پیش‌فرض فروشگاه (تنظیمات فروشگاه)",
    )
    sale_price = models.PositiveIntegerField("قیمت حراج (تومان)", null=True, blank=True,
                                             help_text="خالی = بدون حراج؛ باید کمتر از قیمت اصلی باشد")
    sale_starts_at = models.DateTimeField("شروع حراج", null=True, blank=True, help_text="خالی = از همین حالا")
    sale_ends_at = models.DateTimeField("پایان حراج", null=True, blank=True, help_text="خالی = تا اطلاع بعدی")
    sale_campaign = models.ForeignKey(SaleCampaign, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="variants", verbose_name="حراج گروهی")

    class Meta:
        ordering = ["size_ml"]
        unique_together = [("product", "size_ml")]
        verbose_name = "حجم / قیمت"
        verbose_name_plural = "حجم‌ها و قیمت‌ها"

    def __str__(self):
        return f"{self.product.name} — {self.size_ml} میل"

    def is_on_sale(self, now=None):
        now = now or timezone.now()
        return (self.sale_price is not None and self.sale_price < self.price
                and (self.sale_starts_at is None or self.sale_starts_at <= now)
                and (self.sale_ends_at is None or self.sale_ends_at > now))

    @property
    def on_sale(self):
        return self.is_on_sale()

    @property
    def current_price(self):
        """قیمتی که مشتری الان می‌پردازد (سبد، سفارش، نمایش)."""
        return self.sale_price if self.is_on_sale() else self.price

    @property
    def discount_percent(self):
        return round((self.price - self.sale_price) * 100 / self.price) if self.is_on_sale() and self.price else 0

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.sale_price is not None and self.price is not None and self.sale_price >= self.price:
            raise ValidationError({"sale_price": "قیمت حراج باید کمتر از قیمت اصلی باشد."})
        if self.sale_starts_at and self.sale_ends_at and self.sale_ends_at <= self.sale_starts_at:
            raise ValidationError({"sale_ends_at": "پایان حراج باید بعد از شروع آن باشد."})


class BackInStockRequest(models.Model):
    """«موجود شد خبرم کن»: مشتری برای حجم ناموجود شماره می‌گذارد؛ با موجود شدن یک پیامک می‌گیرد."""

    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="stock_requests",
                                verbose_name="کالا")
    phone = models.CharField("موبایل", max_length=11)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="+", verbose_name="کاربر")
    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True)
    notified_at = models.DateTimeField("زمان اطلاع‌رسانی", null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "درخواست «موجود شد خبرم کن»"
        verbose_name_plural = "درخواست‌های «موجود شد خبرم کن»"
        constraints = [
            models.UniqueConstraint(fields=["variant", "phone"], condition=models.Q(notified_at__isnull=True),
                                    name="catalog_one_open_stock_request"),
        ]

    def __str__(self):
        return f"{self.variant} ← {self.phone}"


class StockMovement(models.Model):
    """دفتر موجودی: هر تغییر موجودی یک ردیف تغییرناپذیر دارد؛ جمع change هر حجم = موجودی فعلی آن.

    به سفارش با «reference» (شماره سفارش) اشاره می‌شود تا کاتالوگ به اپ سفارش وابسته نباشد.
    """

    class Reason(models.TextChoices):
        INITIAL = "initial", "موجودی اولیه"
        ADJUSTMENT = "adjustment", "اصلاح دستی"
        RESERVED = "reserved", "رزرو برای سفارش"
        RELEASED = "released", "آزادسازی رزرو / لغو سفارش"
        RESTOCK = "restock", "ورود کالا"
        RETURNED = "returned", "مرجوعی مشتری"
        IMPORT = "import", "ورود گروهی از فایل"

    variant = models.ForeignKey("ProductVariant", on_delete=models.CASCADE, related_name="movements", verbose_name="کالا")
    change = models.IntegerField("تغییر")
    reason = models.CharField("علت", max_length=12, choices=Reason.choices)
    reference = models.CharField("مرجع", max_length=40, blank=True, db_index=True, help_text="مثلاً شماره سفارش")
    note = models.CharField("یادداشت", max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="کاربر"
    )
    created_at = models.DateTimeField("زمان", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "گردش موجودی"
        verbose_name_plural = "گردش موجودی"

    def __str__(self):
        return f"{self.variant} {self.change:+d} ({self.get_reason_display()})"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images", verbose_name="محصول")
    image = models.ImageField("تصویر", upload_to="products/gallery/", validators=[image_upload])
    order = models.PositiveSmallIntegerField("ترتیب", default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "تصویر گالری"
        verbose_name_plural = "گالری تصاویر"


class PriceChangeBatch(StoreOwned):
    """یک تغییر گروهی قیمت (یا ورود از فایل) با قیمت قبلی هر حجم تا بتوان آن را برگرداند."""

    description = models.CharField("شرح", max_length=200)
    changes = models.JSONField("تغییرات", default=list, help_text="[[شناسه حجم، قیمت قبلی، قیمت جدید]، …]")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+", verbose_name="کاربر")
    created_at = models.DateTimeField("زمان", auto_now_add=True)
    reverted_at = models.DateTimeField("زمان بازگرداندن", null=True, blank=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "تغییر گروهی قیمت"
        verbose_name_plural = "تغییرهای گروهی قیمت"

    def __str__(self):
        return self.description

    @property
    def count(self):
        return len(self.changes)
