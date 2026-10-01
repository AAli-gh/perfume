"""نقاط اتصال سفارش به ماژول‌های بیرونی بدون وابستگی مستقیم (Dependency Inversion).

اپ payments هنگام راه‌اندازی، تابعی ثبت می‌کند که مشخص می‌کند پرداخت آنلاین برای یک فروشگاه
در دسترس است یا نه. سفارش‌ها هرگز payments را import نمی‌کنند.
"""

_online_payment_provider = None


def register_online_payment_provider(func):
    global _online_payment_provider
    _online_payment_provider = func


def online_payment_available(store):
    return bool(_online_payment_provider and _online_payment_provider(store))
