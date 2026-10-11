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
    page.locator(".product-card form[action$='/cart/add/'] button").first.click()
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
    # هر درخواست تا رسیدن پاسخ صبر می‌کند؛ HTMX درخواست جدید فرم را تا پاسخ قبلی کنار می‌گذارد
    for _ in range(10):
        page.fill("#coupon", "WRONG")
        with page.expect_response("**/cart/coupon/") as response:
            page.click("#cart-area form button[type=submit]")
        assert response.value.status == 200
    page.fill("#coupon", "WRONG")
    with page.expect_response("**/cart/coupon/") as response:
        page.click("#cart-area form button[type=submit]")
    assert response.value.status == 429
    expect(page.locator("#toasts")).to_contain_text("تعداد درخواست‌ها زیاد است")
    # HTMX پاسخ ۴۲۹ را در console گزارش می‌کند؛ در این تست مورد انتظار است
    probe.errors[:] = [e for e in probe.errors if "Error Code 429" not in e]


def test_mobile_layout_and_menu(site, new_probe):
    page = new_probe(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True).page
    page.goto(site + "/product/mystic-oud/")
    page.click("form[id^=compare-button] button")
    page.wait_for_timeout(300)
    for path in ["/", "/shop/", "/product/mystic-oud/", "/collections/", "/blog/", "/contact/", "/cart/",
                 "/account/login/", "/compare/", "/finder/"]:
        page.goto(site + path)
        overflow = page.evaluate("document.documentElement.scrollWidth - innerWidth")
        assert overflow <= 0, f"اسکرول افقی در {path}: {overflow}px"
    page.goto(site + "/")
    page.click("[data-menu-toggle]")
    expect(page.locator("#main-nav")).to_have_attribute("data-open", "")
    # پنل منو تا پایین صفحه را می‌پوشاند (header با backdrop-filter، containing block عنصر fixed است)
    page.wait_for_timeout(400)
    box = page.locator("#main-nav").bounding_box()
    assert box["y"] == 72 and box["height"] >= 844 - 72 - 1, box
    assert page.evaluate("document.elementFromPoint(200, 700).closest('#main-nav') !== null")
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


def test_compare_and_perfume_finder(site, page):
    # مقایسه: از کارت محصول (HTMX) و صفحه محصول
    page.goto(f"{site}/shop/")
    page.locator("article:has(a[href='/product/mystic-oud/']) form[id^=compare-icon] button").click()
    expect(page.locator("#compare-badge")).to_be_visible()
    expect(page.locator("#toasts")).to_contain_text("به مقایسه اضافه شد")
    page.goto(f"{site}/product/royal-saffron/")
    page.click("form[id^=compare-button] button")
    expect(page.locator("form[id^=compare-button] button")).to_contain_text("در فهرست مقایسه")
    page.click("#compare-badge")
    page.wait_for_url("**/compare/")
    expect(page.locator(".compare-table thead th")).to_have_count(3)
    expect(page.locator(".compare-table")).to_contain_text("شباهت به «عود رازآلود»")
    page.click("text=فقط تفاوت‌ها")
    expect(page.locator(".compare-table")).not_to_contain_text("موجودی")

    # عطریاب: هشت مرحله با HTMX و سپس نتیجه
    page.goto(f"{site}/finder/")
    for step, choice in enumerate(["زنانه", "شب و مهمانی", "زمستان", "شرقی", "وانیل", None, "قوی و بسیار ماندگار",
                                   "بالاتر هم اشکالی ندارد"]):
        # تا پاسخ HTMX مرحله قبل جایگزین نشده، روی فرم قدیمی کلیک نشود
        expect(page.locator("#finder input[name=step]")).to_have_value(str(step))
        if choice:
            page.locator("label.finder-option", has_text=choice).first.click()
        page.click("#finder button[type=submit]")
    page.wait_for_url("**/finder/results/")
    expect(page.locator("h1")).to_contain_text("عطرهای پیشنهادی")
    expect(page.locator(".match-ring").first).to_contain_text("٪")
    page.click("text=مقایسه")
    page.wait_for_url("**/compare/")
    expect(page.locator(".compare-table thead th")).not_to_have_count(1)


