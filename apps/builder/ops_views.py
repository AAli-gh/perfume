"""استودیو ← عملیات فروشگاه: سفارش‌ها (چاپ گروهی، رهگیری گروهی) و موجودی.

مثل بقیه استودیو: view فقط هماهنگ‌کننده است؛ تغییر وضعیت از orders.workflow و تغییر موجودی از
catalog.inventory عبور می‌کند تا تاریخچه، دفتر موجودی و پیامک‌ها مثل پنل مدیریت ثبت شوند.
"""

import re
import secrets

from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.catalog import bulk, inventory, search_log
from apps.catalog import sales as sale_service
from apps.catalog.models import PriceChangeBatch, ProductVariant, SaleCampaign, StockMovement, sale_active
from apps.core import spreadsheet
from apps.core.audit import record
from apps.core.forms import en_digits
from apps.cart.models import SavedCart
from apps.notifications import campaigns
from apps.notifications.services import settings_for as notification_settings
from apps.notifications.models import Campaign
from apps.notifications.tasks import send_campaign_task
from apps.orders import customers as customers_service
from apps.orders import returns
from apps.orders.models import Order, ReturnRequest
from apps.orders.workflow import InvalidTransition, transition

from . import ops
from .access import CAMPAIGN_PERM, CUSTOMERS_PERM, ORDERS_PERM, PRODUCTS_PERM, REPORTS_PERM, studio_required
from .ops_forms import CampaignForm, CustomerProfileForm, ImportForm, PriceChangeForm, SaleForm

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


# ---------- محصولات: خروجی، ورود از فایل، تغییر گروهی قیمت ----------

IMPORT_TTL = 1800


@studio_required(PRODUCTS_PERM)
def products(request):
    return render(request, "builder/ops/products.html", {
        "nav": "products", "import_form": ImportForm(), "price_form": PriceChangeForm(store=request.store),
        "batches": PriceChangeBatch.objects.for_store(request.store).select_related("created_by")[:10],
        "columns": bulk.COLUMNS,
    })


