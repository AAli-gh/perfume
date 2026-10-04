"""موتور پیشنهاد رایحه (محتوامحور، بدون سرویس خارجی).

هر محصول یک «بردار نت» دارد: وزن هر نت بسته به لایه هرم (پایه بیشترین اثر را در شخصیت عطر دارد).
- شباهت دو عطر: شباهت کسینوسی بردار نت‌ها + امتیاز هم‌خانوادگی رایحه.
- سلیقه کاربر (Taste): جمع وزن‌دار بردار عطرهایی که خریده، پسندیده یا دیده است.
- پیشنهاد: عطرهای فعال فروشگاه به ترتیب شباهت به سلیقه، همراه دلیل («نت‌های محبوب شما: عود، زعفران»).

برای فروشگاه‌های تا چند هزار محصول، محاسبه در حافظه و با یک کوئری (prefetch نت‌ها) انجام می‌شود.
"""

import math
from collections import Counter
from dataclasses import dataclass, field

from django.db.models import Prefetch

from .models import ProductNote
from .selectors import listable_products

LAYER_WEIGHTS = {ProductNote.Layer.TOP: 0.7, ProductNote.Layer.HEART: 1.0, ProductNote.Layer.BASE: 1.3}
FAMILY_BONUS = 0.15  # سهم هم‌خانوادگی رایحه در شباهت (۰ تا ۱)


def note_vector(product):
    """{note_id: وزن}؛ با prefetch روی notes__note بدون کوئری اضافه."""
    vector = Counter()
    for link in product.notes.all():
        vector[link.note_id] = max(vector[link.note_id], LAYER_WEIGHTS.get(link.layer, 1.0))
    return vector


def note_names(product):
    return {link.note_id: link.note.name for link in product.notes.all()}


def cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(weight * b.get(key, 0) for key, weight in a.items())
    norm = math.sqrt(sum(w * w for w in a.values())) * math.sqrt(sum(w * w for w in b.values()))
    return dot / norm if norm else 0.0


def similarity(a, b):
    """شباهت دو محصول بین ۰ و ۱."""
    score = (1 - FAMILY_BONUS) * cosine(note_vector(a), note_vector(b))
    if a.scent_id and a.scent_id == b.scent_id:
        score += FAMILY_BONUS
    return round(min(score, 1.0), 4)


def candidates(store):
    """محصولات فعال قابل پیشنهاد، همراه نت‌ها (یک کوئری prefetch)."""
    return listable_products(store).prefetch_related(
        Prefetch("notes", queryset=ProductNote.objects.select_related("note")))


def similar_products(product, limit=8, pool=None):
    """عطرهای مشابه یک محصول (بیشترین نت مشترک)، بدون خود محصول."""
    pool = list(pool if pool is not None else candidates(product.store_id))
    scored = [(similarity(product, p), p) for p in pool if p.pk != product.pk]
    scored = [item for item in scored if item[0] > 0]
    scored.sort(key=lambda item: (-item[0], item[1].pk))
    for score, p in scored:
        p.similarity = score
    return [p for _, p in scored[:limit]]


@dataclass
class Taste:
    """سلیقه رایحه یک کاربر: وزن نت‌ها و خانواده‌ها."""

    notes: Counter = field(default_factory=Counter)
    families: Counter = field(default_factory=Counter)
    names: dict = field(default_factory=dict)  # note_id ← نام (برای توضیح پیشنهاد)
    seen: set = field(default_factory=set)  # محصولاتی که پیشنهاد داده نمی‌شوند (قبلاً خریده/پسندیده)

    def add(self, product, weight=1.0):
        for note_id, w in note_vector(product).items():
            self.notes[note_id] += w * weight
        self.names.update(note_names(product))
        if product.scent_id:
            self.families[product.scent_id] += weight

    @property
    def is_empty(self):
        return not self.notes

    def favorite_notes(self, limit=6):
        return [self.names[n] for n, _ in self.notes.most_common(limit) if n in self.names]


def recommend(store, taste, limit=8, pool=None):
    """پیشنهاد بر اساس سلیقه؛ هر محصول دارای match (۰ تا ۱۰۰) و reasons است."""
    if taste.is_empty:
        return []
    pool = list(pool if pool is not None else candidates(store))
    top_family = taste.families.most_common(1)[0][0] if taste.families else None
    favorites = {n for n, _ in taste.notes.most_common(8)}
    results = []
    for p in pool:
        if p.pk in taste.seen:
            continue
        vector = note_vector(p)
        score = (1 - FAMILY_BONUS) * cosine(taste.notes, vector)
        if top_family and p.scent_id == top_family:
            score += FAMILY_BONUS
        if score <= 0:
            continue
        shared = [taste.names[n] for n in sorted(vector, key=lambda n: -taste.notes.get(n, 0)) if n in favorites]
        p.match = round(min(score, 1.0) * 100)
        p.reasons = []
        if shared:
            p.reasons.append("نت‌های محبوب شما: " + "، ".join(shared[:3]))
        if top_family and p.scent_id == top_family:
            p.reasons.append(f"از خانواده رایحه محبوب شما ({p.scent.name})")
        results.append(p)
    results.sort(key=lambda p: (-p.match, p.pk))
    return results[:limit]
