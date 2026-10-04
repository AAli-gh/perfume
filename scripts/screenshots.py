"""تصاویر مستندات (docs/screenshots/) را از یک سرور در حال اجرا با داده seed_demo می‌گیرد.

    python manage.py migrate && python manage.py seed_demo && python manage.py createsuperuser
    python manage.py runserver
    SHOTS_EMAIL=... SHOTS_PASSWORD=... python scripts/screenshots.py [storefront] [mobile] [studio]

بخش storefront یک سفارش آزمایشی (درگاه آزمایشی) ثبت می‌کند و بخش studio پیش‌تنظیم‌ها را یکی‌یکی منتشر می‌کند؛
فقط روی دیتابیس آزمایشی اجرا کنید.
"""

import io
import os
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

BASE = os.environ.get("SHOTS_BASE_URL", "http://localhost:8000")
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
EMAIL, PASSWORD = os.environ.get("SHOTS_EMAIL", ""), os.environ.get("SHOTS_PASSWORD", "")
DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}
PUBLISH = "form[action$='/studio/publish/'] button[type=submit]"
PRESETS = [("gold", "طلایی لوکس"), ("emerald", "زمرد لوکس"), ("black", "مشکی لوکس"),
           ("pearl", "مروارید"), ("minimal", "مینیمال روشن")]


def save(page, name, full=False):
    img = Image.open(io.BytesIO(page.screenshot(full_page=full))).convert("RGB")
    path = OUT / f"{name}.jpg"
    img.save(path, "JPEG", quality=82, optimize=True, progressive=True)
    print(f"{name:24} {img.width}×{img.height}  {path.stat().st_size // 1024} KB")


def settle(page, ms=600):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(ms)


def go(page, path, ms=600):
    page.goto(BASE + path)
    settle(page, ms)


def shot(page, path, name, **kwargs):
    go(page, path)
    save(page, name, **kwargs)


def click(page, selector, ms=600):
    page.locator(selector).first.click()
    settle(page, ms)


def login(page):
    page.goto(f"{BASE}/account/login/")
    page.fill('form[action$="login/"] input[name=username]', EMAIL)
    page.fill('form[action$="login/"] input[name=password]', PASSWORD)
    click(page, 'form[action$="login/"] button[type=submit]')


def apply_preset(page, label, publish=True):
    go(page, "/studio/theme/")
    page.locator("label.studio-choice", has_text=label).click()
    click(page, "button[name=action][value=preset]")
    if publish and page.locator(PUBLISH).count():
        click(page, PUBLISH)


def storefront(browser):
    page = browser.new_context(viewport=DESKTOP, locale="fa-IR").new_page()
    shot(page, "/", "home-hero")
    save(page, "home-full", full=True)
    shot(page, "/shop/", "shop")
    page.check("input[name=scent][value=woody]")
    settle(page)
    save(page, "shop-filtered")
    shot(page, "/product/royal-saffron/", "product")
    shot(page, "/collections/", "collections")
    click(page, 'a.btn:has-text("مشاهده کالکشن")')
    save(page, "collection-detail")
    shot(page, "/blog/", "blog")
    click(page, "#posts article a")
    save(page, "blog-post")
    for path, name in [("/about/", "about"), ("/contact/", "contact"), ("/account/login/", "login"),
                       ("/no-such-page/", "404")]:
        shot(page, path, name)

    # سبد، تسویه و درگاه آزمایشی (یک سفارش واقعی برای تصاویر پنل مدیریت)
    for slug in ("mystic-oud", "royal-saffron"):
        go(page, f"/product/{slug}/")
        click(page, "form[data-variant-form] button[type=submit]", 800)
    go(page, "/cart/")
    page.fill("#coupon", "MAJD10")
    click(page, "#cart-area form button[type=submit]", 800)
    save(page, "cart")
    for field, value in [("first_name", "علی"), ("last_name", "رضایی"), ("phone", "09121234567"),
                         ("city", "تهران"), ("address", "خیابان آزادی، پلاک ۱"), ("postal_code", "1234567890")]:
        page.fill(f"#id_{field}", value)
    page.select_option("#id_province", "تهران")
    page.locator("#order-section").scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    save(page, "checkout")
    page.check("#id_accept_terms")
    page.click("#order-section button[type=submit]")
    page.wait_for_url("**/payments/test-gateway/**")
    settle(page)
    save(page, "payment-gateway")
    page.click("text=پرداخت موفق")
    page.wait_for_url("**/orders/MJ*/")
    settle(page)
    save(page, "order-success")
    page.context.close()


def mobile(browser):
    ctx = browser.new_context(viewport=MOBILE, device_scale_factor=2, is_mobile=True, has_touch=True, locale="fa-IR")
    page = ctx.new_page()
    for path, name in [("/", "m-home"), ("/shop/", "m-shop"), ("/product/mystic-oud/", "m-product"),
                       ("/cart/", "m-cart")]:
        shot(page, path, name)
    go(page, "/")
    click(page, "[data-menu-toggle]", 500)
    save(page, "m-menu")
    ctx.close()


def studio(browser):
    page = browser.new_context(viewport=DESKTOP, locale="fa-IR").new_page()
    page.on("dialog", lambda dialog: dialog.accept())  # data-confirm
    login(page)
    for path, name in [("/studio/", "studio-dashboard"), ("/studio/theme/", "studio-presets"),
                       ("/studio/theme/colors/", "studio-colors"), ("/studio/theme/typography/", "studio-typography"),
                       ("/studio/theme/components/", "studio-components"), ("/studio/theme/header/", "studio-header")]:
        shot(page, path, name)
    go(page, "/studio/pages/")
    click(page, "main a[href^='/studio/pages/']:not([href='/studio/pages/'])", 1500)
    save(page, "studio-page-editor")
    click(page, "a[href*='/sections/'][href$='/']", 1000)
    save(page, "studio-section-edit")

    # یک تغییر پیش‌نویس تا نوار انتشار و پیش‌نمایش چیزی برای نشان دادن داشته باشند
    apply_preset(page, "زمرد لوکس", publish=False)
    save(page, "studio-draft-bar")
    go(page, "/studio/preview/", 2000)
    save(page, "studio-preview")
    click(page, PUBLISH)
    shot(page, "/studio/history/", "studio-history")

    for path, name in [("/admin/", "admin-index"), ("/admin/orders/order/", "admin-orders"),
                       ("/admin/catalog/product/", "admin-products"), ("/admin/discounts/coupon/", "admin-coupons")]:
        shot(page, path, name)
    go(page, "/admin/orders/order/")
    click(page, "#result_list tbody tr th a")
    save(page, "admin-order-detail")

    # هر پیش‌تنظیم منتشر می‌شود و فروشگاه از دید مشتری (بدون ورود) گرفته می‌شود
    customer = browser.new_context(viewport=DESKTOP, locale="fa-IR").new_page()
    for code, label in PRESETS:
        apply_preset(page, label)
        shot(customer, "/", f"preset-{code}")
    apply_preset(page, PRESETS[0][1])  # بازگشت به پیش‌تنظیم پیش‌فرض


def main(steps):
    if "studio" in steps and not (EMAIL and PASSWORD):
        sys.exit("برای بخش studio متغیرهای SHOTS_EMAIL و SHOTS_PASSWORD را تنظیم کنید.")
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for step in ("storefront", "mobile", "studio"):
            if step in steps:
                globals()[step](browser)
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:] or ["storefront", "mobile", "studio"])
