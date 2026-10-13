"""رویدادهای تخفیف برای اپ‌های دیگر (اطلاع‌رسانی)؛ discounts به هیچ اپ دیگری وابسته نیست.

- referral_rewarded(referral): معرف پاداش معرفی دوست را گرفت.
"""

from django.dispatch import Signal

referral_rewarded = Signal()
