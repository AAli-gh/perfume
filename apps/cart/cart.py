"""سبد خرید مبتنی بر نشست (session)."""

from dataclasses import dataclass

from apps.catalog.models import ProductVariant
from apps.core.stores import get_current_store
from apps.discounts.selectors import find_coupon
from apps.shipping.selectors import default_method

from .pricing import calculate

SESSION_KEY = "cart"
PICKS_KEY = "sample_picks"  # {شناسه حجم باکس تست: [شناسه دکانت‌ها]}
COUPON_KEY = "coupon"
MAX_QTY = 20


@dataclass
class CartLine:
    variant: ProductVariant
    quantity: int
    picks: tuple = ()  # دکانت‌های داخل باکس تست

    @property
    def product(self):
        return self.variant.product

    @property
    def unit_price(self):
        return self.variant.current_price  # قیمت حراج اگر فعال باشد

    @property
    def regular_price(self):
        return self.variant.price

    @property
    def line_total(self):
        return self.unit_price * self.quantity


def persist(store, user, data):
    """سبد مشتری واردشده در پایگاه داده هم نگه داشته می‌شود (یادآوری سبد رهاشده، دستگاه دیگر)."""
    if user is None or not user.is_authenticated or store is None:
        return
    from .models import SavedCart

    saved = SavedCart.objects.filter(store=store, user=user).first()
    if saved is None:
        if data:
            SavedCart.objects.create(store=store, user=user, items=dict(data))
        return
    if saved.items != data:
        saved.items, saved.reminded_at = dict(data), None  # سبد عوض شد ← یادآوری بعدی دوباره مجاز
        saved.save(update_fields=["items", "reminded_at", "updated_at"])


def restore(request, user):
    """بعد از ورود: سبد ذخیره‌شده با سبد فعلی نشست ادغام می‌شود (تعداد بیشتر هر قلم)."""
    from .models import SavedCart

    store = getattr(request, "store", None) or get_current_store()
    saved = SavedCart.objects.filter(store=store, user=user).first()
    current = dict(request.session.get(SESSION_KEY) or {})
    if saved and saved.items:
        for key, qty in saved.items.items():
            current[key] = max(current.get(key, 0), int(qty))
    request.session[SESSION_KEY] = current
    persist(store, user, current)


class Cart:
    def __init__(self, request):
        self.store = getattr(request, "store", None) or get_current_store()
        self.session = request.session
        self.user = getattr(request, "user", None)
        self._data = self.session.get(SESSION_KEY) or {}
        self._lines = None
        self._pricing = None

    # ---------- تغییر سبد ----------
    def _save(self):
        self.session[SESSION_KEY] = self._data
        self.session.modified = True
        self._lines = None
        self._pricing = None
        persist(self.store, self.user, self._data)

    @property
    def _picks(self):
        return self.session.setdefault(PICKS_KEY, {})

    def _limit(self, variant, picks=()):
        return min([MAX_QTY, variant.stock, *(p.stock for p in picks)])

    def add(self, variant, quantity=1, picks=()):
        """افزودن به سبد؛ کالای ناموجود اضافه نمی‌شود (خروجی False). باکس تست با دکانت‌های انتخابی (picks)."""
        if variant.stock <= 0 or (variant.product.is_sample_box and not picks):
            return False
        key = str(variant.pk)
        if picks:  # انتخاب تازه جای انتخاب قبلی همین باکس را می‌گیرد
            self._picks[key] = [p.pk for p in picks]
            self.session.modified = True
        current = self._data.get(key, 0)
        self._data[key] = max(1, min(self._limit(variant, picks), current + quantity))
        self._save()
        return True

    def set(self, variant, quantity):
        key = str(variant.pk)
        line = next((line for line in self.lines if line.variant.pk == variant.pk), None)
        quantity = max(1, min(self._limit(variant, line.picks if line else ()), quantity))
        self._data[key] = quantity
        self._save()

    def remove(self, variant_id):
        self._data.pop(str(variant_id), None)
        self._picks.pop(str(variant_id), None)
        self.session.modified = True
        self._save()

    def clear(self):
        self._data = {}
        self.session.pop(COUPON_KEY, None)
        self.session.pop(PICKS_KEY, None)
        self._save()

    # ---------- خواندن سبد ----------
    @property
    def lines(self):
        if self._lines is None:
            variants = ProductVariant.objects.filter(
                pk__in=self._data.keys(), product__is_active=True, product__store=self.store
            ).select_related("product", "product__brand")
            by_id = {str(v.pk): v for v in variants}
            picks = self._valid_picks(by_id)
            # حذف اقلامی که دیگر وجود ندارند (و باکس تستی که نمونه‌هایش در دسترس نیست)
            keep = {k for k in by_id if not by_id[k].product.is_sample_box or k in picks}
            if keep != set(self._data):
                self._data = {k: q for k, q in self._data.items() if k in keep}
                self.session[PICKS_KEY] = {k: [p.pk for p in v] for k, v in picks.items() if k in keep}
                self._save()
            self._lines = [CartLine(by_id[k], q, tuple(picks.get(k, ()))) for k, q in self._data.items() if k in keep]
        return self._lines

    def _valid_picks(self, by_id):
        from apps.catalog.samples import PickError, validate_picks

        out = {}
        for key, ids in (self.session.get(PICKS_KEY) or {}).items():
            if key in by_id and by_id[key].product.is_sample_box:
                try:
                    out[key] = validate_picks(by_id[key], ids)
                except PickError:
                    continue
        return out

    def __iter__(self):
        return iter(self.lines)

    def __len__(self):
        return sum(self._data.values())

    @property
    def is_empty(self):
        return not self._data

    # ---------- قیمت (cart.pricing) ----------
    @property
    def pricing(self):
        if self._pricing is None:
            self._pricing = self.quote()
        return self._pricing

    def quote(self, shipping_method=None, province="", extra=()):
        """قیمت سبد با روش ارسال و استان مشخص (پیش‌فرض: اولین روش ارسال فعال، بدون استان).

        extra: اقلامی که فقط در این محاسبه به سبد افزوده می‌شوند (مثل باکس هدیه انتخاب‌شده در تسویه).
        """
        code = self.session.get(COUPON_KEY)
        method = shipping_method or default_method(self.store)
        return calculate([*self.lines, *extra], self.store.config, find_coupon(self.store, code) if code else None,
                         shipping_method=method, province=province)

    @property
    def subtotal(self):
        return self.pricing.subtotal

    @property
    def coupon(self):
        return self.pricing.coupon

    @property
    def discount(self):
        return self.pricing.discount

    @property
    def shipping(self):
        return self.pricing.shipping

    @property
    def total(self):
        return self.pricing.total

    # ---------- کد تخفیف ----------
    @property
    def coupon_code(self):
        return self.session.get(COUPON_KEY) or ""

    def apply_coupon(self, coupon):
        self.session[COUPON_KEY] = coupon.code
        self.session.modified = True
        self._pricing = None

    def remove_coupon(self):
        self.session.pop(COUPON_KEY, None)
        self.session.modified = True
        self._pricing = None
