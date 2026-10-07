"""جستجوی محصولات با PostgreSQL (بدون موتور جستجوی خارجی).

- هر محصول یک «سند جستجو» نرمال‌شده دارد (search_document) شامل نام، برند، خانواده رایحه، کالکشن،
  دسته‌ها، برچسب‌ها، نت‌ها، ویژگی‌ها و توضیحات.
- search_vector: بردار وزن‌دار ('simple') برای تطبیق کلمه/پیشوند و رتبه‌بندی (نام > برند و نت‌ها > بقیه).
- ایندکس trigram روی search_document برای تطبیق بخشی از کلمه.
- نرمال‌سازی فارسی: ي/ك عربی، اعراب، کشیده، نیم‌فاصله و ارقام فارسی/عربی یکسان می‌شوند.
"""

import re

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import F, FloatField, Q, Value

from apps.core.db import is_postgres

_CHAR_MAP = str.maketrans({
    "ي": "ی", "ى": "ی", "ئ": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ؤ": "و",
    "‌": "", "‍": "", "ـ": "",
    **{d: str(i) for i, d in enumerate("۰۱۲۳۴۵۶۷۸۹")},
    **{d: str(i) for i, d in enumerate("٠١٢٣٤٥٦٧٨٩")},
})
_DIACRITICS = re.compile(r"[ً-ٰٟۖ-ۭ]")
_SPACES = re.compile(r"\s+")
_TOKEN = re.compile(r"\w+", re.UNICODE)


def normalize(text):
    """نرمال‌سازی متن فارسی/انگلیسی برای جستجو."""
    text = _DIACRITICS.sub("", (text or "").translate(_CHAR_MAP)).lower()
    return _SPACES.sub(" ", text).strip()


def _join(parts):
    return normalize(" ".join(p for p in parts if p))


def document_parts(product):
    """بخش‌های وزن‌دار سند جستجوی یک محصول: (A: نام، B: برند/نت/دسته، C: بقیه)."""
    notes = [link.note.name for link in product.notes.all()]
    a = [product.name]
    b = [product.brand.name, product.scent.name if product.scent_id else "باکس هدیه", *notes, *(c.name for c in product.categories.all())]
    c = [
        product.collection.name if product.collection_id else "",
        *(t.name for t in product.tags.all()),
        *(str(v.value) for v in product.attribute_values.all()),
        product.short_description,
        product.description,
    ]
    return _join(a), _join(b), _join(c)


def reindex_products(product_ids):
    """به‌روزرسانی سند و بردار جستجوی محصولات داده‌شده."""
    from .models import Product

    products = (
        Product.objects.filter(pk__in=list(product_ids))
        .select_related("brand", "scent", "collection")
        .prefetch_related("notes__note", "categories", "tags", "attribute_values")
    )
    for product in products:
        a, b, c = document_parts(product)
        if not is_postgres():  # پایگاه نمایشی: فقط سند متنی (بدون tsvector)
            Product.objects.filter(pk=product.pk).update(search_document=" ".join(x for x in (a, b, c) if x))
            continue
        Product.objects.filter(pk=product.pk).update(
            search_document=" ".join(x for x in (a, b, c) if x),
            search_vector=(
                SearchVector(Value(a), weight="A", config="simple")
                + SearchVector(Value(b), weight="B", config="simple")
                + SearchVector(Value(c), weight="C", config="simple")
            ),
        )


def search_products(queryset, raw_query):
    """فیلتر و رتبه‌بندی محصولات بر اساس عبارت جستجو؛ annotate: search_rank."""
    q = normalize(raw_query)
    tokens = _TOKEN.findall(q)
    if not tokens:
        return queryset
    substring = Q()
    for t in tokens:
        substring &= Q(search_document__contains=t)
    if not is_postgres():  # پایگاه نمایشی: تطبیق متن نرمال‌شده، بدون رتبه‌بندی
        return queryset.filter(substring).annotate(search_rank=Value(0.0, output_field=FloatField()))
    # هر کلمه به‌صورت پیشوند (برای جستجو حین تایپ) و همه کلمات با AND
    tsquery = SearchQuery(" & ".join(f"{t}:*" for t in tokens), config="simple", search_type="raw")
    return queryset.filter(Q(search_vector=tsquery) | substring).annotate(
        search_rank=SearchRank(F("search_vector"), tsquery)
    )
