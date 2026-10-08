"""جستجوی هوشمند فارسی: تبدیل عبارت آزاد مشتری به فیلترهای دقیق (بدون سرویس خارجی و بدون AI).

نمونه: «عطر خنک زیر سه تومن» ← خانواده خنک و تازه + قیمت تا ۳٬۰۰۰٬۰۰۰ تومان.

مراحل:
1. parse(): عبارت را به توکن‌های نرمال‌شده می‌شکند و با بلندترین تطبیق، معیارها را تشخیص می‌دهد:
   قیمت (زیر/بالای/بین/حدود، عدد با رقم یا حروف، میلیون/هزار/تومن محاوره‌ای)، حس رایحه (خنک، گرم، شیرین…)،
   خانواده، نت (و «بدون نت»)، برند، جنسیت، فصل، موقعیت، ماندگاری، پخش بو، غلظت، حجم، ترتیب و موجودی.
   کلمات باقی‌مانده جستجوی متنی معمولی می‌شوند؛ اشتباه تایپی نزدیک به واژگان فروشگاه اصلاح می‌شود.
2. apply(): معیارها را روی QuerySet محصولات اعمال می‌کند.
3. search(): اگر نتیجه دقیقی نبود، کم‌اهمیت‌ترین شرط‌ها را یکی‌یکی کنار می‌گذارد و «نزدیک‌ترین» نتایج را
   با توضیح شرط حذف‌شده برمی‌گرداند.

واژگان فروشگاه (خانواده‌ها، نت‌ها، برندها، نام محصولات) از پایگاه داده خوانده و کش می‌شود؛ واژگان ثابت زبان
(حس‌ها، فصل‌ها، واحدهای پول…) پایین همین فایل‌اند.
"""

import difflib
import re
from dataclasses import dataclass, field

from django.core.cache import cache
from django.db.models import Case, Exists, ExpressionWrapper, IntegerField, OuterRef, Q, Value, When

from apps.core.db import is_postgres

from .profile import Gender, Kind, Occasion, Season
from .search import normalize, search_products

VOCAB_TTL = 600
APPROX = 0.2  # «حدود ۳ میلیون» = ±۲۰٪


def _n(text):
    return tuple(normalize(text).split())


# ---------- واژگان ثابت ----------

# حس‌های رایحه: هر حس به خانواده‌های فروشگاه (با slug یا کلمه‌ای در نام خانواده) نگاشت می‌شود؛ اگر فروشگاه
# چنین خانواده‌ای نداشت، به نت‌های شاخص همان حس.
FEELS = {
    "fresh": {
        "label": "خنک و تازه",
        "words": ["خنک", "خنکی", "خنک و تازه", "تازه", "فرش", "فرشی", "fresh", "سبک و خنک", "اسپرت", "اسپورت", "sport"],
        "families": ["fresh", "citrus", "aquatic", "green", "aromatic"],
        "family_words": ["خنک", "تازه", "مرکبات", "دریایی", "fresh"],
        "notes": ["لیمو", "برگاموت", "نعناع", "نت‌های دریایی", "گریپ‌فروت", "نارنگی", "پرتقال", "پرتقال تلخ", "خیار",
                  "چای سبز", "اسطوخودوس"],
    },
    "citrus": {
        "label": "مرکباتی",
        "words": ["مرکباتی", "مرکبات", "لیمویی", "سیتروس", "citrus", "پرتقالی"],
        "families": ["citrus", "fresh"],
        "family_words": ["مرکبات", "خنک", "تازه"],
        "notes": ["لیمو", "برگاموت", "گریپ‌فروت", "نارنگی", "پرتقال", "پرتقال تلخ"],
    },
    "aquatic": {
        "label": "دریایی",
        "words": ["دریایی", "اکواتیک", "aquatic", "اقیانوسی", "آبی"],
        "families": ["aquatic", "fresh"],
        "family_words": ["دریایی", "خنک", "تازه"],
        "notes": ["نت‌های دریایی"],
    },
    "warm": {
        "label": "گرم",
        "words": ["گرم", "گرمی", "warm"],
        "families": ["oriental", "spicy", "amber", "gourmand"],
        "family_words": ["شرقی", "ادویه", "گرم", "کهربا"],
        "notes": ["عنبر", "کهربا", "وانیل", "دارچین", "عود", "بخور"],
    },
    "sweet": {
        "label": "شیرین",
        "words": ["شیرین", "شیرینی", "گورمند", "gourmand", "sweet"],
        "families": ["gourmand"],
        "family_words": ["شیرین", "گورمند"],
        "notes": ["وانیل", "عسل", "تونکا", "کهربا", "بنزوئین", "کارامل", "شکلات", "قهوه", "پرالین"],
    },
    "floral": {
        "label": "گلی",
        "words": ["گلی", "گل", "فلورال", "floral", "گلدار"],
        "families": ["floral"],
        "family_words": ["گل"],
        "notes": ["رز", "یاس", "گل مریم", "گل رز دمشقی", "ارکیده"],
    },
    "woody": {
        "label": "چوبی",
        "words": ["چوبی", "وودی", "woody"],
        "families": ["woody"],
        "family_words": ["چوب"],
        "notes": ["چوب صندل", "چوب سدر", "وتیور", "عود", "پچولی"],
    },
    "oriental": {
        "label": "شرقی",
        "words": ["شرقی", "اورینتال", "oriental", "عربی"],
        "families": ["oriental"],
        "family_words": ["شرقی"],
        "notes": ["عود", "عنبر", "بخور", "زعفران"],
    },
    "spicy": {
        "label": "تند و ادویه‌ای",
        "words": ["تند", "ادویه‌ای", "ادویه ای", "ادویه", "اسپایسی", "spicy"],
        "families": ["spicy"],
        "family_words": ["ادویه", "تند"],
        "notes": ["فلفل", "دارچین", "میخک", "هل", "زنجبیل", "زعفران"],
    },
    "smoky": {
        "label": "دودی و عودی",
        "words": ["دودی", "smoky"],
        "families": [],
        "family_words": [],
        "notes": ["عود", "بخور", "قلب عود", "چرم"],
    },
}

