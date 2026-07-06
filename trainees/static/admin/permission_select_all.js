(function () {
  "use strict";

  const GROUPS = [
    {
      marker: "صلاحيات خاصة بمتابعة متكوني الحضوري الأولي",
      fields: ["initial_view", "initial_add", "initial_change", "initial_delete"],
    },
    {
      marker: "صلاحيات خاصة بمتابعة متكوني التمهين",
      fields: ["apprentice_view", "apprentice_add", "apprentice_change", "apprentice_delete"],
    },
    {
      marker: "صلاحيات خاصة بمتابعة متكوني المسائي والمعابر",
      fields: ["evening_view", "evening_add", "evening_change", "evening_delete"],
    },
  ];

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function findFieldCheckbox(fieldName) {
    const selectors = [
      `input[type="checkbox"][name$="-${fieldName}"]`,
      `input[type="checkbox"][name="${fieldName}"]`,
      `input[type="checkbox"][id$="-${fieldName}"]`,
      `input[type="checkbox"][id$="_${fieldName}"]`,
      `input[type="checkbox"][name$="${fieldName}"]`,
    ];

    for (const selector of selectors) {
      const match = document.querySelector(selector);
      if (match) return match;
    }
    return null;
  }

  function findDescriptionElement(markerText) {
    const marker = normalizeText(markerText);
    const candidates = Array.from(
      document.querySelectorAll(".description, .help, p, div, h2, h3")
    );

    return candidates
      .filter((el) => normalizeText(el.textContent).includes(marker))
      .sort((a, b) => normalizeText(a.textContent).length - normalizeText(b.textContent).length)[0] || null;
  }

  function updateMasterState(master, boxes) {
    const checkedCount = boxes.filter((box) => box.checked).length;
    master.checked = checkedCount === boxes.length;
    master.indeterminate = checkedCount > 0 && checkedCount < boxes.length;
  }

  function addSelectAll(group) {
    const description = findDescriptionElement(group.marker);
    if (!description) return;

    const wrapper = description.closest("fieldset, .module, .tc-permission-card, .form-row, div") || description.parentElement;
    if (!wrapper || wrapper.dataset.tcSelectAllReady === "1") return;

    const boxes = group.fields.map(findFieldCheckbox).filter(Boolean);
    if (boxes.length !== group.fields.length) return;

    wrapper.dataset.tcSelectAllReady = "1";

    const label = document.createElement("label");
    label.className = "tc-pattern-select-all";
    label.innerHTML = '<input type="checkbox" class="tc-pattern-select-all__input"> <span>تحديد الكل</span>';

    const master = label.querySelector("input");

    master.addEventListener("change", function () {
      const value = master.checked;
      boxes.forEach((box) => {
        if (box.checked !== value) {
          box.checked = value;
          box.dispatchEvent(new Event("input", { bubbles: true }));
          box.dispatchEvent(new Event("change", { bubbles: true }));
        }
      });
      updateMasterState(master, boxes);
    });

    boxes.forEach((box) => {
      box.addEventListener("change", function () {
        updateMasterState(master, boxes);
      });
    });

    updateMasterState(master, boxes);
    description.insertAdjacentElement("afterend", label);
  }

  function init() {
    GROUPS.forEach(addSelectAll);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  setTimeout(init, 400);
  setTimeout(init, 1200);
})();
