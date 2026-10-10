"""رویدادهای سفارش برای ماژول‌های بیرونی (اطلاع‌رسانی، گزارش، …) بدون وابستگی سفارش به آن‌ها.

هر دو سیگنال پس از commit تراکنش ارسال می‌شوند؛ گیرنده هرگز سفارشِ rollback‌شده نمی‌بیند.
- order_placed:          kwargs: order
- order_status_changed:  kwargs: order, from_status, to_status
"""

from django.dispatch import Signal

order_placed = Signal()
order_status_changed = Signal()

# درخواست مرجوعی/لغو بخشی ایجاد یا وضعیتش عوض شد (request=ReturnRequest)
return_updated = Signal()
