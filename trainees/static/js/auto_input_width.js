(function () {
  // قياس العرض بحسب الخط الحالي للحقل
  function measureTextWidth(text, el) {  // تعريف دالة
    const span = document.createElement("span");  // تعريف متغير
    span.style.position = "absolute";
    span.style.visibility = "hidden";
    span.style.whiteSpace = "pre";
    span.style.font = getComputedStyle(el).font;
    span.textContent = text || "";
    document.body.appendChild(span);
    const w = span.getBoundingClientRect().width;  // تعريف متغير
    document.body.removeChild(span);
    return w;
  }

  function resize(el) {  // تعريف دالة
    // تجاهل الأنواع التي لا نريدها
    const t = (el.getAttribute("type") || "text").toLowerCase();  // تعريف متغير
    if (["hidden", "checkbox", "radio", "file", "submit", "button", "password", "color", "range"].includes(t)) return;  // شرط
    if (el.tagName !== "INPUT") return;  // شرط
    // حقول بعض الصفحات مثل دخول المطور يجب أن تبقى بعرض كامل ولا تتقلص حسب النص.
    if (el.closest(".dev-login") || el.classList.contains("no-autowidth") || el.getAttribute("data-fixed-width") === "1") return;

    el.classList.add("autowidth");

    const v = el.value || el.getAttribute("value") || el.placeholder || "";  // تعريف متغير
    // 28px = padding + حدود + هامش أمان
    const px = Math.max(40, Math.ceil(measureTextWidth(v, el) + 28));  // تعريف متغير
    el.style.setProperty("width", px + "px", "important");
    el.style.setProperty("display", "inline-block", "important");
  }

  function applyAll() {  // تعريف دالة
    document.querySelectorAll("input").forEach(resize);  // اختيار عنصر من الصفحة باستخدام CSS selector
  }

  // مهم: بعد تحميل الصفحة بالكامل لضمان وجود القيم المعبأة مسبقاً
  window.addEventListener("load", function () {  // ربط حدث (Event) بعنصر
    applyAll();

    // تحديث فوري عند الكتابة
    document.addEventListener("input", function (e) {  // ربط حدث (Event) بعنصر
      if (e.target && e.target.tagName === "INPUT") resize(e.target);  // شرط
    });

    // بعض المتصفحات تغيّر القيمة عند change
    document.addEventListener("change", function (e) {  // ربط حدث (Event) بعنصر
      if (e.target && e.target.tagName === "INPUT") resize(e.target);  // شرط
    });
  });
})();