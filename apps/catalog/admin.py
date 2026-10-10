from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Attribute, AttributeValue, BackInStockRequest, Brand, Category, Collection, FragranceNote, Product, ProductImage, ProductNote,
    ProductVariant, ScentFamily, StockMovement, Tag,
)
from . import inventory
from .profile import Occasion, Season


@admin.register(Brand, ScentFamily)
class SimpleAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    list_filter = ["store"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ["name", "order", "is_wide"]
    list_filter = ["store"]
    list_editable = ["order", "is_wide"]
    prepopulated_fields = {"slug": ["name"]}


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


class NoteInline(admin.TabularInline):
    model = ProductNote
    extra = 1
    autocomplete_fields = ["note"]


class ImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductAdminForm(forms.ModelForm):
    seasons = forms.MultipleChoiceField(label="فصل مناسب", choices=Season.choices, required=False,
                                        widget=forms.CheckboxSelectMultiple)
    occasions = forms.MultipleChoiceField(label="موقعیت مناسب", choices=Occasion.choices, required=False,
                                          widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Product
        fields = "__all__"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ["thumb", "name", "kind", "brand", "scent", "collection", "is_active", "is_featured"]
    list_display_links = ["thumb", "name"]
    list_filter = ["store", "kind", "is_active", "is_featured", "brand", "scent", "collection"]
    list_editable = ["is_active", "is_featured"]
    search_fields = ["name", "short_description", "notes__note__name"]
    filter_horizontal = ["categories", "tags", "attribute_values"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [VariantInline, NoteInline, ImageInline]

    def save_formset(self, request, form, formset, change):
        """تغییر موجودی از پنل → از سرویس inventory تا در دفتر موجودی ثبت شود."""
        if formset.model is not ProductVariant:
            return super().save_formset(request, form, formset, change)
        targets = {}
        for f in formset.forms:
            if f.instance.pk and "stock" in f.changed_data and not f.cleaned_data.get("DELETE"):
                targets[f.instance.pk] = f.cleaned_data["stock"]
                f.instance.stock = f.initial["stock"]
        instances = formset.save()
        for variant in instances:
            if variant.pk in targets:
                inventory.set_stock(variant, targets[variant.pk], user=request.user, note="ویرایش از پنل مدیریت")
            elif variant.stock and not variant.movements.exists():
                inventory.record_initial(variant, user=request.user)
        for variant in formset.queryset.filter(pk__in=targets).exclude(pk__in=[v.pk for v in instances]):
            inventory.set_stock(variant, targets[variant.pk], user=request.user, note="ویرایش از پنل مدیریت")

    fieldsets = (
        (None, {"fields": ("store", "name", "slug", "brand", "scent", "collection", "image", "is_active", "is_featured")}),
        ("توضیحات", {"fields": ("short_description", "description")}),
        ("طبقه‌بندی", {"fields": ("categories", "tags", "attribute_values")}),
        ("سئو", {"fields": ("meta_title", "meta_description", "noindex"), "classes": ("collapse",)}),
    )

    @admin.display(description="تصویر")
    def thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width:48px;height:48px;object-fit:cover">', obj.image.url)
        return "—"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["__str__", "order", "is_active"]
    list_filter = ["store", "is_active"]
    list_editable = ["order", "is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Tag, FragranceNote)
class TaxonomyAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    list_filter = ["store"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}


class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 1
    prepopulated_fields = {"slug": ["value"]}


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ["name", "is_filterable", "order"]
    list_filter = ["store"]
    list_editable = ["is_filterable", "order"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [AttributeValueInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ["created_at", "variant", "change", "reason", "reference", "created_by"]
    list_filter = ["reason"]
    search_fields = ["reference", "variant__product__name"]
    readonly_fields = [f.name for f in StockMovement._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BackInStockRequest)
class BackInStockRequestAdmin(admin.ModelAdmin):
    list_display = ["variant", "phone", "created_at", "notified_at"]
    list_filter = [("notified_at", admin.EmptyFieldListFilter)]
    search_fields = ["phone", "variant__product__name"]
    raw_id_fields = ["variant", "user"]
    readonly_fields = ["created_at", "notified_at"]
