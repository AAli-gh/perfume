"""ورود و خروج گروهی محصولات (Excel/CSV) و تغییر گروهی قیمت با پیش‌نمایش و امکان بازگرداندن.

قالب فایل: هر ردیف یک حجم (variant). ستون‌ها با عنوان فارسی (همان فایل خروجی) یا کلید انگلیسی شناخته می‌شوند.
- ردیفی که «شناسه محصول» آن در فروشگاه هست ← به‌روزرسانی (فقط ستون‌های پر و متفاوت).
- شناسه ناموجود + نام ← محصول جدید (غیرفعال، با تصویر جایگزین تا مدیر تصویر بگذارد و فعال کند).
- حجم ناموجودِ یک محصول موجود ← حجم جدید.
تغییر موجودی از inventory (دفتر موجودی با علت «ورود گروهی از فایل») و تغییر قیمت در PriceChangeBatch ثبت می‌شود.
"""

import io
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.core.forms import en_digits
from apps.core.stores import get_current_store

from . import inventory
from .models import Brand, PriceChangeBatch, Product, ProductVariant, ScentFamily, StockMovement
from .profile import Kind
from .smart_search import invalidate_vocab

COLUMNS = [
    ("slug", "شناسه محصول"),
    ("name", "نام محصول"),
    ("kind", "نوع"),
    ("brand", "برند"),
    ("scent", "خانواده رایحه"),
    ("size", "حجم (میل)"),
    ("price", "قیمت (تومان)"),
    ("stock", "موجودی"),
    ("active", "فعال"),
    ("short", "توضیح کوتاه"),
]
HEADERS = {label: key for key, label in COLUMNS} | {key: key for key, _ in COLUMNS}
KINDS = {"عطر": Kind.PERFUME, "perfume": Kind.PERFUME, "باکس": Kind.GIFT_BOX, "باکس هدیه": Kind.GIFT_BOX,
         "gift_box": Kind.GIFT_BOX}
TRUE = {"بله", "فعال", "1", "true", "yes", "y", "✓", "دارد"}
FALSE = {"خیر", "غیرفعال", "0", "false", "no", "n", "ندارد"}


# ---------- خروجی ----------

def export_rows(store):
    yield [label for _, label in COLUMNS]
    variants = (ProductVariant.objects.filter(product__store=store)
                .select_related("product__brand", "product__scent").order_by("product__name", "size_ml"))
    for v in variants:
        p = v.product
        yield [p.slug, p.name, p.get_kind_display(), p.brand.name, p.scent.name if p.scent_id else "",
               v.size_ml, v.price, v.stock, p.is_active, p.short_description]


# ---------- ورود ----------

def parse_int(value):
    """«۳٬۵۰۰٬۰۰۰ تومان»، «3,500,000» یا «3500000.0» ← 3500000؛ خالی ← None."""
    text = en_digits(str(value or "")).replace("٬", "").replace(",", "").replace("تومان", "").strip()
    if not text:
        return None
    text = re.sub(r"\.0+$", "", text)
    if not re.fullmatch(r"-?\d+", text):
        raise ValueError(f"«{value}» عدد نیست")
    return int(text)


def parse_bool(value):
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in TRUE:
        return True
    if text in FALSE:
        return False
    raise ValueError(f"«{value}» باید «بله» یا «خیر» باشد")


@dataclass
class RowPlan:
    line: int
    title: str
    action: str  # update | new_variant | new_product | unchanged | error
    changes: list = field(default_factory=list)  # [(عنوان، قبلی، جدید)]
    error: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class ImportPlan:
    rows: list
    missing_headers: list

    def count(self, action):
        return sum(r.action == action for r in self.rows)

    @property
    def applicable(self):
        return [r for r in self.rows if r.action in ("update", "new_variant", "new_product")]


