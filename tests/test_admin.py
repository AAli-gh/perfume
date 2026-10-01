"""همه صفحات لیست و افزودن Admin برای مدیر کل باز می‌شوند (smoke test)."""

import pytest
from django.contrib import admin
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("model", list(admin.site._registry), ids=lambda m: m._meta.label)
def test_admin_pages_render(admin_client, admin_user, rf, model):
    meta = model._meta
    assert admin_client.get(reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist")).status_code == 200
    request = rf.get("/")
    request.user = admin_user
    expected = 200 if admin.site._registry[model].has_add_permission(request) else 403  # مثلاً دفتر موجودی فقط‌خواندنی است
    assert admin_client.get(reverse(f"admin:{meta.app_label}_{meta.model_name}_add")).status_code == expected
