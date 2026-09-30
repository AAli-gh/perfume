from django.contrib import admin
from django.utils.html import format_html

from .models import Brand, Collection, Product, ProductImage, ProductVariant, Review, ScentFamily


@admin.register(Brand, ScentFamily)
class SimpleAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ["name", "order", "is_wide"]
    list_editable = ["order", "is_wide"]
    prepopulated_fields = {"slug": ["name"]}


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


class ImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["thumb", "name", "brand", "scent", "collection", "is_active", "is_featured"]
    list_display_links = ["thumb", "name"]
    list_filter = ["is_active", "is_featured", "brand", "scent", "collection"]
    list_editable = ["is_active", "is_featured"]
    search_fields = ["name", "short_description", "notes_top", "notes_middle", "notes_base"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [VariantInline, ImageInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "brand", "scent", "collection", "image", "is_active", "is_featured")}),
        ("توضیحات", {"fields": ("short_description", "description")}),
        ("نت‌های رایحه", {"fields": ("notes_top", "notes_middle", "notes_base")}),
    )

    @admin.display(description="تصویر")
    def thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width:48px;height:48px;object-fit:cover">', obj.image.url)
        return "—"


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["name", "product", "rating", "is_approved", "created_at"]
    list_filter = ["is_approved", "rating"]
    list_editable = ["is_approved"]
    search_fields = ["name", "text", "product__name"]
    actions = ["approve"]

    @admin.action(description="تأیید نظرات انتخاب‌شده")
    def approve(self, request, queryset):
        queryset.update(is_approved=True)
