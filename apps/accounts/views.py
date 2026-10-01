from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import LoginForm, RegisterForm


def _next_url(request, default="accounts:profile"):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()):
        return nxt
    return default


class AuthPageView(LoginView):
    """صفحه ترکیبی ورود و ثبت‌نام."""

    template_name = "accounts/auth.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("register_form", RegisterForm())
        return ctx

    def form_valid(self, form):
        if not form.cleaned_data.get("remember"):
            self.request.session.set_expiry(0)
        messages.success(self.request, f"{form.get_user().display_name} عزیز، خوش آمدید.")
        return super().form_valid(form)


@require_POST
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    form = RegisterForm(request.POST)
    if form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "حساب کاربری شما ساخته شد. به خانواده عطر مجد خوش آمدید!")
        return redirect(_next_url(request))
    return render(request, "accounts/auth.html", {
        "form": LoginForm(request), "register_form": form, "next": request.POST.get("next", ""),
    }, status=422)


@login_required
def profile(request):
    orders = request.user.orders.prefetch_related("items")
    return render(request, "accounts/profile.html", {"orders": orders})
