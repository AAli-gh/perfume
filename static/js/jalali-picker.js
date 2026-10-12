// تقویم شمسی برای ورودی‌های [data-jalali] (پنل مدیریت و استودیو) — بدون وابستگی.
// تبدیل تاریخ بر اساس الگوریتم jalaali-js (بازه ۱ تا ۳۱۷۷ هجری شمسی).
(() => {
  const FA = (s) => String(s).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[d]);
  const EN = (s) => String(s).replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)).replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d));
  const MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"];
  const WEEK = ["ش", "ی", "د", "س", "چ", "پ", "ج"];
  const div = (a, b) => Math.trunc(a / b);
  const BREAKS = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178];

  function jalCal(jy) {
    let gy = jy + 621, leapJ = -14, jp = BREAKS[0], jump = 0;
    for (let i = 1; i < BREAKS.length; i++) {
      const jm = BREAKS[i];
      jump = jm - jp;
      if (jy < jm) break;
      leapJ += div(jump, 33) * 8 + div(jump % 33, 4);
      jp = jm;
    }
    let n = jy - jp;
    leapJ += div(n, 33) * 8 + div((n % 33) + 3, 4);
    if (jump % 33 === 4 && jump - n === 4) leapJ += 1;
    const leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
    const march = 20 + leapJ - leapG;
    if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33;
    let leap = ((((n + 1) % 33) - 1) % 4);
    if (leap === -1) leap = 4;
    return { leap, gy, march };
  }
  function g2d(gy, gm, gd) {
    let d = div((gy + div(gm - 8, 6) + 100100) * 1461, 4) + div(153 * ((gm + 9) % 12) + 2, 5) + gd - 34840408;
    return d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
  }
  function d2g(jdn) {
    let j = 4 * jdn + 139361631;
    j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
    const i = div((j % 1461), 4) * 5 + 308;
    const gd = div((i % 153), 5) + 1, gm = (div(i, 153) % 12) + 1, gy = div(j, 1461) - 100100 + div(8 - gm, 6);
    return [gy, gm, gd];
  }
  function j2d(jy, jm, jd) {
    const r = jalCal(jy);
    return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
  }
  function d2j(jdn) {
    const gy = d2g(jdn)[0];
    let jy = gy - 621;
    const r = jalCal(jy);
    let k = jdn - g2d(gy, 3, r.march);
    if (k >= 0) {
      if (k <= 185) return [jy, 1 + div(k, 31), (k % 31) + 1];
      k -= 186;
    } else {
      jy -= 1;
      k += 179;
      if (r.leap === 1) k += 1;
    }
    return [jy, 7 + div(k, 30), (k % 30) + 1];
  }
  const monthLength = (jy, jm) => (jm <= 6 ? 31 : jm <= 11 ? 30 : jalCal(jy).leap === 0 ? 30 : 29);
  const today = () => { const n = new Date(); return d2j(g2d(n.getFullYear(), n.getMonth() + 1, n.getDate())); };
  const pad = (n) => String(n).padStart(2, "0");

  let popup = null, input = null, view = null;

  function parse(value) {
    const m = EN(value || "").match(/^\s*(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})(?:[\sT،,]+(\d{1,2})(?::(\d{1,2}))?)?/);
    if (!m) return null;
    return { y: +m[1], m: +m[2], d: +m[3], time: m[4] ? `${pad(m[4])}:${pad(m[5] || 0)}` : "" };
  }

  function render() {
    const [ty, tm, td] = today();
    const selected = parse(input.value);
    const first = (j2d(view.y, view.m, 1) + 2) % 7; // ۰ = شنبه
    const days = monthLength(view.y, view.m);
    let cells = "";
    for (let i = 0; i < first; i++) cells += "<span></span>";
    for (let d = 1; d <= days; d++) {
      const cls = [selected && selected.y === view.y && selected.m === view.m && selected.d === d ? "is-selected" : "",
        ty === view.y && tm === view.m && td === d ? "is-today" : ""].join(" ");
      cells += `<button type="button" data-day="${d}" class="${cls}">${FA(d)}</button>`;
    }
    const withTime = input.dataset.jalali === "datetime";
    const time = (selected && selected.time) || input.dataset.defaultTime || "00:00";
    popup.innerHTML = `
      <div class="jp-head"><button type="button" data-nav="1" aria-label="ماه بعد">‹</button>
        <strong>${MONTHS[view.m - 1]} ${FA(view.y)}</strong>
        <button type="button" data-nav="-1" aria-label="ماه قبل">›</button></div>
      <div class="jp-week">${WEEK.map((w) => `<span>${w}</span>`).join("")}</div>
      <div class="jp-days">${cells}</div>
      <div class="jp-foot">${withTime ? `<label>ساعت <input type="time" data-time value="${time}"></label>` : ""}
        <button type="button" data-today>امروز</button><button type="button" data-clear>پاک کردن</button></div>`;
  }

  function open(target) {
    input = target;
    const parsed = parse(input.value);
    const [ty, tm] = today();
    view = parsed && parsed.y < 1700 ? { y: parsed.y, m: parsed.m } : { y: ty, m: tm };
    if (!popup) {
      popup = document.createElement("div");
      popup.className = "jalali-picker";
      popup.setAttribute("dir", "rtl");
      document.body.appendChild(popup);
    }
    render();
    const rect = input.getBoundingClientRect();
    popup.style.top = `${window.scrollY + rect.bottom + 4}px`;
    popup.style.left = `${Math.max(8, window.scrollX + rect.right - 260)}px`;
    popup.hidden = false;
  }

  function close() { if (popup) popup.hidden = true; input = null; }

  function choose(y, m, d) {
    const withTime = input.dataset.jalali === "datetime";
    const time = withTime ? (popup.querySelector("[data-time]")?.value || "00:00") : "";
    input.value = FA(`${y}/${pad(m)}/${pad(d)}${time ? " " + time : ""}`);
    input.dispatchEvent(new Event("change", { bubbles: true }));
    close();
  }

  document.addEventListener("focusin", (e) => {
    const target = e.target.closest && e.target.closest("input[data-jalali]");
    if (target) open(target);
  });
  document.addEventListener("mousedown", (e) => {
    if (!popup || popup.hidden) return;
    if (popup.contains(e.target) || e.target === input) return;
    close();
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  document.addEventListener("click", (e) => {
    if (!popup || popup.hidden || !popup.contains(e.target)) return;
    const nav = e.target.closest("[data-nav]");
    if (nav) {
      view.m += Number(nav.dataset.nav);
      if (view.m > 12) { view.m = 1; view.y += 1; }
      if (view.m < 1) { view.m = 12; view.y -= 1; }
      render();
      return;
    }
    const day = e.target.closest("[data-day]");
    if (day) return choose(view.y, view.m, Number(day.dataset.day));
    if (e.target.closest("[data-today]")) { const [y, m, d] = today(); return choose(y, m, d); }
    if (e.target.closest("[data-clear]")) { input.value = ""; input.dispatchEvent(new Event("change", { bubbles: true })); close(); }
  });
})();
