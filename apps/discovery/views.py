from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.catalog import recommend
from apps.catalog.models import Product
from apps.core.ratelimit import ratelimit

from . import finder
from .compare import MAX_ITEMS, CompareList, build_table, products_by_ids


# ---------- مقایسه ----------

def compare_page(request):
    """جدول مقایسه؛ ?p=slug1,slug2 لینک قابل اشتراک (فهرست شخصی کاربر را تغییر نمی‌دهد)."""
    shared = request.GET.get("p", "")
    if shared:
        slugs = [s for s in shared.split(",") if s][:MAX_ITEMS]
        ids = list(Product.objects.for_store(request.store).filter(slug__in=slugs).values_list("pk", flat=True))
        by_slug = dict(Product.objects.filter(pk__in=ids).values_list("slug", "pk"))
        ids = [by_slug[s] for s in slugs if s in by_slug]
    else:
        ids = CompareList(request).ids
    products = products_by_ids(request.store, ids)
    groups, shared_notes = build_table(products) if products else ([], [])
    only_diff = request.GET.get("diff") == "1" and len(products) > 1
    if only_diff:
        for group in groups:
            group.rows = [row for row in group.rows if not row.is_same]
        groups = [g for g in groups if g.rows]
    suggestions = []
    if products and len(products) < MAX_ITEMS:
        suggestions = [p for p in recommend.similar_products(products[0], limit=8) if p.pk not in ids][:4]
    share_url = request.build_absolute_uri(reverse("discovery:compare") + "?p=" + ",".join(p.slug for p in products))
    return render(request, "discovery/compare.html", {
        "products": products, "groups": groups, "shared_notes": shared_notes, "only_diff": only_diff,
        "is_shared": bool(shared), "suggestions": suggestions, "share_url": share_url, "max_items": MAX_ITEMS,
    })


@ratelimit("compare", "60/1m")
@require_POST
def compare_toggle(request, product_id):
    product = get_object_or_404(Product.objects.for_store(request.store).active(), pk=product_id)
    compare = CompareList(request)
    active, error = compare.toggle(product.pk)
    if request.htmx:
        return render(request, "discovery/partials/compare_toggled.html", {
            "product": product, "active": active, "error": error, "compare": compare,
            "variant": request.POST.get("variant", "button"),
        })
    if error:
        messages.error(request, error)
    return redirect(request.POST.get("next") if request.POST.get("next", "").startswith("/") else "discovery:compare")


@require_POST
def compare_remove(request, product_id):
    compare = CompareList(request)
    if product_id in compare:
        compare.toggle(product_id)
    return redirect("discovery:compare")


@require_POST
def compare_clear(request):
    CompareList(request).clear()
    return redirect("discovery:compare")


@require_POST
def compare_set(request):
    """از نتیجه عطریاب: «این‌ها را مقایسه کن»."""
    ids = [int(v) for v in request.POST.getlist("product") if v.isdigit()][:MAX_ITEMS]
    valid = [p.pk for p in products_by_ids(request.store, ids)]
    CompareList(request).set(valid)
    return redirect("discovery:compare")


# ---------- عطریاب ----------

def _answers(request):
    return dict(request.session.get(finder.SESSION_KEY) or {})


def _step_index(request, answers):
    try:
        index = int(request.GET.get("step", ""))
    except ValueError:
        index = next((i for i, s in enumerate(finder.STEPS) if s.key not in answers), len(finder.STEPS) - 1)
    return max(0, min(index, len(finder.STEPS) - 1))


def _render_step(request, index, form, status=200):
    step = finder.STEPS[index]
    template = "discovery/partials/finder_step.html" if request.htmx else "discovery/finder.html"
    return render(request, template, {
        "step": step, "index": index, "number": index + 1, "total": len(finder.STEPS), "form": form,
        "progress": round(index * 100 / len(finder.STEPS)), "is_last": index == len(finder.STEPS) - 1,
        "multi": step.key in ("families", "likes", "dislikes"),
    }, status=status)


@ratelimit("finder", "120/10m")
def finder_view(request):
    pool = list(recommend.candidates(request.store))
    answers = _answers(request)
    if request.method == "POST":
        try:
            index = max(0, min(int(request.POST.get("step", 0)), len(finder.STEPS) - 1))
        except ValueError:
            raise Http404 from None
        step = finder.STEPS[index]
        form = finder.step_form(step, request.store, pool, data=request.POST)
        if not form.is_valid():
            return _render_step(request, index, form, status=422)
        answers[step.key] = form.cleaned_data[step.key]
        request.session[finder.SESSION_KEY] = answers
        if index + 1 >= len(finder.STEPS):
            if request.htmx:  # مرورگر redirect را خودش دنبال نکند؛ HTMX صفحه نتیجه را کامل باز کند
                return HttpResponse(headers={"HX-Redirect": reverse("discovery:finder_results")})
            return redirect("discovery:finder_results")
        index += 1
        return _render_step(request, index, finder.step_form(finder.STEPS[index], request.store, pool,
                                                             initial={finder.STEPS[index].key: answers.get(finder.STEPS[index].key)}))
    index = _step_index(request, answers)
    step = finder.STEPS[index]
    return _render_step(request, index, finder.step_form(step, request.store, pool, initial={step.key: answers.get(step.key)}))


def finder_results(request):
    answers = _answers(request)
    if not all(step.key in answers for step in finder.STEPS):
        return redirect("discovery:finder")
    products = finder.results(request.store, answers)
    return render(request, "discovery/finder_results.html", {"products": products, "answers": answers})


@require_POST
def finder_reset(request):
    request.session.pop(finder.SESSION_KEY, None)
    return redirect("discovery:finder")
