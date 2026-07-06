(function(){
  function looksNumericValue(v){  // تعريف دالة
    if(!v) return false;
    // contains at least one digit
    return /\d/.test(v);
  }

  function isNumericField(el){  // تعريف دالة
    const type = (el.getAttribute("type") || "").toLowerCase();  // تعريف متغير
    if(type === "number" || type === "date" || type === "tel") return true;

    const name = (el.getAttribute("name") || "");  // تعريف متغير
    const id = (el.getAttribute("id") || "");  // تعريف متغير
    const ph = (el.getAttribute("placeholder") || "");  // تعريف متغير
    const hay = (name + " " + id + " " + ph).toLowerCase();  // تعريف متغير

    // Arabic keywords used in this project
    const keys = [  // تعريف متغير
      "تاريخ",
      "رقم",
      "هاتف",
      "الهاتف",
      "الرقم_التعريفي",
      "رقم_عقد_الميلاد",
      "رقم_التسجيل",
      "رقم_التعريف_الوطني",
      "رقم_الضمان_الاجتماعي",
      "رقم_الشطب",
      "id",
    ];
    if(keys.some(k => hay.includes(k))) return true;

    // fallback: if current value contains digits, treat as numeric-ish
    if(looksNumericValue(el.value)) return true;

    return false;
  }

  function apply(){  // تعريف دالة
    document.querySelectorAll(".fg-field input, .fg-field textarea").forEach(el=>{  // اختيار عنصر من الصفحة باستخدام CSS selector
      const t = (el.getAttribute("type") || "").toLowerCase();  // تعريف متغير
      if(t === "checkbox" || t === "radio" || t === "hidden" || t === "file") return;
      if(isNumericField(el)) el.classList.add("num");

      // keep updated as user types (in case of fallback detection)
      el.addEventListener("input", ()=>{  // ربط حدث (Event) بعنصر
        if(isNumericField(el)) el.classList.add("num");
        else el.classList.remove("num");
      });
    });
  }

  window.addEventListener("load", apply);  // ربط حدث (Event) بعنصر
})();