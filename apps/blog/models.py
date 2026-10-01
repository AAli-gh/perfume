from django.db import models
from django.urls import reverse
from django.utils import timezone


class Category(models.Model):
    name = models.CharField("نام", max_length=100)
    slug = models.SlugField("نامک", unique=True, allow_unicode=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"

    def __str__(self):
        return self.name


class PostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True, published_at__lte=timezone.now())


class Post(models.Model):
    title = models.CharField("عنوان", max_length=200)
    slug = models.SlugField("نامک", unique=True, allow_unicode=True, max_length=210)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="posts", verbose_name="دسته‌بندی")
    cover = models.ImageField("تصویر شاخص", upload_to="blog/")
    excerpt = models.CharField("خلاصه", max_length=400)
    body = models.TextField("متن", help_text="هر پاراگراف را با یک خط خالی جدا کنید. برای تیتر، خط را با ## شروع کنید.")
    is_published = models.BooleanField("منتشر شده", default=True)
    published_at = models.DateTimeField("تاریخ انتشار", default=timezone.now)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at"]
        verbose_name = "مقاله"
        verbose_name_plural = "مقالات"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog:detail", args=[self.slug])
