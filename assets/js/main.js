/* عطر مجد — اسکریپت مشترک همه صفحات */

/* ---------- ابزارها ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const faNum = (n) => Number(n).toLocaleString("fa-IR");
const toman = (n) => `${faNum(Math.round(n))} تومان`;
const escapeHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const toEnDigits = (s) => String(s).replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)).replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d));
const params = new URLSearchParams(location.search);
const findProduct = (id) => PRODUCTS.find((p) => p.id === id);

const store = {
  get(key, fallback) {
    try {
      const v = localStorage.getItem(key);
      return v ? JSON.parse(v) : fallback;
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* حافظه در دسترس نیست */ }
  },
};

/* ---------- آیکون‌ها ---------- */
const ICONS = {
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
  cart: '<path d="M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6.2"/><circle cx="10" cy="20.5" r="1"/><circle cx="17" cy="20.5" r="1"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  chevL: '<path d="m15 6-6 6 6 6"/>',
  chevR: '<path d="m9 6 6 6-6 6"/>',
  grid: '<rect x="4" y="4" width="6" height="6"/><rect x="14" y="4" width="6" height="6"/><rect x="4" y="14" width="6" height="6"/><rect x="14" y="14" width="6" height="6"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r=".8"/><circle cx="4.5" cy="12" r=".8"/><circle cx="4.5" cy="18" r=".8"/>',
  filter: '<path d="M4 5h16l-6 8v5l-4 2v-7z"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="1"/><path d="m3 7 9 6 9-6"/>',
  pin: '<path d="M12 21s-7-6.2-7-12a7 7 0 0 1 14 0c0 5.8-7 12-7 12z"/><circle cx="12" cy="9" r="2.5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  diamond: '<path d="M6 3h12l4 6-10 12L2 9z"/><path d="M2 9h20M9 3l3 18 3-18"/>',
  crown: '<path d="M3 8l4.5 4L12 5l4.5 7L21 8l-2 10H5z"/><path d="M5 21h14"/>',
  flame: '<path d="M12 3c1 4 5 5.5 5 10a5 5 0 0 1-10 0c0-2.5 1.5-3.5 2-5.5 1 1.5 2 2 2.5 3.5C13 8 12 5 12 3z"/>',
  shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="M12 3v18"/>',
  truck: '<path d="M2 6h12v10H2zM14 10h4l3 3v3h-7"/><circle cx="6" cy="18" r="1.8"/><circle cx="17" cy="18" r="1.8"/>',
  gift: '<rect x="3" y="9" width="18" height="12"/><path d="M3 13h18M12 9v12M12 9C9 9 7 4 10 4s2 5 2 5 0-5 3-5 1 5-3 5"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14-5l-2 2M4 13a8 8 0 0 0 14 5l2-2"/><path d="M4 4v4h4M20 20v-4h-4"/>',
  headset: '<path d="M4 14v-2a8 8 0 0 1 16 0v2"/><rect x="3" y="14" width="4" height="6" rx="1"/><rect x="17" y="14" width="4" height="6" rx="1"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  instagram: '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r=".6"/>',
  telegram: '<path d="M21 4 3 11l6 2 2 6 3-4 5 4z"/><path d="m9 13 9-7"/>',
  whatsapp: '<path d="M4 20l1.3-4A8 8 0 1 1 8 18.7z"/><path d="M9 9c0 3 3 6 6 6l1-1.5-2-1-1 1c-1-.5-2-1.5-2.5-2.5l1-1-1-2z"/>',
  x: '<path d="M4 4l16 16M20 4 4 20"/>',
  bag: '<path d="M5 8h14l-1 13H6z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
};
const icon = (name, cls = "") =>
  `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;

/* ---------- سبد خرید ---------- */
const Cart = {
  items() { return store.get("majd-cart", []); },
  save(items) {
    store.set("majd-cart", items);
    updateCartBadge();
  },
  add(id, size = 50, qty = 1) {
    const items = this.items();
    const found = items.find((i) => i.id === id && i.size === size);
    if (found) found.qty = Math.min(20, found.qty + qty);
    else items.push({ id, size, qty });
    this.save(items);
  },
  setQty(id, size, qty) {
    const items = this.items();
    const it = items.find((i) => i.id === id && i.size === size);
    if (it) it.qty = Math.max(1, Math.min(20, qty));
    this.save(items);
  },
  remove(id, size) { this.save(this.items().filter((i) => !(i.id === id && i.size === size))); },
  clear() { this.save([]); },
  count() { return this.items().reduce((s, i) => s + i.qty, 0); },
  unitPrice(item) {
    const p = findProduct(item.id);
    return p ? p.price * (SIZE_FACTOR[item.size] || 1) : 0;
  },
  subtotal() { return this.items().reduce((s, i) => s + this.unitPrice(i) * i.qty, 0); },
};

function updateCartBadge() {
  const n = Cart.count();
  $$(".cart-count").forEach((el) => {
    el.textContent = faNum(n);
    el.dataset.count = n;
  });
}

/* ---------- اعلان ---------- */
function toast(html, ms = 3200) {
  let stack = $(".toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.className = "toast-stack";
    stack.setAttribute("aria-live", "polite");
    document.body.appendChild(stack);
  }
  const t = document.createElement("div");
  t.className = "toast";
  t.innerHTML = html;
  stack.appendChild(t);
  setTimeout(() => t.remove(), ms);
}

function addToCart(id, size = 50, qty = 1) {
  const p = findProduct(id);
  if (!p) return;
  Cart.add(id, size, qty);
  toast(`${icon("check")}<span>«${p.name}» به سبد خرید اضافه شد.</span><a href="cart.html">مشاهده سبد</a>`);
}

/* ---------- قطعات مشترک ---------- */
const NAV = [
  ["index.html", "خانه", "home"],
  ["shop.html", "فروشگاه", "shop"],
  ["collections.html", "کالکشن‌ها", "collections"],
  ["blog.html", "مجله", "blog"],
  ["about.html", "درباره ما", "about"],
  ["contact.html", "تماس با ما", "contact"],
];

function renderHeader() {
  const page = document.body.dataset.page;
  const user = store.get("majd-user", null);
  const header = document.createElement("header");
  header.className = "site-header";
  header.innerHTML = `
    <div class="container header-inner">
      <button class="icon-btn menu-toggle" aria-label="منو" aria-expanded="false">${icon("menu")}</button>
      <a href="index.html" class="logo">عطر مجد</a>
      <nav class="main-nav" aria-label="منوی اصلی">
        <ul>${NAV.map(([href, label, key]) => `<li><a href="${href}" class="${key === page ? "active" : ""}">${label}</a></li>`).join("")}</ul>
      </nav>
      <div class="header-actions">
        <button class="icon-btn search-open" aria-label="جستجو">${icon("search")}</button>
        <a class="icon-btn" href="login.html" aria-label="${user ? "حساب کاربری " + escapeHtml(user.name) : "ورود / ثبت‌نام"}" title="${user ? escapeHtml(user.name) : "ورود / ثبت‌نام"}">${icon("user")}</a>
        <a class="icon-btn" href="cart.html" aria-label="سبد خرید">${icon("cart")}<span class="cart-count" data-count="0">۰</span></a>
      </div>
    </div>`;
  document.body.prepend(header);

  const search = document.createElement("div");
  search.className = "search-panel";
  search.innerHTML = `
    <button class="icon-btn close" aria-label="بستن">${icon("close")}</button>
    <form action="shop.html" role="search">
      <label class="sr-only" for="site-search">جستجوی عطر</label>
      <input id="site-search" name="q" type="search" placeholder="نام عطر، برند یا نت مورد نظر…" autocomplete="off">
      <button class="btn" type="submit">${icon("search")} جستجو</button>
    </form>`;
  document.body.appendChild(search);

  const openSearch = () => { search.classList.add("open"); setTimeout(() => $("input", search).focus(), 50); };
  const closeSearch = () => search.classList.remove("open");
  $(".search-open", header).addEventListener("click", openSearch);
  $(".close", search).addEventListener("click", closeSearch);
  search.addEventListener("click", (e) => { if (e.target === search) closeSearch(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSearch(); });

  const toggle = $(".menu-toggle", header);
  const nav = $(".main-nav", header);
  toggle.addEventListener("click", () => {
    const open = nav.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open);
    toggle.innerHTML = icon(open ? "close" : "menu");
  });
}

function renderFooter() {
  const footer = document.createElement("footer");
  footer.className = "site-footer";
  footer.innerHTML = `
    <div class="container footer-grid">
      <div class="footer-brand">
        <a href="index.html" class="logo">عطر مجد</a>
        <p>خانه عطرهای لوکس و دست‌ساز؛ رایحه‌هایی برای ماندگاری در خاطره‌ها.<br>تهران، خیابان ولیعصر، پلاک ۱۲۳</p>
        <div class="socials">
          <a href="#" aria-label="اینستاگرام">${icon("instagram")}</a>
          <a href="#" aria-label="تلگرام">${icon("telegram")}</a>
          <a href="#" aria-label="واتس‌اپ">${icon("whatsapp")}</a>
        </div>
      </div>
      <div>
        <h4>دسترسی سریع</h4>
        <ul>
          <li><a href="shop.html">فروشگاه</a></li>
          <li><a href="collections.html">کالکشن‌ها</a></li>
          <li><a href="blog.html">مجله</a></li>
          <li><a href="about.html">درباره ما</a></li>
        </ul>
      </div>
      <div>
        <h4>خدمات مشتریان</h4>
        <ul>
          <li><a href="contact.html">سوالات متداول</a></li>
          <li><a href="contact.html">بازگشت و تعویض</a></li>
          <li><a href="contact.html">شرایط ارسال</a></li>
          <li><a href="contact.html">حریم خصوصی</a></li>
          <li><a href="contact.html">قوانین و مقررات</a></li>
        </ul>
      </div>
      <div>
        <h4>تماس با ما</h4>
        <ul>
          <li><a href="mailto:info@atremajd.ir">info@atremajd.ir</a></li>
          <li><a href="tel:+982112345678" dir="ltr">۰۲۱-۱۲۳۴۵۶۷۸</a></li>
          <li>شنبه تا پنجشنبه، ۱۰ تا ۲۱</li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">© ${faNum(1404).replace(/٬/g, "")} عطر مجد — تمامی حقوق محفوظ است.</div>`;
  document.body.appendChild(footer);
}

