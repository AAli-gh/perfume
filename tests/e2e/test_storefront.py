"""سناریوهای اصلی مشتری در مرورگر واقعی."""

from playwright.sync_api import expect

from apps.orders.models import Order

from .conftest import E2E_MARKS

pytestmark = E2E_MARKS


def test_purchase_end_to_end(site, page):
    # فروشگاه: فیلتر HTMX (بدون بارگذاری کامل صفحه) و افزودن به سبد از کارت محصول
    page.goto(f"{site}/shop/")
    expect(page.locator("#results > div:first-child > span:first-child")).to_contain_text("از ۱۲ محصول")
    page.check("input[name=scent][value=woody]")
    expect(page.locator("#results > div:first-child > span:first-child")).to_contain_text("از ۲ محصول")
    assert "scent=woody" in page.url  # hx-push-url
    page.locator(".product-card button[type=submit]").first.click()
    expect(page.locator("#cart-badge")).to_have_text("۱")
    expect(page.locator("#toasts")).to_contain_text("به سبد خرید اضافه شد")

    # صفحه محصول: انتخاب حجم و تعداد
    page.goto(f"{site}/product/royal-saffron/")
    page.click('label:has-text("۱۰۰ میل")')
    expect(page.locator("[data-variant-price]")).to_contain_text("تومان")
    page.click('[data-qty-step="1"]')
    page.click("form[data-variant-form] button[type=submit]")
    expect(page.locator("#cart-badge")).to_have_text("۳")

    # سبد: تغییر تعداد و کد تخفیف (HTMX)
    page.goto(f"{site}/cart/")
    page.click("#cart-area tbody tr:first-child button[aria-label=افزایش]")
    expect(page.locator("#cart-badge")).to_have_text("۴")
    page.fill("#coupon", "majd10")
    page.click("#cart-area form button[type=submit]")
    expect(page.locator("#cart-area .alert")).to_contain_text("MAJD10")

    # تسویه: اول با خطای اعتبارسنجی، سپس کامل
    page.click("#order-section button[type=submit]")
    expect(page.locator(".field-error").first).to_be_visible()
    page.fill("#id_first_name", "علی")
    page.fill("#id_last_name", "رضایی")
    page.fill("#id_phone", "۰۹۱۲۱۲۳۴۵۶۷")
    page.select_option("#id_province", "تهران")
    page.fill("#id_city", "تهران")
    page.fill("#id_address", "خیابان آزادی ۱")
    page.fill("#id_postal_code", "1234567890")
    page.check("#id_accept_terms")
    page.click("#order-section button[type=submit]")
    page.wait_for_url("**/payments/test-gateway/**")

    # درگاه آزمایشی ← بازگشت و سفارش پرداخت‌شده
    page.click("text=پرداخت موفق")
    page.wait_for_url("**/orders/MJ*/")
    expect(page.locator("h1")).to_contain_text("پرداخت با موفقیت انجام شد")
    order = Order.objects.get()
    assert order.status == Order.Status.PAID and order.coupon_code == "MAJD10"
    assert order.items.count() == 2


def test_review_contact_and_blog_filters(site, page):
    page.goto(f"{site}/product/mystic-oud/")
    page.click("[aria-controls=tab-reviews]")
    page.fill("#id_name", "تست")
    page.fill("#id_text", "عطر بسیار خوبی است")
    page.click("#review-form button")
    expect(page.locator("#review-form .alert")).to_contain_text("پس از تأیید")

    page.goto(f"{site}/contact/")
    page.fill("#id_name", "رضا")
    page.fill("#id_email", "reza@example.com")
    page.fill("#id_message", "سلام، سوالی درباره ارسال داشتم.")
    page.click("#contact-form button")
    expect(page.locator("#contact-form .alert")).to_contain_text("دریافت شد")

    page.goto(f"{site}/blog/")
    page.click('label:has-text("نکات عطرشناسی")')
    expect(page).to_have_url(f"{site}/blog/?q=&cat=tips")
    expect(page.locator("#posts article")).to_have_count(2)


def test_register_wishlist_and_search(site, page):
    page.goto(f"{site}/account/login/")
    page.fill("#id_first_name", "مهسا")
    page.fill("#id_last_name", "احمدی")
    page.fill('form[action$="register/"] #id_email', "mahsa@example.com")
    page.fill("#id_password1", "Atr-Majd-2026!")
    page.fill("#id_password2", "Atr-Majd-2026!")
    page.click('form[action$="register/"] button')
    expect(page.locator("h1")).to_contain_text("مهسا")

    page.goto(f"{site}/product/mystic-oud/")
    page.locator("[id^=wishlist-] button").first.click()
    expect(page.locator("[id^=wishlist-] button").first).to_contain_text("در فهرست علاقه‌مندی‌ها")
    page.goto(f"{site}/account/wishlist/")
    expect(page.locator("main")).to_contain_text("عود رازآلود")

    # جستجو با نویسه عربی (ي/ك) همان نتیجه فارسی را می‌دهد
    page.goto(f"{site}/shop/?q=ميخك")
    expect(page.locator("#results > div:first-child > span:first-child")).to_contain_text("از ۲ محصول")


def test_collection_landing_and_category_links(site, page):
    page.goto(f"{site}/collections/")
    page.locator('a.btn:has-text("مشاهده کالکشن")').first.click()
    page.wait_for_url("**/collections/*/")
    expect(page.locator("h1")).to_contain_text("کالکشن")
    expect(page.locator("#results")).to_contain_text("محصول")
    assert page.locator('link[rel="canonical"]').get_attribute("href") == page.url


def test_rate_limited_htmx_request_shows_toast(site, probe):
    page = probe.page
    page.goto(f"{site}/product/royal-saffron/")
    page.click("form[data-variant-form] button[type=submit]")
    expect(page.locator("#cart-badge")).to_have_text("۱")
    page.goto(f"{site}/cart/")
    for _ in range(10):
        page.fill("#coupon", "WRONG")
        page.click("#cart-area form button[type=submit]")
        expect(page.locator("#cart-area .alert")).to_be_visible()
    page.fill("#coupon", "WRONG")
    page.click("#cart-area form button[type=submit]")
    expect(page.locator("#toasts")).to_contain_text("تعداد درخواست‌ها زیاد است")
    # HTMX پاسخ ۴۲۹ را در console گزارش می‌کند؛ در این تست مورد انتظار است
    probe.errors[:] = [e for e in probe.errors if "Error Code 429" not in e]


def test_mobile_layout_and_menu(site, new_probe):
    page = new_probe(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True).page
    for path in ["/", "/shop/", "/product/mystic-oud/", "/collections/", "/blog/", "/contact/", "/cart/",
                 "/account/login/"]:
        page.goto(site + path)
        overflow = page.evaluate("document.documentElement.scrollWidth - innerWidth")
        assert overflow <= 0, f"اسکرول افقی در {path}: {overflow}px"
    page.goto(site + "/")
    page.click("[data-menu-toggle]")
    expect(page.locator("#main-nav")).to_have_attribute("data-open", "")
    page.click("#main-nav >> text=فروشگاه")
    page.wait_for_url("**/shop/")
    page.click("[data-drawer-open]")
    expect(page.locator("[data-drawer]")).to_have_attribute("data-open", "")


def test_404_page(site, page):
    response = page.goto(f"{site}/no-such-page/")
    assert response.status == 404
    expect(page.locator("h1")).to_contain_text("پیدا نشد")
    page.fill("#nf-search", "عود")
    page.click("form[role=search] button[type=submit] >> nth=-1")
    page.wait_for_url("**/shop/?q=*")
