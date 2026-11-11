(() => {
  'use strict';
  const root = document.documentElement;
  const user = root.dataset.interfaceUser || 'public';
  const accountKey = 'portal_account_ui_' + user;
  const tourKey = 'portal_tour_' + user;
  const defaults = {theme: 'light', contrast: false, motion: 'full'};
  const accountDefaults = {private: false, avatar: 'initial', avatarColor: 'purple'};
  function stored(key, fallback) {
    try { return {...fallback, ...JSON.parse(localStorage.getItem(key) || '{}')}; }
    catch { return {...fallback}; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
  }
  const preferences = stored('portal_preferences', defaults);
  const account = stored(accountKey, accountDefaults);
  account.private = account.private === true;
  const originalAmounts = new WeakMap();
  const themeQuery = matchMedia('(prefers-color-scheme: dark)');

  function amounts() {
    root.dataset.privateAmounts = account.private ? 'hidden' : 'visible';
    document.querySelectorAll('[data-balance], [data-credited], [data-spent], [data-current-balance], [data-private-amount]').forEach(node => {
      const text = node.textContent;
      if (text !== '••••') originalAmounts.set(node, text);
      if (account.private && text.trim()) {
        node.textContent = '••••';
        node.setAttribute('aria-label', 'Importe oculto');
      } else if (!account.private && text === '••••' && originalAmounts.has(node)) {
        node.textContent = originalAmounts.get(node);
        node.removeAttribute('aria-label');
      }
    });
    document.querySelectorAll('[data-toggle-privacy]').forEach(button => {
      button.hidden = false;
      button.setAttribute('aria-pressed', String(account.private));
      button.setAttribute('aria-label', account.private ? 'Mostrar importes' : 'Ocultar importes');
    });
    root.dataset.privacyReady = 'true';
  }

  function avatars() {
    const symbols = {leaf: 'icon-leaf', sun: 'icon-sun', star: 'icon-star'};
    document.querySelectorAll('[data-personal-avatar]').forEach(avatar => {
      avatar.dataset.avatarColor = ['purple','lime','lavender'].includes(account.avatarColor) ? account.avatarColor : 'purple';
      avatar.replaceChildren();
      if (symbols[account.avatar]) {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        const use = document.createElementNS(svg.namespaceURI, 'use');
        svg.classList.add('ui-icon');
        use.setAttribute('href', '#' + symbols[account.avatar]);
        svg.append(use);
        avatar.append(svg);
      } else avatar.textContent = avatar.dataset.avatarInitial || '';
    });
  }
  function applyPreferences() {
    const theme = ['light','dark','system'].includes(preferences.theme) ? preferences.theme : 'light';
    root.dataset.theme = theme === 'dark' || (theme === 'system' && themeQuery.matches) ? 'dark' : 'light';
    root.dataset.contrast = preferences.contrast === true ? 'high' : 'normal';
    root.dataset.motionLevel = ['full','soft','none'].includes(preferences.motion) ? preferences.motion : 'full';
    avatars();
    amounts();
    document.dispatchEvent(new Event('portal:preferences-updated'));
  }
  themeQuery.addEventListener('change', applyPreferences);
  document.addEventListener('portal:amounts-updated', amounts);
  document.querySelectorAll('[data-toggle-privacy]').forEach(button => button.addEventListener('click', () => {
    account.private = !account.private;
    save(accountKey, account);
    amounts();
  }));
  const form = document.querySelector('[data-preferences-form]');
  if (form) {
    for (const [key, value] of Object.entries({...preferences, ...account})) {
      const field = form.elements.namedItem(key);
      if (!field) continue;
      if (field instanceof HTMLInputElement && field.type === 'checkbox') field.checked = value === true;
      else field.value = value;
    }
    form.addEventListener('submit', event => event.preventDefault());
    form.addEventListener('change', () => {
      preferences.theme = form.elements.theme.value;
      preferences.motion = form.elements.motion.value;
      preferences.contrast = form.elements.contrast.checked;
      account.private = form.elements.private.checked;
      account.avatar = form.elements.avatar.value;
      account.avatarColor = form.elements.avatarColor.value;
      const persisted = save('portal_preferences', preferences) && save(accountKey, account);
      applyPreferences();
      form.querySelector('[data-preferences-status]').textContent = persisted
        ? 'Preferencias guardadas en este navegador.' : 'Preferencias aplicadas. El navegador no permitió guardarlas.';
    });
  }
  applyPreferences();

  document.querySelectorAll('dialog [data-close-dialog]').forEach(button => {
    button.addEventListener('click', () => button.closest('dialog').close());
  });
  document.querySelectorAll('dialog.dialog-card').forEach(dialog => {
    dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      const box = dialog.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
    });
  });

  const search = document.querySelector('[data-action-search]');
  if (search) {
    const input = search.querySelector('[data-action-query]');
    const list = search.querySelector('[data-action-results]');
    function options() {
      const all = [...document.querySelectorAll('.desktop-nav a, .profile-options a, .notification-access, .topbar a')];
      return [...new Map(all.map(link => [link.href, {
        href: link.href, text: link.textContent.trim() || link.getAttribute('aria-label'),
      }])).values()].filter(item => item.text && new URL(item.href).origin === location.origin);
    }
    function results() {
      const query = input.value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
      list.replaceChildren();
      options().filter(item => item.text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().includes(query)).forEach(item => {
        const li = document.createElement('li');
        const link = document.createElement('a');
        link.href = item.href;
        link.textContent = item.text;
        li.append(link);
        list.append(li);
      });
      if (!list.children.length) {
        const li = document.createElement('li');
        li.textContent = 'No hay opciones que coincidan.';
        list.append(li);
      }
    }
    function openSearch() {
      if (search.open || document.querySelector('dialog[open]')) return;
      input.value = '';
      results();
      search.showModal();
      input.focus();
    }
    document.querySelectorAll('[data-open-actions]').forEach(button => {
      button.hidden = false;
      button.addEventListener('click', openSearch);
    });
    input.addEventListener('input', results);
    input.addEventListener('keydown', event => {
      if (event.key === 'ArrowDown') { event.preventDefault(); list.querySelector('a')?.focus(); }
      if (event.key === 'Enter' && list.querySelectorAll('a').length === 1) list.querySelector('a').click();
    });
    document.addEventListener('keydown', event => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault(); openSearch();
      }
    });
  }

  const drawer = document.querySelector('[data-movement-drawer]');
  if (drawer) {
    let endpoint = '';
    let sequence = 0;
    const loading = drawer.querySelector('[data-drawer-loading]');
    const error = drawer.querySelector('[data-drawer-error]');
    const content = drawer.querySelector('[data-drawer-content]');
    async function loadDetail() {
      const id = ++sequence;
      loading.hidden = false; error.hidden = true; content.hidden = true;
      const result = await window.Pluxee.request(endpoint);
      if (id !== sequence || !drawer.open) return;
      loading.hidden = true;
      if (!result.ok || !result.data) {
        drawer.querySelector('[data-drawer-error-text]').textContent = result.message || 'No fue posible consultar el movimiento.';
        drawer.querySelector('[data-drawer-retry]').hidden = result.code === 401 || result.code === 404;
        error.hidden = false;
        return;
      }
      const data = result.data;
      drawer.querySelector('[data-drawer-amount]').textContent = (data.kind === 'cargo' ? '− ' : '+ ') + window.Pluxee.money(data.amount);
      drawer.querySelector('[data-drawer-description]').textContent = data.description;
      const facts = drawer.querySelector('[data-drawer-facts]');
      facts.replaceChildren();
      [['Tipo',data.type],['Fecha',window.Pluxee.dateTime(data.date)],['Cuenta','Terminada en ' + data.account_suffix],
        ['Comercio',data.merchant],['Número de movimiento',data.id]].forEach(([label,value]) => {
        if (value === null) return;
        const group = document.createElement('div');
        const dt = document.createElement('dt');
        const dd = document.createElement('dd');
        dt.textContent = label; dd.textContent = value;
        group.append(dt,dd); facts.append(group);
      });
      for (const [selector,path] of [['[data-drawer-receipt]',data.receipt_url],['[data-drawer-pdf]',data.pdf_url]]) {
        const link = drawer.querySelector(selector);
        link.hidden = !path;
        if (path) link.href = path;
        else link.removeAttribute('href');
      }
      content.hidden = false;
      amounts();
    }
    document.addEventListener('click', event => {
      const trigger = event.target.closest('[data-movement-detail]');
      if (!trigger) return;
      const path = trigger.dataset.movementDetail;
      if (!/^\/api\/movimientos\/\d+\/detalle\/$/.test(path)) return;
      event.preventDefault();
      endpoint = path;
      drawer.showModal();
      loadDetail();
    });
    drawer.addEventListener('close', () => { sequence += 1; });
    drawer.querySelector('[data-drawer-retry]').addEventListener('click', loadDetail);
  }

  const tour = document.querySelector('[data-tour-dialog]');
  if (tour) {
    const admin = document.body.classList.contains('app-admin');
    const steps = admin ? [
      ['Revisa la actividad','Seguimiento reúne los indicadores y el estado de los servicios.'],
      ['Consulta la bitácora','Bitácora reúne los eventos registrados, sus filtros y la exportación CSV.'],
      ['Gestiona las cuentas','Usuarios permite editar datos, revisar movimientos y gestionar el acceso.'],
      ['Atiende los reportes','La bandeja de reportes reúne las consultas de los beneficiarios.'],
      ['Mantén el catálogo','Comercios permite crear, editar y activar los locales disponibles.'],
      ['Consulta los informes','Informes reúne los movimientos por periodo y su exportación.'],
      ['Ajusta los parámetros','Parámetros permite cambiar el abono inicial, los intentos de ingreso, la inactividad de la sesión y el máximo por compra.'],
      ['Personaliza el portal','Apariencia permite cambiar tema, avatar, contraste y movimiento.'],
    ] : [
      ['Consulta tu saldo','Inicio reúne el saldo, los accesos rápidos y el resumen de compras.'],
      ['Revisa antes de pagar','Pagar permite elegir el medio y revisar el importe antes de confirmar.'],
      ['Encuentra comercios','El catálogo permite buscar y guardar favoritos.'],
      ['Gestiona tu cuenta','Mi perfil reúne tarjeta, sesiones, reportes y preferencias visuales.'],
    ];
    let index = 0;
    const invite = document.querySelector('[data-tour-invite]');
    let seen = false;
    try { seen = localStorage.getItem(tourKey) === 'seen'; } catch {}
    if (invite) invite.hidden = seen;
    function finishTour() {
      try { localStorage.setItem(tourKey,'seen'); } catch {}
      if (invite) invite.hidden = true;
    }
    function renderStep() {
      tour.querySelector('[data-tour-progress]').textContent = `Paso ${index + 1} de ${steps.length}`;
      tour.querySelector('#tour-title').textContent = steps[index][0];
      tour.querySelector('[data-tour-description]').textContent = steps[index][1];
      tour.querySelector('[data-tour-prev]').disabled = index === 0;
      tour.querySelector('[data-tour-next]').textContent = index === steps.length - 1 ? 'Terminar' : 'Siguiente';
    }
    document.querySelectorAll('[data-start-tour]').forEach(button => button.addEventListener('click', () => {
      index = 0; renderStep(); tour.showModal();
    }));
    document.querySelector('[data-tour-dismiss]')?.addEventListener('click',finishTour);
    tour.addEventListener('close',finishTour);
    tour.querySelector('[data-tour-prev]').addEventListener('click', () => { index = Math.max(0,index-1); renderStep(); });
    tour.querySelector('[data-tour-next]').addEventListener('click', () => {
      if (index === steps.length-1) tour.close();
      else { index += 1; renderStep(); }
    });
  }
})();
