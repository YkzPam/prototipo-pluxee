(() => {
  'use strict';
  const app = document.querySelector('[data-account]');
  if (!app || !window.Pluxee) return;
  const api = window.Pluxee;
  const accountId = encodeURIComponent(app.dataset.account);
  const view = app.dataset.view;
  const base = `/api/cuentas/${accountId}/`;
  let balanceBusy = false;
  let movementsBusy = false;
  let currentPage = 1;
  let totalPages = 1;
  const all = selector => [...app.querySelectorAll(selector)];
  const setText = (selector, value) => all(selector).forEach(el => { el.textContent = value; });

  function clearBalance() {
    ['[data-balance]', '[data-credited]', '[data-spent]'].forEach(selector => setText(selector, '—'));
  }

  function errorBox(selector, message, show) {
    const box = app.querySelector(selector);
    if (!box) return;
    box.hidden = !show;
    const detail = box.querySelector('[data-error-message]');
    if (detail) detail.textContent = message;
  }

  async function balance() {
    if (balanceBusy || api.isExpired()) return;
    balanceBusy = true;
    const buttons = all('[data-refresh-balance], [data-retry-balance]');
    buttons.forEach(button => { button.disabled = true; });
    clearBalance();
    setText('[data-state-label]', 'Consultando información…');
    setText('[data-state-detail]', 'Se está comprobando el saldo de esta cuenta.');
    setText('[data-updated]', '');
    errorBox('[data-balance-error]', '', false);
    const result = await api.request(base + 'saldo/');
    const label = app.querySelector('[data-state-label]');
    if (result.ok && result.status === 'updated' && result.data && !api.isExpired()) {
      setText('[data-balance]', api.money(result.data.balance));
      setText('[data-credited]', api.money(result.data.credited));
      setText('[data-spent]', api.money(result.data.spent));
      setText('[data-state-label]', 'Información actualizada');
      setText('[data-state-detail]', result.message || 'La consulta terminó correctamente. El monto corresponde a los registros de prueba.');
      setText('[data-updated]', result.updated_at ? 'Última consulta: ' + api.dateTime(result.updated_at) : '');
      if (label) label.classList.remove('pending');
    } else {
      clearBalance();
      setText('[data-state-label]', result.code === 401 ? 'Sesión finalizada' : result.code === 403 ? 'Acceso no autorizado' : 'Consulta pendiente');
      setText('[data-state-detail]', result.message || 'No se obtuvo un saldo actualizado.');
      if (label) label.classList.add('pending');
      if (result.code !== 401) errorBox('[data-balance-error]', result.message || 'La consulta sigue pendiente. Se puede reintentar.', true);
    }
    balanceBusy = false;
    buttons.forEach(button => { button.disabled = api.isExpired(); });
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function recentRows(items) {
    const holder = app.querySelector('[data-recent-movements]');
    if (!holder) return;
    holder.replaceChildren();
    if (!items.length) {
      holder.append(element('p', 'empty-state', 'Sin movimientos. La cuenta aún no tiene operaciones registradas.'));
      return;
    }
    items.slice(0, 3).forEach(item => {
      const row = element('div', 'movement-row');
      const credit = item.kind === 'abono';
      const icon = element('span', 'movement-symbol' + (credit ? ' credit' : ''), credit ? '↓' : '↑');
      icon.setAttribute('aria-hidden', 'true');
      const description = element('div', 'movement-description');
      description.append(element('strong', '', item.description), element('small', '', api.date(item.date)));
      row.append(icon, description, element('span', 'movement-money' + (credit ? ' credit' : ''), (credit ? '+ ' : '− ') + api.money(item.amount)));
      holder.append(row);
    });
  }

  function tableRows(items) {
    const holder = app.querySelector('[data-movement-rows]');
    if (!holder) return;
    holder.replaceChildren();
    if (!items.length) {
      placeholder('Sin movimientos para los filtros seleccionados.');
      return;
    }
    items.forEach(item => {
      const row = element('tr');
      const credit = item.kind === 'abono';
      const kind = element('td');
      kind.append(element('span', 'status-badge ' + (credit ? 'status-success' : 'status-neutral'), credit ? 'Abono' : 'Cargo'));
      row.append(element('td', '', item.description), element('td', 'nowrap', api.date(item.date)), kind, element('td', 'amount-cell movement-money' + (credit ? ' credit' : ''), (credit ? '+ ' : '− ') + api.money(item.amount)));
      holder.append(row);
    });
  }

  function placeholder(message) {
    const recent = app.querySelector('[data-recent-movements]');
    if (recent) recent.replaceChildren(element('p', 'empty-state', message));
    const holder = app.querySelector('[data-movement-rows]');
    if (holder) {
      const row = element('tr');
      const cell = element('td');
      cell.colSpan = 4;
      cell.append(element('div', 'empty-state', message));
      row.append(cell);
      holder.replaceChildren(row);
    }
  }

  async function movements(page = 1) {
    if (movementsBusy || api.isExpired()) return;
    movementsBusy = true;
    const buttons = all('[data-retry-movements], [data-page-prev], [data-page-next], [data-movement-filters] button');
    buttons.forEach(button => { button.disabled = true; });
    errorBox('[data-movements-error]', '', false);
    placeholder('Consultando los registros…');
    setText('[data-movement-count]', 'Consultando movimientos…');
    setText('[data-movements-updated]', '');
    const pagination = app.querySelector('[data-pagination]');
    if (pagination) pagination.hidden = true;
    const params = new URLSearchParams();
    const form = app.querySelector('[data-movement-filters]');
    if (form) new FormData(form).forEach((value, key) => { if (value) params.set(key, value); });
    params.set('page', page);
    const result = await api.request(base + 'movimientos/?' + params.toString());
    if (result.ok && result.status === 'updated' && result.data && !api.isExpired()) {
      const items = Array.isArray(result.data.items) ? result.data.items : [];
      if (view === 'dashboard') recentRows(items); else tableRows(items);
      currentPage = result.data.page || 1;
      totalPages = result.data.pages || 1;
      const total = result.data.total || 0;
      setText('[data-movement-count]', total === 1 ? '1 movimiento encontrado' : `${total} movimientos encontrados`);
      setText('[data-movements-updated]', result.updated_at ? 'Consulta: ' + api.dateTime(result.updated_at) : '');
      setText('[data-page-label]', `Página ${currentPage} de ${totalPages}`);
      if (pagination) pagination.hidden = totalPages <= 1;
    } else {
      placeholder(result.code === 401 ? 'La sesión finalizó. Es necesario ingresar nuevamente.' : 'La consulta no se completó. No se muestra un historial vacío como resultado.');
      setText('[data-movement-count]', result.code === 400 ? 'Revisar los filtros' : 'Consulta pendiente');
      if (result.code !== 401) errorBox('[data-movements-error]', result.message || 'No fue posible recuperar el historial. Se puede reintentar.', true);
    }
    movementsBusy = false;
    buttons.forEach(button => { button.disabled = api.isExpired(); });
    const prev = app.querySelector('[data-page-prev]');
    const next = app.querySelector('[data-page-next]');
    if (prev) prev.disabled = api.isExpired() || currentPage <= 1;
    if (next) next.disabled = api.isExpired() || currentPage >= totalPages;
  }

  all('[data-refresh-balance], [data-retry-balance]').forEach(button => button.addEventListener('click', balance));
  all('[data-retry-movements]').forEach(button => button.addEventListener('click', () => movements(currentPage)));
  const form = app.querySelector('[data-movement-filters]');
  if (form) {
    form.addEventListener('submit', event => { event.preventDefault(); movements(1); });
    form.addEventListener('reset', () => { requestAnimationFrame(() => movements(1)); });
  }
  const prev = app.querySelector('[data-page-prev]');
  const next = app.querySelector('[data-page-next]');
  if (prev) prev.addEventListener('click', () => movements(Math.max(1, currentPage - 1)));
  if (next) next.addEventListener('click', () => movements(Math.min(totalPages, currentPage + 1)));
  document.addEventListener('prototype:expired', () => {
    clearBalance();
    placeholder('La sesión finalizó. Es necesario ingresar nuevamente.');
    setText('[data-state-label]', 'Sesión finalizada');
    setText('[data-state-detail]', 'Es necesario volver a ingresar para consultar información.');
    setText('[data-updated]', '');
    setText('[data-movement-count]', 'Acceso finalizado');
    all('button').forEach(button => { button.disabled = true; });
  });
  if (view === 'dashboard' || view === 'balance') balance();
  if (view === 'dashboard' || view === 'movements') movements();
})();
