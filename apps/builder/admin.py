from django.contrib import admin

from .models import Revision


@admin.register(Revision)
class RevisionAdmin(admin.ModelAdmin):
    """تاریخچه انتشار فقط‌خواندنی است؛ بازگردانی از استودیو انجام می‌شود."""

    list_display = ["number", "store", "kind", "label", "created_by", "created_at"]
    list_filter = ["store", "kind"]
    readonly_fields = [f.name for f in Revision._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
