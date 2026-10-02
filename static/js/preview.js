/* فقط در حالت پیش‌نمایش بارگذاری می‌شود.
   - داخل iframe استودیو: نوار پیش‌نمایش پنهان می‌شود (استودیو نوار خودش را دارد).
   - استودیو هنگام تغییر رنگ‌ها (قبل از ذخیره) متغیرهای CSS را با postMessage می‌فرستد. */
(() => {
  const framed = window.self !== window.top;
  if (framed) document.querySelector("[data-preview-banner]")?.remove();
  const NAME = /^--color-[a-z0-9-]{1,40}$/;
  const VALUE = /^\d{1,3} \d{1,3} \d{1,3}$/;
  window.addEventListener("message", (e) => {
    if (e.origin !== window.location.origin || !e.data || e.data.type !== "majd:tokens") return;
    for (const [name, value] of Object.entries(e.data.vars || {})) {
      if (NAME.test(name) && VALUE.test(value)) document.documentElement.style.setProperty(name, value);
    }
  });
  if (framed) {
    // پیوندهای خارجی بیرون از iframe باز شوند
    document.addEventListener("click", (e) => {
      const a = e.target.closest?.("a[href]");
      if (a && a.origin !== window.location.origin) a.target = "_blank";
    });
  }
})();
