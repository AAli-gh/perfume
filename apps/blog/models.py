from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import SeoFields, StoreOwned, StoreQuerySet


class Category(StoreOwned):
    name = models.CharField("نام", max_length=100)
    slug = models.SlugField("نامک", allow_unicode=True)

    objects = StoreQuerySet.as_manager()

    class Meta:
        ordering = ["id"]
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="blog_category_unique_slug_per_store"),
        ]

    def __str__(self):
        return self.name


class PostQuerySet(StoreQuerySet):
    def published(self):
        return self.filter(is_published=True, published_at__lte=timezone.now())


class Post(StoreOwned, SeoFields):
    title = models.CharField("عنوان", max_length=200)
    slug = models.SlugField("نامک", allow_unicode=True, max_length=210)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="posts", verbose_name="دسته‌بندی")
    cover = models.ImageField("تصویر شاخص", upload_to="blog/")
    excerpt = models.CharField("خلاصه", max_length=400)
    body = models.TextField("متن", help_text="هر پاراگراف را با یک خط خالی جدا کنید. برای تیتر، خط را با ## شروع کنید.")
    is_published = models.BooleanField("منتشر شده", default=True)
    published_at = models.DateTimeField("تاریخ انتشار", default=timezone.now)
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at"]
        verbose_name = "مقاله"
        verbose_name_plural = "مقالات"
        constraints = [
            models.UniqueConstraint(fields=["store", "slug"], name="blog_post_unique_slug_per_store"),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog:detail", args=[self.slug])
