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

  // ---------- رنگ‌ها: نمایش مقدار و پیش‌نمایش سریع ----------
  const hexToRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(" ");
  document.addEventListener("input", (e) => {
    const input = e.target;
    if (!input.matches?.("input[type=color][data-token]")) return;
    const label = input.parentNode.querySelector("[data-color-value]");
    if (label) label.textContent = input.value;
    document.querySelector("[data-mini-preview]")?.style.setProperty(`--color-${input.dataset.token}`, hexToRgb(input.value));
  });
})();