def _header_map(header):
    mapping = {}
    for index, title in enumerate(header):
        key = HEADERS.get(str(title).strip()) or HEADERS.get(str(title).strip().lower())
        if key and key not in mapping:
            mapping[key] = index
    return mapping


def plan_import(store, table):
    if not table:
        return ImportPlan([], ["slug", "size"])
    mapping = _header_map(table[0])
    missing = [label for key, label in COLUMNS if key in ("slug", "size") and key not in mapping]
    if missing:
        return ImportPlan([], missing)
    products = {p.slug: p for p in Product.objects.for_store(store).select_related("brand", "scent")}
    variants = {(v.product.slug, v.size_ml): v
                for v in ProductVariant.objects.filter(product__store=store).select_related("product")}
    seen, plans = set(), []
    new_products = {}
    for line, raw in enumerate(table[1:], start=2):
        row = {key: (raw[i] if i < len(raw) else "") for key, i in mapping.items()}
        slug = slugify(str(row.get("slug", "")).strip(), allow_unicode=True)
        try:
            size = parse_int(row.get("size"))
            price, stock = parse_int(row.get("price")), parse_int(row.get("stock"))
            active = parse_bool(row.get("active"))
        except ValueError as exc:
            plans.append(RowPlan(line, slug or "—", "error", error=str(exc)))
            continue
        title = f"{row.get('name') or slug} ({size} میل)" if size else (row.get("name") or slug)
        if not slug:
            plans.append(RowPlan(line, title or "—", "error", error="شناسه محصول خالی است"))
            continue
        if size is None or size < 0 or size > 5000:
            plans.append(RowPlan(line, title, "error", error="حجم نامعتبر است"))
            continue
        if (price is not None and not 0 < price < 2_000_000_000) or (stock is not None and not 0 <= stock < 1_000_000):
            plans.append(RowPlan(line, title, "error", error="قیمت یا موجودی خارج از محدوده است"))
            continue
        if (slug, size) in seen:
            plans.append(RowPlan(line, title, "error", error="این محصول و حجم در فایل تکرار شده است"))
            continue
        seen.add((slug, size))
        data = {"slug": slug, "size": size, "price": price, "stock": stock, "active": active,
                "name": str(row.get("name") or "").strip()[:150], "brand": str(row.get("brand") or "").strip(),
                "scent": str(row.get("scent") or "").strip(), "short": str(row.get("short") or "").strip()[:300],
                "kind": KINDS.get(str(row.get("kind") or "").strip(), None)}
        product = products.get(slug)
        if product is None and slug not in new_products:
            if not data["name"] or not data["brand"] or price is None:
                plans.append(RowPlan(line, title, "error",
                                     error="محصول جدید: نام، برند و قیمت لازم است (شناسه در فروشگاه نیست)"))
                continue
            if (data["kind"] or Kind.PERFUME) == Kind.PERFUME and not data["scent"]:
                plans.append(RowPlan(line, title, "error", error="محصول جدید: خانواده رایحه لازم است"))
                continue
            new_products[slug] = data
            plans.append(RowPlan(line, title, "new_product", [("محصول جدید", "", data["name"])], data=data))
            continue
        if product is None:  # حجم دیگری از محصول جدیدی که در همین فایل است
            if price is None:
                plans.append(RowPlan(line, title, "error", error="حجم جدید: قیمت لازم است"))
                continue
            plans.append(RowPlan(line, title, "new_variant", [("حجم جدید", "", f"{size} میل")], data=data))
            continue
        variant = variants.get((slug, size))
        changes = []
        if variant is None:
            if price is None:
                plans.append(RowPlan(line, title, "error", error="حجم جدید: قیمت لازم است"))
                continue
            changes.append(("حجم جدید", "", f"{size} میل"))
        else:
            if price is not None and price != variant.price:
                changes.append(("قیمت", variant.price, price))
            if stock is not None and stock != variant.stock:
                changes.append(("موجودی", variant.stock, stock))
        if active is not None and active != product.is_active:
            changes.append(("فعال", "بله" if product.is_active else "خیر", "بله" if active else "خیر"))
        if data["name"] and data["name"] != product.name:
            changes.append(("نام", product.name, data["name"]))
        if data["short"] and data["short"] != product.short_description:
            changes.append(("توضیح کوتاه", product.short_description[:40], data["short"][:40]))
        action = "new_variant" if variant is None else ("update" if changes else "unchanged")
        plans.append(RowPlan(line, title, action, changes, data=data))
    return ImportPlan(plans, [])


