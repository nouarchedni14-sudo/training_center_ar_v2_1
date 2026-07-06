(function () {
  function ready(fn) {  // تعريف دالة
    if (document.readyState !== 'loading') fn();  // شرط
    else document.addEventListener('DOMContentLoaded', fn);  // ربط حدث (Event) بعنصر
  }

  function isChangeList() {  // تعريف دالة
    return document.body && document.body.classList.contains('change-list');
  }

  // Normalize wheel behavior so vertical wheel never drifts the horizontal scroll in RTL.
  function lockHorizontalOnVerticalWheel(scroller) {  // تعريف دالة
    let lastScrollLeft = scroller.scrollLeft;  // تعريف متغير

    scroller.addEventListener(  // ربط حدث (Event) بعنصر
      'scroll',
      function () {  // تعريف دالة
        lastScrollLeft = scroller.scrollLeft;
      },
      { passive: true }
    );

    scroller.addEventListener(  // ربط حدث (Event) بعنصر
      'wheel',
      function (e) {  // تعريف دالة
        // If user intends horizontal scroll (trackpad deltaX or Shift+wheel), let it happen.
        const wantsHorizontal = e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY);  // تعريف متغير
        if (wantsHorizontal) return;  // شرط

        // Prevent browsers (especially with RTL tables) from translating vertical wheel into horizontal scroll.
        const before = scroller.scrollLeft;  // تعريف متغير
        // Allow page to scroll vertically normally; just restore any accidental horizontal change.
        requestAnimationFrame(function () {
          if (scroller.scrollLeft !== before) scroller.scrollLeft = before;  // شرط
        });
      },
      { passive: true }
    );
  }

  // Create a sticky bottom horizontal scrollbar synced with the table scroller.
  function addStickyBottomScrollbar(scroller) {  // تعريف دالة
    const xbar = document.createElement('div');  // تعريف متغير
    xbar.className = 'tc-xbar';

    const spacer = document.createElement('div');  // تعريف متغير
    spacer.className = 'tc-xbar__spacer';
    xbar.appendChild(spacer);

    // Insert right after scroller
    scroller.parentElement.appendChild(xbar);

    function syncSpacerWidth() {  // تعريف دالة
      spacer.style.width = scroller.scrollWidth + 'px';
    }

    // Sync scroll positions
    let syncing = false;  // تعريف متغير
    function sync(from, to) {  // تعريف دالة
      if (syncing) return;  // شرط
      syncing = true;
      to.scrollLeft = from.scrollLeft;
      requestAnimationFrame(function () {
        syncing = false;
      });
    }

    scroller.addEventListener('scroll', function () {  // ربط حدث (Event) بعنصر
      sync(scroller, xbar);
    });

    xbar.addEventListener('scroll', function () {  // ربط حدث (Event) بعنصر
      sync(xbar, scroller);
    });

    // Keep widths correct
    syncSpacerWidth();
    window.addEventListener('resize', syncSpacerWidth);  // ربط حدث (Event) بعنصر

    // Also update after images/fonts/layout settle
    setTimeout(syncSpacerWidth, 250);
    setTimeout(syncSpacerWidth, 1000);

    // Start aligned
    xbar.scrollLeft = scroller.scrollLeft;
  }



  function addRowNumbers(table) {  // تعريف دالة
    if (!table || table.dataset.tcRowNumbers === '1') return;  // شرط

    const headRow = table.querySelector('thead tr');  // تعريف متغير
    if (headRow) {  // شرط
      const th = document.createElement('th');  // تعريف متغير
      th.className = 'tc-rownum-head';
      th.textContent = '#';
      headRow.insertBefore(th, headRow.firstChild);
    }

    table.querySelectorAll('tbody tr').forEach(function (row, index) {  // ربط حدث (Event) بعنصر
      const td = document.createElement('td');  // تعريف متغير
      td.className = 'tc-rownum';
      td.textContent = String(index + 1).padStart(2, '0');
      row.insertBefore(td, row.firstChild);
    });

    const footRow = table.querySelector('tfoot tr');
    if (footRow) {
      const td = document.createElement('td');
      td.className = 'tc-rownum-foot';
      td.textContent = '';
      footRow.insertBefore(td, footRow.firstChild);
    }

    table.dataset.tcRowNumbers = '1';
  }

  // Wrap #result_list table with a horizontal scroller so sticky header works and we control scrolling.
  function enhanceChangeListTable() {  // تعريف دالة
    const table = document.querySelector('table#result_list');  // تعريف متغير
    if (!table) return;  // شرط

    // If actions row exists, adjust sticky header offset via a body class.
    const actions = document.querySelector('#changelist-form .actions');  // تعريف متغير
    if (actions) document.body.classList.add('tc-has-actions');  // شرط

    // If already enhanced, skip.
    if (table.closest('.tc-table-scroll')) return;  // شرط

    const wrap = document.createElement('div');  // تعريف متغير
    wrap.className = 'tc-table-wrap';

    const scroller = document.createElement('div');  // تعريف متغير
    scroller.className = 'tc-table-scroll';

    // Place wrapper where the table currently is.
    const parent = table.parentElement;  // تعريف متغير
    if (!parent) return;  // شرط

    parent.insertBefore(wrap, table);
    scroller.appendChild(table);
    wrap.appendChild(scroller);

    // Make sure the table is wide enough to require horizontal scroll when needed.
    table.style.minWidth = 'max-content';

    // Fix the RTL wheel drift problem.
    lockHorizontalOnVerticalWheel(scroller);

    // Add sticky bottom scrollbar.
    addStickyBottomScrollbar(scroller);
  }

  ready(function () {
    if (!isChangeList()) return;  // شرط
    const table = document.querySelector('table#result_list');
    addRowNumbers(table);
    enhanceChangeListTable();
  });
})();
