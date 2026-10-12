/* استودیو — تأیید عملیات، کشیدن و رها کردن بخش‌ها، پیش‌نمایش رنگ‌ها. بدون وابستگی (به‌جز HTMX). */
(() => {
  // ---------- تأیید قبل از عملیات حساس (فرم معمولی و HTMX) ----------
  document.addEventListener("submit", (e) => {
    const message = e.submitter?.dataset.confirm || e.target.dataset.confirm;
    if (message && !window.confirm(message)) {
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  }, true);

  // ---------- کشیدن و رها کردن بخش‌ها ----------
  // دکمه‌های بالا/پایین جایگزین کامل این قابلیت هستند (صفحه‌کلید، موبایل، بدون JS).
  let dragged = null;
  document.addEventListener("dragstart", (e) => {
    const row = e.target.closest?.("[data-sortable] > [data-id]");
    if (!row) return;
    dragged = row;
    row.classList.add("is-dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", row.dataset.id);
  });
  document.addEventListener("dragover", (e) => {
    if (!dragged) return;
    const over = e.target.closest?.("[data-sortable] > [data-id]");
    if (!over || over === dragged || over.parentNode !== dragged.parentNode) return;
    e.preventDefault();
    const rect = over.getBoundingClientRect();
    const after = e.clientY > rect.top + rect.height / 2;
    over.parentNode.insertBefore(dragged, after ? over.nextSibling : over);
  });
  document.addEventListener("drop", (e) => { if (dragged) e.preventDefault(); });
  document.addEventListener("dragend", () => {
    if (!dragged) return;
    const list = dragged.parentNode;
    dragged.classList.remove("is-dragging");
    dragged = null;
    const form = document.getElementById("reorder-form");
    if (!form) return;
    form.querySelectorAll("input[name=order]").forEach((i) => i.remove());
    list.querySelectorAll(":scope > [data-id]").forEach((row) => {
      const input = document.createElement("input");
      input.type = "hidden"; input.name = "order"; input.value = row.dataset.id;
      form.appendChild(input);
    });
    form.requestSubmit();
  });

  // ---------- رنگ‌ها: نمایش مقدار و اعمال فوری در پیش‌نمایش زنده (قبل از ذخیره) ----------
  const hexToRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(" ");
  const frames = () => document.querySelectorAll("iframe[data-preview-frame]");
  const pending = {};
  const pushTokens = (frame) => frame.contentWindow?.postMessage({ type: "majd:tokens", vars: pending }, window.location.origin);
  document.addEventListener("input", (e) => {
    const input = e.target;
    if (!input.matches?.("input[type=color][data-token]")) return;
    const label = input.parentNode.querySelector("[data-color-value]");
    if (label) label.textContent = input.value;
    pending[`--color-${input.dataset.token}`] = hexToRgb(input.value);
    frames().forEach(pushTokens);
  });
  // اگر iframe دوباره بارگذاری شد (مثلاً کاربر داخلش جابه‌جا شد)، رنگ‌های ذخیره‌نشده دوباره اعمال شوند
  document.addEventListener("load", (e) => { if (e.target.matches?.("iframe[data-preview-frame]")) pushTokens(e.target); }, true);

  // ---------- پیش‌نمایش: اندازه دستگاه، بارگذاری دوباره، کپی لینک ----------
  const reloadFrames = () => frames().forEach((f) => { try { f.contentWindow.location.reload(); } catch { f.src = f.src; } });
  document.body.addEventListener("preview-refresh", reloadFrames);  // HX-Trigger پس از تغییر بخش‌ها
  document.addEventListener("click", (e) => {
    const device = e.target.closest?.("[data-device]");
    if (device) {
      frames().forEach((f) => { f.style.width = device.dataset.device; });
      document.querySelectorAll("[data-device]").forEach((b) => b.setAttribute("aria-pressed", String(b === device)));
    }
    if (e.target.closest?.("[data-preview-reload]")) reloadFrames();
    const copy = e.target.closest?.("[data-copy]");
    if (copy) {
      const field = document.querySelector(copy.dataset.copy);
      field.select();
      navigator.clipboard?.writeText(field.value).then(() => { copy.textContent = "کپی شد"; }, () => {});
    }
  });
})();

// انتخاب همه سطرهای جدول (سفارش‌ها، مشتریان، …)
document.addEventListener("change", (e) => {
  const all = e.target.closest("[data-check-all]");
  if (!all) return;
  const form = all.closest("form");
  form.querySelectorAll('input[type=checkbox][name="ids"]').forEach((box) => { box.checked = all.checked; });
});