def test_gift_box_packaging_at_checkout(site, page):
    page.goto(f"{site}/gift-boxes/")
    expect(page.locator("main")).to_contain_text("باکس")
    page.goto(f"{site}/product/royal-saffron/")
    page.click("form[data-variant-form] button[type=submit]")
    expect(page.locator("#cart-badge")).to_have_text("۱")

    page.goto(f"{site}/cart/")
    details = page.locator("#gift-packaging [data-gift-details]")
    expect(details).to_be_hidden()  # بسته‌بندی معمولی: جزئیات هدیه پنهان (فقط CSS)
    page.locator("#gift-packaging label", has_text="داخل باکس هدیه").click()
    expect(details).to_be_visible()
    expect(page.locator("#gift-packaging [data-gift-custom]")).to_be_hidden()
    page.locator(".gift-box-option", has_text="سلطنتی").click()
    expect(page.locator("#checkout-summary [data-extra-line]")).to_contain_text("سلطنتی")  # قیمت با HTMX به‌روز شد
    page.fill("#id_gift_message", "تولدت مبارک")
    page.fill("#id_gift_from", "سارا")

    page.fill("#id_first_name", "علی")
    page.fill("#id_last_name", "رضایی")
    page.fill("#id_phone", "09121234567")
    page.select_option("#id_province", "تهران")
    page.fill("#id_city", "تهران")
    page.fill("#id_address", "خیابان آزادی ۱")
    page.fill("#id_postal_code", "1234567890")
    page.check("input[name=payment_method][value=cod]")
    page.check("#id_accept_terms")
    page.click("#order-section button[type=submit]")
    page.wait_for_url("**/orders/MJ*/")
    expect(page.locator("#order-gift")).to_contain_text("تولدت مبارک")
    order = Order.objects.get()
    assert order.packaging == Order.Packaging.IN_BOX and order.items.count() == 2


def test_smart_search_live_suggestions_and_chips(site, page):
    page.goto(f"{site}/")
    page.click("[data-search-open]")
    expect(page.locator("#search-suggest [data-search-examples]")).to_be_visible()
    page.fill("#site-search", "عطر خنک زیر سه تومن")
    suggest = page.locator("#search-suggest")
    expect(suggest.locator("[data-smart-query]")).to_contain_text("خنک و تازه")
    expect(suggest.locator("[data-smart-query]")).to_contain_text("قیمت تا ۳ میلیون تومان")
    expect(suggest.locator("[data-relaxed]")).to_be_visible()  # داده نمونه عطر خنک زیر ۳ میلیون ندارد
    expect(suggest.locator("[data-suggest-results] li").first).to_contain_text("آکوا اینفرنو")
    page.press("#site-search", "Enter")
    page.wait_for_url("**/shop/?q=*")
    expect(page.locator("#results [data-smart-query]")).to_contain_text("خنک و تازه")
    expect(page.locator("#results .product-card").first).to_contain_text("آکوا اینفرنو")

    # ✕ روی برچسب قیمت: همان جستجو بدون شرط قیمت
    page.locator("#results .smart-chip", has_text="قیمت").click()
    page.wait_for_load_state()
    expect(page.locator("#shop-search")).to_have_value("عطر خنک")
    expect(page.locator("#results [data-relaxed]")).to_have_count(0)

    page.fill("#shop-search", "زنانه شیرین برای شب")
    page.press("#shop-search", "Enter")
    page.wait_for_url("**/shop/?q=*")
    expect(page.locator("#results .smart-chip")).to_have_count(3)
    expect(page.locator("#results .product-card")).not_to_have_count(0)
