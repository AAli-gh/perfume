/* عطر مجد — منطق اختصاصی هر صفحه */

window.PAGES = {
  /* ---------- خانه ---------- */
  home() {
    const best = [...PRODUCTS].sort((a, b) => b.rating - a.rating).slice(0, 8);
    $("#bestsellers .carousel-track").innerHTML = best.map(productCard).join("");
    setupCarousel($("#bestsellers"));

    $("#home-collections").innerHTML = COLLECTIONS.slice(0, 3).map(collectionCard).join("");

    $("#home-posts").innerHTML = POSTS.slice(0, 2).map(postCard).join("");

    $("#newsletter-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const form = e.target;
      if (!validateForm(form)) return;
      showMsg($(".form-msg", form), "عضویت شما در خبرنامه عطر مجد با موفقیت انجام شد.");
      form.reset();
    });
  },

  /* ---------- فروشگاه ---------- */
  shop() {
    const PER_PAGE = 8;
    const prices = PRODUCTS.map((p) => p.price);
    const MIN = Math.floor(Math.min(...prices) / 100000) * 100000;
    const MAX = Math.ceil(Math.max(...prices) / 100000) * 100000;
    const state = {
      brands: new Set(),
      scents: new Set(),
      min: MIN,
      max: MAX,
      q: (params.get("q") || "").trim(),
      collection: params.get("collection") || "",
      sort: "default",
      page: 1,
      view: store.get("majd-view", "grid"),
    };

    const countBy = (key, val) => PRODUCTS.filter((p) => p[key] === val).length;
    $("#brand-filters").innerHTML = Object.entries(BRANDS).map(([k, v]) =>
      `<label class="check"><input type="checkbox" value="${k}" data-group="brands"> ${v} <span class="count">(${faNum(countBy("brand", k))})</span></label>`).join("");
    $("#scent-filters").innerHTML = Object.entries(SCENTS).map(([k, v]) =>
      `<label class="check"><input type="checkbox" value="${k}" data-group="scents"> ${v} <span class="count">(${faNum(countBy("scent", k))})</span></label>`).join("");

    const minR = $("#price-min"), maxR = $("#price-max");
    [minR, maxR].forEach((r) => { r.min = MIN; r.max = MAX; r.step = 100000; });
    minR.value = MIN; maxR.value = MAX;

    const grid = $("#product-grid");
    const setView = (v) => {
      state.view = v;
      store.set("majd-view", v);
      grid.classList.toggle("list-view", v === "list");
      $$(".view-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === v));
    };
    setView(state.view);

    function filtered() {
      const q = state.q.toLowerCase();
      let list = PRODUCTS.filter((p) =>
        (!state.brands.size || state.brands.has(p.brand)) &&
        (!state.scents.size || state.scents.has(p.scent)) &&
        (!state.collection || p.collection === state.collection) &&
        p.price >= state.min && p.price <= state.max &&
        (!q || [p.name, BRANDS[p.brand], SCENTS[p.scent], p.desc, ...Object.values(p.notes)].join(" ").toLowerCase().includes(q))
      );
      const sorters = {
        "price-asc": (a, b) => a.price - b.price,
        "price-desc": (a, b) => b.price - a.price,
        rating: (a, b) => b.rating - a.rating,
        name: (a, b) => a.name.localeCompare(b.name, "fa"),
      };
      if (sorters[state.sort]) list = [...list].sort(sorters[state.sort]);
      return list;
    }

    function render() {
      const list = filtered();
      const pages = Math.max(1, Math.ceil(list.length / PER_PAGE));
      state.page = Math.min(state.page, pages);
      const start = (state.page - 1) * PER_PAGE;
      const slice = list.slice(start, start + PER_PAGE);

      grid.innerHTML = slice.length
        ? slice.map(productCard).join("")
        : `<div class="empty-state" style="grid-column:1/-1">${icon("search")}<p>عطری با این مشخصات پیدا نشد.</p><button class="btn btn-ghost btn-sm" id="empty-clear">پاک کردن فیلترها</button></div>`;
      $("#empty-clear")?.addEventListener("click", clearAll);

      $("#result-count").textContent = list.length
        ? `نمایش ${faNum(start + 1)}–${faNum(start + slice.length)} از ${faNum(list.length)} محصول`
        : "۰ محصول";

      const chips = [];
      if (state.q) chips.push(`جستجو: «${escapeHtml(state.q)}» <button data-clear="q" aria-label="حذف">✕</button>`);
      if (state.collection) {
        const c = COLLECTIONS.find((c) => c.id === state.collection);
        chips.push(`${c ? c.name : ""} <button data-clear="collection" aria-label="حذف">✕</button>`);
      }
      $("#active-query").innerHTML = chips.join(" · ");

      const pag = $("#pagination");
      if (pages <= 1) { pag.innerHTML = ""; return; }
      let html = `<button data-page="${state.page - 1}" ${state.page === 1 ? "disabled" : ""}>قبلی</button>`;
      for (let i = 1; i <= pages; i++) html += `<button data-page="${i}" class="${i === state.page ? "active" : ""}">${faNum(i)}</button>`;
      html += `<button data-page="${state.page + 1}" ${state.page === pages ? "disabled" : ""}>بعدی</button>`;
      pag.innerHTML = html;
    }

    function updatePriceLabel() {
      $("#price-label-min").textContent = toman(state.min);
      $("#price-label-max").textContent = toman(state.max);
    }

    function clearAll() {
      state.brands.clear(); state.scents.clear();
      state.min = MIN; state.max = MAX; state.q = ""; state.collection = ""; state.page = 1;
      $$(".filters input[type=checkbox]").forEach((c) => (c.checked = false));
      minR.value = MIN; maxR.value = MAX;
      history.replaceState(null, "", "shop.html");
      updatePriceLabel(); render();
    }

    $(".filters").addEventListener("change", (e) => {
      const g = e.target.dataset.group;
      if (!g) return;
      e.target.checked ? state[g].add(e.target.value) : state[g].delete(e.target.value);
      state.page = 1; render();
    });
    const onRange = (e) => {
      let a = +minR.value, b = +maxR.value;
      if (a > b) { if (e.target === minR) minR.value = a = b; else maxR.value = b = a; }
      state.min = a; state.max = b; state.page = 1;
      updatePriceLabel(); render();
    };
    minR.addEventListener("input", onRange);
    maxR.addEventListener("input", onRange);
    $("#clear-filters").addEventListener("click", clearAll);
    $("#sort").addEventListener("change", (e) => { state.sort = e.target.value; state.page = 1; render(); });
    $$(".view-btn").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
    $("#pagination").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-page]");
      if (!b || b.disabled) return;
      state.page = +b.dataset.page; render();
      $(".shop-toolbar").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    $("#active-query").addEventListener("click", (e) => {
      const k = e.target.dataset.clear;
      if (!k) return;
      state[k] = ""; state.page = 1;
      const u = new URLSearchParams(location.search); u.delete(k);
      history.replaceState(null, "", "shop.html" + (u.toString() ? "?" + u : ""));
      render();
    });

    const filters = $(".filters");
    $("#filter-toggle").addEventListener("click", () => filters.classList.add("open"));
    $("#filter-close").addEventListener("click", () => filters.classList.remove("open"));

    updatePriceLabel();
    render();
  },

  /* ---------- کالکشن‌ها ---------- */
  collections() {
    $("#collections-grid").innerHTML = COLLECTIONS.map(collectionCard).join("");
  },

  /* ---------- صفحه محصول ---------- */
  product() {
    const p = findProduct(params.get("id")) || findProduct("mystic");
    document.title = `${p.name} | عطر مجد`;
    $("#crumb-name").textContent = p.name;

    const gallery = p.gallery || [p.img, COLLECTIONS.find((c) => c.id === p.collection).img, "assets/img/product-main.jpg"];
    let idx = 0;
    const mainImg = $("#gallery-img");
    const thumbs = $("#gallery-thumbs");
    thumbs.innerHTML = gallery.map((src, i) =>
      `<button class="${i === 0 ? "active" : ""}" data-i="${i}" aria-label="تصویر ${faNum(i + 1)}"><img src="${src}" alt=""></button>`).join("");
    const show = (i) => {
      idx = (i + gallery.length) % gallery.length;
      mainImg.src = gallery[idx];
      mainImg.alt = `عطر ${p.name}`;
      $$("button", thumbs).forEach((b, j) => b.classList.toggle("active", j === idx));
    };
    show(0);
    thumbs.addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) show(+b.dataset.i); });
    $("#gallery-prev").addEventListener("click", () => show(idx - 1));
    $("#gallery-next").addEventListener("click", () => show(idx + 1));

    $("#p-name").textContent = p.name;
    $("#p-brand").textContent = BRANDS[p.brand];
    $("#p-stars").innerHTML = `${stars(p.rating)} <span>(${faNum(p.reviews)} نظر مشتری)</span>`;
    $("#p-short").textContent = p.desc;
    $("#p-desc").textContent = p.desc;
    $("#note-top").textContent = p.notes.top;
    $("#note-mid").textContent = p.notes.mid;
    $("#note-base").textContent = p.notes.base;
    $("#reviews-count").textContent = faNum(p.reviews);

    let size = 50;
    const qtyInput = $("#qty");
    const renderPrice = () => {
      $("#p-price").innerHTML = `${toman(p.price * SIZE_FACTOR[size])} <small>/ ${faNum(size)} میل</small>`;
    };
    renderPrice();
    $$(".chip[data-size]").forEach((c) => c.addEventListener("click", () => {
      size = +c.dataset.size;
      $$(".chip[data-size]").forEach((x) => x.classList.toggle("active", x === c));
      renderPrice();
    }));
    const clampQty = (v) => Math.max(1, Math.min(20, parseInt(toEnDigits(v), 10) || 1));
    $("#qty-minus").addEventListener("click", () => (qtyInput.value = clampQty(qtyInput.value) - 1 || 1));
    $("#qty-plus").addEventListener("click", () => (qtyInput.value = clampQty(+qtyInput.value + 1)));
    qtyInput.addEventListener("change", () => (qtyInput.value = clampQty(qtyInput.value)));
    $("#add-to-cart").addEventListener("click", () => addToCart(p.id, size, clampQty(qtyInput.value)));

    const shareUrl = encodeURIComponent(location.href);
    const shareText = encodeURIComponent(`عطر ${p.name} از عطر مجد`);
    $("#share-telegram").href = `https://t.me/share/url?url=${shareUrl}&text=${shareText}`;
    $("#share-whatsapp").href = `https://wa.me/?text=${shareText}%20${shareUrl}`;
    $("#share-x").href = `https://twitter.com/intent/tweet?url=${shareUrl}&text=${shareText}`;
    $("#share-mail").href = `mailto:?subject=${shareText}&body=${shareUrl}`;

    // تب‌ها
    $$(".tab-list button").forEach((tab) => tab.addEventListener("click", () => {
      $$(".tab-list button").forEach((t) => t.setAttribute("aria-selected", t === tab));
      $$(".tab-panel").forEach((panel) => (panel.hidden = panel.id !== tab.getAttribute("aria-controls")));
    }));

    // نظرات
    const key = `majd-reviews-${p.id}`;
    const seed = [
      { name: "سارا", rating: 5, date: "۱۲ آذر ۱۴۰۴", text: "ماندگاری فوق‌العاده‌ای دارد و تا شب رایحه‌اش حس می‌شود." },
      { name: "امیر", rating: 5, date: "۲ آذر ۱۴۰۴", text: "بسته‌بندی بسیار شیک و رایحه‌ای کاملاً خاص. پیشنهاد می‌کنم." },
      { name: "نگار", rating: 4, date: "۲۰ آبان ۱۴۰۴", text: "خیلی خوش‌بوست، فقط کاش حجم بزرگ‌ترش هم تخفیف داشت." },
    ];
    const renderReviews = () => {
      const all = [...store.get(key, []), ...seed];
      $("#reviews-list").innerHTML = all.map((r) => `
        <article class="review">
          <header><strong>${escapeHtml(r.name)}</strong> ${stars(r.rating)} <time>${r.date}</time></header>
          <p>${escapeHtml(r.text)}</p>
        </article>`).join("");
    };
    renderReviews();
    $("#review-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const f = e.target;
      if (!validateForm(f)) return;
      const mine = store.get(key, []);
      mine.unshift({
        name: f.name.value.trim(), rating: +f.rating.value, text: f.text.value.trim(),
        date: new Date().toLocaleDateString("fa-IR", { day: "numeric", month: "long", year: "numeric" }),
      });
      store.set(key, mine);
      f.reset();
      renderReviews();
      showMsg($(".form-msg", f), "نظر شما ثبت شد. سپاس از همراهی شما!");
    });

    const related = PRODUCTS.filter((x) => x.id !== p.id)
      .sort((a, b) => (b.collection === p.collection) - (a.collection === p.collection) || (b.scent === p.scent) - (a.scent === p.scent));
    $("#related .carousel-track").innerHTML = related.slice(0, 8).map(productCard).join("");
    setupCarousel($("#related"));
  },

  /* ---------- مجله ---------- */
  blog() {
    let cat = params.get("cat") || "all";
    let q = "";
    const catList = $("#cat-list");
    const cats = [["all", "همه مطالب", POSTS.length], ...Object.entries(POST_CATS).map(([k, v]) => [k, v, POSTS.filter((p) => p.cat === k).length])];
    catList.innerHTML = cats.map(([k, v, n]) => `<li><button data-cat="${k}">${v} <span class="count">${faNum(n)}</span></button></li>`).join("");
    const render = () => {
      $$("button", catList).forEach((b) => b.classList.toggle("active", b.dataset.cat === cat));
      const list = POSTS.filter((p) => (cat === "all" || p.cat === cat) && (!q || (p.title + p.excerpt).includes(q)));
      $("#posts-grid").innerHTML = list.length
        ? list.map(postCard).join("")
        : `<div class="empty-state" style="grid-column:1/-1">${icon("search")}<p>مطلبی یافت نشد.</p></div>`;
    };
    catList.addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { cat = b.dataset.cat; render(); } });
    $("#blog-search").addEventListener("input", (e) => { q = e.target.value.trim(); render(); });
    render();
  },

  post() {
    const post = POSTS.find((p) => p.id === params.get("id")) || POSTS[0];
    document.title = `${post.title} | مجله عطر مجد`;
    $("#crumb-name").textContent = post.title;
    $("#article").innerHTML = `
      <img class="cover" src="${post.img}" alt="">
      <span class="post-meta">${post.date} <span class="tag">${POST_CATS[post.cat]}</span></span>
      <h1>${post.title}</h1>
      <div class="article-body">
        <p><strong>${post.excerpt}</strong></p>
        ${post.body.map(([h, t]) => (h ? `<h2>${h}</h2>` : "") + `<p>${t}</p>`).join("")}
      </div>
      <p style="margin-top:30px"><a class="btn btn-ghost" href="blog.html">بازگشت به مجله</a> <a class="btn" href="shop.html">مشاهده فروشگاه</a></p>`;
    $("#more-posts").innerHTML = POSTS.filter((p) => p.id !== post.id).slice(0, 2).map(postCard).join("");
  },

  /* ---------- سبد خرید و تسویه ---------- */
  cart() {
    let coupon = store.get("majd-coupon", null);
    if (coupon && !COUPONS[coupon]) coupon = null;

    function totals() {
      const sub = Cart.subtotal();
      const discount = coupon ? sub * COUPONS[coupon] : 0;
      const shipping = sub > 0 ? SHIPPING_COST : 0;
      return { sub, discount, shipping, total: sub - discount + shipping };
    }

    function render() {
      const items = Cart.items().filter((i) => findProduct(i.id));
      const hasItems = items.length > 0;
      $("#cart-content").hidden = !hasItems;
      $("#cart-empty").hidden = hasItems;
      $("#order-section").hidden = !hasItems;
      if (!hasItems) return;

      $("#cart-body").innerHTML = items.map((i) => {
        const p = findProduct(i.id);
        const unit = Cart.unitPrice(i);
        return `
          <tr>
            <td><div class="cart-product"><img src="${p.img}" alt=""><div><a href="product.html?id=${p.id}">${p.name}</a><small>${BRANDS[p.brand]}، ${faNum(i.size)} میل</small></div></div></td>
            <td data-label="قیمت">${toman(unit)}</td>
            <td><div class="qty" data-id="${i.id}" data-size="${i.size}">
              <button type="button" data-d="-1" aria-label="کاهش">−</button>
              <input type="number" value="${i.qty}" min="1" max="20" aria-label="تعداد">
              <button type="button" data-d="1" aria-label="افزایش">+</button>
            </div></td>
            <td data-label="جمع">${toman(unit * i.qty)}</td>
            <td><button class="remove-btn" data-remove="${i.id}" data-size="${i.size}" aria-label="حذف">${icon("trash")}</button></td>
          </tr>`;
      }).join("");

      const summaryItems = items.map((i) => {
        const p = findProduct(i.id);
        return `<div class="summary-item"><img src="${p.img}" alt=""><div class="name">${p.name} × ${faNum(i.qty)}<small>${BRANDS[p.brand]}، ${faNum(i.size)} میل</small></div><span>${toman(Cart.unitPrice(i) * i.qty)}</span></div>`;
      }).join("");
      const t = totals();
      const rows = `
        <div class="summary-row"><span>جمع جزء</span><span>${toman(t.sub)}</span></div>
        ${t.discount ? `<div class="summary-row discount"><span>تخفیف (${coupon})</span><span>− ${toman(t.discount)}</span></div>` : ""}
        <div class="summary-row"><span>هزینه ارسال</span><span>${toman(t.shipping)}</span></div>
        <div class="summary-row total"><span>مبلغ قابل پرداخت</span><span>${toman(t.total)}</span></div>`;
      $("#cart-summary").innerHTML = summaryItems + rows;
      $("#order-summary").innerHTML = summaryItems + rows;
    }

    $("#cart-body").addEventListener("click", (e) => {
      const d = e.target.closest("[data-d]");
      if (d) {
        const box = d.closest(".qty");
        const input = $("input", box);
        Cart.setQty(box.dataset.id, +box.dataset.size, (+input.value || 1) + +d.dataset.d);
        render();
      }
      const r = e.target.closest("[data-remove]");
      if (r) { Cart.remove(r.dataset.remove, +r.dataset.size); render(); }
    });
    $("#cart-body").addEventListener("change", (e) => {
      if (e.target.matches(".qty input")) {
        const box = e.target.closest(".qty");
        Cart.setQty(box.dataset.id, +box.dataset.size, parseInt(toEnDigits(e.target.value), 10) || 1);
        render();
      }
    });
    $("#update-cart").addEventListener("click", () => { render(); toast(`${icon("check")}<span>سبد خرید به‌روزرسانی شد.</span>`); });

    const applyCoupon = (input, msgEl) => {
      const code = toEnDigits(input.value.trim()).toUpperCase();
      if (!code) return showMsg(msgEl, "کد تخفیف را وارد کنید.", "err");
      if (!COUPONS[code]) return showMsg(msgEl, "کد تخفیف معتبر نیست.", "err");
      coupon = code;
      store.set("majd-coupon", code);
      showMsg(msgEl, `کد ${code} اعمال شد: ${faNum(COUPONS[code] * 100)}٪ تخفیف`);
      render();
    };
    $("#coupon-form").addEventListener("submit", (e) => { e.preventDefault(); applyCoupon($("#coupon"), $("#coupon-msg")); });

    $("#checkout-form").addEventListener("submit", (e) => {
      e.preventDefault();
      if (!validateForm(e.target)) return;
      const orderNo = "MJ-" + Date.now().toString().slice(-7);
      const t = totals();
      $("#order-no").textContent = toEnDigits(orderNo);
      $("#order-total").textContent = toman(t.total);
      Cart.clear();
      store.set("majd-coupon", null);
      coupon = null;
      $("#order-modal").hidden = false;
      render();
    });

    render();
  },

  /* ---------- ورود و ثبت‌نام ---------- */
  login() {
    const user = store.get("majd-user", null);
    if (user) {
      $("#auth-forms").hidden = true;
      $("#welcome").hidden = false;
      $("#welcome-name").textContent = user.name;
      $("#logout").addEventListener("click", () => { store.set("majd-user", null); location.reload(); });
      return;
    }
    $("#login-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const f = e.target;
      if (!validateForm(f)) return;
      // نسخه نمایشی: بدون سرور، فقط نام کاربری در مرورگر نگه داشته می‌شود (رمز عبور ذخیره نمی‌شود)
      store.set("majd-user", { name: f.email.value.split("@")[0], email: f.email.value });
      showMsg($(".form-msg", f), "ورود با موفقیت انجام شد. در حال انتقال…");
      setTimeout(() => (location.href = "index.html"), 1200);
    });
    $("#register-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const f = e.target;
      if (!validateForm(f)) return;
      store.set("majd-user", { name: `${f.first.value.trim()} ${f.last.value.trim()}`, email: f.email.value });
      showMsg($(".form-msg", f), "حساب کاربری شما ساخته شد. به خانواده عطر مجد خوش آمدید!");
      setTimeout(() => (location.href = "index.html"), 1400);
    });
    $("#forgot").addEventListener("click", (e) => {
      e.preventDefault();
      toast(`${icon("mail")}<span>لینک بازیابی رمز عبور به ایمیل شما ارسال خواهد شد.</span>`);
    });
  },

  /* ---------- تماس ---------- */
  contact() {
    $("#contact-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const f = e.target;
      if (!validateForm(f)) return;
      showMsg($(".form-msg", f), `${f.name.value.trim()} عزیز، پیام شما دریافت شد. کارشناسان ما به‌زودی پاسخ می‌دهند.`);
      f.reset();
    });
  },
};

/* ---------- قالب‌های مشترک ---------- */
function collectionCard(c) {
  const n = PRODUCTS.filter((p) => p.collection === c.id).length;
  return `
    <article class="collection-card reveal ${c.wide ? "wide" : ""}">
      <a class="media" href="shop.html?collection=${c.id}"><img src="${c.img}" alt="${c.name}" loading="lazy"></a>
      <div class="info">
        <h3>${c.name}</h3>
        <p>${c.tagline} · ${faNum(n)} عطر</p>
        <a class="btn btn-sm" href="shop.html?collection=${c.id}">مشاهده کالکشن</a>
      </div>
    </article>`;
}

function postCard(p) {
  return `
    <article class="post-card">
      <a class="media" href="post.html?id=${p.id}"><img src="${p.img}" alt="" loading="lazy"></a>
      <h3><a href="post.html?id=${p.id}">${p.title}</a></h3>
      <time>${p.date} <span class="tag">${POST_CATS[p.cat]}</span></time>
      <p>${p.excerpt}</p>
      <a class="btn btn-sm" href="post.html?id=${p.id}">ادامه مطلب</a>
    </article>`;
}