/* ---------- کارت محصول ---------- */
function stars(rating, reviews) {
  const full = Math.round(rating);
  return `<span class="stars" aria-label="امتیاز ${faNum(rating)} از ۵">${"★".repeat(full)}${"☆".repeat(5 - full)}${
    reviews !== undefined ? `<small>(${faNum(reviews)})</small>` : ""
  }</span>`;
}

function productCard(p) {
  return `
    <article class="product-card">
      <a class="thumb" href="product.html?id=${p.id}"><img src="${p.img}" alt="عطر ${p.name}" loading="lazy"></a>
      <div class="body">
        <h3><a href="product.html?id=${p.id}">${p.name}</a></h3>
        <span class="brand">${BRANDS[p.brand]}</span>
        ${stars(p.rating, p.reviews)}
        <span class="price">${toman(p.price)}</span>
        <p class="desc">${p.desc}</p>
        <button class="btn btn-sm" data-add="${p.id}">افزودن به سبد</button>
      </div>
    </article>`;
}

function setupCarousel(root) {
  const track = $(".carousel-track", root);
  const step = () => track.clientWidth * 0.75;
  // در حالت راست‌به‌چپ، اسکرول مثبت به سمت چپ نیست؛ جهت را با dir تنظیم می‌کنیم
  $(".carousel-btn.next", root)?.addEventListener("click", () => track.scrollBy({ left: -step() }));
  $(".carousel-btn.prev", root)?.addEventListener("click", () => track.scrollBy({ left: step() }));
}

