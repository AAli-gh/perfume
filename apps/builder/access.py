"""دسترسی استودیو: فقط کارکنان (is_staff) با مجوز Django مربوط به هر بخش.

مجوزها از سیستم استاندارد Django (گروه‌ها / مجوزهای کاربر در پنل مدیریت) خوانده می‌شوند:
- ظاهر و پوسته:   themes.change_themesettings
- ویرایش بخش‌ها:  pages.change_pagesection   (افزودن: pages.add_pagesection، حذف: pages.delete_pagesection)
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

THEME_PERM = "themes.change_themesettings"
SECTION_CHANGE_PERM = "pages.change_pagesection"
SECTION_ADD_PERM = "pages.add_pagesection"
SECTION_DELETE_PERM = "pages.delete_pagesection"
STUDIO_PERMS = (THEME_PERM, SECTION_CHANGE_PERM)


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
