"""تست‌های سرتاسری (E2E) با مرورگر واقعی (Playwright) روی سرور زنده Django و دیتابیس تست.

اجرا:   npm run build:css && pytest -m e2e
- داده‌ها با همان دستور seed_demo ساخته می‌شوند (نمایش واقعی فروشگاه).
- هر تست اگر خطای جاوااسکریپت یا نقض CSP در مرورگر رخ دهد شکست می‌خورد (CSP در تنظیمات تست فعال است).
"""

import os
import re
import secrets
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command

playwright_api = pytest.importorskip("playwright.sync_api", reason="pip install playwright")

# خطاهای بارگذاری منابع خارجی (فونت گوگل در محیط بدون اینترنت) و تصاویر media (سرور تست media سرو نمی‌کند)
IGNORED_CONSOLE = re.compile(r"Failed to load resource|ERR_CERT|ERR_NAME_NOT_RESOLVED|ERR_CONNECTION|fonts\.g")

CSP_HOOK = """
document.addEventListener('securitypolicyviolation', (e) =>
  console.error(`CSP-VIOLATION ${e.violatedDirective} ${e.blockedURI}`));
"""


# هر ماژول E2E این را به‌صورت pytestmark اعلام می‌کند. باید در زمان collection اعلام شود (نه با hook)،
# چون pytest-django بر اساس آن تصمیم می‌گیرد داده migrationها (پوسته پیش‌فرض و …) را برای بازگردانی
# پس از flush دیتابیس serialize کند.
E2E_MARKS = [pytest.mark.e2e, pytest.mark.django_db(transaction=True, serialized_rollback=True)]


@pytest.fixture(scope="module")
def browser():
    """هر ماژول مرورگر خودش را دارد: حلقه رویداد Playwright پس از ماژول بسته می‌شود و به تست‌های بعدی
    (که ORM همزمان را ممنوع می‌دانند) نشت نمی‌کند."""
    if not (Path(settings.BASE_DIR) / "static" / "css" / "app.css").exists():
        pytest.skip("CSS ساخته نشده است: npm run build:css")
    # Playwright (sync) یک event loop در همین thread اجرا می‌کند؛ تا وقتی باز است (از جمله پاک‌سازی دیتابیس
    # پس از هر تست) ORM باید مجاز بماند. فقط در طول همین ماژول تنظیم و سپس برگردانده می‌شود.
    previous = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    try:
        with playwright_api.sync_playwright() as p:
            browser = p.chromium.launch()
            yield browser
            browser.close()
    finally:
        if previous is None:
            os.environ.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)
        else:
            os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = previous


@pytest.fixture
def site(live_server):
    """سرور زنده با داده نمایشی کامل.

    داده‌هایی که migrationها می‌سازند (پوسته پیش‌فرض) صریحاً دوباره ساخته می‌شوند، چون تست تراکنشی بعد از
    هر اجرا کل دیتابیس را خالی می‌کند و بازگردانی serialize‌شده Django با greenletهای Playwright قابل اتکا نیست.
    """
    call_command("sync_themes", verbosity=0)
    call_command("seed_demo", verbosity=0)
    return live_server.url


class PageProbe:
    """صفحه مرورگر + فهرست خطاهای JS و نقض‌های CSP که در پایان تست بررسی می‌شوند."""

    def __init__(self, context):
        self.context = context
        self.errors = []
        context.add_init_script(CSP_HOOK)
        self.page = self.new_page()

    def new_page(self):
        page = self.context.new_page()
        page.on("pageerror", lambda exc: self.errors.append(f"JS error: {exc}"))
        page.on("console", self._console)
        page.on("dialog", lambda dialog: dialog.accept())  # تأییدهای data-confirm
        page.set_default_timeout(10_000)
        return page

    def _console(self, message):
        text = message.text
        if text.startswith("CSP-VIOLATION") or (message.type == "error" and not IGNORED_CONSOLE.search(text)):
            self.errors.append(text)


def _probe(browser, **context_args):
    context = browser.new_context(locale="fa-IR", **context_args)
    probe = PageProbe(context)
    return context, probe


@pytest.fixture
def probe(browser):
    context, probe = _probe(browser, viewport={"width": 1280, "height": 900})
    yield probe
    context.close()
    assert not probe.errors, "\n".join(probe.errors)


@pytest.fixture
def page(probe):
    return probe.page


@pytest.fixture
def new_probe(browser):
    """برای کاربر دوم (مثلاً مشتری ناشناس کنار مدیر) یا اندازه موبایل."""
    made = []

    def factory(**context_args):
        context_args.setdefault("viewport", {"width": 1280, "height": 900})
        context, probe = _probe(browser, **context_args)
        made.append((context, probe))
        return probe

    yield factory
    for context, probe in made:
        context.close()
        assert not probe.errors, "\n".join(probe.errors)


@pytest.fixture
def staff_credentials(db):
    from apps.accounts.models import User

    password = secrets.token_urlsafe(16)
    User.objects.create_superuser(email="owner@example.com", password=password)
    return "owner@example.com", password


def login(page, base, email, password, next_url="/"):
    page.goto(f"{base}/account/login/?next={next_url}")
    page.fill('form[action$="login/"] input[name=username]', email)
    page.fill('form[action$="login/"] input[name=password]', password)
    page.click('form[action$="login/"] button[type=submit]')
    page.wait_for_load_state("networkidle")