def _placeholder_image(name):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (600, 720), (34, 24, 19)).save(buffer, "JPEG", quality=80)
    return ContentFile(buffer.getvalue(), name=f"{slugify(name, allow_unicode=True) or 'product'}.jpg")


@transaction.atomic
def apply_import(store, plan, user=None):
    """اعمال ردیف‌های بدون خطا؛ خروجی dict شمارش‌ها."""
    store = store or get_current_store()
    counts = {"updated": 0, "new_products": 0, "new_variants": 0, "stock": 0, "prices": 0}
    price_changes = []
    products = {p.slug: p for p in Product.objects.for_store(store)}
    for row in plan.applicable:
        d = row.data
        product = products.get(d["slug"])
        if product is None:
            brand = Brand.objects.for_store(store).filter(name=d["brand"]).first() or Brand.objects.create(
                store=store, name=d["brand"], slug=_unique_slug(Brand, store, d["brand"]))
            kind = d["kind"] or Kind.PERFUME
            scent = None
            if kind == Kind.PERFUME:
                scent = ScentFamily.objects.for_store(store).filter(name=d["scent"]).first() or ScentFamily.objects.create(
                    store=store, name=d["scent"], slug=_unique_slug(ScentFamily, store, d["scent"]))
            product = Product(store=store, slug=d["slug"], name=d["name"], brand=brand, scent=scent, kind=kind,
                              short_description=d["short"] or d["name"], description=d["short"] or d["name"],
                              is_active=False, gift_capacity=1 if kind == Kind.GIFT_BOX else None)
            product.image.save(f"{d['slug']}.jpg", _placeholder_image(d["slug"]), save=False)
            product.save()
            products[d["slug"]] = product
            counts["new_products"] += 1
        else:
            fields = []
            if d["active"] is not None and d["active"] != product.is_active:
                product.is_active, fields = d["active"], fields + ["is_active"]
            if d["name"] and d["name"] != product.name:
                product.name, fields = d["name"], fields + ["name"]
            if d["short"] and d["short"] != product.short_description:
                product.short_description, fields = d["short"], fields + ["short_description"]
            if fields:
                product.save(update_fields=fields)
        variant = ProductVariant.objects.filter(product=product, size_ml=d["size"]).first()
        if variant is None:
            variant = ProductVariant.objects.create(product=product, size_ml=d["size"], price=d["price"], stock=0)
            if d["stock"]:
                inventory.set_stock(variant, d["stock"], user=user, note="ورود گروهی از فایل",
                                    reason=StockMovement.Reason.IMPORT)
            if row.action != "new_product":
                counts["new_variants"] += 1
            continue
        if d["price"] is not None and d["price"] != variant.price:
            price_changes.append([variant.pk, variant.price, d["price"]])
            ProductVariant.objects.filter(pk=variant.pk).update(price=d["price"])
            counts["prices"] += 1
        if d["stock"] is not None and d["stock"] != variant.stock:
            inventory.set_stock(variant, d["stock"], user=user, note="ورود گروهی از فایل",
                                reason=StockMovement.Reason.IMPORT)
            counts["stock"] += 1
        counts["updated"] += 1
    if price_changes:
        PriceChangeBatch.objects.create(store=store, description="ورود قیمت از فایل", changes=price_changes,
                                        created_by=user if user and user.is_authenticated else None)
    transaction.on_commit(lambda: invalidate_vocab(store.pk))  # بازه قیمت جستجوی هوشمند
    return counts


