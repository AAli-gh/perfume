"""تشخیص فروشگاه جاری (Tenant).

- در چرخه درخواست: StoreMiddleware فروشگاه را از روی Host پیدا می‌کند و در request.store
  و یک ContextVar قرار می‌دهد.
- بیرون از درخواست (Celery، دستورهای مدیریتی، تست): فروشگاه پیش‌فرض استفاده می‌شود،
  مگر اینکه با use_store() مشخص شود.
"""

from contextlib import contextmanager
from contextvars import ContextVar

_current_store = ContextVar("current_store", default=None)


def get_default_store():
    from .models import Store, StoreSettings

    store = Store.objects.select_related("config").filter(is_default=True).first()
    if store is None:
        store, _ = Store.objects.get_or_create(code="default", defaults={"name": "فروشگاه", "is_default": True})
        StoreSettings.objects.get_or_create(store=store)
    return store


def default_store_id():
    """پیش‌فرض فیلد store در مدل‌ها (برای سازگاری با کدی که فروشگاه را مشخص نمی‌کند)."""
    current = _current_store.get()
    return current.pk if current is not None else get_default_store().pk


def resolve_store(host):
    from .models import StoreDomain

    domain = (host or "").split(":")[0].strip().lower()
    match = (
        StoreDomain.objects.select_related("store__config")
        .filter(domain=domain, store__is_active=True)
        .first()
    )
    return match.store if match else get_default_store()


def get_current_store():
    return _current_store.get() or get_default_store()


@contextmanager
def use_store(store):
    token = _current_store.set(store)
    try:
        yield store
    finally:
        _current_store.reset(token)


class StoreMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.store = resolve_store(request.get_host())
        with use_store(request.store):
            return self.get_response(request)
