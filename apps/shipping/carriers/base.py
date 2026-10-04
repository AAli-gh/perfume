"""رابط مشترک شرکت‌های حمل (Adapter).

برای اتصال به API یک شرکت حمل (پست، تیپاکس، پیک‌های شهری، …) یک زیرکلاس Carrier بسازید و با @register ثبت کنید:
- quote():           هزینه ارسال از API (اختیاری؛ None یعنی «از جدول نرخ روش ارسال استفاده شود»)
- create_shipment(): ثبت مرسوله نزد شرکت و گرفتن کد رهگیری (اختیاری)
- tracking_url():    پیوند پیگیری مرسوله برای مشتری

اعتبارنامه‌ها (api_key، api_secret، account_id) روی خود ShippingMethod هر فروشگاه ذخیره می‌شوند.
سفارش، سبد و قیمت‌گذاری بدون تغییر از آن استفاده می‌کنند.
"""

from dataclasses import dataclass, field


class CarrierError(Exception):
    """خطای قابل نمایش به مدیر (ارتباط با API، رد درخواست، …)."""


class ShipmentNotSupported(CarrierError):
    pass


@dataclass
class Shipment:
    tracking_code: str
    raw: dict = field(default_factory=dict)


class Carrier:
    code = ""
    label = ""
    supports_api = False  # ثبت خودکار مرسوله / استعلام قیمت از API

    def __init__(self, method):
        self.method = method  # ShippingMethod (شامل اعتبارنامه‌ها)

    def quote(self, *, province, amount):
        """هزینه ارسال به تومان یا None (← جدول نرخ روش ارسال)."""
        return None

    def create_shipment(self, order) -> Shipment:
        raise ShipmentNotSupported(f"ثبت خودکار مرسوله برای «{self.label}» پشتیبانی نمی‌شود؛ کد رهگیری را دستی وارد کنید.")

    def tracking_url(self, tracking_code):
        template = self.method.tracking_url_template
        if not (template and tracking_code):
            return ""
        return template.replace("{code}", tracking_code)
