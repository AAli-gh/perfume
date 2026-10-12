"""رویدادهای موجودی برای اطلاع‌رسانی (اپ notifications گوش می‌دهد؛ catalog آن را import نمی‌کند).

- stock_low(variant_id, stock): موجودی یک حجم از آستانه پایین‌تر رفت (یک بار برای هر بار عبور از آستانه).
- back_in_stock(variant_id, stock): حجمی که ناموجود بود دوباره موجود شد.
هر دو پس از commit تراکنش ارسال می‌شوند.
"""

from django.dispatch import Signal

stock_low = Signal()
back_in_stock = Signal()
