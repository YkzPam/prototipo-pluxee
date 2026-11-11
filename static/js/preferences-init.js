(() => {
  'use strict';
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem('portal_preferences') || '{}') || {}; } catch {}
  const choice = ['light', 'dark', 'system'].includes(saved.theme) ? saved.theme : 'light';
  const dark = choice === 'dark' || (choice === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  document.documentElement.dataset.contrast = saved.contrast === true ? 'high' : 'normal';
  document.documentElement.dataset.motionLevel = ['full','soft','none'].includes(saved.motion) ? saved.motion : 'full';
  // Antes del primer cuadro, para que la transición entre páginas respete la pausa de animaciones.
  try { if (localStorage.getItem('portal_motion') === 'off') document.documentElement.dataset.motion = 'off'; } catch {}
  // Una transición omitida (pestaña en segundo plano, clic rápido) no es un error de la página.
  const settle = event => {
    const transition = event.viewTransition;
    if (!transition) return;
    transition.ready.catch(() => {});
    transition.finished.catch(() => {});
    const root = document.documentElement;
    if (event.type === 'pagereveal' && (root.dataset.motion === 'off' || root.dataset.motionLevel === 'none')) {
      transition.skipTransition();
    }
  };
  addEventListener('pageswap', settle);
  addEventListener('pagereveal', settle);
  try {
    const account = JSON.parse(localStorage.getItem('portal_account_ui_' + document.documentElement.dataset.interfaceUser) || '{}');
    document.documentElement.dataset.privateAmounts = account?.private === true ? 'hidden' : 'visible';
  } catch {}
})();