@studio_required(PRODUCTS_PERM)
def products_export(request):
    rows = list(bulk.export_rows(request.store))
    stamp = timezone.localdate().isoformat()
    record("studio.export_products", request, target=f"{len(rows) - 1} ردیف")
    if request.GET.get("format") == "csv":
        response = HttpResponse(spreadsheet.write_csv(rows), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="products-{stamp}.csv"'
        return response
    response = HttpResponse(spreadsheet.write_xlsx(rows, "محصولات"),
                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="products-{stamp}.xlsx"'
    return response


@studio_required(PRODUCTS_PERM)
@require_POST
def products_import(request):
    """مرحله ۱: خواندن فایل و نمایش پیش‌نمایش تغییرات (هنوز چیزی ذخیره نمی‌شود)."""
    form = ImportForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "فایلی انتخاب نشده است.")
        return redirect("builder:products")
    upload = form.cleaned_data["file"]
    try:
        table = spreadsheet.read_table(upload.name, upload.read(spreadsheet.MAX_UPLOAD + 1))
    except spreadsheet.SpreadsheetError as exc:
        messages.error(request, str(exc))
        return redirect("builder:products")
    plan = bulk.plan_import(request.store, table)
    token = secrets.token_urlsafe(16)
    cache.set(f"studio-import:{request.user.pk}:{token}", table, IMPORT_TTL)
    return render(request, "builder/ops/import_preview.html", {
        "nav": "products", "plan": plan, "token": token, "filename": upload.name,
        "counts": {a: plan.count(a) for a in ("update", "new_variant", "new_product", "unchanged", "error")},
    })


@studio_required(PRODUCTS_PERM)
@require_POST
def products_import_confirm(request):
    """مرحله ۲: اعمال همان فایل (با وضعیت فعلی پایگاه داده دوباره برنامه‌ریزی می‌شود)."""
    key = f"studio-import:{request.user.pk}:{request.POST.get('token', '')}"
    table = cache.get(key)
    if table is None:
        messages.error(request, "مهلت پیش‌نمایش تمام شده است؛ فایل را دوباره بارگذاری کنید.")
        return redirect("builder:products")
    cache.delete(key)
    plan = bulk.plan_import(request.store, table)
    counts = bulk.apply_import(request.store, plan, user=request.user)
    record("studio.import_products", request, target=str(counts))
    messages.success(request, (
        f"اعمال شد: {counts['updated']} حجم به‌روز شد ({counts['prices']} قیمت، {counts['stock']} موجودی)، "
        f"{counts['new_products']} محصول جدید و {counts['new_variants']} حجم جدید."
        + (" محصولات جدید غیرفعال‌اند؛ در پنل مدیریت تصویرشان را بگذارید و فعالشان کنید." if counts["new_products"]
           else "")))
    return redirect("builder:products")


@studio_required(PRODUCTS_PERM)
def products_prices(request):
    """تغییر گروهی قیمت: GET = پیش‌نمایش، POST با confirm = اعمال."""
    source = request.POST if request.method == "POST" else request.GET
    form = PriceChangeForm(source, store=request.store)
    if not form.is_valid():
        return render(request, "builder/ops/products.html", {
            "nav": "products", "import_form": ImportForm(), "price_form": form, "columns": bulk.COLUMNS,
            "batches": PriceChangeBatch.objects.for_store(request.store).select_related("created_by")[:10],
        }, status=422)
    rows = bulk.plan_prices(bulk.price_scope(request.store, **form.scope_kwargs()), form.rule)
    description = f"{form.scope_label()}: {form.rule.describe()}"
    if request.method == "POST" and request.POST.get("confirm") == "1":
        if not rows:
            messages.error(request, "قیمتی تغییر نمی‌کند.")
            return redirect("builder:products")
        batch = bulk.apply_prices(request.store, rows, description, user=request.user)
        record("studio.bulk_price", request, target=description)
        messages.success(request, f"قیمت {batch.count} حجم تغییر کرد ({description}). در صورت اشتباه از «تاریخچه تغییر قیمت» برگردانید.")
        return redirect("builder:products")
    return render(request, "builder/ops/price_preview.html", {
        "nav": "products", "rows": rows[:500], "total": len(rows), "description": description,
        "query": source.urlencode(),
    })


@studio_required(PRODUCTS_PERM)
@require_POST
def products_price_revert(request, pk):
    batch = PriceChangeBatch.objects.for_store(request.store).filter(pk=pk).first()
    if batch is None:
        raise Http404
    reverted, skipped = bulk.revert_batch(batch)
    record("studio.revert_price", request, target=batch.description)
    messages.success(request, f"قیمت {reverted} حجم به قبل برگشت."
                              + (f" {skipped} حجم بعد از آن دوباره تغییر کرده بود و دست نخورد." if skipped else ""))
    return redirect("builder:products")


# ---------- حراج زمان‌دار ----------

@studio_required(PRODUCTS_PERM)
def sales(request):
    form = SaleForm(request.POST or None, store=request.store)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        variants = bulk.price_scope(request.store, **form.scope_kwargs())
        campaign, applied, replaced = sale_service.create_campaign(
            request.store, variants, name=d["name"], percent=d["percent"], starts_at=d["starts_at"],
            ends_at=d["ends_at"], rounding=d["rounding"], user=request.user)
        record("studio.sale_create", request, target=f"{campaign.name} ({applied})")
        messages.success(request, f"حراج «{campaign.name}» برای {applied} حجم ثبت شد ({campaign.get_status_display()})."
                                  + (f" حراج قبلی {replaced} حجم جایگزین شد." if replaced else ""))
        return redirect("builder:sales")
    campaigns = (SaleCampaign.objects.for_store(request.store).select_related("created_by")
                 .annotate(variant_count=Count("variants"))[:30])
    on_sale = (ProductVariant.objects.filter(product__store=request.store).filter(sale_active())
               .select_related("product").order_by("product__name")[:100])
    return render(request, "builder/ops/sales.html", {
        "nav": "sales", "form": form, "campaigns": campaigns, "on_sale": on_sale,
    }, status=422 if request.method == "POST" else 200)


@studio_required(PRODUCTS_PERM)
@require_POST
def sale_end(request, pk):
    campaign = SaleCampaign.objects.for_store(request.store).filter(pk=pk).first()
    if campaign is None:
        raise Http404
    count = sale_service.end_campaign(campaign)
    record("studio.sale_end", request, target=campaign.name)
    messages.success(request, f"حراج «{campaign.name}» پایان یافت؛ قیمت {count} حجم به حالت عادی برگشت.")
    return redirect("builder:sales")


# ---------- مشتریان و پیامک گروهی ----------

def _customer_filters(request):
    try:
        vip = max(0, int(en_digits(request.GET.get("vip", "")) or 20_000_000))
    except ValueError:
        vip = 20_000_000
    segment = request.GET.get("seg", "all")
    return customers_service.CustomerFilters(
        segment=segment if segment in dict(customers_service.SEGMENTS) else "all",
        search=en_digits(request.GET.get("s", "")).strip()[:50], tag=request.GET.get("tag", "").strip()[:50],
        vip_threshold=vip, sort=request.GET.get("sort", "spent"))


def _audience_label(filters):
    label = dict(customers_service.SEGMENTS)[filters.segment]
    if filters.segment == "vip":
        label += f" (خرید ≥ {filters.vip_threshold:,} تومان)"
    if filters.tag:
        label += f"، برچسب «{filters.tag}»"
    if filters.search:
        label += f"، جستجوی «{filters.search}»"
    return label


@studio_required(CUSTOMERS_PERM)
def customers(request):
    filters = _customer_filters(request)
    qs = customers_service.customers(request.store, filters)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    rows = list(page.object_list)
    profiles = customers_service.profiles(request.store, [r["phone"] for r in rows])
    for row in rows:
        row["profile"] = profiles.get(row["phone"])
    return render(request, "builder/ops/customers.html", {
        "nav": "customers", "page": page, "rows": rows, "filters": filters, "segments": customers_service.SEGMENTS,
        "total": page.paginator.count, "audience": _audience_label(filters),
    })


@studio_required(CUSTOMERS_PERM)
def customer_detail(request, phone):
    info = customers_service.customer(request.store, phone)
    if info is None:
        raise Http404
    profile = customers_service.profile_for(request.store, phone)
    can_edit = request.user.has_perm("accounts.change_user")
    form = CustomerProfileForm(request.POST or None, initial={"tags": profile.tags if profile else "",
                                                              "note": profile.note if profile else ""})
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        if form.is_valid():
            customers_service.save_profile(request.store, phone, note=form.cleaned_data["note"],
                                           tags=form.cleaned_data["tags"], user=request.user)
            messages.success(request, "یادداشت مشتری ذخیره شد.")
            return redirect("builder:customer", phone=phone)
    orders = Order.objects.for_store(request.store).filter(phone=phone).order_by("-created_at")[:50]
    return render(request, "builder/ops/customer.html", {
        "nav": "customers", "c": info, "profile": profile, "form": form, "orders": orders, "can_edit": can_edit,
    })


@studio_required(CUSTOMERS_PERM, CAMPAIGN_PERM)
def campaign_new(request):
    """پیامک گروهی به همان گروهی که در فهرست مشتریان فیلتر شده است."""
    filters = _customer_filters(request)
    recipients = [(r["phone"], r["first_name"]) for r in customers_service.customers(request.store, filters)]
    form = CampaignForm(request.POST or None)
    if request.method == "POST" and form.is_valid() and recipients:
        d = form.cleaned_data
        coupon = campaigns.make_coupon(request.store, percent=d["percent"], days=d["days"] or 7,
                                       uses=len(recipients)) if d["with_coupon"] else None
        campaign = campaigns.create_campaign(request.store, name=d["name"], message=d["message"],
                                             recipients=recipients, audience=_audience_label(filters), coupon=coupon,
                                             opt_out=d["opt_out"], user=request.user)
        record("studio.sms_campaign", request, target=f"{campaign.name} → {campaign.total}")
        transaction.on_commit(lambda: send_campaign_task.delay(campaign.pk))
        messages.success(request, f"پیامک «{campaign.name}» برای {campaign.total} مشتری در صف ارسال قرار گرفت."
                                  + (f" کد تخفیف: {coupon.code}" if coupon else ""))
        return redirect("builder:campaigns")
    sample = None
    if recipients and form.is_bound and form.is_valid():
        sample = campaigns.render(form.cleaned_data["message"], store=request.store, name=recipients[0][1])
    return render(request, "builder/ops/campaign_new.html", {
        "nav": "customers", "form": form, "count": len(recipients), "audience": _audience_label(filters),
        "query": request.GET.urlencode(), "sample": sample,
    }, status=422 if request.method == "POST" else 200)


@studio_required(CUSTOMERS_PERM, CAMPAIGN_PERM)
def campaigns_list(request):
    return render(request, "builder/ops/campaigns.html", {
        "nav": "customers",
        "campaigns": Campaign.objects.filter(store=request.store).select_related("created_by")[:50],
    })


# ---------- سبدهای رهاشده ----------

@studio_required(REPORTS_PERM)
def abandoned_carts(request):
    """سبدهای مشتریان واردشده که پر شده‌اند ولی سفارشی بعد از آخرین تغییرشان ثبت نشده است."""
    carts = list(SavedCart.objects.for_store(request.store).exclude(items={})
                 .exclude(Exists(Order.objects.filter(store=request.store, user=OuterRef("user"),
                                                      created_at__gte=OuterRef("updated_at"))))
                 .select_related("user")[:100])
    variants = {str(v.pk): v for v in ProductVariant.objects.filter(
        pk__in={k for c in carts for k in c.items}).select_related("product")}
    for cart in carts:
        cart.lines = [(variants[k], int(q)) for k, q in cart.items.items() if k in variants]
        cart.value = sum(v.current_price * q for v, q in cart.lines)
    conf = notification_settings(request.store)
    return render(request, "builder/ops/carts.html", {
        "nav": "orders", "carts": carts, "total_value": sum(c.value for c in carts), "conf": conf,
    })


# ---------- گزارش جستجوها ----------

SEARCH_PERIODS = {1: "امروز", 7: "۷ روز", 30: "۳۰ روز", 90: "۹۰ روز"}


@studio_required(REPORTS_PERM)
def searches(request):
    try:
        days = int(request.GET.get("days", 7))
    except ValueError:
        days = 7
    days = days if days in SEARCH_PERIODS else 7
    return render(request, "builder/ops/searches.html", {
        "nav": "searches", "days": days, "periods": SEARCH_PERIODS.items(),
        "report": search_log.report(request.store, days),
    })


# ---------- مرجوعی و لغو بخشی ----------

def _qty_from_post(order, data):
    out = {}
    for item in order.items.all():
        try:
            qty = int(en_digits(data.get(f"qty-{item.pk}", "0")) or 0)
        except ValueError:
            qty = 0
        if qty > 0:
            out[item] = qty
    return out


@studio_required(REPORTS_PERM)
def returns_list(request):
    show = request.GET.get("show", "open")
    qs = ReturnRequest.objects.filter(order__store=request.store).select_related("order").prefetch_related(
        "items__order_item")
    if show == "open":
        qs = qs.filter(status__in=[ReturnRequest.Status.REQUESTED, ReturnRequest.Status.APPROVED,
                                   ReturnRequest.Status.RECEIVED])
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "builder/ops/returns.html", {"nav": "returns", "page": page, "show": show})


