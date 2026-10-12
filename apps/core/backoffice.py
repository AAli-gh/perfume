"""پنهان کردن پنل مدیریت و استودیو از همه به‌جز کارکنان واردشده.

برای مهمان یا مشتری، هر آدرسی زیر /studio/ و آدرس پنل مدیریت (ADMIN_URL) دقیقاً مثل یک آدرس ناموجود
پاسخ ۴۰۴ می‌گیرد؛ پس با حدس زدن آدرس هم نمی‌توان فهمید پنلی وجود دارد. کارکنان از همان صفحه ورود فروشگاه
وارد می‌شوند و دکمه «مدیریت» در هدر سایت به آن‌ها نشان داده می‌شود.
"""

from django.conf import settings
from django.http import Http404


def backoffice_prefixes():
    return ("/studio/", "/" + settings.ADMIN_URL)


def is_backoffice_path(path):
    return path.startswith(backoffice_prefixes())


class HideBackofficeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_backoffice_path(request.path) and not is_backoffice_open(request):
            raise Http404
        return self.get_response(request)


def is_backoffice_open(request):
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_staff and user.is_active:
        return True
    # لینک اشتراک پیش‌نمایش پیش‌نویس و خروج از آن، برای کسی که حساب ندارد، عمداً عمومی‌اند
    return request.path.startswith(PUBLIC_PREFIXES)


PUBLIC_PREFIXES = ("/studio/preview/s/", "/studio/preview/exit/")
