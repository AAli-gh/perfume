from django.contrib import messages
from django.contrib.auth import login
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from apps.core.audit import record
from apps.core.ratelimit import ratelimit

from . import otp
from .forms import CodeForm, PhoneForm
from .services import send_otp, settings_for, sms_available


def otp_enabled(store):
    return sms_available() and settings_for(store).otp_login_enabled


def _next(request):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    return nxt if url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()) else ""


def _phone_key(request):
    from apps.core.forms import en_digits

    return en_digits(request.POST.get("phone", ""))[:11] or None


@ratelimit("otp-send-ip", "10/10m")
@ratelimit("otp-send-phone", "3/10m", key=_phone_key)
def otp_login(request):
    """گام ۱: شماره موبایل ← پیامک کد."""
    if not otp_enabled(request.store):
        raise Http404
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    form = PhoneForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone"]
        code = otp.issue(request.store, phone)
        if send_otp(request.store, phone, code, otp.TTL_SECONDS // 60):
            record("auth.otp_sent", request, target=phone)
            return render(request, "accounts/otp.html", {
                "step": "code", "form": CodeForm(initial={"phone": phone}), "phone": phone, "next": _next(request),
            })
        form.add_error(None, "ارسال پیامک انجام نشد؛ لطفاً کمی بعد دوباره تلاش کنید یا با ایمیل وارد شوید.")
    return render(request, "accounts/otp.html", {"step": "phone", "form": form, "next": _next(request)},
                  status=422 if form.errors else 200)


@ratelimit("otp-verify-ip", "20/10m")
def otp_verify(request):
    """گام ۲: بررسی کد ← ورود (یا ساخت حساب برای شماره جدید)."""
    if not otp_enabled(request.store) or request.method != "POST":
        raise Http404
    form = CodeForm(request.POST)
    if form.is_valid():
        phone, code = form.cleaned_data["phone"], form.cleaned_data["code"]
        try:
            otp.verify(request.store, phone, code)
            user, created = otp.user_for_phone(phone)
        except otp.OTPError as exc:
            record("auth.otp_failed", request, target=phone)
            form.add_error("code", str(exc))
        else:
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            record("auth.otp_register" if created else "auth.otp_login", request, user=user, target=phone)
            messages.success(request, "حساب شما با این شماره ساخته شد. خوش آمدید!" if created else "خوش آمدید.")
            return redirect(_next(request) or "accounts:profile")
    return render(request, "accounts/otp.html", {
        "step": "code", "form": form, "phone": request.POST.get("phone", ""), "next": _next(request),
    }, status=422)
