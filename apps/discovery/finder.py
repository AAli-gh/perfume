"""«عطر مناسب من را پیدا کن»: پرسش‌ها، امتیازدهی و دلیل هر پیشنهاد.

هر پاسخ سهمی از امتیاز ۱۰۰ دارد. عطری که مشخصاتش ثبت نشده، در آن معیار امتیاز میانه می‌گیرد
(نه صفر)؛ پس تکمیل نبودن داده‌ها عطر را حذف نمی‌کند. فیلترهای قطعی: جنسیت مخالف، خارج از بودجه
و داشتن نتی که کاربر «دوست ندارد» در لایه میانی یا پایه.
"""

from dataclasses import dataclass

from django import forms

from apps.catalog import recommend
from apps.catalog.models import FragranceNote, ProductNote, ScentFamily
from apps.catalog.profile import Occasion, Season

SESSION_KEY = "finder"
WEIGHTS = {"family": 25, "notes": 25, "occasion": 15, "season": 15, "intensity": 10, "gender": 10}
INTENSITY = {"soft": (2, 2), "balanced": (3, 3), "strong": (5, 4)}  # (ماندگاری، پخش بو) هدف


def _radio(label, choices, required=True):
    return forms.ChoiceField(label=label, choices=choices, widget=forms.RadioSelect, required=required)


def _multi(label, choices):
    return forms.MultipleChoiceField(label=label, choices=choices, widget=forms.CheckboxSelectMultiple, required=False)


@dataclass(frozen=True)
class Step:
    key: str
    title: str
    hint: str = ""


STEPS = [
    Step("gender", "این عطر را برای چه کسی می‌خواهید؟"),
    Step("occasion", "بیشتر کجا از آن استفاده می‌کنید؟"),
    Step("season", "در کدام فصل بیشتر می‌زنید؟"),
    Step("families", "چه حس و حالی را دوست دارید؟", "می‌توانید چند مورد را انتخاب کنید."),
    Step("likes", "کدام نت‌ها را دوست دارید؟", "اختیاری؛ چند نت محبوبتان را انتخاب کنید."),
    Step("dislikes", "نتی هست که دوست نداشته باشید؟", "اختیاری؛ عطرهایی که این نت‌ها در قلب یا پایه‌شان باشد پیشنهاد نمی‌شوند."),
    Step("intensity", "عطرتان چقدر قوی و ماندگار باشد؟"),
    Step("budget", "بودجه شما برای یک شیشه چقدر است؟"),
]
FAMILY_HINTS = {
    "floral": "لطیف، رمانتیک و بهاری", "woody": "گرم، آرام و باوقار", "oriental": "شیرین، گرم و اسرارآمیز",
    "fresh": "خنک، تمیز و پرانرژی", "spicy": "تند، جسور و پرحرارت",
}


