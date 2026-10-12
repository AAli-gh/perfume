"""دسترسی استودیو: فقط کارکنان (is_staff) با مجوز Django مربوط به هر بخش.

مجوزها از سیستم استاندارد Django (گروه‌ها / مجوزهای کاربر در پنل مدیریت) خوانده می‌شوند:
- ظاهر و پوسته:   themes.change_themesettings
- ویرایش بخش‌ها:  pages.change_pagesection   (افزودن: pages.add_pagesection، حذف: pages.delete_pagesection)
- انتشار:         builder.publish_site        (ویرایشگر بدون این مجوز فقط پیش‌نویس می‌سازد)
- گزارش فروش، پیشخوان سفارش‌ها، چاپ فاکتور و گزارش جستجوها: orders.view_order
- رهگیری گروهی، مرجوعی و لغو بخشی سفارش:                   orders.change_order
- موجودی، ورود/خروج محصولات، تغییر قیمت و حراج:             catalog.change_product
- مشتریان:                                                  accounts.view_user (یادداشت: accounts.change_user)
- پیامک گروهی به مشتریان:                                   notifications.add_campaign
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

THEME_PERM = "themes.change_themesettings"
SECTION_CHANGE_PERM = "pages.change_pagesection"
SECTION_ADD_PERM = "pages.add_pagesection"
SECTION_DELETE_PERM = "pages.delete_pagesection"
PUBLISH_PERM = "builder.publish_site"  # انتشار، کنار گذاشتن تغییرات و بازگشت به نسخه قبلی
REPORTS_PERM = "orders.view_order"  # گزارش فروش، پیشخوان سفارش‌ها و چاپ فاکتور
ORDERS_PERM = "orders.change_order"  # ثبت گروهی کد رهگیری، مرجوعی و لغو بخشی
PRODUCTS_PERM = "catalog.change_product"  # موجودی، ورود/خروج محصولات، تغییر گروهی قیمت و حراج
CUSTOMERS_PERM = "accounts.view_user"  # فهرست و گروه‌های مشتریان، یادداشت (تغییر: accounts.change_user)
CAMPAIGN_PERM = "notifications.add_campaign"  # پیامک گروهی
STUDIO_PERMS = (THEME_PERM, SECTION_CHANGE_PERM, PUBLISH_PERM, REPORTS_PERM, PRODUCTS_PERM, CUSTOMERS_PERM)


def can_use_studio(user):
    return user.is_active and user.is_staff and any(user.has_perm(p) for p in STUDIO_PERMS)


def studio_required(*perms):
    """بدون ورود ← صفحه ورود؛ کاربر عادی یا کارمند بدون مجوز ← ۴۰۳."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not can_use_studio(user) or not all(user.has_perm(p) for p in perms):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