GENDER_WORDS = {
    Gender.MEN: ["مردانه", "مردونه", "مرد", "مردها", "مردا", "آقا", "آقایان", "آقایون", "پسرانه", "پسرونه", "پسر",
                 "شوهرم", "پدرم", "بابام", "برادرم", "داداشم", "پسرم", "men", "male"],
    Gender.WOMEN: ["زنانه", "زنونه", "زن", "زنها", "خانم", "خانوم", "خانمها", "بانو", "بانوان", "دخترانه", "دخترونه",
                   "دختر", "مادرم", "مامانم", "خواهرم", "دخترم", "خانمم", "women", "female", "lady"],
    Gender.UNISEX: ["یونیسکس", "مشترک", "دوجنسیتی", "دو جنسیتی", "هم مردانه هم زنانه", "unisex"],
}

SEASON_WORDS = {
    Season.SUMMER: ["تابستان", "تابستون", "تابستانی", "تابستونی", "گرما", "هوای گرم", "فصل گرم", "summer"],
    Season.WINTER: ["زمستان", "زمستون", "زمستانی", "زمستونی", "سرما", "هوای سرد", "فصل سرد", "winter"],
    Season.SPRING: ["بهار", "بهاری", "spring"],
    Season.AUTUMN: ["پاییز", "پاییزی", "پائیز", "پائیزی", "autumn", "fall"],
}

OCCASION_WORDS = {
    Occasion.DAILY: ["روزانه", "هر روز", "هرروز", "روزمره", "استفاده روزانه", "دانشگاه", "daily"],
    Occasion.OFFICE: ["اداری", "اداره", "محل کار", "محیط کار", "سر کار", "کار", "شرکت", "دفتر", "office"],
    Occasion.EVENING: ["شب", "شبانه", "مهمانی", "مهمونی", "پارتی", "دورهمی", "party"],
    Occasion.FORMAL: ["مجلسی", "رسمی", "عروسی", "مراسم", "جشن", "formal"],
    Occasion.ROMANTIC: ["قرار", "عاشقانه", "رمانتیک", "دیت", "ولنتاین", "romantic", "date"],
}

CONCENTRATION_WORDS = {
    "extrait": ["اکستریت", "اکسترکت", "عصاره", "پرفیوم اکستریت", "extrait", "parfum"],
    "edp": ["ادو پرفیوم", "ادوپرفیوم", "او دو پرفیوم", "پرفیوم", "edp"],
    "edt": ["ادو تویلت", "ادوتویلت", "او دو تویلت", "تویلت", "edt"],
    "edc": ["ادو کلن", "او دو کلن", "edc"],
}
CONCENTRATION_LABELS = {"extrait": "اکستریت", "edp": "ادو پرفیوم", "edt": "ادو تویلت", "edc": "ادو کلن"}

LONGEVITY_WORDS = {
    5: ["خیلی ماندگار", "بسیار ماندگار", "فوق ماندگار", "فوق العاده ماندگار", "خیلی موندگار", "ماندگاری خیلی بالا"],
    4: ["ماندگار", "موندگار", "پرماندگار", "ماندگاری بالا", "ماندگاری زیاد", "ماندگاری خوب", "موندگاری بالا",
        "موندگاری خوب", "طولانی", "طولانی مدت", "long lasting"],
}
SILLAGE_STRONG = ["پرپخش", "پر پخش", "پخش بالا", "پخش بوی بالا", "پخش بو بالا", "پخش زیاد", "پخش خوب", "قوی", "بمب",
                  "قدرتمند", "strong"]
SILLAGE_SOFT = ["ملایم", "لایت", "سبک", "آرام", "آروم", "خفیف", "کم پخش", "نزدیک پوست", "soft", "light"]

SORT_WORDS = {
    "price": ["ارزان", "ارزون", "ارزانترین", "ارزونترین", "ارزان ترین", "ارزون ترین", "اقتصادی", "مقرون به صرفه",
              "قیمت مناسب", "cheap", "cheapest"],
    "-price": ["گرانترین", "گرونترین", "گران ترین", "گرون ترین", "لوکس ترین", "لوکسترین"],
    "new": ["جدیدترین", "جدید ترین", "جدید", "تازه ترین", "تازه‌ترین", "جدیدا", "new"],
    "rating": ["محبوبترین", "محبوب ترین", "محبوب", "پرفروش", "پرفروشترین", "پرفروش ترین", "بهترین", "پرطرفدار",
               "پرطرفدارترین", "معروف", "best"],
}
SORT_LABELS = {"price": "ارزان‌ترین", "-price": "گران‌ترین", "new": "جدیدترین", "rating": "محبوب‌ترین"}

STOCK_WORDS = ["موجود", "در دسترس", "آماده ارسال"]
GIFT_BOX_WORDS = ["باکس", "باکس هدیه", "جعبه هدیه", "جعبه کادو", "گیفت باکس", "باکس کادو"]
NEGATABLE = {"note", "feel", "family", "brand", "category", "tag"}
NEGATIONS = ["بدون", "غیر", "غیر از", "به جز", "بجز", "منهای", "نه", "بی"]

