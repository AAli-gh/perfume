"""استودیو در مرورگر واقعی: پیش‌نمایش زنده، پیش‌نویس، انتشار، لینک پیش‌نمایش و بازگردانی."""

import re

from playwright.sync_api import expect

from apps.builder.models import Revision

from .conftest import E2E_MARKS, login

pytestmark = E2E_MARKS


def primary(page):
    return re.search(r"--color-primary:([\d ]+)", page.content()).group(1)


def test_draft_preview_publish_and_restore(site, page, new_probe, staff_credentials):
    customer = new_probe().page
    customer.goto(f"{site}/")
    original = primary(customer)
    login(page, site, *staff_credentials, next_url="/studio/")
    expect(page.locator("#publish-bar")).to_contain_text("همه تغییرات منتشر شده")

    # رنگ: پیش از ذخیره، داخل iframe پیش‌نمایش زنده اعمال می‌شود (postMessage زیر CSP)
    page.goto(f"{site}/studio/theme/colors/")
    frame = page.frame_locator("iframe[data-preview-frame]")
    expect(frame.locator("body")).to_be_visible()
    page.eval_on_selector('input[data-token="primary"]',
                          "el => { el.value = '#2266cc'; el.dispatchEvent(new Event('input', {bubbles: true})); }")
    live = page.frames[1]
    expect(live.locator("html")).to_have_attribute("style", re.compile(r"--color-primary:\s*34 102 204"))
    page.click("button[value=save]")
    expect(page.locator("#publish-bar")).to_contain_text("رنگ‌ها")

    # مشتری هنوز نسخه منتشرشده را می‌بیند
    customer.reload()
    assert primary(customer) == original

    # بخش‌ها: کشیدن و رها کردن + غیرفعال کردن (HTMX، نوار انتشار هم به‌روز می‌شود)
    page.goto(f"{site}/studio/pages/")
    page.locator("a.studio-card").first.click()
    rows = page.locator("[data-sortable] > [data-id]")
    expect(rows).to_have_count(7)
    rows.nth(6).drag_to(rows.nth(0), target_position={"x": 40, "y": 5})
    expect(rows.nth(0)).to_contain_text("خبرنامه")
    page.reload()
    expect(rows.nth(0)).to_contain_text("خبرنامه")  # ذخیره شده
    page.locator('[data-sortable] > [data-id]:has-text("بنر تبلیغاتی") button:has-text("غیرفعال کن")').click()
    expect(page.locator("#publish-bar")).to_contain_text("صفحه «صفحه اصلی»")

    # لینک پیش‌نمایش برای مهمان (بدون حساب)
    page.goto(f"{site}/studio/preview/")
    page.click('button:has-text("ساخت لینک پیش‌نمایش")')
    link = page.input_value("#share-link")
    guest = new_probe().page
    guest.goto(link)
    expect(guest.locator("[data-preview-banner]")).to_be_visible()
    assert primary(guest) == "34 102 204"
    assert "هنر عطرسازی" not in guest.content()

    # انتشار
    page.fill("#publish-label", "آبی و بدون بنر")
    page.click('#publish-bar button:has-text("انتشار")')
    expect(page.locator(".alert").first).to_contain_text("منتشر شد")
    customer.reload()
    assert primary(customer) == "34 102 204"
    body = customer.content()
    assert "هنر عطرسازی" not in body and body.index("عضویت در خبرنامه") < body.index("دنیای رایحه‌های")
    guest.reload()
    expect(guest.locator("[data-preview-banner]")).to_have_count(0)  # لینک با انتشار باطل شد

    # تاریخچه و بازگردانی به نسخه اولیه ← پیش‌نمایش ← انتشار
    page.goto(f"{site}/studio/history/")
    expect(page.locator("ol > li")).to_have_count(2)
    page.locator('ol > li:has-text("نسخه اولیه") button:has-text("بازگردانی")').click()
    page.wait_for_url("**/studio/preview/")
    page.click('#publish-bar button:has-text("انتشار")')
    customer.reload()
    assert primary(customer) == original and "هنر عطرسازی" in customer.content()
    assert Revision.objects.count() == 3


def test_section_editor_with_repeater_and_device_preview(site, page, staff_credentials):
    login(page, site, *staff_credentials, next_url="/studio/pages/")
    page.locator("a.studio-card").first.click()
    page.select_option("select[name=type]", "faq")
    page.click('button:has-text("افزودن به انتهای صفحه")')
    page.fill('input[name="items-0-question"]', "ارسال چقدر طول می‌کشد؟")
    page.fill('textarea[name="items-0-answer"]', "دو تا چهار روز کاری.")
    page.click('button:has-text("ذخیره در پیش‌نویس")')
    expect(page.locator(".alert").first).to_contain_text("ذخیره شد")

    page.goto(f"{site}/studio/preview/")
    frame = page.frame_locator("iframe[data-preview-frame]")
    expect(frame.locator("main")).to_contain_text("ارسال چقدر طول می‌کشد؟")
    page.click('[data-device="390px"]')
    # عرض با transition تغییر می‌کند؛ تا رسیدن به ۳۹۰ صبر می‌کنیم
    # (wait_for_function رشته را در صفحه eval می‌کند که CSP عمداً اجازه نمی‌دهد)
    for _ in range(30):
        width = page.eval_on_selector("iframe[data-preview-frame]", "f => f.getBoundingClientRect().width")
        if width == 390:
            break
        page.wait_for_timeout(100)
    assert width == 390
    expect(page.locator('[data-device="390px"]')).to_have_attribute("aria-pressed", "true")

    page.click('#publish-bar button:has-text("کنار گذاشتن")')
    expect(page.locator("#publish-bar")).to_contain_text("همه تغییرات منتشر شده")


def test_studio_requires_staff(site, page):
    page.goto(f"{site}/studio/")
    page.wait_for_url("**/account/login/?next=/studio/")