/* ---------- انیمیشن ظاهر شدن ---------- */
function setupReveal() {
  const els = $$(".reveal");
  if (!("IntersectionObserver" in window)) return els.forEach((el) => el.classList.add("visible"));
  const io = new IntersectionObserver(
    (entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("visible"); io.unobserve(e.target); }
    }),
    { threshold: 0.12 }
  );
  els.forEach((el) => io.observe(el));
}

/* ---------- اعتبارسنجی فرم ---------- */
function validateForm(form) {
  let ok = true;
  $$("[required], [data-pattern]", form).forEach((input) => {
    const field = input.closest(".field");
    const val = input.type === "checkbox" ? input.checked : toEnDigits(input.value.trim());
    let msg = "";
    if (input.type === "checkbox") {
      if (!val) msg = "لطفاً این گزینه را تأیید کنید.";
    } else if (input.required && !val) {
      msg = "این فیلد الزامی است.";
    } else if (val && input.type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) {
      msg = "ایمیل معتبر نیست.";
    } else if (val && input.dataset.pattern && !new RegExp(input.dataset.pattern).test(val)) {
      msg = input.dataset.msg || "مقدار وارد شده معتبر نیست.";
    } else if (val && input.minLength > 0 && val.length < input.minLength) {
      msg = `حداقل ${faNum(input.minLength)} کاراکتر وارد کنید.`;
    }
    if (field) {
      field.classList.toggle("invalid", !!msg);
      let err = $(".error", field);
      if (!err) { err = document.createElement("span"); err.className = "error"; field.appendChild(err); }
      err.textContent = msg;
    }
    if (msg && ok) { input.focus(); ok = false; }
  });
  return ok;
}

function showMsg(el, text, type = "ok") {
  el.textContent = text;
  el.className = `form-msg show ${type}`;
}

/* ---------- راه‌اندازی ---------- */
document.addEventListener("DOMContentLoaded", () => {
  renderHeader();
  renderFooter();
  updateCartBadge();
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-add]");
    if (btn) addToCart(btn.dataset.add);
  });
  const init = window.PAGES && window.PAGES[document.body.dataset.page];
  if (typeof init === "function") init();
  setupReveal();
});
