/* عطر مجد — تعاملات کوچک سمت کاربر (بقیه با HTMX انجام می‌شود) */
(() => {
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const toggle = (el, on) => el && (on ? el.setAttribute("data-open", "") : el.removeAttribute("data-open"));

  function init(root = document) {
    // اسلایدر محصولات (در حالت RTL، حرکت به جلو یعنی اسکرول به سمت چپ)
    $$("[data-carousel]", root).forEach((c) => {
      if (c.dataset.ready) return;
      c.dataset.ready = "1";
      const track = c.querySelector("[data-carousel-track]");
      const step = () => track.clientWidth * 0.75;
      c.querySelector("[data-carousel-next]")?.addEventListener("click", () => track.scrollBy({ left: -step() }));
      c.querySelector("[data-carousel-prev]")?.addEventListener("click", () => track.scrollBy({ left: step() }));
    });

    // نمای شبکه‌ای / فهرستی فروشگاه
    const view = safeGet("majd-view") || "grid";
    $$("[data-product-grid]", root).forEach((g) => g.classList.toggle("list-view", view === "list"));
    $$("[data-view]").forEach((b) => b.toggleAttribute("data-active", b.dataset.view === view));

    // انیمیشن ظاهر شدن
    const els = $$(".reveal:not(.visible)", root);
    if (!("IntersectionObserver" in window)) return els.forEach((el) => el.classList.add("visible"));
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("visible"); io.unobserve(e.target); }
    }), { threshold: 0.12 });
    els.forEach((el) => io.observe(el));

    // حذف خودکار اعلان‌ها
    $$("[data-autohide]", root).forEach((t) => {
      if (t.dataset.timer) return;
      t.dataset.timer = setTimeout(() => t.remove(), 4000);
    });
  }

  // پاسخ ۴۲۹ (محدودیت تعداد درخواست) برای درخواست‌های HTMX: HTMX پاسخ خطا را جایگزین نمی‌کند، پس اعلان می‌دهیم
  document.addEventListener("htmx:responseError", (e) => {
    if (e.detail.xhr.status !== 429) return;
    const box = document.getElementById("toasts");
    if (!box) return;
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.setAttribute("data-autohide", "");
    toast.textContent = "تعداد درخواست‌ها زیاد است؛ لطفاً کمی بعد دوباره تلاش کنید.";
    box.appendChild(toast);
    init(box);
  });

  function safeGet(k) { try { return localStorage.getItem(k); } catch { return null; } }
  function safeSet(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } }

  document.addEventListener("click", (e) => {
    const t = e.target;

    // منوی موبایل
    const menuBtn = t.closest("[data-menu-toggle]");
    if (menuBtn) {
      const nav = document.getElementById("main-nav");
      const open = !nav.hasAttribute("data-open");
      toggle(nav, open);
      menuBtn.setAttribute("aria-expanded", open);
    }

    // جستجو
    const panel = document.querySelector("[data-search-panel]");
    if (t.closest("[data-search-open]")) { toggle(panel, true); setTimeout(() => panel.querySelector("input").focus(), 50); }
    if (t.closest("[data-search-close]") || t === panel) toggle(panel, false);

    // کشوی فیلترها (موبایل)
    const drawer = document.querySelector("[data-drawer]");
    const backdrop = document.querySelector("[data-drawer-backdrop]");
    if (t.closest("[data-drawer-open]")) { toggle(drawer, true); toggle(backdrop, true); }
    if (t.closest("[data-drawer-close]") || t === backdrop) { toggle(drawer, false); toggle(backdrop, false); }

    // نمای شبکه / فهرست
    const viewBtn = t.closest("[data-view]");
    if (viewBtn) { safeSet("majd-view", viewBtn.dataset.view); init(); }

    // گالری محصول
    const gallery = t.closest("[data-gallery]");
    if (gallery) {
      const thumbs = $$("[data-gallery-thumb]", gallery);
      let idx = thumbs.findIndex((b) => b.hasAttribute("data-active"));
      const thumb = t.closest("[data-gallery-thumb]");
      if (thumb) idx = thumbs.indexOf(thumb);
      else if (t.closest("[data-gallery-next]")) idx = (idx + 1) % thumbs.length;
      else if (t.closest("[data-gallery-prev]")) idx = (idx - 1 + thumbs.length) % thumbs.length;
      else idx = -1;
      if (idx >= 0) {
        gallery.querySelector("[data-gallery-main]").src = thumbs[idx].dataset.galleryThumb;
        thumbs.forEach((b, i) => b.toggleAttribute("data-active", i === idx));
      }
    }

    // تعداد در صفحه محصول
    const step = t.closest("[data-qty-step]");
    if (step) {
      const input = step.closest("[data-qty]").querySelector("input");
      input.value = Math.max(1, Math.min(20, (parseInt(input.value, 10) || 1) + +step.dataset.qtyStep));
    }

    // تب‌ها
    const tab = t.closest("[role=tab]");
    if (tab) {
      const box = tab.closest("[data-tabs]");
      $$("[role=tab]", box).forEach((b) => b.setAttribute("aria-selected", b === tab));
      $$("[role=tabpanel]", box).forEach((p) => (p.hidden = p.id !== tab.getAttribute("aria-controls")));
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") $$("[data-open]").forEach((el) => toggle(el, false));
  });

  // قیمت متناسب با حجم انتخاب‌شده
  document.addEventListener("change", (e) => {
    const radio = e.target.closest("[data-variant-form] input[name=variant]");
    if (radio) radio.form.querySelector("[data-variant-price]").textContent = radio.dataset.price;
  });

  // برچسب محدوده قیمت
  const FA = (n) => Number(n).toLocaleString("fa-IR") + " تومان";
  document.addEventListener("input", (e) => {
    const box = e.target.closest("[data-price-range]");
    if (!box) return;
    const [lo, hi] = box.querySelectorAll("input[type=range]");
    if (+lo.value > +hi.value) (e.target === lo ? (lo.value = hi.value) : (hi.value = lo.value));
    box.querySelector("[data-price-min]").textContent = FA(lo.value);
    box.querySelector("[data-price-max]").textContent = FA(hi.value);
  });

  // لینک به تب نظرات
  if (location.hash === "#reviews") document.querySelector('[aria-controls="tab-reviews"]')?.click();

  document.addEventListener("DOMContentLoaded", () => init());
  document.addEventListener("htmx:afterSettle", () => init());
  document.addEventListener("htmx:oobAfterSwap", () => init());
  // درخواست‌های HTMX با خطای اعتبارسنجی (۴۲۲) هم باید جایگزین شوند
  document.addEventListener("htmx:beforeSwap", (e) => {
    if (e.detail.xhr.status === 422) { e.detail.shouldSwap = true; e.detail.isError = false; }
  });
})();
