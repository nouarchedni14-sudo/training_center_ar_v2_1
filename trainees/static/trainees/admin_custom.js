// تحسين بسيط لتجربة الفلاتر العلوية:
// - عند فتح فلتر، نغلق البقية (مثل Dropdown)
// - زر مسح الفلاتر (إن وجد) يبقى عادي كرابط

(function () {
  function ready(fn) {  // تعريف دالة
    if (document.readyState !== 'loading') fn();  // شرط
    else document.addEventListener('DOMContentLoaded', fn);  // ربط حدث (Event) بعنصر
  }

  ready(function () {
    const wrap = document.querySelector('.top-filters');  // تعريف متغير
    if (!wrap) return;  // شرط

    const boxes = Array.from(wrap.querySelectorAll('details'));  // تعريف متغير
    boxes.forEach((d) => {
      d.addEventListener('toggle', () => {  // ربط حدث (Event) بعنصر
        if (!d.open) return;  // شرط
        boxes.forEach((other) => {
          if (other !== d) other.removeAttribute('open');  // شرط
        });
      });
    });
  });
})();
