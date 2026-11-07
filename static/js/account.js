(() => {
  'use strict';
  const app = document.querySelector('[data-account]');
  if (!app || !window.Pluxee) return;
  const api = window.Pluxee;
  const accountId = encodeURIComponent(app.dataset.account);
  const view = app.dataset.view;
  const base = `/api/cuentas/${accountId}/`;
  const balanceCard = app.querySelector('[data-balance-card]');
  const balanceButton = balanceCard?.querySelector('[data-refresh-balance]');
  let balanceBusy = false;
  let lastConfirmed = null;
  let movementsBusy = false;
  let currentPage = 1;
  let totalPages = 1;
  const all = selector => [...app.querySelectorAll(selector)];
  const setText = (selector, value) => all(selector).forEach(el => { el.textContent = value; });

  function readSnapshot(snapshot) {
    if (!snapshot || !Number.isFinite(snapshot.balance) || typeof snapshot.updated_at !== 'string'
        || !Number.isFinite(Date.parse(snapshot.updated_at))) return null;
    return snapshot;
  }

  function showBalance(state, label, snapshot = null, message = '') {
    if (!balanceCard) return;
    balanceCard.dataset.balanceState = state;
    setText('[data-balance-heading]', label);
    setText('[data-balance]', snapshot ? api.money(snapshot.balance) : '—');

    const reference = balanceCard.querySelector('[data-balance-reference]');
    const date = balanceCard.querySelector('[data-balance-time]');
    if (snapshot) {
      setText('[data-balance-reference-label]', state === 'current' ? 'Confirmado el' : 'Último saldo confirmado el');
      date.dateTime = snapshot.updated_at;
      date.textContent = api.dateTime(snapshot.updated_at);
    } else {
      date.removeAttribute('datetime');
      date.textContent = '';
    }
    reference.hidden = !snapshot;

    const detail = balanceCard.querySelector('[data-state-detail]');
    detail.textContent = message;
    detail.hidden = !message;
  }

  function showBalanceSummary(data = null) {
    setText('[data-current-balance]', data ? api.money(data.balance) : '—');
    setText('[data-credited]', data ? api.money(data.credited) : '—');
    setText('[data-spent]', data ? api.money(data.spent) : '—');
  }

  function errorBox(selector, message, show) {
    const box = app.querySelector(selector);
    if (!box) return;
    box.hidden = !show;
    const detail = box.querySelector('[data-error-message]');
    if (detail) detail.textContent = message;
  }

  async function balance() {
    if (!balanceButton || balanceBusy || api.isExpired()) return;
    balanceBusy = true;
    // El mismo botón conserva el foco del teclado mientras espera la respuesta.
    balanceButton.setAttribute('aria-disabled', 'true');
    balanceButton.textContent = 'Consultando…';
    showBalance('loading', lastConfirmed ? 'Saldo sin actualizar' : 'Consultando saldo…', lastConfirmed);
    showBalanceSummary();
    const result = await api.request(base + 'saldo/');
    const expired = result.code === 401 || api.isExpired();
    const denied = result.code === 403;
    const confirmed = readSnapshot({balance: result.data?.balance, updated_at: result.updated_at});
    if (result.ok && result.status === 'updated' && confirmed && !expired) {
      lastConfirmed = confirmed;
      showBalance('current', 'Saldo actualizado', confirmed);
      showBalanceSummary(result.data);
      balanceButton.textContent = 'Actualizar saldo';
    } else {
      // Ante una respuesta del servidor se usa solo la copia de la sesión actual.
      // Si falla la conexión completa, sigue disponible la copia de esta página.
      if (expired || denied) lastConfirmed = null;
      else if (result.code !== 0) lastConfirmed = readSnapshot(result.last_confirmed);
      if (expired || denied) {
        showBalance(expired ? 'expired' : 'denied', expired ? 'Sesión finalizada' : 'Acceso no autorizado',
          null, result.message || 'No se pudo consultar el saldo.');
        balanceButton.textContent = 'Actualizar saldo';
      } else {
        showBalance(lastConfirmed ? 'stale' : 'unavailable',
          lastConfirmed ? 'Saldo sin actualizar' : 'Saldo no disponible', lastConfirmed,
          result.message || 'No se pudo actualizar el saldo.');
        balanceButton.textContent = 'Reintentar';
      }
    }
    balanceBusy = false;
    balanceButton.disabled = expired || denied;
    balanceButton.removeAttribute('aria-disabled');
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
    if (form) new FormData(form).forEach((value, key) => {
      if (value && (key !== 'tipo' || value !== 'todos')) params.set(key, value);
    });
    params.set('page', page);
    if (form) {
      const url = new URL(location.href);
      url.search = params.toString();
      if (page === 1) url.searchParams.delete('page');
      if (url.href !== location.href) history.replaceState(history.state, '', url);
    }
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

  balanceButton?.addEventListener('click', balance);
  all('[data-retry-movements]').forEach(button => button.addEventListener('click', () => movements(currentPage)));
  const form = app.querySelector('[data-movement-filters]');
  let initialPage = 1;
  if (form) {
    const saved = new URLSearchParams(location.search);
    for (const name of ['desde', 'hasta', 'tipo']) {
      const field = form.elements.namedItem(name);
      const value = saved.get(name);
      if (field && value && (name !== 'tipo' || ['abono', 'cargo', 'todos'].includes(value))) field.value = value;
    }
    const page = Number(saved.get('page'));
    if (Number.isInteger(page) && page >= 1 && page <= 100000) initialPage = page;
    form.addEventListener('submit', event => { event.preventDefault(); movements(1); });
    form.addEventListener('reset', () => { requestAnimationFrame(() => movements(1)); });
  }
  const prev = app.querySelector('[data-page-prev]');
  const next = app.querySelector('[data-page-next]');
  if (prev) prev.addEventListener('click', () => movements(Math.max(1, currentPage - 1)));
  if (next) next.addEventListener('click', () => movements(Math.min(totalPages, currentPage + 1)));
  document.addEventListener('prototype:expired', () => {
    lastConfirmed = null;
    showBalance('expired', 'Sesión finalizada', null, 'Vuelve a ingresar para consultar el saldo.');
    showBalanceSummary();
    if (balanceButton) balanceButton.textContent = 'Actualizar saldo';
    placeholder('La sesión finalizó. Es necesario ingresar nuevamente.');
    setText('[data-movement-count]', 'Acceso finalizado');
    all('button').forEach(button => { button.disabled = true; });
  });
  if (view === 'dashboard' || view === 'balance') balance();
  if (view === 'dashboard' || view === 'movements') movements(initialPage);
})();
