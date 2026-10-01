from django.contrib import admin

from .models import WishlistItem


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ["user", "product", "created_at"]
    list_filter = ["product__store"]
    search_fields = ["user__email", "product__name"]
    raw_id_fields = ["user", "product"]
