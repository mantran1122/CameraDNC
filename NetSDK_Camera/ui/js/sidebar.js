'use strict';
// Sidebar collapse + nav behaviour. Theme is managed by app.js (html[data-theme]).
(function (global) {
  var LS_COLLAPSED = 'dnc.sidebar.collapsed';

  function $(sel, root)  { return (root || document).querySelector(sel); }
  function $$(sel, root) { return [].slice.call((root || document).querySelectorAll(sel)); }
  function getSidebar()  { return $('.sidebar'); }

  function setCollapsed(collapsed) {
    var sb = getSidebar();
    if (!sb) { return; }
    sb.classList.toggle('collapsed', !!collapsed);
    try { localStorage.setItem(LS_COLLAPSED, collapsed ? '1' : '0'); } catch (e) {}
    if (collapsed) {
      $$('.nav-item.open', sb).forEach(function (el) { el.classList.remove('open'); });
      $$('.submenu', sb).forEach(function (el) { el.classList.add('shut'); });
    }
  }

  function toggle() {
    var sb = getSidebar();
    if (!sb) { return; }
    setCollapsed(!sb.classList.contains('collapsed'));
  }

  function bindNav() {
    var sb = getSidebar();
    if (!sb) { return; }

    var btn = $('.sidebar-toggle', sb);
    if (btn && !btn.__sbBound) {
      btn.addEventListener('click', toggle);
      btn.__sbBound = true;
    }

    $$('.nav-item', sb).forEach(function (item) {
      if (item.__sbBound) { return; }
      item.__sbBound = true;
      item.addEventListener('click', function () {
        var wrap    = item.closest('.nav-item-wrap');
        var submenu = wrap ? wrap.querySelector('.submenu') : null;
        if (submenu) {
          var isOpen = item.classList.toggle('open');
          submenu.classList.toggle('shut', !isOpen);
        } else {
          $$('.nav-item.active', sb).forEach(function (el) { el.classList.remove('active'); });
          $$('.sub-item.active', sb).forEach(function (el) { el.classList.remove('active'); });
          item.classList.add('active');
        }
      });
    });

    $$('.sub-item', sb).forEach(function (item) {
      if (item.__sbBound) { return; }
      item.__sbBound = true;
      item.addEventListener('click', function () {
        $$('.nav-item.active', sb).forEach(function (el) { el.classList.remove('active'); });
        $$('.sub-item.active', sb).forEach(function (el) { el.classList.remove('active'); });
        item.classList.add('active');
      });
    });
  }

  function init() {
    var saved = false;
    try { saved = localStorage.getItem(LS_COLLAPSED) === '1'; } catch (e) {}
    setCollapsed(saved);
    bindNav();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  global.Sidebar = { init: init, toggle: toggle, setCollapsed: setCollapsed };
})(window);
