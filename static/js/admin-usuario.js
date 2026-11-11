(() => {
  const cancel = document.querySelector('[data-admin-cancel]');
  if (cancel) {
    const confirmation = cancel.closest('details');
    cancel.hidden = false;
    cancel.addEventListener('click', () => {
      confirmation.open = false;
      confirmation.querySelector('summary').focus();
    });
  }

  if (!window.matchMedia('(prefers-reduced-motion: no-preference)').matches || !document.referrer) return;
  const navigation = performance.getEntriesByType('navigation')[0];
  if (navigation?.type !== 'navigate') return;

  const previous = new URL(document.referrer);
  const current = new URL(window.location.href);
  if (previous.origin !== current.origin || previous.pathname !== current.pathname) return;

  const section = (url) => url.searchParams.get('seccion') || 'datos';
  if (section(previous) !== section(current)) {
    document.querySelector('[data-admin-user-section]')?.animate(
      [{ opacity: .55, transform: 'translateY(6px)' }, { opacity: 1, transform: 'translateY(0)' }],
      { duration: 180, easing: 'ease-out' },
    );
  }
})();
