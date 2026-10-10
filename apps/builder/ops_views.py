"""استودیو ← عملیات فروشگاه: سفارش‌ها (چاپ گروهی، رهگیری گروهی) و موجودی.

مثل بقیه استودیو: view فقط هماهنگ‌کننده است؛ تغییر وضعیت از orders.workflow و تغییر موجودی از
catalog.inventory عبور می‌کند تا تاریخچه، دفتر موجودی و پیامک‌ها مثل پنل مدیریت ثبت شوند.
"""

import re

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.catalog import inventory
from apps.catalog.models import ProductVariant, StockMovement
from apps.core.audit import record
from apps.core.forms import en_digits
from apps.orders.models import Order
from apps.orders.workflow import InvalidTransition, transition

from . import ops
from .access import ORDERS_PERM, PRODUCTS_PERM, REPORTS_PERM, studio_required

S = Order.Status
ORDER_TABS = [
    ("todo", "نیازمند اقدام"),
    ("card", "کارت به کارت"),
    ("prepare", "آماده‌سازی"),
    ("ship", "ارسال"),
    ("shipped", "ارسال‌شده"),
    ("all", "همه"),
]
DOCS = {"invoice": "فاکتور", "packing": "برگه بسته‌بندی", "labels": "برچسب ارسال"}
MAX_PRINT = 100


def _tab_queryset(store, tab):
    return {
        "todo": ops.needs_action,
        "card": ops.awaiting_card,
        "prepare": ops.to_prepare,
        "ship": ops.to_ship,
        "shipped": lambda s: Order.objects.for_store(s).filter(status=S.SHIPPED),
        "all": lambda s: Order.objects.for_store(s),
    }[tab](store)


@studio_required(REPORTS_PERM)
def orders(request):
    tab = request.GET.get("q", "todo")
    tab = tab if tab in dict(ORDER_TABS) else "todo"
    qs = _tab_queryset(request.store, tab)
    search = en_digits(request.GET.get("s", "")).strip()
    if search:
        qs = qs.filter(Q(number__icontains=search) | Q(phone__contains=search) | Q(last_name__icontains=search)
                       | Q(first_name__icontains=search) | Q(tracking_code__icontains=search))
    qs = qs.order_by("created_at" if tab in ("todo", "card", "prepare", "ship") else "-created_at")
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    counted = ("todo", "card", "prepare", "ship")
    tabs = [(key, label, _tab_queryset(request.store, key).count() if key in counted else 0)
            for key, label in ORDER_TABS]
    return render(request, "builder/ops/orders.html", {
        "nav": "orders", "tab": tab, "tabs": tabs, "page": page, "search": search, "docs": DOCS,
    })


def _selected(request, source):
    ids = [int(i) for i in source.getlist("ids") if str(i).isdigit()][:MAX_PRINT]
    return Order.objects.for_store(request.store).filter(pk__in=ids)


@studio_required(REPORTS_PERM)
def print_orders(request):
    """چاپ فاکتور، برگه بسته‌بندی یا برچسب ارسال یک یا چند سفارش (هر سفارش یک صفحه)."""
    doc = request.GET.get("doc", "invoice")
    if doc not in DOCS:
        raise Http404
    selected = list(_selected(request, request.GET).prefetch_related("items").select_related("shipping_method")
                    .order_by("created_at"))
    if not selected:
        messages.error(request, "هیچ سفارشی برای چاپ انتخاب نشده است.")
        return redirect("builder:orders")
    record("studio.print_orders", request, target=f"{doc}: {', '.join(o.number for o in selected[:20])}")
    return render(request, f"builder/print/{doc}.html", {"orders": selected, "doc": doc, "title": DOCS[doc]})


@studio_required(ORDERS_PERM)
@require_POST
def orders_status(request):
    """تغییر گروهی وضعیت (مثلاً «در حال آماده‌سازی» یا «پرداخت شده» برای کارت به کارت‌های تأییدشده)."""
    to_status = request.POST.get("to")
    if to_status not in (S.PAID, S.PROCESSING, S.DELIVERED):
        raise Http404
    done, failed = 0, []
    for order in _selected(request, request.POST):
        try:
            transition(order, to_status, by=request.user, note="تغییر گروهی از استودیو")
            done += 1
        except InvalidTransition:
            failed.append(order.number)
    if done:
        messages.success(request, f"وضعیت {done} سفارش به «{S(to_status).label}» تغییر کرد.")
    if failed:
        messages.error(request, f"این سفارش‌ها در وضعیتی نبودند که این تغییر مجاز باشد: {'، '.join(failed)}")
    return redirect(request.POST.get("next") or "builder:orders")


TRACKING_LINE = re.compile(r"^\s*(MJ[0-9A-Z]+)[\s,،;:\t-]+([0-9A-Za-z-]{4,60})\s*$", re.IGNORECASE)


