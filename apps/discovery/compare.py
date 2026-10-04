"""فهرست مقایسه (نشست کاربر، حداکثر ۴ عطر) و ساخت جدول مقایسه."""

from dataclasses import dataclass, field

from apps.catalog import recommend
from apps.catalog.models import ProductNote
from apps.catalog.profile import LEVELS, LONGEVITY_HOURS, Concentration, Gender

SESSION_KEY = "compare"
MAX_ITEMS = 4


class CompareList:
    def __init__(self, request):
        self.session = request.session
        self.ids = [pk for pk in self.session.get(SESSION_KEY, []) if isinstance(pk, int)][:MAX_ITEMS]

    def __len__(self):
        return len(self.ids)

    def __contains__(self, product_id):
        return product_id in self.ids

    @property
    def is_full(self):
        return len(self.ids) >= MAX_ITEMS

    def _save(self):
        self.session[SESSION_KEY] = self.ids
        self.session.modified = True

    def toggle(self, product_id):
        """خروجی: (در فهرست است؟, پیام خطا یا None)."""
        if product_id in self.ids:
            self.ids.remove(product_id)
            self._save()
            return False, None
        if self.is_full:
            return False, f"حداکثر {MAX_ITEMS} عطر را می‌توان مقایسه کرد؛ یکی را از فهرست مقایسه حذف کنید."
        self.ids.append(product_id)
        self._save()
        return True, None

    def set(self, ids):
        self.ids = list(dict.fromkeys(ids))[:MAX_ITEMS]
        self._save()

    def clear(self):
        self.ids = []
        self._save()


def products_by_ids(store, ids):
    """محصولات فعال همین فروشگاه، به ترتیب ids (شناسه‌های نامعتبر یا فروشگاه دیگر نادیده گرفته می‌شوند)."""
    found = {p.pk: p for p in recommend.candidates(store).prefetch_related("attribute_values__attribute")
             .filter(pk__in=ids)}
    return [found[pk] for pk in ids if pk in found]


# ---------- جدول مقایسه ----------

@dataclass
class Row:
    label: str
    cells: list  # هر خانه: {"text"|"level"|"notes"...}
    kind: str = "text"
    best: set = field(default_factory=set)  # اندیس ستون‌های برتر این ردیف

    @property
    def is_same(self):
        values = [repr(c.get("value")) for c in self.cells]
        return len(set(values)) <= 1


@dataclass
class Group:
    title: str
    rows: list


def _price_range(p):
    prices = sorted(v.price for v in p.variants.all())
    return (prices[0], prices[-1]) if prices else (None, None)


def _per_ml(p):
    values = [v.price / v.size_ml for v in p.variants.all() if v.size_ml]
    return round(min(values)) if values else None


def _best(values, highest=True):
    present = [v for v in values if v is not None]
    if len(present) < 2 or len(set(present)) == 1:
        return set()
    target = max(present) if highest else min(present)
    return {i for i, v in enumerate(values) if v == target}


def _notes_row(products, layer, label, counts):
    cells = []
    for p in products:
        names = [link.note.name for link in sorted(p.notes.all(), key=lambda n: (n.order, n.pk)) if link.layer == layer]
        cells.append({"value": tuple(names), "notes": [{"name": n, "shared": counts[n] > 1, "everyone": counts[n] == len(products)}
                                                       for n in names]})
    return Row(label, cells, kind="notes")


def build_table(products):
    """گروه‌های ردیف جدول مقایسه؛ برترین مقدار هر ردیف (ارزان‌ترین، ماندگارترین، …) علامت می‌خورد."""
    gender, concentration = dict(Gender.choices), dict(Concentration.choices)
    prices = [_price_range(p) for p in products]
    per_ml = [_per_ml(p) for p in products]
    ratings = [round(p.rating_avg, 1) if p.rating_avg else None for p in products]
    longevity = [p.longevity for p in products]
    sillage = [p.sillage for p in products]

    note_counts = {}
    for p in products:
        for name in {link.note.name for link in p.notes.all()}:
            note_counts[name] = note_counts.get(name, 0) + 1

    summary = Group("خلاصه", [
        Row("قیمت", [{"value": pr, "low": pr[0], "high": pr[1]} for pr in prices], kind="price",
            best=_best([pr[0] for pr in prices], highest=False)),
        Row("قیمت هر میلی‌لیتر (ارزان‌ترین حجم)", [{"value": v, "money": v} for v in per_ml], kind="money",
            best=_best(per_ml, highest=False)),
        Row("حجم‌ها", [{"value": tuple(sorted(v.size_ml for v in p.variants.all()))} for p in products], kind="sizes"),
        Row("امتیاز مشتریان", [{"value": r, "rating": r, "count": p.review_count} for r, p in zip(ratings, products, strict=True)],
            kind="rating", best=_best(ratings)),
        Row("موجودی", [{"value": p.in_stock, "text": "موجود" if p.in_stock else "ناموجود"} for p in products]),
        Row("برند", [{"value": p.brand.name, "text": p.brand.name} for p in products]),
    ])
    character = Group("شخصیت رایحه", [
        Row("خانواده رایحه", [{"value": p.scent.name, "text": p.scent.name} for p in products]),
        Row("غلظت", [{"value": p.concentration, "text": concentration.get(p.concentration, "—")} for p in products]),
        Row("مناسب برای", [{"value": p.gender, "text": gender.get(p.gender, "—")} for p in products]),
        Row("ماندگاری", [{"value": v, "level": v, "hint": LONGEVITY_HOURS.get(v, "")} for v in longevity],
            kind="level", best=_best(longevity)),
        Row("پخش بو", [{"value": v, "level": v, "hint": LEVELS.get(v, "")} for v in sillage], kind="level",
            best=_best(sillage)),
        Row("فصل مناسب", [{"value": tuple(p.seasons), "chips": p.season_labels} for p in products], kind="chips"),
        Row("موقعیت مناسب", [{"value": tuple(p.occasions), "chips": p.occasion_labels} for p in products], kind="chips"),
    ])
    attrs = {}
    for p in products:
        for av in p.attribute_values.all():
            attrs.setdefault(av.attribute.name, {})[p.pk] = av.value
    if attrs:
        character.rows += [Row(name, [{"value": values.get(p.pk), "text": values.get(p.pk, "—")} for p in products])
                           for name, values in sorted(attrs.items())]

    L = ProductNote.Layer
    pyramid = Group("هرم نت‌ها", [
        _notes_row(products, L.TOP, "نت آغازین", note_counts),
        _notes_row(products, L.HEART, "نت میانی", note_counts),
        _notes_row(products, L.BASE, "نت پایه", note_counts),
    ])
    shared_all = sorted(n for n, c in note_counts.items() if c == len(products) and len(products) > 1)
    groups = [summary, character, pyramid]
    if len(products) > 1:
        first = products[0]
        groups.append(Group("شباهت رایحه", [
            Row(f"شباهت به «{first.name}»", [{"value": None if p.pk == first.pk else recommend.similarity(first, p),
                                             "percent": None if p.pk == first.pk else round(recommend.similarity(first, p) * 100)}
                                            for p in products], kind="percent"),
        ]))
    return groups, shared_all
