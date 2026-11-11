(() => {
  'use strict';
  if (!document.body.classList.contains('app-admin')) return;
  const toolbars = [...document.querySelectorAll('[data-admin-density-toolbar]')];
  if (!toolbars.length) return;
  const key = 'portal_admin_density';
  let density = 'comfortable';
  try {
    if (localStorage.getItem(key) === 'compact') density = 'compact';
  } catch {}

  function apply(value) {
    density = value === 'compact' ? 'compact' : 'comfortable';
    document.documentElement.dataset.adminDensity = density;
    toolbars.forEach(toolbar => {
      toolbar.hidden = false;
      toolbar.querySelectorAll('[data-admin-density]').forEach(button => {
        button.setAttribute('aria-pressed', String(button.dataset.adminDensity === density));
      });
    });
  }
  apply(density);
  toolbars.forEach(toolbar => toolbar.addEventListener('click', event => {
    const button = event.target.closest('[data-admin-density]');
    if (!button) return;
    apply(button.dataset.adminDensity);
    try { localStorage.setItem(key, density); } catch {}
    document.dispatchEvent(new CustomEvent('portal:admin-density', {detail: density}));
  }));
})();
