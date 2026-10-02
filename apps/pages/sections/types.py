"""انواع بخش‌های صفحه."""

from django import forms
from django.core.exceptions import ValidationError

from apps.blog.models import Post
from apps.catalog import selectors as catalog
from apps.catalog.models import Category, Collection
from apps.core.templatetags.majd import ICONS
from apps.marketing.forms import NewsletterForm
from apps.reviews.models import Review

from .base import LinkField, SectionForm, SectionType, validate_static_image
from .registry import register


def _text(label, initial="", required=False, max_length=300, textarea=False):
    widget = forms.Textarea(attrs={"rows": 3}) if textarea else None
    return forms.CharField(label=label, initial=initial, required=required, max_length=max_length, widget=widget)


def _limit(initial, max_value=24):
    return forms.IntegerField(label="تعداد", initial=initial, min_value=1, max_value=max_value)


class ListOfDictsField(forms.JSONField):
    """فهرست آیتم‌ها با کلیدهای مشخص و متن کوتاه (مثلاً ویژگی‌ها یا پرسش‌ها)."""

    def __init__(self, *, keys, max_items=12, choices=None, **kwargs):
        self.keys, self.max_items, self.key_choices = keys, max_items, choices or {}
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)

    def clean(self, value):
        value = super().clean(value) or []
        if not isinstance(value, list) or len(value) > self.max_items:
            raise ValidationError(f"فهرستی با حداکثر {self.max_items} آیتم")
        cleaned = []
        for item in value:
            if not isinstance(item, dict):
                raise ValidationError("هر آیتم باید یک شیء باشد")
            row = {}
            for key in self.keys:
                text = item.get(key, "")
                if not isinstance(text, str) or len(text) > 600:
                    raise ValidationError(f"مقدار «{key}» نامعتبر است")
                if key in self.key_choices and text not in self.key_choices[key]:
                    raise ValidationError(f"«{text}» برای {key} مجاز نیست")
                row[key] = text.strip()
            cleaned.append(row)
        return cleaned


# ---------- هیرو ----------

class HeroForm(SectionForm):
    title = _text("عنوان (هر خط جدید = شکست خط)", "دنیای رایحه‌های\nماندگار عطر مجد", required=True, textarea=True)
    subtitle = _text("زیرعنوان", "مجموعه‌ای از عطرهای لوکس و دست‌ساز که برای مسحور کردن حواس شما خلق شده‌اند.", textarea=True)
    cta_text = _text("متن دکمه", "همین حالا خرید کنید", max_length=60)
    cta_url = LinkField(label="پیوند دکمه", initial="/shop/")
    image_static = forms.CharField(label="تصویر پوسته", initial="img/hero-shop.jpg", required=False,
                                   validators=[validate_static_image], max_length=200)
    large = forms.BooleanField(label="هیرو بزرگ", initial=True, required=False)


@register
class HeroSection(SectionType):
    key, label, icon, form_class = "hero", "هیرو (بنر اصلی)", "diamond", HeroForm
    full_bleed = True
    uses_image = True

    def get_context(self, settings, *, request, section=None):
        return {**settings, "image_url": self.image_url(section, settings)}


# ---------- ویژگی‌ها ----------

class FeaturesForm(SectionForm):
    items = ListOfDictsField(
        label="آیتم‌ها", keys=("icon", "title", "text"), max_items=8, choices={"icon": set(ICONS)},
        initial=[
            {"icon": "truck", "title": "ارسال سریع", "text": "به سراسر ایران"},
            {"icon": "shield-check", "title": "ضمانت اصالت", "text": "۱۰۰٪ اورجینال"},
            {"icon": "gift", "title": "بسته‌بندی هدیه", "text": "رایگان برای همه سفارش‌ها"},
            {"icon": "headset", "title": "مشاوره رایحه", "text": "همه روزه ۱۰ تا ۲۱"},
        ],
    )


@register
class FeaturesSection(SectionType):
    key, label, icon, form_class = "features", "ویژگی‌ها و مزایا", "shield-check", FeaturesForm

    def is_visible(self, context):
        return bool(context["items"])


# ---------- فهرست‌های محصول ----------

class ProductListForm(SectionForm):
    title = _text("عنوان", "پرفروش‌ترین عطرها", required=True)
    link_text = _text("متن پیوند", "مشاهده فروشگاه ←", max_length=60)
    link_url = LinkField(label="پیوند", initial="/shop/")
    limit = _limit(8)


@register
class BestSellersSection(SectionType):
    key, label, icon, form_class = "best_sellers", "پرفروش‌ترین‌ها", "flame", ProductListForm

    def get_context(self, settings, *, request, section=None):
        return {**settings, "products": catalog.best_sellers(request.store, limit=settings["limit"])}

    def is_visible(self, context):
        return bool(context["products"])


class FeaturedForm(ProductListForm):
    title = _text("عنوان", "محصولات ویژه", required=True)


@register
class FeaturedProductsSection(SectionType):
    key, label, icon, form_class = "featured_products", "محصولات ویژه", "crown", FeaturedForm
    template = "sections/best_sellers.html"  # همان چیدمان اسلایدر

    def get_context(self, settings, *, request, section=None):
        products = catalog.listable_products(request.store).filter(is_featured=True).order_by("-created_at")
        return {**settings, "products": products[: settings["limit"]]}

    def is_visible(self, context):
        return bool(context["products"])


