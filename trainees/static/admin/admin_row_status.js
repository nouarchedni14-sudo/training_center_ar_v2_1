(function () {
  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  function normalize(value) {
    return (value || '').replace(/\s+/g, ' ').trim();
  }

  ready(function () {
    const table = document.querySelector('#result_list');
    if (!table) return;

    let statusIndex = -1;
    table.querySelectorAll('thead th').forEach(function (th, index) {
      const txt = normalize(th.textContent);
      if (txt.indexOf('تصنيف الحالة') !== -1) statusIndex = index;
    });
    if (statusIndex === -1) return;

    table.querySelectorAll('tbody tr').forEach(function (row) {
      const cells = row.querySelectorAll('td, th');
      const cell = cells[statusIndex];
      if (!cell) return;
      const value = normalize(cell.textContent);
      row.classList.remove('tc-row--active', 'tc-row--recent-removed', 'tc-row--removed');
      if (value.indexOf('مشطوب حديث') !== -1) row.classList.add('tc-row--recent-removed');
      else if (value.indexOf('مشطوب') !== -1) row.classList.add('tc-row--removed');
      else if (value.indexOf('حالي') !== -1) row.classList.add('tc-row--active');
    });
  });
})();
