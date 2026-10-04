"""ارسال با جدول نرخ و کد رهگیری دستی — برای پست، تیپاکس یا پیک تا زمان اتصال API.

کد رهگیری را مدیر در سفارش وارد می‌کند؛ پیوند پیگیری از «الگوی پیوند پیگیری» روش ارسال ساخته می‌شود.
"""

from .base import Carrier
from .registry import register


@register
class ManualCarrier(Carrier):
    code = "manual"
    label = "دستی (جدول نرخ + کد رهگیری دستی)"