# ---------- کالکشن‌ها و دسته‌ها ----------

class CollectionsForm(SectionForm):
    title = _text("عنوان", "کالکشن‌های ویژه", required=True)
    link_text = _text("متن پیوند", "مشاهده همه ←", max_length=60)
    link_url = LinkField(label="پیوند", initial="/collections/")
    limit = _limit(3, 12)
    show_count = forms.BooleanField(label="نمایش تعداد عطرهای هر کالکشن", initial=False, required=False)


@register
class CollectionsSection(SectionType):
    key, label, icon, form_class = "collections", "کالکشن‌ها", "grid", CollectionsForm

    def get_context(self, settings, *, request, section=None):
        if settings["show_count"]:
            collections = catalog.collections_with_counts(request.store)
        else:
            collections = Collection.objects.for_store(request.store).order_by(*Collection._meta.ordering)
        return {**settings, "collections": collections[: settings["limit"]]}

    def is_visible(self, context):
        return bool(context["collections"])


class CategoriesForm(SectionForm):
    title = _text("عنوان", "دسته‌بندی‌ها", required=True)
    limit = _limit(6, 12)


@register
class CategoriesSection(SectionType):
    key, label, icon, form_class = "categories", "دسته‌بندی‌ها", "list", CategoriesForm

    def get_context(self, settings, *, request, section=None):
        roots = Category.objects.for_store(request.store).filter(parent=None, is_active=True)
        return {**settings, "categories": roots.order_by(*Category._meta.ordering)[: settings["limit"]]}

    def is_visible(self, context):
        return bool(context["categories"])


# ---------- بنر تبلیغاتی ----------

class BannerForm(SectionForm):
    title = _text("عنوان", "هنر عطرسازی", required=True)
    text = _text("متن", "ما روغن‌های اسانسی کمیاب و عصاره‌های طبیعی را از گوشه و کنار جهان گرد هم می‌آوریم؛ از زعفران خراسان و گل محمدی کاشان تا عود اصیل شرق دور، تا عطری بسازیم که روایتگر داستان شما باشد.", textarea=True, max_length=1000)
    cta_text = _text("متن دکمه", "داستان ما را بخوانید", max_length=60)
    cta_url = LinkField(label="پیوند دکمه", initial="/about/")
    image_static = forms.CharField(label="تصویر پوسته", initial="img/about-art.jpg", required=False,
                                   validators=[validate_static_image], max_length=200)
    image_alt = _text("متن جایگزین تصویر", "عطرساز در حال ساخت عطر", max_length=150)


@register
class BannerSection(SectionType):
    key, label, icon, form_class = "banner", "بنر تبلیغاتی", "gift", BannerForm
    uses_image = True

    def get_context(self, settings, *, request, section=None):
        return {**settings, "image_url": self.image_url(section, settings)}


# ---------- نظرات مشتریان ----------

class TestimonialsForm(SectionForm):
    title = _text("عنوان", "نظر مشتریان ما", required=True)
    limit = _limit(3, 12)


@register
class TestimonialsSection(SectionType):
    key, label, icon, form_class = "testimonials", "نظرات مشتریان", "user", TestimonialsForm

    def get_context(self, settings, *, request, section=None):
        reviews = (
            Review.objects.filter(product__store=request.store, product__is_active=True, is_approved=True, rating__gte=4)
            .select_related("product").order_by("-rating", "-created_at")
        )
        return {**settings, "reviews": reviews[: settings["limit"]]}

    def is_visible(self, context):
        return bool(context["reviews"])


# ---------- مجله ----------

class BlogForm(SectionForm):
    title = _text("عنوان", "از مجله عطر مجد", required=True)
    link_text = _text("متن پیوند", "همه مقالات ←", max_length=60)
    link_url = LinkField(label="پیوند", initial="/blog/")
    limit = _limit(2, 12)


@register
class BlogSection(SectionType):
    key, label, icon, form_class = "blog", "مقالات مجله", "list", BlogForm

    def get_context(self, settings, *, request, section=None):
        posts = Post.objects.for_store(request.store).published().select_related("category")
        return {**settings, "posts": posts[: settings["limit"]]}

    def is_visible(self, context):
        return bool(context["posts"])


# ---------- خبرنامه ----------

class NewsletterSectionForm(SectionForm):
    title = _text("عنوان", "عضویت در خبرنامه", required=True)
    text = _text("متن", "از تازه‌ترین عطرها، کالکشن‌های محدود و تخفیف‌های ویژه باخبر شوید.", textarea=True)


@register
class NewsletterSection(SectionType):
    key, label, icon, form_class = "newsletter", "خبرنامه", "mail", NewsletterSectionForm

    def get_context(self, settings, *, request, section=None):
        return {**settings, "form": NewsletterForm()}


# ---------- پرسش‌های متداول ----------

class FaqForm(SectionForm):
    title = _text("عنوان", "پرسش‌های متداول", required=True)
    items = ListOfDictsField(label="پرسش و پاسخ‌ها", keys=("question", "answer"), max_items=20, initial=[])


@register
class FaqSection(SectionType):
    key, label, icon, form_class = "faq", "پرسش‌های متداول", "alert", FaqForm

    def is_visible(self, context):
        return bool(context["items"])
