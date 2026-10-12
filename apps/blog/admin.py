from django.contrib import admin

from apps.core.jalali import JalaliAdminMixin

from .models import Category, Post


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    list_filter = ["store"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Post)
class PostAdmin(JalaliAdminMixin, admin.ModelAdmin):
    list_display = ["title", "category", "is_published", "published_at"]
    list_filter = ["store", "is_published", "category"]
    search_fields = ["title", "excerpt", "body"]
    prepopulated_fields = {"slug": ["title"]}
    date_hierarchy = "published_at"
