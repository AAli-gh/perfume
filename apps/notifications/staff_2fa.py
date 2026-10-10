"""ورود دومرحله‌ای کارکنان: بعد از رمز عبور، کد پیامکی به موبایل حساب کارمند.

با روشن کردن «ورود دومرحله‌ای کارکنان» در تنظیمات اطلاع‌رسانی، هر کارمند واردشده برای باز کردن پنل مدیریت
یا استودیو باید یک بار در هر نشست کد ۶ رقمی را وارد کند. کارمند بدون موبایل اجازه ورود ندارد؛ فقط مدیر کل
(superuser) بدون موبایل با هشدار عبور می‌کند تا فروشگاه قفل نشود و او موبایلش را ثبت کند.
"""

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from apps.core.audit import record
from apps.core.forms import en_digits
from apps.core.ratelimit import hit

from . import events as E
from . import otp
from .services import send_otp, settings_for

SESSION_KEY = "staff_2fa_user"


def _protected(path):
    return path.startswith("/studio/") or path.startswith("/" + settings.ADMIN_URL)


def _key(user):
    return f"staff2fa:{user.pk}"


def is_verified(request):
    return request.session.get(SESSION_KEY) == request.user.pk


class StaffTwoFactorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        store = getattr(request, "store", None)
        if (user is not None and user.is_authenticated and user.is_staff and store is not None
                and _protected(request.path) and not is_verified(request)
                and settings_for(store).staff_2fa_enabled):
            if not user.phone and user.is_superuser:
                messages.warning(request, "ورود دومرحله‌ای روشن است ولی موبایل حساب شما ثبت نشده؛ "
                                          "برای امنیت، موبایل خود را در پنل ثبت کنید.")
                return self.get_response(request)
            target = reverse("notifications:staff_2fa") + "?next=" + request.get_full_path()
            if request.headers.get("HX-Request"):
                response = HttpResponse(status=204)
                response["HX-Redirect"] = target
                return response
            return redirect(target)
        return self.get_response(request)


def verify_view(request):
    user = request.user
    if not user.is_authenticated or not user.is_staff:
        return redirect("accounts:login")
    next_url = request.POST.get("next") or request.GET.get("next") or reverse("builder:dashboard")
    if not url_has_allowed_host_and_scheme(next_url, {request.get_host()}, require_https=request.is_secure()):
        next_url = reverse("builder:dashboard")
    if is_verified(request):
        return redirect(next_url)
    phone = user.phone
    sent = request.session.get("staff_2fa_sent") == user.pk
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "send" and phone:
            allowed, _retry = hit("staff-2fa-send", str(user.pk), 5, 600)
            if not allowed:
                messages.error(request, "تعداد درخواست کد زیاد است؛ چند دقیقه دیگر دوباره تلاش کنید.")
            else:
                code = otp.issue(request.store, _key(user))
                if send_otp(request.store, phone, code, otp.TTL_SECONDS // 60, event=E.STAFF_OTP):
                    request.session["staff_2fa_sent"] = user.pk
                    messages.success(request, f"کد به موبایل ‎…{phone[-4:]}‎ ارسال شد.")
                else:
                    messages.error(request, "ارسال پیامک ممکن نشد؛ تنظیمات سرویس پیامک را بررسی کنید.")
            return redirect(reverse("notifications:staff_2fa") + "?next=" + next_url)
        if action == "verify":
            try:
                otp.verify(request.store, _key(user), en_digits(request.POST.get("code", "")))
            except otp.OTPError as exc:
                record("staff.2fa_failed", request, target=user.get_username())
                messages.error(request, str(exc))
                return redirect(reverse("notifications:staff_2fa") + "?next=" + next_url)
            request.session[SESSION_KEY] = user.pk
            request.session.pop("staff_2fa_sent", None)
            record("staff.2fa_ok", request, target=user.get_username())
            return redirect(next_url)
    return render(request, "notifications/staff_2fa.html", {"phone": phone, "sent": sent, "next": next_url})
