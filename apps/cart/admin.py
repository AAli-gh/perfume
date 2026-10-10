from django.contrib import admin

from .models import SavedCart


@admin.register(SavedCart)
class SavedCartAdmin(admin.ModelAdmin):
    list_display = ["user", "quantity", "updated_at", "reminded_at"]
    list_filter = ["store", ("reminded_at", admin.EmptyFieldListFilter)]
    search_fields = ["user__email", "user__phone"]
    readonly_fields = ["store", "user", "items", "updated_at", "reminded_at"]

    def has_add_permission(self, request):
        return False