def _unique_slug(model, store, name):
    base = slugify(name, allow_unicode=True)[:90] or "item"
    slug, n = base, 2
    while model.objects.for_store(store).filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


# ---------- تغییر گروهی قیمت ----------

ROUNDING = [(0, "بدون گرد کردن"), (1000, "۱٬۰۰۰ تومان"), (10_000, "۱۰٬۰۰۰ تومان"), (50_000, "۵۰٬۰۰۰ تومان"),
            (100_000, "۱۰۰٬۰۰۰ تومان")]


@dataclass(frozen=True)
class PriceRule:
    mode: str  # percent | amount
    value: Decimal  # +۱۵ یعنی ۱۵٪ (یا ۱۵ تومان) افزایش؛ منفی یعنی کاهش
    rounding: int = 0

    def apply(self, price):
        new = Decimal(price) * (1 + self.value / 100) if self.mode == "percent" else Decimal(price) + self.value
        if self.rounding:
            new = (new / self.rounding).quantize(Decimal(1), rounding=ROUND_HALF_UP) * self.rounding
        return max(int(new.quantize(Decimal(1), rounding=ROUND_HALF_UP)), 1000)

    def describe(self):
        sign = "+" if self.value >= 0 else "−"
        amount = f"{abs(self.value).normalize():f}٪" if self.mode == "percent" else f"{int(abs(self.value)):,} تومان"
        text = f"{sign}{amount}"
        return text + (f"، گرد به {self.rounding:,}" if self.rounding else "")


def price_scope(store, *, brands=(), scents=(), collections=(), kind="", active_only=False):
    qs = ProductVariant.objects.filter(product__store=store).select_related("product__brand")
    if brands:
        qs = qs.filter(product__brand__in=brands)
    if scents:
        qs = qs.filter(product__scent__in=scents)
    if collections:
        qs = qs.filter(product__collection__in=collections)
    if kind:
        qs = qs.filter(product__kind=kind)
    if active_only:
        qs = qs.filter(product__is_active=True)
    return qs.order_by("product__name", "size_ml")


def plan_prices(variants, rule):
    """[(variant, قیمت فعلی، قیمت جدید)] فقط برای حجم‌هایی که قیمتشان عوض می‌شود."""
    rows = []
    for v in variants:
        new = rule.apply(v.price)
        if new != v.price:
            rows.append((v, v.price, new))
    return rows


@transaction.atomic
def apply_prices(store, rows, description, user=None):
    for variant, _old, new in rows:
        ProductVariant.objects.filter(pk=variant.pk).update(price=new)
    transaction.on_commit(lambda: invalidate_vocab(store.pk))
    return PriceChangeBatch.objects.create(
        store=store, description=description[:200], changes=[[v.pk, old, new] for v, old, new in rows],
        created_by=user if user and user.is_authenticated else None)


@transaction.atomic
def revert_batch(batch):
    """بازگرداندن قیمت‌ها؛ حجمی که بعد از این تغییر دوباره قیمتش عوض شده دست نمی‌خورد. خروجی: (برگشت، ردشده)."""
    batch = PriceChangeBatch.objects.select_for_update().get(pk=batch.pk)
    if batch.reverted_at:
        return 0, 0
    current = dict(ProductVariant.objects.filter(pk__in=[c[0] for c in batch.changes]).values_list("pk", "price"))
    reverted = skipped = 0
    for variant_id, old, new in batch.changes:
        if current.get(variant_id) == new:
            ProductVariant.objects.filter(pk=variant_id).update(price=old)
            reverted += 1
        else:
            skipped += 1
    batch.reverted_at = timezone.now()
    batch.save(update_fields=["reverted_at"])
    transaction.on_commit(lambda: invalidate_vocab(batch.store_id))
    return reverted, skipped