@studio_required(REPORTS_PERM)
def return_detail(request, pk):
    req = (ReturnRequest.objects.filter(order__store=request.store, pk=pk).select_related("order", "handled_by")
           .prefetch_related("items__order_item").first())
    if req is None:
        raise Http404
    if request.method == "POST":
        if not request.user.has_perm(ORDERS_PERM):
            raise PermissionDenied
        action, note = request.POST.get("action"), request.POST.get("note", "").strip()[:500]
        try:
            if action == "approve":
                returns.approve(req, request.user, note)
            elif action == "reject":
                returns.reject(req, request.user, note)
            elif action == "receive":
                returns.receive(req, request.user, restock=request.POST.get("restock") == "on", note=note)
            elif action == "refund":
                amount = int(en_digits(request.POST.get("amount", "0")).replace(",", "").replace("٬", "") or 0)
                method = request.POST.get("method", "")
                if method not in dict(ReturnRequest.RefundMethod.choices):
                    raise returns.ReturnError("روش بازپرداخت را انتخاب کنید.")
                returns.refund(req, amount=amount, method=method, reference=request.POST.get("reference", "").strip(),
                               user=request.user, note=note)
            else:
                raise Http404
        except (returns.ReturnError, ValueError) as exc:
            messages.error(request, str(exc) if isinstance(exc, returns.ReturnError) else "مبلغ نامعتبر است.")
            return redirect("builder:return", pk=pk)
        record(f"studio.return_{action}", request, target=req.order.number)
        messages.success(request, "ثبت شد؛ وضعیت با پیامک به مشتری اطلاع داده می‌شود.")
        return redirect("builder:return", pk=pk)
    return render(request, "builder/ops/return_detail.html", {
        "nav": "returns", "r": req, "methods": ReturnRequest.RefundMethod.choices,
    })


