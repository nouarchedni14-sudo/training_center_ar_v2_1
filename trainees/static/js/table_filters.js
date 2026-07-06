(function () {
  const PROGRAM = window.__TC_PROGRAM__ || "";  // تعريف متغير
  const STORAGE_KEY = "tc_filters_v2_" + PROGRAM;  // تعريف متغير

  const table = document.querySelector(".rtl-table");  // تعريف متغير
  if (!table) return;  // شرط

  const tbody = table.querySelector("tbody");  // تعريف متغير
  const popup = document.getElementById("filter-popup");  // تعريف متغير
  const valuesBox = document.getElementById("filter-values");  // تعريف متغير
  const searchInput = document.getElementById("popup-search-input");  // تعريف متغير

  // Guard: popup markup must exist
  if (!popup || !valuesBox || !searchInput) return;  // شرط

  // ---- Cache for fast filtering ----
  const allRows = Array.from(tbody.querySelectorAll("tr"));  // تعريف متغير
  function ensureCache(row) {  // تعريف دالة
    if (row.__cellCache) return;  // شرط
    const cells = Array.from(row.children);  // تعريف متغير
    row.__cellCache = cells.map((td) => (td.textContent || "").trim());
    row.__cellCacheLower = row.__cellCache.map((v) => v.toLowerCase());
  }
  function cellVal(row, col) { ensureCache(row); return row.__cellCache[col] ?? ""; }  // تعريف دالة
  function cellValLower(row, col) { ensureCache(row); return row.__cellCacheLower[col] ?? ""; }  // تعريف دالة

  function debounce(fn, wait) {  // تعريف دالة
    let t = null;  // تعريف متغير
    return function (...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), wait);
    };
  }

  // ---- Columns definition ----
  const headers = Array.from(table.querySelectorAll("thead tr.header-row th"))  // تعريف متغير
    .map((th, idx) => ({ th, idx, field: th.dataset.field || "", btn: th.querySelector(".filter-btn") }))  // اختيار عنصر من الصفحة باستخدام CSS selector
    .filter((x) => x.field && x.btn);

  // ---- Filters state (multi-column) ----
  // filters[field] = { colIndex, selected:Set<string>, lastQuery }
  const filters = {};  // تعريف متغير
  let current = { colIndex: null, field: null };  // تعريف متغير

  function persistState() {  // تعريف دالة
    const obj = {};  // تعريف متغير
    Object.keys(filters).forEach((field) => {
      const f = filters[field];  // تعريف متغير
      if (!f || !f.selected || f.selected.size === 0) return;  // شرط
      obj[field] = { values: Array.from(f.selected), lastQuery: f.lastQuery || "" };
    });
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(obj)); } catch (e) {}
  }

  function restoreState() {  // تعريف دالة
    // URL params first (server-side filtering)
    const sp = new URLSearchParams(window.location.search);  // تعريف متغير
    let anyFromUrl = false;  // تعريف متغير

    headers.forEach((h) => {
      const vals = sp.getAll(h.field);  // تعريف متغير
      if (vals && vals.length) {  // شرط
        anyFromUrl = true;
        filters[h.field] = { colIndex: h.idx, selected: new Set(vals), lastQuery: "" };
      }
    });

    if (anyFromUrl) return;  // شرط

    // LocalStorage second
    try {
      const raw = localStorage.getItem(STORAGE_KEY);  // تعريف متغير
      if (!raw) return;  // شرط
      const obj = JSON.parse(raw);  // تعريف متغير
      Object.keys(obj || {}).forEach((field) => {
        const entry = obj[field];  // تعريف متغير
        if (!entry || !Array.isArray(entry.values)) return;  // شرط
        const h = headers.find((x) => x.field === field);  // تعريف متغير
        if (!h) return;  // شرط
        filters[field] = { colIndex: h.idx, selected: new Set(entry.values), lastQuery: entry.lastQuery || "" };
      });
    } catch (e) {}
  }

  function buildUrlParams(extra) {  // تعريف دالة
    const sp = new URLSearchParams();  // تعريف متغير
    Object.keys(filters).forEach((field) => {
      const f = filters[field];  // تعريف متغير
      if (!f || !f.selected || f.selected.size === 0) return;  // شرط
      f.selected.forEach((v) => sp.append(field, v));
    });
    if (extra) {  // شرط
      Object.keys(extra).forEach((k) => {
        if (extra[k] !== undefined && extra[k] !== null && String(extra[k]).length) sp.set(k, String(extra[k]));  // شرط
      });
    }
    return sp;
  }

  function rowPassesAll(row) {  // تعريف دالة
    for (const field of Object.keys(filters)) {  // حلقة
      const f = filters[field];  // تعريف متغير
      if (!f || !f.selected || f.selected.size === 0) continue;  // شرط
      const v = cellVal(row, f.colIndex);  // تعريف متغير
      if (!f.selected.has(v)) return false;  // شرط
    }
    return true;
  }

  function applyAllClient() {  // تعريف دالة
    const highlightCol = current.colIndex;  // تعريف متغير
    const q = (!popup.hidden) ? (searchInput.value || "").trim().toLowerCase() : "";  // تعريف متغير

    let i = 0;  // تعريف متغير
    const n = allRows.length;  // تعريف متغير

    function step() {  // تعريف دالة
      const end = Math.min(i + 700, n);  // تعريف متغير
      for (; i < end; i++) {  // حلقة
        const r = allRows[i];  // تعريف متغير
        const ok = rowPassesAll(r);  // تعريف متغير
        r.style.display = ok ? "" : "none";

        // Smart highlight for matches during search
        r.classList.remove("row-match");
        if (ok && q && highlightCol !== null) {  // شرط
          if (cellValLower(r, highlightCol).includes(q)) r.classList.add("row-match");  // شرط
        }
      }
      if (i < n) requestAnimationFrame(step);  // شرط
    }
    requestAnimationFrame(step);
  }

  function closeFilter() {  // تعريف دالة
    popup.hidden = true;
    current = { colIndex: null, field: null };
  }
  window.closeFilter = closeFilter;

  function openFilter(btn, colIndex, field) {  // تعريف دالة
    current = { colIndex, field };
    popup.hidden = false;
    searchInput.value = "";
    valuesBox.innerHTML = "";

    if (!filters[field]) filters[field] = { colIndex, selected: new Set(), lastQuery: "" };  // شرط
    filters[field].colIndex = colIndex;

    // Unique values from currently visible rows (Excel behavior)
    const set = new Set();  // تعريف متغير
    allRows.forEach((r) => {
      if (r.style.display === "none") return;  // شرط
      set.add(cellVal(r, colIndex));
    });

    const allValues = Array.from(set).sort((a, b) => String(a).localeCompare(String(b), "ar"));  // تعريف متغير
    const selected = filters[field].selected;  // تعريف متغير

    if (selected.size === 0) allValues.forEach((v) => selected.add(String(v)));  // شرط
    else {
      for (const v of Array.from(selected)) if (!set.has(v)) selected.delete(v);  // حلقة
      if (selected.size === 0) allValues.forEach((v) => selected.add(String(v)));  // شرط
    }

    // Select all row
    const top = document.createElement("div");  // تعريف متغير
    top.className = "popup-item sticky";
    top.innerHTML = '<label><input id="chk-all" type="checkbox"> <span class="val">تحديد الكل</span></label>';
    valuesBox.appendChild(top);

    const chkAll = top.querySelector("#chk-all");  // تعريف متغير
    function refreshAllCheck() {  // تعريف دالة
      const items = Array.from(valuesBox.querySelectorAll("input.val-chk"));  // تعريف متغير
      chkAll.checked = items.length ? items.every((x) => x.checked) : false;
    }

    chkAll.addEventListener("change", (ev) => {  // ربط حدث (Event) بعنصر
      const on = ev.target.checked;  // تعريف متغير
      valuesBox.querySelectorAll("input.val-chk").forEach((c) => {  // اختيار عنصر من الصفحة باستخدام CSS selector
        c.checked = on;
        if (on) selected.add(c.value);  // شرط
        else selected.delete(c.value);
      });
    });

    // values
    allValues.forEach((vRaw) => {
      const v = String(vRaw);  // تعريف متغير
      const div = document.createElement("div");  // تعريف متغير
      div.className = "popup-item";
      const label = document.createElement("label");  // تعريف متغير

      const chk = document.createElement("input");  // تعريف متغير
      chk.className = "val-chk";
      chk.type = "checkbox";
      chk.value = v;
      chk.checked = selected.has(v);

      const span = document.createElement("span");  // تعريف متغير
      span.className = "val";
      span.textContent = (v.trim() === "") ? "(فارغ)" : v;

      chk.addEventListener("change", (ev) => {  // ربط حدث (Event) بعنصر
        const val = ev.target.value;  // تعريف متغير
        if (ev.target.checked) selected.add(val);  // شرط
        else selected.delete(val);
        refreshAllCheck();
      });

      label.appendChild(chk);
      label.appendChild(document.createTextNode(" "));
      label.appendChild(span);
      div.appendChild(label);
      valuesBox.appendChild(div);
    });

    refreshAllCheck();

    // Position popup under the same TH (RTL-safe)
    const th = btn.closest("th");  // تعريف متغير
    if (th) {  // شرط
      th.style.position = "relative";
      th.appendChild(popup);
      popup.style.position = "absolute";
      popup.style.top = "calc(100% + 6px)";
      popup.style.right = "0";
      popup.style.left = "auto";
    }
  }

  // Sorting: use server-side to keep consistent across many rows
  window.sortCol = function (dir) {
    const field = current.field;  // تعريف متغير
    if (!field) return;  // شرط
    persistState();
    const sp = buildUrlParams({ sort: field, dir: dir });  // تعريف متغير
    window.location.search = sp.toString();
  };

  window.applyFilter = function () {
    const field = current.field;  // تعريف متغير
    if (!field) return;  // شرط

    filters[field].lastQuery = (searchInput.value || "").trim();
    persistState();

    // Large dataset: server-side
    if (allRows.length > 2000) {  // شرط
      const sp = buildUrlParams();  // تعريف متغير
      window.location.search = sp.toString();
      return;
    }

    applyAllClient();
    closeFilter();
  };

  window.clearFilter = function () {
    const field = current.field;  // تعريف متغير
    if (field && filters[field]) delete filters[field];  // شرط
    persistState();

    if (allRows.length > 2000) {  // شرط
      const sp = buildUrlParams();  // تعريف متغير
      window.location.search = sp.toString();
      return;
    }

    applyAllClient();
    closeFilter();
  };

  window.filterValueList = debounce(function (q) {
    const query = (q || "").trim().toLowerCase();  // تعريف متغير
    valuesBox.querySelectorAll(".popup-item:not(.sticky)").forEach((item) => {  // اختيار عنصر من الصفحة باستخدام CSS selector
      const text = item.textContent.toLowerCase();  // تعريف متغير
      item.style.display = text.includes(query) ? "" : "none";
    });

    // Live highlight (client-side only)
    if (allRows.length <= 2000) applyAllClient();  // شرط
  }, 120);

  // Wire buttons
  headers.forEach((h) => {
    h.btn.addEventListener("click", (e) => {  // ربط حدث (Event) بعنصر
      e.preventDefault();
      e.stopPropagation();
      openFilter(h.btn, h.idx, h.field);
    });
  });

  // Keyboard shortcuts
  document.addEventListener("keydown", (e) => {  // ربط حدث (Event) بعنصر
    if (popup.hidden) return;  // شرط
    if (e.key === "Escape") { e.preventDefault(); closeFilter(); }  // شرط
    else if (e.key === "Enter") { e.preventDefault(); window.applyFilter(); }
  });

  document.addEventListener("click", function () { closeFilter(); });  // ربط حدث (Event) بعنصر
  popup.addEventListener("click", function (e) { e.stopPropagation(); });  // ربط حدث (Event) بعنصر

  restoreState();
  if (Object.keys(filters).length && allRows.length <= 2000) applyAllClient();  // شرط
})();