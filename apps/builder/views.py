"""استودیو: ویرایش ظاهر فروشگاه و چیدمان صفحه‌ها بدون کدنویسی.

Viewها فقط هماهنگ‌کننده هستند: اعتبارسنجی در فرم‌ها/schemaها و ذخیره‌سازی در services هر اپ انجام می‌شود.
"""

from functools import wraps

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.core.templatetags.majd import fa
from apps.pages import services as page_services
from apps.pages.models import Page, PageSection
from apps.themes import chrome
from apps.themes import services as theme_services
from apps.themes import tokens as T

from . import forms as F
from . import preview
from . import services as builder
from .access import (
    PUBLISH_PERM, SECTION_ADD_PERM, SECTION_CHANGE_PERM, SECTION_DELETE_PERM, THEME_PERM, studio_required,
)
from .models import Revision
from apps.core.audit import record
from apps.core.ratelimit import ratelimit

SAVED = "در پیش‌نویس ذخیره شد. برای دیدن نتیجه «پیش‌نمایش» را باز کنید و سپس منتشر کنید."


def edits_draft(view):
    """هر درخواست POST موفق در استودیو، آخرین ویرایشگر پیش‌نویس را ثبت می‌کند."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        if request.method == "POST" and response.status_code < 400:
            builder.touch(request.store, request.user)
        return response

    return wrapped

PANELS = [
    ("preset", "پوسته و پیش‌تنظیم", "diamond"),
    ("colors", "رنگ‌ها", "flame"),
    ("typography", "فونت، اندازه و فاصله", "list"),
    ("components", "سبک اجزا", "grid"),
    ("branding", "لوگو و فاوآیکون", "crown"),
    ("header", "هدر و منو", "menu"),
    ("footer", "فوتر", "pin"),
]
TOKEN_PANELS = {
    "colors": (F.ColorsForm, ["colors"]),
    "typography": (F.TypographyForm, ["typography", "radius", "spacing"]),
    "components": (F.ComponentsForm, ["components"]),
}
SWATCHES = ["background", "panel", "primary", "accent", "text"]


@studio_required()
def dashboard(request):
    page = page_services.ensure_home_page(request.store)
    status = PageSection.Status.DRAFT if page.has_draft else PageSection.Status.PUBLISHED
    return render(request, "builder/dashboard.html", {
        "theme_settings": theme_services.draft_settings(request.store, create=False)
        or theme_services.ensure_store_theme(request.store),
        "home": page,
        "section_count": page_services.page_sections(page, status).filter(is_enabled=True).count(),
        "last_revision": Revision.objects.for_store(request.store).select_related("created_by").first(),
        "nav": "dashboard",
    })


# ---------- ظاهر ----------

@studio_required(THEME_PERM)
@edits_draft
def theme_editor(request, panel="preset"):
    if panel not in dict((p[0], p) for p in PANELS):
        panel = "preset"
    ts = theme_services.editable_settings(request.store)
    if ts is None:
        messages.error(request, "هیچ پوسته‌ای نصب نیست. ابتدا دستور sync_themes را اجرا کنید.")
        return redirect("builder:dashboard")
    preview.enter_staff_preview(request)  # برای iframe پیش‌نمایش زنده کنار ویرایشگر
    tokens = T.resolve(ts)
    here = reverse("builder:theme_panel", args=[panel])
    context = {"panel": panel, "panels": PANELS, "theme_settings": ts, "tokens": tokens, "nav": "theme"}

    if panel == "preset":
        preset_form = F.PresetForm(theme=ts.theme, initial={"preset": ts.preset})
        theme_form = F.ThemeChoiceForm(initial={"theme": ts.theme})
        if request.method == "POST":
            if request.POST.get("action") == "theme":
                theme_form = F.ThemeChoiceForm(request.POST)
                if theme_form.is_valid():
                    if theme_form.cleaned_data["theme"] != ts.theme:
                        theme_services.change_theme(ts, theme_form.cleaned_data["theme"])
                        messages.success(request, "پوسته تغییر کرد.")
                    return redirect(here)
            else:
                preset_form = F.PresetForm(request.POST, theme=ts.theme)
                if preset_form.is_valid():
                    theme_services.apply_preset(ts, preset_form.cleaned_data["preset"])
                    messages.success(request, f"پیش‌تنظیم «{preset_form.cleaned_data['preset'].name}» اعمال شد.")
                    return redirect(here)
        presets = [
            {"preset": p, "swatches": [T.merge(T.validate(p.tokens, partial=True))["colors"][c] for c in SWATCHES]}
            for p in ts.theme.presets.all()
        ]
        context.update(preset_form=preset_form, theme_form=theme_form, presets=presets,
                       has_overrides=bool(ts.overrides))

    elif panel in TOKEN_PANELS:
        form_class, groups = TOKEN_PANELS[panel]
        form = form_class(initial=form_class.initial_from(tokens))
        if request.method == "POST":
            if request.POST.get("action") == "reset":
                theme_services.reset_tokens(ts, groups)
                messages.success(request, "مقادیر این بخش به پیش‌تنظیم برگشت.")
                return redirect(here)
            form = form_class(request.POST)
            if form.is_valid():
                theme_services.save_tokens(ts, form.to_tokens())
                messages.success(request, SAVED)
                return redirect(here)
        context.update(form=form, customized=any(g in (ts.overrides or {}) for g in groups))

    elif panel == "branding":
        header = chrome.resolve("header", ts)
        form = F.BrandingForm(initial={"logo_height": header["logo_height"], "monogram": header["monogram"]})
        if request.method == "POST":
            form = F.BrandingForm(request.POST, request.FILES)
            if form.is_valid():
                data = form.cleaned_data
                theme_services.save_branding(
                    ts, logo=data["logo"], clear_logo=data["clear_logo"],
                    favicon=data["favicon"], clear_favicon=data["clear_favicon"],
                )
                theme_services.save_chrome(ts, "header", form.chrome_values())
                messages.success(request, SAVED)
                return redirect(here)
        context.update(form=form)

    else:  # header / footer
        form_class = F.HeaderEditForm if panel == "header" else F.FooterEditForm
        form = form_class(initial=chrome.resolve(panel, ts))
        if request.method == "POST":
            if request.POST.get("action") == "reset":
                theme_services.save_chrome(ts, panel, {k: v for k, v in chrome.defaults(panel).items() if k in form.fields})
                messages.success(request, "تنظیمات به حالت پیش‌فرض برگشت.")
                return redirect(here)
            form = form_class(request.POST)
            if form.is_valid():
                theme_services.save_chrome(ts, panel, form.cleaned_data)
                messages.success(request, SAVED)
                return redirect(here)
        context.update(form=form)

    return render(request, "builder/theme.html", context)


# ---------- صفحه‌ها ----------

def _store_page(request, pk):
    return get_object_or_404(Page.objects.for_store(request.store), pk=pk)


def _store_section(request, page_pk, pk):
    return get_object_or_404(
        PageSection.objects.select_related("page"),
        pk=pk, page_id=page_pk, page__store=request.store, status=PageSection.Status.DRAFT,
    )


def _section_rows(page):
    rows = []
    for section in page_services.page_sections(page, PageSection.Status.DRAFT):
        section_type = section.section_type
        title = str((section.settings or {}).get("title", "")).splitlines()
        rows.append({
            "section": section,
            "type": section_type,
            "summary": title[0] if title else "",
            "editable": section_type is not None,
        })
    return rows


def _editor_context(request, page):
    user = request.user
    return {
        "page": page,
        "rows": _section_rows(page),
        "add_form": F.AddSectionForm(),
        "can_add": user.has_perm(SECTION_ADD_PERM),
        "can_delete": user.has_perm(SECTION_DELETE_PERM),
        "nav": "pages",
    }


def _sections_response(request, page):
    if request.htmx:
        response = render(request, "builder/_sections.html", _editor_context(request, page))
        response["HX-Trigger"] = "preview-refresh"  # iframe پیش‌نمایش کنار ویرایشگر تازه می‌شود
        return response
    return redirect("builder:page", pk=page.pk)


@studio_required(SECTION_CHANGE_PERM)
def page_list(request):
    page_services.ensure_home_page(request.store)
    pages = Page.objects.for_store(request.store)
    return render(request, "builder/pages.html", {"pages": pages, "nav": "pages"})


@studio_required(SECTION_CHANGE_PERM)
def page_editor(request, pk):
    page = builder.editable_page(_store_page(request, pk))
    preview.enter_staff_preview(request)
    return render(request, "builder/page_editor.html", _editor_context(request, page))


@require_POST
@studio_required(SECTION_CHANGE_PERM)
@edits_draft
def section_reorder(request, pk):
    page = builder.editable_page(_store_page(request, pk))
    ids = []
    for value in request.POST.getlist("order"):
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    page_services.reorder_sections(page, ids)
    return _sections_response(request, page)


@require_POST
@studio_required(SECTION_CHANGE_PERM)
@edits_draft
def section_move(request, pk, section_pk):
    section = _store_section(request, pk, section_pk)
    page_services.move_section(section, -1 if request.POST.get("direction") == "up" else 1)
    return _sections_response(request, section.page)


@require_POST
@studio_required(SECTION_CHANGE_PERM)
@edits_draft
def section_toggle(request, pk, section_pk):
    section = _store_section(request, pk, section_pk)
    page_services.toggle_section(section)
    return _sections_response(request, section.page)


@require_POST
@studio_required(SECTION_CHANGE_PERM, SECTION_DELETE_PERM)
@edits_draft
def section_delete(request, pk, section_pk):
    section = _store_section(request, pk, section_pk)
    page_services.delete_section(section)
    if not request.htmx:
        messages.success(request, "بخش حذف شد.")
    return _sections_response(request, section.page)


@require_POST
@studio_required(SECTION_CHANGE_PERM, SECTION_ADD_PERM)
@edits_draft
def section_add(request, pk):
    page = builder.editable_page(_store_page(request, pk))
    form = F.AddSectionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "نوع بخش نامعتبر است.")
        return redirect("builder:page", pk=page.pk)
    section = page_services.add_section(page, form.cleaned_data["type"])
    messages.success(request, f"بخش «{section.section_type.label}» به انتهای صفحه اضافه شد.")
    return redirect("builder:section", pk=page.pk, section_pk=section.pk)


@studio_required(SECTION_CHANGE_PERM)
@edits_draft
def section_edit(request, pk, section_pk):
    section = _store_section(request, pk, section_pk)
    section_type = section.section_type
    if section_type is None:
        messages.error(request, "این نوع بخش دیگر پشتیبانی نمی‌شود؛ فقط می‌توانید آن را حذف کنید.")
        return redirect("builder:page", pk=pk)
    try:
        initial = section_type.clean_settings(section.settings)
    except Exception:  # noqa: BLE001 — تنظیمات خراب نباید مانع ویرایش شود
        initial = section_type.defaults()
        messages.warning(request, "تنظیمات ذخیره‌شده این بخش نامعتبر بود؛ مقادیر پیش‌فرض نمایش داده می‌شود.")
    form = F.section_settings_form(section_type, initial=initial)
    image_form = F.SectionImageForm() if section_type.uses_image else None
    if request.method == "POST":
        form = F.section_settings_form(section_type, request.POST)
        image_form = F.SectionImageForm(request.POST, request.FILES) if section_type.uses_image else None
        if form.is_valid() and (image_form is None or image_form.is_valid()):
            image_data = image_form.cleaned_data if image_form else {}
            page_services.update_section(
                section, form.cleaned_data,
                image=image_data.get("image"), clear_image=image_data.get("clear_image", False),
            )
            messages.success(request, f"بخش «{section_type.label}» {SAVED}")
            return redirect("builder:page", pk=pk)
    return render(request, "builder/section_edit.html", {
        "page": section.page, "section": section, "section_type": section_type,
        "form": form, "image_form": image_form, "nav": "pages",
    })



# ---------- پیش‌نمایش، انتشار و تاریخچه ----------

def _back(request, default="builder:dashboard"):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, require_https=request.is_secure()):
        return redirect(target)
    return redirect(default)


@studio_required()
def preview_page(request):
    """فروشگاه با پیش‌نویس، داخل iframe با اندازه‌های دسکتاپ / تبلت / موبایل."""
    preview.enter_staff_preview(request)
    path = request.GET.get("path") or "/"
    if not url_has_allowed_host_and_scheme(path, set()) or not path.startswith("/") or path.startswith("/studio/"):
        path = "/"
    return render(request, "builder/preview.html", {
        "path": path, "nav": "preview",
        "share_link": request.session.pop("builder_share_link", None), "link_hours": builder.PREVIEW_LINK_HOURS,
    })


def preview_exit(request):
    """خروج از حالت پیش‌نمایش (برای کارکنان و دارندگان لینک)."""
    preview.exit_preview(request)
    return redirect("pages:home")


@ratelimit("preview-link", "30/10m", methods=("GET",))
def preview_share(request, token):
    """لینک عمومی و موقت پیش‌نمایش؛ نیازی به ورود ندارد ولی فقط دیدن پیش‌نویس را ممکن می‌کند."""
    if not builder.check_preview_token(token, request.store):
        raise Http404("لینک پیش‌نمایش نامعتبر یا منقضی شده است.")
    preview.enter_link_preview(request, token)
    return redirect("pages:home")


@require_POST
@studio_required(PUBLISH_PERM)
def preview_link(request):
    token = builder.preview_link_token(request.store)
    request.session["builder_share_link"] = request.build_absolute_uri(reverse("builder:preview_share", args=[token]))
    record("studio.preview_link", request)
    return redirect("builder:preview")


@require_POST
@studio_required(PUBLISH_PERM)
def publish(request):
    try:
        revision = builder.publish(request.store, request.user, request.POST.get("label", "").strip())
    except builder.NothingToPublish:
        messages.info(request, "تغییری برای انتشار وجود ندارد.")
    else:
        record("studio.publish", request, target=f"revision {revision.number}", changes="، ".join(revision.changes))
        messages.success(request, f"نسخه {fa(revision.number)} منتشر شد: {'، '.join(revision.changes)}.")
    return _back(request)


@require_POST
@studio_required(PUBLISH_PERM)
def discard(request):
    builder.discard(request.store)
    record("studio.discard", request)
    messages.success(request, "تغییرات منتشرنشده کنار گذاشته شد؛ پیش‌نویس برابر نسخه فعلی فروشگاه است.")
    return _back(request)


@studio_required()
def history(request):
    revisions = Revision.objects.for_store(request.store).select_related("created_by")
    return render(request, "builder/history.html", {"revisions": revisions, "nav": "history"})


@require_POST
@studio_required(PUBLISH_PERM)
def restore(request, number):
    revision = get_object_or_404(Revision.objects.for_store(request.store), number=number)
    builder.restore(request.store, revision, request.user)
    record("studio.restore", request, target=f"revision {revision.number}")
    messages.success(request, f"نسخه {fa(revision.number)} در پیش‌نویس بارگذاری شد. پیش‌نمایش را ببینید و در صورت "
                              f"رضایت منتشر کنید.")
    return redirect("builder:preview")