@studio_required(ORDERS_PERM)
def order_adjust(request, pk):
    """لغو بخشی (پیش از ارسال) یا ثبت مرجوعی از طرف مشتری (پس از ارسال)."""
    order = Order.objects.for_store(request.store).filter(pk=pk).first()
    if order is None:
        raise Http404
    mode = "cancel" if order.status in returns.CANCELLABLE else "return" if order.status in returns.RETURNABLE else None
    if mode is None:
        messages.error(request, "برای سفارش لغوشده امکان لغو بخشی یا مرجوعی نیست.")
        return redirect("builder:orders")
    if request.method == "POST":
        reason = request.POST.get("reason", "")
        if reason not in dict(ReturnRequest.Reason.choices):
            messages.error(request, "علت را انتخاب کنید.")
            return redirect("builder:order_adjust", pk=pk)
        try:
            quantities = _qty_from_post(order, request.POST)
            note = request.POST.get("note", "").strip()
            if mode == "cancel":
                req = returns.partial_cancel(order, quantities, reason=reason, user=request.user, note=note)
            else:
                req = returns.request_return(order, quantities, reason=reason, description=note, by_customer=False,
                                             user=request.user)
        except returns.ReturnError as exc:
            messages.error(request, str(exc))
            return redirect("builder:order_adjust", pk=pk)
        record(f"studio.{mode}_items", request, target=order.number)
        messages.success(request, "لغو بخشی ثبت شد و کالاها به انبار برگشت." if mode == "cancel"
                         else "درخواست مرجوعی ثبت شد.")
        return redirect("builder:return", pk=req.pk)
    return render(request, "builder/ops/order_adjust.html", {
        "nav": "returns", "order": order, "mode": mode, "available": returns.available(order),
        "reasons": ReturnRequest.Reason.choices,
    })