def budget_bands(pool):
    """سه بازه قیمت از روی کمترین قیمت محصولات همین فروشگاه + «فرقی ندارد»."""
    prices = sorted(p.min_price for p in pool if p.min_price)
    if len(prices) < 3:
        return [("any", "فرقی ندارد", None)]
    from apps.core.templatetags.majd import toman

    low, high = prices[len(prices) // 3], prices[2 * len(prices) // 3]
    return [
        ("low", f"تا {toman(low)}", low),
        ("mid", f"تا {toman(high)}", high),
        ("high", "بالاتر هم اشکالی ندارد", None),
    ]


def step_form(step, store, pool, data=None, initial=None):
    """فرم یک مرحله (فیلدها از داده همین فروشگاه ساخته می‌شوند)."""
    form = forms.Form(data=data, initial=initial)
    key = step.key
    if key == "gender":
        form.fields[key] = _radio(step.title, [("women", "زنانه"), ("men", "مردانه"), ("any", "فرقی ندارد / یونیسکس")])
    elif key == "occasion":
        form.fields[key] = _radio(step.title, [*Occasion.choices, ("any", "همه‌جا")])
    elif key == "season":
        form.fields[key] = _radio(step.title, [*Season.choices, ("any", "همه فصل‌ها")])
    elif key == "families":
        families = ScentFamily.objects.for_store(store).filter(products__in=[p.pk for p in pool]).distinct()
        form.fields[key] = _multi(step.title, [(str(f.pk), f"{f.name} — {FAMILY_HINTS[f.slug]}" if f.slug in FAMILY_HINTS
                                                else f.name) for f in families])
    elif key in ("likes", "dislikes"):
        notes = (FragranceNote.objects.for_store(store).filter(product_links__product__in=[p.pk for p in pool])
                 .distinct().order_by("name"))
        form.fields[key] = _multi(step.title, [(str(n.pk), n.name) for n in notes])
    elif key == "intensity":
        form.fields[key] = _radio(step.title, [("soft", "ملایم و نزدیک به پوست"), ("balanced", "متعادل"),
                                               ("strong", "قوی و بسیار ماندگار")])
    elif key == "budget":
        form.fields[key] = _radio(step.title, [(code, label) for code, label, _ in budget_bands(pool)])
    return form


def _ids(values):
    return {int(v) for v in values or [] if str(v).isdigit()}


def score(product, answers, budget_limit=None):
    """(درصد تطابق ۰ تا ۱۰۰ یا None اگر حذف شود، دلایل)."""
    reasons = []
    total = 0.0

    gender = answers.get("gender", "any")
    if gender in ("men", "women") and product.gender and product.gender not in (gender, "unisex"):
        return None, []
    if gender == "any" or not product.gender:
        total += WEIGHTS["gender"] * (0.5 if not product.gender else 1)
    else:
        total += WEIGHTS["gender"]
        reasons.append("یونیسکس؛ مناسب همه" if product.gender == "unisex"
                       else ("مردانه" if product.gender == "men" else "زنانه"))

    if budget_limit is not None and product.min_price and product.min_price > budget_limit:
        return None, []

    dislikes = _ids(answers.get("dislikes"))
    layers = {link.note_id: link.layer for link in product.notes.all()}
    if any(layers.get(n) in (ProductNote.Layer.HEART, ProductNote.Layer.BASE) for n in dislikes):
        return None, []

    families = _ids(answers.get("families"))
    if not families:
        total += WEIGHTS["family"] * 0.5
    elif product.scent_id in families:
        total += WEIGHTS["family"]
        reasons.append(f"خانواده رایحه دلخواه شما: {product.scent.name}")

    likes = _ids(answers.get("likes"))
    if likes:
        vector = recommend.note_vector(product)
        hits = [n for n in likes if n in vector]
        if hits:
            names = {link.note_id: link.note.name for link in product.notes.all()}
            total += WEIGHTS["notes"] * min(1.0, sum(vector[n] for n in hits) / max(1.3, 0.6 * len(likes)))
            reasons.append("نت‌های محبوب شما: " + "، ".join(names[n] for n in hits[:3]))
    else:
        total += WEIGHTS["notes"] * 0.5
    if any(layers.get(n) == ProductNote.Layer.TOP for n in dislikes):
        total -= 5  # نت ناخوشایند فقط در آغاز است و زود محو می‌شود

    for key, field_name, labels in (("occasion", "occasions", dict(Occasion.choices)),
                                    ("season", "seasons", dict(Season.choices))):
        wanted = answers.get(key, "any")
        values = getattr(product, field_name)
        if wanted == "any":
            total += WEIGHTS[key] * (0.8 if values else 0.5)
        elif not values:
            total += WEIGHTS[key] * 0.5
        elif wanted in values:
            total += WEIGHTS[key]
            reasons.append(f"مناسب {labels[wanted]}")

    target = INTENSITY.get(answers.get("intensity"))
    if target and product.longevity and product.sillage:
        distance = abs(product.longevity - target[0]) + abs(product.sillage - target[1])
        total += WEIGHTS["intensity"] * max(0.0, 1 - distance / 6)
        if distance <= 1:
            reasons.append({"soft": "ملایم و لطیف", "balanced": "ماندگاری متعادل",
                            "strong": "قوی و بسیار ماندگار"}[answers["intensity"]])
    else:
        total += WEIGHTS["intensity"] * 0.5

    return max(0, min(100, round(total))), reasons


def results(store, answers, pool=None, limit=6):
    pool = list(pool if pool is not None else recommend.candidates(store))
    limits = {code: limit_ for code, _, limit_ in budget_bands(pool)}
    budget_limit = limits.get(answers.get("budget"))
    matches = []
    for p in pool:
        match, reasons = score(p, answers, budget_limit)
        if match is None:
            continue
        p.match, p.reasons = match, reasons
        matches.append(p)
    matches.sort(key=lambda p: (-p.match, -(p.rating_avg or 0), p.pk))
    return matches[:limit]
