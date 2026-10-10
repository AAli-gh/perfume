"""کارت هدیه و امتیاز باشگاه مشتریان: اعتبارهایی که بعد از تخفیف و هزینه ارسال از مبلغ قابل پرداخت کم می‌شوند.

ترتیب: مبلغ سفارش (جمع − تخفیف کد + ارسال) ← امتیاز باشگاه (تا سقف درصد تنظیمات) ← کارت هدیه ← مبلغ قابل پرداخت.
- خرج و برگشت همیشه با قفل ردیف (select_for_update) تا دو سفارش هم‌زمان مانده را بیش از موجودی خرج نکنند.
- لغو سفارش: مبلغ کارت و امتیاز خرج‌شده برمی‌گردد و امتیاز کسب‌شده از همان سفارش کسر می‌شود.
- امتیاز کسب‌شده: پس از تحویل سفارش، به ازای مبلغ پرداختی بدون هزینه ارسال.
"""

import secrets
import string
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Sum

from .models import GiftCard, GiftCardTransaction, LoyaltyAccount, LoyaltyEntry

__all__ = ["GiftCard", "LoyaltyAccount", "LoyaltyEntry"]

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # بدون O/0 و I/1 برای خوانایی


# ---------- کارت هدیه ----------

def new_code(store, length=10):
    for _ in range(20):
        code = "".join(secrets.choice(ALPHABET) for _ in range(length))
        if not GiftCard.objects.filter(store=store, code=code).exists():
            return code
    raise RuntimeError("ساخت کد یکتا ممکن نشد")


def format_code(code):
    return "-".join(code[i:i + 4] for i in range(0, len(code), 4))


def normalize_code(code):
    from apps.core.forms import en_digits

    return "".join(ch for ch in en_digits(code or "").upper() if ch in string.ascii_uppercase + string.digits)


def find_card(store, code):
    code = normalize_code(code)
    return GiftCard.objects.for_store(store).filter(code=code).first() if code else None


def issue_card(store, amount, *, source=GiftCard.Source.MANUAL, order_number="", expires_at=None, recipient_name="",
               recipient_phone="", sender_name="", message=""):
    card = GiftCard.objects.create(
        store=store, code=new_code(store), initial_amount=amount, balance=amount, expires_at=expires_at, source=source,
        order_number=order_number, recipient_name=recipient_name[:80], recipient_phone=recipient_phone[:11],
        sender_name=sender_name[:80], message=message[:200])
    GiftCardTransaction.objects.create(card=card, amount=amount, order_number=order_number, note="صدور")
    return card


# ---------- باشگاه مشتریان ----------

def loyalty_config(store):
    config = getattr(store, "config", None)
    return config if config is not None and config.loyalty_enabled else None


def points_balance(store, user):
    if user is None or not user.is_authenticated:
        return 0
    account = LoyaltyAccount.objects.for_store(store).filter(user=user).first()
    return account.points if account else 0


def _account(store, user, lock=False):
    account, _ = LoyaltyAccount.objects.get_or_create(store=store, user=user)
    return LoyaltyAccount.objects.select_for_update().get(pk=account.pk) if lock else account


def add_points(store, user, points, reason, *, order_number="", note="", by=None):
    with transaction.atomic():
        account = _account(store, user, lock=True)
        if account.points + points < 0:
            points = -account.points  # مانده منفی نمی‌شود
        if not points:
            return 0
        account.points += points
        account.save(update_fields=["points"])
        LoyaltyEntry.objects.create(account=account, points=points, reason=reason, order_number=order_number,
                                    note=note[:200], created_by=by)
    return points


def points_for_amount(config, amount):
    return amount // config.loyalty_earn_per if config.loyalty_earn_per else 0


# ---------- محاسبه اعتبار در سبد و ثبت سفارش ----------

@dataclass(frozen=True)
class Credits:
    points: int = 0  # امتیاز خرج‌شده
    points_amount: int = 0
    gift_card: object = None
    gift_amount: int = 0
    payable: int = 0
    error: str = ""


def compute(store, total, *, card=None, use_points=False, user=None, points_available=None):
    """پیش‌نمایش یا محاسبه نهایی اعتبار؛ card و points_available در ثبت سفارش از ردیف‌های قفل‌شده می‌آیند."""
    points = points_amount = 0
    config = loyalty_config(store)
    if use_points and config is not None and user is not None and user.is_authenticated:
        available = points_balance(store, user) if points_available is None else points_available
        if available >= config.loyalty_min_redeem and config.loyalty_point_value:
            cap = total * config.loyalty_max_percent // 100
            points = min(available, cap // config.loyalty_point_value)
            points_amount = points * config.loyalty_point_value
    remaining = total - points_amount
    gift_amount, error = 0, ""
    if card is not None:
        error = card.check_usable() or ""
        if not error:
            gift_amount = min(card.balance, remaining)
    return Credits(points, points_amount, card if gift_amount else None, gift_amount, remaining - gift_amount, error)


@transaction.atomic
def redeem(store, order, *, card_code="", use_points=False, user=None, total):
    """خرج اعتبار برای سفارش ثبت‌شده (قفل کارت و حساب امتیاز). خروجی Credits."""
    card = None
    if card_code:
        card = GiftCard.objects.select_for_update().filter(store=store, code=normalize_code(card_code)).first()
    available = None
    if use_points and user is not None and user.is_authenticated and loyalty_config(store) is not None:
        available = _account(store, user, lock=True).points
    credits = compute(store, total, card=card, use_points=use_points, user=user, points_available=available)
    if credits.gift_amount:
        GiftCard.objects.filter(pk=card.pk).update(balance=card.balance - credits.gift_amount)
        GiftCardTransaction.objects.create(card=card, amount=-credits.gift_amount, order_number=order.number,
                                           note="خرج در سفارش")
    if credits.points:
        add_points(store, user, -credits.points, LoyaltyEntry.Reason.REDEEMED, order_number=order.number)
    return credits


@transaction.atomic
def restore_for_order(order):
    """لغو سفارش: برگشت مبلغ کارت هدیه و امتیاز خرج‌شده، و کسر امتیاز کسب‌شده از همین سفارش."""
    spent = (GiftCardTransaction.objects.filter(card__store=order.store, order_number=order.number)
             .values("card").annotate(total=Sum("amount")))
    for row in spent:
        if row["total"] < 0:
            card = GiftCard.objects.select_for_update().get(pk=row["card"])
            card.balance += -row["total"]
            card.save(update_fields=["balance"])
            GiftCardTransaction.objects.create(card=card, amount=-row["total"], order_number=order.number,
                                               note="برگشت (لغو سفارش)")
    if order.user_id:
        net = (LoyaltyEntry.objects.filter(account__store=order.store, account__user_id=order.user_id,
                                           order_number=order.number).aggregate(n=Sum("points"))["n"] or 0)
        if net:
            reason = LoyaltyEntry.Reason.RESTORED if net < 0 else LoyaltyEntry.Reason.REVOKED
            add_points(order.store, order.user, -net, reason, order_number=order.number, note="لغو سفارش")


def earn_for_order(order):
    """امتیاز خرید پس از تحویل (یک بار برای هر سفارش)."""
    config = loyalty_config(order.store)
    if config is None or not order.user_id:
        return 0
    if LoyaltyEntry.objects.filter(account__store=order.store, order_number=order.number,
                                   reason=LoyaltyEntry.Reason.EARNED).exists():
        return 0
    points = points_for_amount(config, max(order.total + order.gift_card_amount - order.shipping, 0))
    return add_points(order.store, order.user, points, LoyaltyEntry.Reason.EARNED, order_number=order.number) \
        if points else 0