STOPWORDS = {
    normalize(w) for w in (
        "عطر عطری عطرهای عطرها ادکلن ادکلنی ادوکلن یه یک چند تا یک عدد می خوام میخوام میخواستم میخواهم می‌خواهم"
        " دنبال هستم هستیم لطفا لطفاً پیشنهاد بده بدید بدین بدهید معرفی کن کنید کنین برای واسه واسه‌ی با که و از به"
        " در رو را یا خوب خوبی خوش خوشبو قشنگ عالی باشه باشد داشته داره دارد بوی بو رایحه رایحه‌ی نت نت‌های مناسب"
        " هم خیلی ترجیحا ترجیحاً همسرم دوستم هدیه کادو تولد یچیز یه چیز چیزی چی چه کدوم کدام نسبتا نسبتاً قیمت"
        " تومن تومان حدودی اینکه این اون آن ای the a for with"
    ).split()
}

# ---------- اعداد و پول ----------

UNITS = {"یک": 1, "یه": 1, "دو": 2, "سه": 3, "چهار": 4, "چار": 4, "پنج": 5, "پنح": 5, "شش": 6, "شیش": 6, "هفت": 7,
         "هشت": 8, "نه": 9, "ده": 10, "یازده": 11, "دوازده": 12, "سیزده": 13, "چهارده": 14, "پانزده": 15,
         "پونزده": 15, "شانزده": 16, "شونزده": 16, "هفده": 17, "هیفده": 17, "هجده": 18, "هیجده": 18, "نوزده": 19}
TENS = {"بیست": 20, "سی": 30, "چهل": 40, "پنجاه": 50, "شصت": 60, "هفتاد": 70, "هشتاد": 80, "نود": 90}
HUNDREDS = {"صد": 100, "یکصد": 100, "دویست": 200, "سیصد": 300, "چهارصد": 400, "پانصد": 500, "پونصد": 500,
            "ششصد": 600, "شیشصد": 600, "هفتصد": 700, "هشتصد": 800, "نهصد": 900}
NUMBER_WORDS = {**UNITS, **TENS, **HUNDREDS}
MILLION = {"میلیون", "ملیون", "میلیونی", "ملیونی", "م", "million", "m"}
THOUSAND = {"هزار", "هزاری", "k", "هزارتومن", "هزارتومان", "هزارتومنی"}
TOMAN = {"تومن", "تومان", "تومنی", "تومانی", "t"}
RIAL = {"ریال", "ریالی"}
ML = {"میل", "میلی", "میلیلیتر", "میلی لیتر", "ml", "cc", "سیسی", "سی سی"}

MAX_BEFORE = [("زیر",), ("کمتر", "از"), ("کمتراز",), ("کمتر",), ("تا",), ("حداکثر",), ("نهایتا",), ("نهایت",),
              ("ماکزیمم",), ("سقف",), ("ارزانتر", "از"), ("ارزونتر", "از"), ("ارزان", "تر", "از"),
              ("ارزون", "تر", "از"), ("پایینتر", "از"), ("پایین", "تر", "از"), ("زیره",), ("تا", "سقف"),
              ("under",), ("below",), ("max",)]
MIN_BEFORE = [("بالای",), ("بالاتر", "از"), ("بالا", "تر", "از"), ("بیشتر", "از"), ("بیش", "از"), ("حداقل",),
              ("گرانتر", "از"), ("گرونتر", "از"), ("over",), ("above",), ("min",)]
APPROX_BEFORE = [("حدود",), ("حدودا",), ("حدودای",), ("در", "حد"), ("تقریبا",), ("دور", "و", "بر"), ("اطراف",),
                 ("با", "قیمت"), ("قیمت",), ("حوالی",), ("around",)]
MAX_AFTER = [("به", "پایین"), ("به", "پایینتر"), ("یا", "کمتر"), ("و", "کمتر"), ("کمتر",), ("پایینتر",), ("پایین",)]
MIN_AFTER = [("به", "بالا"), ("به", "بالاتر"), ("یا", "بیشتر"), ("و", "بیشتر"), ("بیشتر",), ("بالاتر",), ("بالا",)]
RANGE_SEP = {"تا", "الی", "-", "و"}

_DIGITS = re.compile(r"^\d+(?:\.\d+)?$")
_PUNCT = re.compile(r"[،,؛;!?؟()«»\"'\[\]{}:]")
_SPLIT_NUM = re.compile(r"(?<=\d)(?=[^\d\s.])|(?<=[^\d\s.])(?=\d)")


