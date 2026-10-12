// صفحه چاپ فاکتور/برچسب استودیو: دکمه «چاپ»
document.addEventListener("click", (e) => {
  if (e.target.closest("[data-print]")) window.print();
});