def parse_tracking_lines(text):
    """«شماره سفارش  کد رهگیری» در هر خط (خروجی اکسل یا پنل پست) ← (dict شماره→کد، خطوط نامعتبر)."""
    pairs, bad = {}, []
    for line in en_digits(text).splitlines():
        if not line.strip():
            continue
        match = TRACKING_LINE.match(line)
        if match:
            pairs[match.group(1).upper()] = match.group(2)
        else:
            bad.append(line.strip())
    return pairs, bad


@studio_required(ORDERS_PERM)
def tracking(request):
    """ثبت گروهی کد رهگیری: یک کادر برای هر سفارش یا چسباندن فهرست «شماره سفارش، کد رهگیری»."""
    store_orders = Order.objects.for_store(request.store)
    if request.method == "POST":
        codes = {}
        for key, value in request.POST.items():
            if key.startswith("code-") and value.strip():
                codes[key[5:]] = en_digits(value).strip()[:60]
        pasted, bad = parse_tracking_lines(request.POST.get("bulk", ""))
        by_number = {o.number: o for o in store_orders.filter(number__in=list(pasted))}
        unknown = [n for n in pasted if n not in by_number]
        for number, code in pasted.items():
            if number in by_number:
                codes[str(by_number[number].pk)] = code
        mark_shipped = request.POST.get("ship") == "on"
        saved, shipped, failed = 0, 0, []
        for order in store_orders.filter(pk__in=[int(k) for k in codes if k.isdigit()]):
            order.tracking_code = codes[str(order.pk)]
            order.save(update_fields=["tracking_code"])
            saved += 1
            if mark_shipped and order.status != S.SHIPPED:
                try:
                    if order.status in (S.PAID, S.PENDING):
                        transition(order, S.PROCESSING, by=request.user, note="ثبت گروهی کد رهگیری")
                    transition(order, S.SHIPPED, by=request.user, note="ثبت گروهی کد رهگیری")
                    shipped += 1
                except InvalidTransition:
                    failed.append(order.number)
        if saved:
            record("studio.bulk_tracking", request, target=f"{saved} سفارش")
            messages.success(request, f"کد رهگیری {saved} سفارش ثبت شد"
                                      + (f" و {shipped} سفارش «ارسال شده» شد (پیامک کد رهگیری برای مشتری می‌رود)."
                                         if mark_shipped else "."))
        for label, items in (("سفارش پیدا نشد", unknown), ("خط نامعتبر", bad),
                             ("وضعیت اجازه «ارسال شده» نمی‌داد", failed)):
            if items:
                messages.error(request, f"{label}: {'، '.join(items[:20])}")
        return redirect("builder:tracking")
    selected = _selected(request, request.GET)
    rows = selected if selected.exists() else ops.to_ship(request.store)
    return render(request, "builder/ops/tracking.html", {"nav": "orders", "rows": rows.order_by("created_at")[:MAX_PRINT]})


# ---------- موجودی ----------

@studio_required(PRODUCTS_PERM)
def stock(request):
    """کالاهای رو به اتمام با «افزودن موجودی» سریع و تعداد «خبرم کن»های منتظر."""
    if request.method == "POST":
        return _restock(request)
    show_all = request.GET.get("all") == "1"
    if show_all:
        default = getattr(getattr(request.store, "config", None), "low_stock_threshold", 3)
        variants = (ProductVariant.objects.filter(product__store=request.store, product__is_active=True)
                    .select_related("product").order_by("stock", "product__name"))
        for v in variants:
            v.threshold = v.low_stock_threshold if v.low_stock_threshold is not None else default
    else:
        variants = ops.low_stock(request.store)
    page = Paginator(variants, 50).get_page(request.GET.get("page"))
    return render(request, "builder/ops/stock.html", {"nav": "stock", "page": page, "show_all": show_all})


def _restock(request):
    variant = ProductVariant.objects.filter(pk=request.POST.get("variant"), product__store=request.store).first()
    if variant is None:
        raise Http404
    try:
        added = int(en_digits(request.POST.get("add", "0")) or 0)
        threshold = request.POST.get("threshold", "").strip()
        threshold = None if threshold == "" else int(en_digits(threshold))
    except ValueError:
        messages.error(request, "عدد واردشده معتبر نیست.")
        return redirect(request.get_full_path())
    if added < 0 or added > 100_000 or (threshold is not None and not 0 <= threshold <= 10_000):
        messages.error(request, "عدد واردشده خارج از محدوده است.")
        return redirect(request.get_full_path())
    if threshold != variant.low_stock_threshold and "threshold" in request.POST:
        variant.low_stock_threshold = threshold
        variant.save(update_fields=["low_stock_threshold"])
    if added:
        inventory.set_stock(variant, variant.stock + added, user=request.user, note="ورود کالا از استودیو",
                            reason=StockMovement.Reason.RESTOCK)
        messages.success(request, f"{added} عدد به موجودی «{variant}» اضافه شد؛ موجودی فعلی {variant.stock}.")
    else:
        messages.success(request, f"آستانه «{variant}» ذخیره شد.")
    return redirect(request.get_full_path())
