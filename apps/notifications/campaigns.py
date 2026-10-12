"""پیامک گروهی به مشتریان: ساخت (با کد تخفیف اختیاری) و ارسال در Celery."""

import secrets
import string
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.discounts.models import Coupon

from . import events as E
from .models import Campaign, NotificationLog
from .services import send_sms_text

OPT_OUT = "\nلغو۱۱"


def make_coupon(store, *, percent, days, uses, prefix="VIP"):
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(10):
        code = prefix[:8].upper() + "".join(secrets.choice(alphabet) for _ in range(5))
        if not Coupon.objects.filter(store=store, code=code).exists():
            break
    return Coupon.objects.create(store=store, code=code, percent=percent, usage_limit=uses or None,
                                 valid_to=timezone.now() + timedelta(days=days))


def render(message, *, store, name, coupon=None, shop_url=""):
    context = {"store": store.name, "name": name or "مشتری", "shop_url": shop_url,
               "code": coupon.code if coupon else "", "percent": coupon.percent if coupon else ""}
    return E.render_text(message, context)


@transaction.atomic
def create_campaign(store, *, name, message, recipients, audience="", coupon=None, opt_out=True, user=None):
    """recipients: [(موبایل، نام)]؛ تکراری‌ها حذف می‌شوند. ارسال با send_campaign_task."""
    seen, unique = set(), []
    for phone, person in recipients:
        if phone and phone not in seen:
            seen.add(phone)
            unique.append([phone, person or ""])
    return Campaign.objects.create(
        store=store, name=name[:100], message=message + (OPT_OUT if opt_out and "لغو" not in message else ""),
        audience=audience[:200], recipients=unique, coupon_code=coupon.code if coupon else "",
        created_by=user if user and user.is_authenticated else None)


def send_campaign(campaign_id):
    campaign = Campaign.objects.select_related("store").get(pk=campaign_id)
    store = campaign.store
    coupon = Coupon.objects.filter(store=store, code=campaign.coupon_code).first() if campaign.coupon_code else None
    done = set(NotificationLog.objects.filter(campaign=campaign, status=NotificationLog.SENT)
               .values_list("recipient", flat=True))
    for phone, person in campaign.recipients:
        if phone in done:  # اجرای دوباره task پیامک تکراری نمی‌فرستد
            continue
        text = render(campaign.message, store=store, name=person, coupon=coupon, shop_url=store.base_url + "/shop/")
        entry = send_sms_text(store, E.CAMPAIGN, phone, text)
        NotificationLog.objects.filter(pk=entry.pk).update(campaign=campaign)
        field = "sent" if entry.status == NotificationLog.SENT else "failed"
        Campaign.objects.filter(pk=campaign.pk).update(**{field: F(field) + 1})
    Campaign.objects.filter(pk=campaign.pk).update(status=Campaign.DONE)
