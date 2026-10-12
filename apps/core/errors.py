"""صفحه‌های خطا: ۴۰۳ خطای CSRF و ۴۰۵ (روش غیرمجاز) با طرح سایت.

۴۰۰، ۴۰۳، ۴۰۴ و ۵۰۰ را خود Django با قالب‌های 400.html، 403.html، 404.html و 500.html نشان می‌دهد و ۴۲۹ را
apps.core.ratelimit. پاسخ ۴۰۵ در Django بدنه ندارد؛ این middleware برای مرورگر صفحه 405.html را جایگزین می‌کند.
"""

from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.template.loader import get_template
from django.views.decorators.csrf import requires_csrf_token


@requires_csrf_token
def bad_request(request, exception=None):
    """handler400: بدون request رندر می‌شود؛ ۴۰۰ (مثلاً Host نامعتبر) ممکن است پیش از session و فروشگاه رخ دهد."""
    return HttpResponseBadRequest(get_template("400.html").render())


def csrf_failure(request, reason=""):
    """CSRF_FAILURE_VIEW: به‌جای صفحه انگلیسی Django، صفحه خطای فارسی با طرح فروشگاه."""
    return render(request, "403_csrf.html", status=403)


class ErrorPageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (response.status_code == 405 and not response.content and not getattr(response, "streaming", False)
                and not request.headers.get("HX-Request") and request.method in ("GET", "POST")):
            page = render(request, "405.html", status=405)
            if response.has_header("Allow"):
                page["Allow"] = response["Allow"]
            return page
        return response