def _fa(n):
    """نمایش عدد با ارقام فارسی و جداکننده هزارگان."""
    text = f"{n:,}".replace(",", "٬")
    return text.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def money_label(amount):
    if amount >= 1_000_000:
        m = amount / 1_000_000
        text = f"{m:.1f}".rstrip("0").rstrip(".") if m < 100 else str(round(m))
        return text.replace(".", "٫").translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")) + " میلیون"
    if amount >= 1000 and amount % 1000 == 0:
        return _fa(amount // 1000) + " هزار"
    return _fa(amount)


# ---------- ساختار خروجی ----------

@dataclass
class Criterion:
    kind: str  # price, feel, family, note, brand, gender, season, occasion, longevity, sillage, concentration,
    #            size, sort, stock, gift_box, text
    value: object
    label: str
    tokens: tuple = ()  # اندیس توکن‌های عبارت اصلی که این معیار از آن‌ها ساخته شد
    negated: bool = False
    note: str = ""  # توضیح (مثلاً اصلاح املایی)


@dataclass
class ParsedQuery:
    raw: str
    tokens: list  # توکن‌های اصلی (برای ساختن عبارت بدون یک معیار)
    criteria: list = field(default_factory=list)
    ignored: list = field(default_factory=list)  # کلماتی که هیچ معنایی نداشتند

    @property
    def structured(self):
        return [c for c in self.criteria if c.kind != "text"]

    @property
    def is_smart(self):
        return bool(self.structured)

    @property
    def needs_filters(self):
        """آیا عبارت فقط با فیلتر ساخت‌یافته درست جواب می‌گیرد؟

        یک واژه تنها (یک نت، برند، حس یا فصل) با جستجوی متنی هم پیدا می‌شود و نتیجه کامل‌تری دارد (مثلاً «مشک»
        «مشک سفید» را هم می‌آورد)؛ اما قیمت، حجم، ترتیب، نفی یا ترکیب چند معیار فیلتر لازم دارد.
        """
        structured = self.structured
        strong = {"price", "size", "sort", "stock", "longevity", "sillage", "concentration", "gift_box"}
        return len(structured) > 1 or any(c.kind in strong or c.negated or c.note for c in structured)

    @property
    def text(self):
        return " ".join(c.value for c in self.criteria if c.kind == "text")

    @property
    def sort(self):
        return next((c.value for c in self.criteria if c.kind == "sort"), "")

    def of(self, kind):
        return [c for c in self.criteria if c.kind == kind]

    def without(self, criterion):
        """متن جستجو بدون کلمات یک معیار (برای دکمه ✕ هر برچسب)."""
        drop = set(criterion.tokens)
        return " ".join(t for i, t in enumerate(self.tokens) if i not in drop)


@dataclass
class Vocab:
    families: list  # [(pk, slug, normalized name)]
    notes: list  # [(pk, slug, name)]
    brands: list  # [(pk, slug, name)]
    categories: list  # [(pk, ids شامل زیرشاخه‌ها, name)]
    tags: list  # [(pk, slug, name)]
    product_names: list  # نام‌های نرمال‌شده محصولات و برندها برای تشخیص جستجوی نام
    price_range: tuple = (0, 0)


@dataclass
class SearchResult:
    products: object
    parsed: ParsedQuery | None = None
    relaxed: list = field(default_factory=list)  # معیارهایی که برای رسیدن به نتیجه کنار گذاشته شدند
    exact: bool = True


# ---------- واژگان فروشگاه ----------

def vocab_key(store_id):
    return f"smart-search-vocab:{store_id}"


def load_vocab(store):
    from .models import Brand, Category, FragranceNote, Product, ProductVariant, ScentFamily, Tag

    store_id = getattr(store, "pk", store)
    cached = cache.get(vocab_key(store_id))
    if cached is not None:
        return cached
    families = [(pk, slug, name) for pk, slug, name in
                ScentFamily.objects.for_store(store_id).values_list("pk", "slug", "name")]
    notes = list(FragranceNote.objects.for_store(store_id).values_list("pk", "slug", "name"))
    brands = list(Brand.objects.for_store(store_id).values_list("pk", "slug", "name"))
    categories = [(c.pk, sorted(c.descendant_ids()), c.name)
                  for c in Category.objects.for_store(store_id).filter(is_active=True)]
    tags = list(Tag.objects.for_store(store_id).values_list("pk", "slug", "name"))
    names = [normalize(n) for n in Product.objects.for_store(store_id).active().values_list("name", flat=True)]
    prices = list(ProductVariant.objects.filter(product__store_id=store_id, product__is_active=True,
                                                product__kind=Kind.PERFUME).values_list("price", flat=True))
    vocab = Vocab(families, notes, brands, categories, tags, names + [normalize(b[2]) for b in brands],
                  (min(prices), max(prices)) if prices else (0, 0))
    cache.set(vocab_key(store_id), vocab, VOCAB_TTL)
    return vocab


def invalidate_vocab(store_id):
    cache.delete(vocab_key(store_id))


# ---------- واژه‌نامه عبارت‌ها ----------

class _Lexicon:
    """عبارت (تاپل توکن‌های نرمال‌شده) ← فهرست معناها؛ برای تطبیق بلندترین عبارت."""

    PRIORITY = {"brand": 0, "family": 1, "category": 1, "tag": 2, "concentration": 2, "longevity": 2, "sillage": 2, "sort": 2, "season": 3,
                "gender": 3, "occasion": 4, "gift_box": 4, "stock": 4, "feel": 5, "note": 6}

    def __init__(self):
        self.entries = {}
        self.longest = 1

    def add(self, phrase, kind, value, label):
        key = _n(phrase) if isinstance(phrase, str) else phrase
        if not key:
            return
        self.entries.setdefault(key, []).append((kind, value, label))
        self.longest = max(self.longest, len(key))

    def match(self, tokens, i):
        for size in range(min(self.longest, len(tokens) - i), 0, -1):
            meanings = self.entries.get(tuple(tokens[i:i + size]))
            if meanings:
                return size, min(meanings, key=lambda m: self.PRIORITY.get(m[0], 9))
        return 0, None

    def single_words(self, kinds):
        """واژه‌های تک‌کلمه‌ای از نوع‌های داده‌شده (برای اصلاح املایی فقط نام‌های فروشگاه: نت، برند، خانواده)."""
        return [k[0] for k, meanings in self.entries.items()
                if len(k) == 1 and len(k[0]) >= 4 and any(m[0] in kinds for m in meanings)]


def _static_lexicon():
    lex = _Lexicon()
    for key, feel in FEELS.items():
        for w in feel["words"]:
            lex.add(w, "feel", key, feel["label"])
    labels = dict(Gender.choices)
    for value, words in GENDER_WORDS.items():
        for w in words:
            lex.add(w, "gender", value, labels[value])
    labels = dict(Season.choices)
    for value, words in SEASON_WORDS.items():
        for w in words:
            lex.add(w, "season", value, labels[value])
    labels = dict(Occasion.choices)
    for value, words in OCCASION_WORDS.items():
        for w in words:
            lex.add(w, "occasion", value, labels[value])
    for value, words in CONCENTRATION_WORDS.items():
        for w in words:
            lex.add(w, "concentration", value, CONCENTRATION_LABELS[value])
    for level, words in LONGEVITY_WORDS.items():
        for w in words:
            lex.add(w, "longevity", level, "خیلی ماندگار" if level == 5 else "ماندگار")
    for w in SILLAGE_STRONG:
        lex.add(w, "sillage", "strong", "پخش بوی بالا")
    for w in SILLAGE_SOFT:
        lex.add(w, "sillage", "soft", "ملایم")
    for value, words in SORT_WORDS.items():
        for w in words:
            lex.add(w, "sort", value, SORT_LABELS[value])
    for w in STOCK_WORDS:
        lex.add(w, "stock", True, "فقط موجود")
    for w in GIFT_BOX_WORDS:
        lex.add(w, "gift_box", True, "باکس هدیه")
    return lex


_STATIC = _static_lexicon()


def _lexicon(vocab):
    lex = _Lexicon()
    lex.entries = {k: list(v) for k, v in _STATIC.entries.items()}
    lex.longest = _STATIC.longest
    for pk, _slug, name in vocab.families:
        lex.add(name, "family", pk, name)
    for pk, _slug, name in vocab.notes:
        lex.add(name, "note", pk, name)
        key = _n(name)
        if len(key) == 1:  # صفت: «وانیلی»، «عودی»، «کهربایی»
            lex.add((key[0] + ("یی" if key[0][-1] in "او" else "ی"),), "note", pk, name)
    for pk, _slug, name in vocab.brands:
        lex.add(name, "brand", pk, name)
    # دسته‌ها و برچسب‌های خود فروشگاه بر واژگان عمومی مقدم‌اند (مثلاً دسته «زنانه»)
    for _pk, ids, name in vocab.categories:
        lex.add(name, "category", tuple(ids), name)
    for pk, _slug, name in vocab.tags:
        lex.add(name, "tag", pk, name)
    return lex


# ---------- توکن‌سازی ----------

def tokenize(text):
    """توکن‌های اصلی (برای نمایش و ساختن دوباره عبارت) و نرمال‌شده، با نگاشت یک‌به‌یک."""
    text = re.sub(r"(?<=[\d۰-۹٠-٩])[٫/](?=[\d۰-۹٠-٩])", ".", text or "")
    text = re.sub(r"(?<=[\d۰-۹٠-٩])[٬,](?=[\d۰-۹٠-٩]{3})", "", text)
    text = _PUNCT.sub(" ", text)
    raw, norm = [], []
    for part in text.split():
        n = normalize(part)
        if not n:
            continue
        if _SPLIT_NUM.search(n):  # «3میلیون»، «100ml»، «2-3»
            for piece in _SPLIT_NUM.split(n):
                piece = piece.strip(".")
                if piece:
                    raw.append(piece)
                    norm.append(piece)
        elif n.strip("."):
            raw.append(part.strip("."))
            norm.append(n.strip("."))
    return raw, norm


# ---------- اعداد ----------

def _number(tokens, i):
    """(عدد، اندیس بعدی) یا (None, i)؛ «سه»، «۲.۵»، «بیست و پنج»، «سیصد و پنجاه»، «سه و نیم»."""
    if i >= len(tokens):
        return None, i
    t = tokens[i]
    if _DIGITS.match(t):
        value, j = float(t), i + 1
    elif t in NUMBER_WORDS:
        value, j = NUMBER_WORDS[t], i + 1
        # ترکیب: «صد و پنجاه»، «بیست و پنج»
        while j + 1 < len(tokens) and tokens[j] == "و" and tokens[j + 1] in NUMBER_WORDS \
                and NUMBER_WORDS[tokens[j + 1]] < value and value >= 20:
            value += NUMBER_WORDS[tokens[j + 1]]
            j += 2
    elif t == "نیم":
        value, j = 0.5, i + 1
    else:
        return None, i
    if j + 1 < len(tokens) and tokens[j] == "و" and tokens[j + 1] == "نیم":
        value += 0.5
        j += 2
    return value, j


def _amount(tokens, i):
    """مبلغ: (عدد، ضریب واحد یا None، اندیس بعدی). ضریب None یعنی واحدی ذکر نشده."""
    n, j = _number(tokens, i)
    if n is None:
        return None, None, i
    unit = None
    if j < len(tokens):
        t = tokens[j]
        if t in MILLION:
            unit, j = 1_000_000, j + 1
        elif t in THOUSAND:
            unit, j = 1000, j + 1
        elif t in RIAL:
            unit, j = 0.1, j + 1
        elif t in TOMAN:
            unit, j = "toman", j + 1
    if unit in (1_000_000, 1000) and j < len(tokens) and tokens[j] in TOMAN | RIAL:
        if tokens[j] in RIAL:
            unit = unit / 10
        j += 1
    if unit == 1_000_000:
        # «سه میلیون و نیم»، «دو میلیون و پانصد هزار»
        if j + 1 < len(tokens) and tokens[j] == "و" and tokens[j + 1] == "نیم":
            n += 0.5
            j += 2
        elif j + 1 < len(tokens) and tokens[j] == "و":
            m, k = _number(tokens, j + 1)
            if m is not None and k < len(tokens) and tokens[k] in THOUSAND:
                n += m / 1000
                j = k + 1
                if j < len(tokens) and tokens[j] in TOMAN:
                    j += 1
    return n, unit, j


def _resolve(n, unit, price_range):
    """مبلغ به تومان؛ واحد محاوره‌ای («سه تومن»، «زیر ۵۰۰») با توجه به بازه قیمت فروشگاه حدس زده می‌شود."""
    if isinstance(unit, (int, float)):
        return int(round(n * unit))
    if n >= 10_000:
        return int(n)
    lo, hi = price_range
    lo, hi = (lo or 100_000) / 3, (hi or 50_000_000) * 3
    for factor in (1_000_000, 1000, 1):
        value = n * factor
        if lo <= value <= hi:
            return int(round(value))
    return int(round(n * (1_000_000 if n < 100 else 1000)))


def _starts(tokens, i, phrases):
    for p in sorted(phrases, key=len, reverse=True):
        if tuple(tokens[i:i + len(p)]) == p:
            return len(p)
    return 0


def _price(tokens, i, price_range):
    """تشخیص بازه قیمت از اندیس i: (min, max, اندیس بعدی) یا None."""
    def amount_at(k, need_unit):
        n, unit, end = _amount(tokens, k)
        if n is None or (need_unit and unit is None):
            return None
        return n, unit, end

    # بین A و/تا B  |  از A تا B
    for lead in (("بین",), ("از",), ("between",), ("from",)):
        if tuple(tokens[i:i + 1]) == lead:
            a = amount_at(i + 1, need_unit=False)
            if a and a[2] < len(tokens) and tokens[a[2]] in RANGE_SEP | {"and", "to"}:
                b = amount_at(a[2] + 1, need_unit=False)
                if b:
                    unit = a[1] if a[1] is not None else b[1]
                    lo, hi = _resolve(a[0], unit, price_range), _resolve(b[0], b[1] or unit, price_range)
                    return min(lo, hi), max(lo, hi), b[2]
            if lead == ("از",) and a and a[1] is not None:
                k = _starts(tokens, a[2], MIN_AFTER)
                if k:
                    return _resolve(a[0], a[1], price_range), None, a[2] + k
    # A تا B (بدون «بین»)
    a = amount_at(i, need_unit=False)
    if a and a[2] < len(tokens) and tokens[a[2]] in {"تا", "الی", "-"}:
        b = amount_at(a[2] + 1, need_unit=False)
        if b and (a[1] is not None or b[1] is not None):
            unit = a[1] if a[1] is not None else b[1]
            lo, hi = _resolve(a[0], unit, price_range), _resolve(b[0], b[1] or unit, price_range)
            return min(lo, hi), max(lo, hi), b[2]
    for cues, kind in ((MAX_BEFORE, "max"), (MIN_BEFORE, "min"), (APPROX_BEFORE, "approx")):
        k = _starts(tokens, i, cues)
        if k:
            a = amount_at(i + k, need_unit=False)
            if a and not (a[1] is None and a[0] < 1 and a[0] != 0.5):
                value = _resolve(a[0], a[1], price_range)
                end = a[2] + (_starts(tokens, a[2], MAX_AFTER if kind == "max" else MIN_AFTER) if kind != "approx" else 0)
                if kind == "max":
                    return None, value, end
                if kind == "min":
                    return value, None, end
                return int(value * (1 - APPROX)), int(value * (1 + APPROX)), end
    # A به پایین / A به بالا / A تومنی
    a = amount_at(i, need_unit=True)
    if a:
        value = _resolve(a[0], a[1], price_range)
        k = _starts(tokens, a[2], MAX_AFTER)
        if k:
            return None, value, a[2] + k
        k = _starts(tokens, a[2], MIN_AFTER)
        if k:
            return value, None, a[2] + k
        return int(value * (1 - APPROX)), int(value * (1 + APPROX)), a[2]
    return None


def _size(tokens, i):
    n, j = _number(tokens, i)
    if n is None or j >= len(tokens):
        return None
    for size in (2, 1):
        if " ".join(tokens[j:j + size]) in ML and 1 <= n <= 1000:
            return int(n), j + size
    return None


def price_label(lo, hi):
    if lo and hi:
        a, b = money_label(lo), money_label(hi)
        if a.endswith(" میلیون") and b.endswith(" میلیون"):
            a = a.removesuffix(" میلیون")
        return f"قیمت {a} تا {b} تومان"
    if hi:
        return f"قیمت تا {money_label(hi)} تومان"
    return f"قیمت از {money_label(lo)} تومان"


# ---------- تجزیه ----------

def parse(text, vocab):
    raw, tokens = tokenize(text)
    parsed = ParsedQuery(raw=text or "", tokens=raw)
    if not tokens:
        return parsed
    lex = _lexicon(vocab)
    fuzzy_pool = None
    i = 0
    negate_until = -1  # «بدون عود و چرم»: نفی تا پایان فهرست
    negated_kind = None
    while i < len(tokens):
        t = tokens[i]
        # قیمت و حجم
        size = _size(tokens, i)
        if size:
            parsed.criteria.append(Criterion("size", size[0], f"حجم {_fa(size[0])} میل", tuple(range(i, size[1]))))
            i = size[1]
            continue
        price = _price(tokens, i, vocab.price_range)
        if price:
            lo, hi, end = price
            parsed.criteria.append(Criterion("price", (lo, hi), price_label(lo, hi), tuple(range(i, end))))
            i = end
            continue
        # نفی: «بدون عود»، «نه شیرین»، «غیر از گلی»
        k = _starts(tokens, i, [_n(w) for w in NEGATIONS])
        if k:
            size_m, meaning = lex.match(tokens, i + k)
            if meaning and meaning[0] in NEGATABLE:
                kind, value, label = meaning
                span = tuple(range(i, i + k + size_m))
                parsed.criteria.append(Criterion(kind, value, f"بدون {label}", span, negated=True))
                i += k + size_m
                negate_until, negated_kind = i, kind
                continue
        # ادامه فهرست نفی: «بدون عود و چرم»
        if t == "و" and i == negate_until:
            size_m, meaning = lex.match(tokens, i + 1)
            if meaning and meaning[0] in NEGATABLE and negated_kind:
                kind, value, label = meaning
                parsed.criteria.append(Criterion(kind, value, f"بدون {label}", tuple(range(i, i + 1 + size_m)),
                                                 negated=True))
                i += 1 + size_m
                negate_until = i
                continue
        size_m, meaning = lex.match(tokens, i)
        if not meaning and t.endswith("ون") and len(t) > 3:  # محاوره: «زعفرون» ← «زعفران»
            alt = tokens[:i] + [t[:-2] + "ان"] + tokens[i + 1:]
            size_m, meaning = lex.match(alt, i)
        if meaning:
            kind, value, label = meaning
            parsed.criteria.append(Criterion(kind, value, label, tuple(range(i, i + size_m))))
            i += size_m
            continue
        if t in STOPWORDS or t in NUMBER_WORDS or len(t) < 2:
            i += 1
            continue
        # اشتباه تایپی نزدیک به واژگان (فقط وقتی کلمه در هیچ نام محصولی هم نیست)
        if len(t) >= 4 and not any(t in name for name in vocab.product_names):
            if fuzzy_pool is None:
                fuzzy_pool = lex.single_words({"note", "brand", "family", "category"})
            close = difflib.get_close_matches(t, fuzzy_pool, n=1, cutoff=0.8)
            if close and close[0][0] == t[0]:  # حرف اول معمولاً درست تایپ می‌شود
                kind, value, label = lex.match([close[0]], 0)[1]
                parsed.criteria.append(Criterion(kind, value, label, (i,), note=f"«{raw[i]}» ← «{label}»"))
                i += 1
                continue
        parsed.criteria.append(Criterion("text", t, f"«{raw[i]}»", (i,)))
        i += 1
    _merge(parsed)
    return parsed


def _merge(parsed):
    """چند قیمت ← یک بازه؛ چند جنسیت ← آخری؛ تکراری‌ها حذف."""
    prices = parsed.of("price")
    if len(prices) > 1:
        lo = max((p.value[0] for p in prices if p.value[0]), default=None)
        hi = min((p.value[1] for p in prices if p.value[1]), default=None)
        merged = Criterion("price", (lo, hi), price_label(lo, hi), tuple(t for p in prices for t in p.tokens))
        parsed.criteria = [c for c in parsed.criteria if c.kind != "price"] + [merged]
    genders = parsed.of("gender")
    if len(genders) > 1:
        values = {g.value for g in genders}
        keep = Criterion("gender", Gender.UNISEX, dict(Gender.choices)[Gender.UNISEX],
                         tuple(t for g in genders for t in g.tokens)) if len(values) > 1 else genders[-1]
        parsed.criteria = [c for c in parsed.criteria if c.kind != "gender"] + [keep]
    seen, unique = set(), []
    for c in parsed.criteria:
        key = (c.kind, c.value, c.negated)
        if key in seen and c.kind != "text":
            continue
        seen.add(key)
        unique.append(c)
    parsed.criteria = unique


def is_name_query(text, vocab):
    """جستجوی مستقیم نام محصول یا برند («عود رازآلود»، «شب کهربایی») ← جستجوی متنی ساده."""
    q = normalize(text)
    return len(q) >= 3 and any(q in name for name in vocab.product_names)


# ---------- اعمال روی QuerySet ----------

def _feel_q(feel_key, vocab):
    """(Q، بر اساس نت؟) یک حس: خانواده‌های متناظر فروشگاه، یا اگر نبود، نت‌های شاخص."""
    feel = FEELS[feel_key]
    words = [normalize(w) for w in feel["family_words"]]
    family_ids = [pk for pk, slug, name in vocab.families
                  if slug in feel["families"] or any(w in normalize(name) for w in words)]
    if family_ids:
        return Q(scent_id__in=family_ids), False
    wanted = {normalize(n) for n in feel["notes"]}
    note_ids = [pk for pk, _slug, name in vocab.notes if normalize(name) in wanted]
    return (Q(notes__note_id__in=note_ids) if note_ids else Q(pk__in=[])), True


def _list_overlap(products, field_name, values):
    """(محصولاتی که دست‌کم یکی از values را دارند یا این فهرست را خالی گذاشته‌اند، Q «خالی»)."""
    if is_postgres():
        unknown = Q(**{f"{field_name}__len": 0}) | Q(**{f"{field_name}__isnull": True})
        return products.filter(Q(**{f"{field_name}__overlap": list(values)}) | unknown), unknown
    matched, empty = [], []
    for pk, current in products.values_list("pk", field_name):
        (matched if set(current or []) & set(values) else empty if not current else []).append(pk)
    return products.filter(pk__in=matched + empty), Q(pk__in=empty)


def apply(products, parsed, vocab):
    """اعمال معیارهای parsed روی محصولات (listable_products)."""
    from .models import ProductVariant

    crit = parsed.criteria
    if any(c.kind == "gift_box" for c in crit):
        products = products.filter(kind=Kind.GIFT_BOX)
    elif any(c.kind != "text" for c in crit):  # «عطر ارزان»، «۱۰۰ میل»: فقط عطرها، مگر «باکس» گفته شود
        products = products.filter(kind=Kind.PERFUME)

    family_q, distinct = Q(), False
    for c in crit:
        if c.kind == "feel" and not c.negated:
            q, by_notes = _feel_q(c.value, vocab)
            if by_notes:  # حس‌های نت‌محور (مثل «شیرین») با بقیه AND می‌شوند
                products = products.filter(q)
                distinct = True
            else:  # حس‌ها و خانواده‌ها با هم OR: «خنک یا مرکباتی»
                family_q |= q
        elif c.kind == "family" and not c.negated:
            family_q |= Q(scent_id=c.value)
    if family_q:
        products = products.filter(family_q)

    for c in crit:
        if c.kind == "note":
            if c.negated:
                products = products.exclude(notes__note_id=c.value)
            else:
                products = products.filter(notes__note_id=c.value)
                distinct = True
        elif c.kind in ("feel", "family") and c.negated:
            products = products.exclude(_feel_q(c.value, vocab)[0] if c.kind == "feel" else Q(scent_id=c.value))
        elif c.kind == "brand" and c.negated:
            products = products.exclude(brand_id=c.value)
    brands = [c.value for c in crit if c.kind == "brand" and not c.negated]
    if brands:
        products = products.filter(brand_id__in=brands)

    for c in crit:
        if c.kind == "category":
            q = Q(categories__in=list(c.value))
            products = products.exclude(q) if c.negated else products.filter(q)
            distinct = distinct or not c.negated
        elif c.kind == "tag":
            q = Q(tags__id=c.value)
            products = products.exclude(q) if c.negated else products.filter(q)
            distinct = distinct or not c.negated

    # مشخصات رایحه اختیاری‌اند: محصولی که این مشخصه را ندارد حذف نمی‌شود ولی بعد از تطبیق‌های قطعی می‌آید
    rank = []
    gender = next((c.value for c in crit if c.kind == "gender"), None)
    if gender:
        allowed = [gender] if gender == Gender.UNISEX else [gender, Gender.UNISEX]
        products = products.filter(Q(gender__in=allowed) | Q(gender=""))
        rank.append(Case(When(gender=gender, then=Value(0)), When(gender="", then=Value(2)), default=Value(1)))
    for kind, field_name in (("season", "seasons"), ("occasion", "occasions")):
        values = {c.value for c in crit if c.kind == kind}
        if values:
            products, unknown = _list_overlap(products, field_name, values)
            rank.append(Case(When(unknown, then=Value(2)), default=Value(0)))
    concentrations = {c.value for c in crit if c.kind == "concentration"}
    if concentrations:
        products = products.filter(Q(concentration__in=concentrations) | Q(concentration=""))
        rank.append(Case(When(concentration="", then=Value(2)), default=Value(0)))
    longevity = max((c.value for c in crit if c.kind == "longevity"), default=None)
    if longevity:
        products = products.filter(Q(longevity__gte=longevity) | Q(longevity__isnull=True))
        rank.append(Case(When(longevity__isnull=True, then=Value(2)), default=Value(0)))
    for c in crit:
        if c.kind == "sillage":
            q = Q(sillage__gte=4) if c.value == "strong" else Q(sillage__lte=3)
            products = products.filter(q | Q(sillage__isnull=True))
            rank.append(Case(When(sillage__isnull=True, then=Value(2)), default=Value(0)))
    if rank:
        total = rank[0]
        for r in rank[1:]:
            total = total + r
        products = products.annotate(profile_rank=ExpressionWrapper(total, output_field=IntegerField()))

    # قیمت، حجم و موجودی روی یک حجم (variant) مشترک: «۱۰۰ میل زیر ۵ میلیون»
    variant_q = Q()
    for c in crit:
        if c.kind == "price":
            lo, hi = c.value
            if lo:
                variant_q &= Q(price__gte=lo)
            if hi:
                variant_q &= Q(price__lte=hi)
        elif c.kind == "size":
            variant_q &= Q(size_ml=c.value)
        elif c.kind == "stock":
            variant_q &= Q(stock__gt=0)
    if variant_q:
        products = products.filter(Exists(ProductVariant.objects.filter(variant_q, product=OuterRef("pk"))))

    if parsed.text:
        products = search_products(products, parsed.text)
    if distinct:
        products = products.distinct()
    return products


# ---------- جستجو با کنار گذاشتن شرط‌ها ----------

# ترتیب کنار گذاشتن وقتی نتیجه دقیقی نیست (کم‌اهمیت‌ترین اول). قیمت قبل از نوع رایحه و جنسیت کنار گذاشته
# می‌شود: «عطر خنک کمی گران‌تر» از «عطر غیرخنک ارزان» به خواسته مشتری نزدیک‌تر است.
RELAX_ORDER = ["text", "stock", "occasion", "season", "sillage", "longevity", "concentration", "size", "note", "brand",
               "price", "gender", "feel", "family"]


def _without(parsed, removed):
    return ParsedQuery(parsed.raw, parsed.tokens, [c for c in parsed.criteria if c not in removed], parsed.ignored)


def relax(products_fn, parsed):
    """products_fn(parsed) ← QuerySet. اگر نتیجه‌ای نبود، اول کنار گذاشتن تک‌تک گروه‌های معیار (به ترتیب
    RELAX_ORDER) و سپس کنار گذاشتن تجمعی را امتحان می‌کند.

    خروجی: (QuerySet، فهرست معیارهای کنارگذاشته‌شده).
    """
    qs = products_fn(parsed)
    if not parsed.is_smart or qs.exists():
        return qs, []
    groups = []
    for kind in RELAX_ORDER:
        group = [c for c in parsed.criteria if c.kind == kind and not c.negated]
        if group:
            groups.append(group)
    for group in groups:
        qs = products_fn(_without(parsed, group))
        if qs.exists():
            return qs, group
    dropped = []
    for group in groups:
        dropped += group
        qs = products_fn(_without(parsed, dropped))
        if qs.exists():
            break
    return qs, dropped


def prune_text(parsed, products):
    """کلمات متنی که در هیچ محصولی نیستند کنار گذاشته می‌شوند (و به مشتری گفته می‌شود)."""
    texts = parsed.of("text")
    if not texts or not parsed.is_smart:
        return parsed
    for c in texts[:6]:
        if not products.filter(search_document__contains=c.value).exists():
            parsed.criteria.remove(c)
            parsed.ignored.append(c.label)
    return parsed
