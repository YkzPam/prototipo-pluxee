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
  const queryStatus = app.querySelector('[data-query-status]');
  const queryBalanceButton = queryStatus?.querySelector('[data-query-retry="balance"]');
  const queryMovementsButton = queryStatus?.querySelector('[data-query-retry="movements"]');
  let balanceBusy = false;
  let lastConfirmed = null;
  let movementsBusy = false;
  let statusBusy = false;
  let statusTimer;
  let currentPage = 1;
  let totalPages = 1;
  const all = selector => [...app.querySelectorAll(selector)];
  const setText = (selector, value) => all(selector).forEach(el => { el.textContent = value; });
  const movementRetryButtons = all('[data-retry-movements]');
  const movementActions = all('[data-page-prev], [data-page-next], [data-movement-filters] button');
  const prev = app.querySelector('[data-page-prev]');
  const next = app.querySelector('[data-page-next]');
  const monthSelect = app.querySelector('[data-monthly-select]');

  function retryCountdown(buttons) {
    const labels = new Map();
    let timer;

    function clear() {
      clearTimeout(timer);
      for (const [button, label] of labels) {
        button.textContent = label;
        button.removeAttribute('aria-disabled');
        delete button.dataset.retryWaiting;
      }
      labels.clear();
    }

    function start(seconds, onReady) {
      if (api.isExpired() || !Number.isSafeInteger(seconds) || seconds <= 0) return false;
      const deadline = performance.now() + seconds * 1000;
      for (const button of buttons) {
        labels.set(button, button.textContent);
        button.setAttribute('aria-disabled', 'true');
        button.dataset.retryWaiting = 'true';
      }

      function tick() {
        const remaining = deadline - performance.now();
        if (remaining <= 0) {
          clear();
          onReady?.();
          return;
        }
        const secondsLeft = Math.ceil(remaining / 1000);
        for (const button of buttons) button.textContent = `Reintentar en ${secondsLeft} s`;
        timer = setTimeout(tick, remaining - (secondsLeft - 1) * 1000);
      }

      tick();
      return true;
    }

    return {start, clear, waiting: () => labels.size > 0};
  }

  const balanceRetry = retryCountdown([balanceButton, queryBalanceButton].filter(Boolean));
  const movementRetry = retryCountdown([...movementRetryButtons, queryMovementsButton].filter(Boolean));

  function updateMovementControls(waiting) {
    const disabled = waiting || api.isExpired();
    movementActions.forEach(button => { button.disabled = disabled; });
    if (prev) prev.disabled = disabled || currentPage <= 1;
    if (next) next.disabled = disabled || currentPage >= totalPages;
  }

  function readSnapshot(snapshot) {
    if (!snapshot || !Number.isFinite(snapshot.balance) || typeof snapshot.updated_at !== 'string'
        || !Number.isFinite(Date.parse(snapshot.updated_at))) return null;
    return snapshot;
  }

  let shownBalance = null;
  let countFrame = 0;

  function motionAllowed() {
    const root = document.documentElement;
    return root.dataset.motion !== 'off' && root.dataset.motionLevel !== 'none'
      && !matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  // El importe sube desde el valor mostrado antes; con importes ocultos o movimiento reducido se muestra directo.
  function countBalance(to) {
    cancelAnimationFrame(countFrame);
    const from = shownBalance ?? 0;
    shownBalance = to;
    const reading = balanceCard.querySelector('.balance-reading');
    const hidden = () => document.documentElement.dataset.privateAmounts === 'hidden';
    if (from === to || !motionAllowed() || hidden()) {
      setText('[data-balance]', api.money(to));
      return;
    }
    reading.setAttribute('aria-busy', 'true');
    const start = performance.now();
    const duration = 650;
    const step = now => {
      const progress = Math.min(1, (now - start) / duration);
      if (progress < 1 && !hidden()) {
        const eased = 1 - (1 - progress) ** 3;
        setText('[data-balance]', api.money(Math.round(from + (to - from) * eased)));
        countFrame = requestAnimationFrame(step);
        return;
      }
      setText('[data-balance]', api.money(to));
      reading.removeAttribute('aria-busy');
      amountsUpdated();
    };
    countFrame = requestAnimationFrame(step);
  }

  function showBalance(state, label, snapshot = null, message = '') {
    if (!balanceCard) return;
    balanceCard.dataset.balanceState = state;
    balanceCard.dataset.balanceEmpty = String(!snapshot);
    setText('[data-balance-heading]', label);
    if (state === 'current' && snapshot) countBalance(snapshot.balance);
    else {
      cancelAnimationFrame(countFrame);
      balanceCard.querySelector('.balance-reading').removeAttribute('aria-busy');
      setText('[data-balance]', snapshot ? api.money(snapshot.balance) : '—');
      if (snapshot) shownBalance = snapshot.balance;
    }

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
    amountsUpdated();
  }

  function showBalanceSummary(data = null) {
    setText('[data-current-balance]', data ? api.money(data.balance) : '—');
    setText('[data-credited]', data ? api.money(data.credited) : '—');
    setText('[data-spent]', data ? api.money(data.spent) : '—');
    amountsUpdated();
  }

  function errorBox(selector, message, show) {
    const box = app.querySelector(selector);
    if (!box) return;
    box.hidden = !show;
    const detail = box.querySelector('[data-error-message]');
    if (detail) detail.textContent = message;
  }

  function showQueryStatus(interrupted, snapshotAtRequest) {
    const balanceInterrupted = interrupted.includes('balance');
    const movementsInterrupted = interrupted.includes('movements');
    const visible = balanceInterrupted || movementsInterrupted;
    const notice = queryStatus.querySelector('[data-query-status-message]');
    const subject = balanceInterrupted && movementsInterrupted ? 'las consultas de saldo y movimientos'
      : balanceInterrupted ? 'la consulta de saldo' : 'la consulta de movimientos';
    const message = visible ? `Hay una interrupción simulada en ${subject}.` : '';
    if (notice.textContent !== message) {
      notice.textContent = message;
      setText('[data-query-status-announcement]', message || 'Se restablecieron los servicios de consulta.');
    }
    const focused = document.activeElement;
    queryBalanceButton.hidden = !balanceInterrupted;
    queryMovementsButton.hidden = !movementsInterrupted;
    queryStatus.hidden = !visible;
    if (focused === queryBalanceButton && !balanceInterrupted) balanceButton.focus({preventScroll: true});
    if (focused === queryMovementsButton && !movementsInterrupted) {
      app.querySelector('#recent-heading').focus();
    }
    if (balanceInterrupted && lastConfirmed === snapshotAtRequest && balanceCard.dataset.balanceState === 'current') {
      showBalance('stale', 'Saldo sin actualizar', lastConfirmed, 'El servicio de saldo está interrumpido en esta prueba.');
      balanceButton.textContent = 'Reintentar';
    }
  }

  function scheduleQueryStatusCheck() {
    clearTimeout(statusTimer);
    if (queryStatus && !queryStatus.hidden && !document.hidden && !api.isExpired()) {
      statusTimer = setTimeout(refreshQueryStatus, 15000);
    }
  }

  async function refreshQueryStatus() {
    if (!queryStatus || document.hidden || api.isExpired() || statusBusy) return;
    clearTimeout(statusTimer);
    statusBusy = true;
    const snapshotAtRequest = lastConfirmed;
    const result = await api.request(queryStatus.dataset.statusUrl);
    statusBusy = false;
    if (!api.isExpired() && result.ok && result.status === 'updated' && Array.isArray(result.data?.interrupted)) {
      showQueryStatus(result.data.interrupted, snapshotAtRequest);
    }
    scheduleQueryStatusCheck();
  }

  async function balance() {
    if (!balanceButton || balanceBusy || balanceRetry.waiting() || api.isExpired()) return;
    balanceBusy = true;
    // El mismo botón conserva el foco del teclado mientras espera la respuesta.
    balanceButton.setAttribute('aria-disabled', 'true');
    queryBalanceButton?.setAttribute('aria-disabled', 'true');
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
    queryBalanceButton?.removeAttribute('aria-disabled');
    balanceRetry.start(result.retryAfter);
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function privateMoney(tag, className, text) {
    const node = element(tag, className, text);
    node.setAttribute('data-private-amount', '');
    return node;
  }

  function detailTrigger(item, className) {
    const button = element('button', className);
    button.type = 'button';
    button.dataset.movementDetail = `/api/movimientos/${encodeURIComponent(item.id)}/detalle/`;
    return button;
  }

  const CATEGORY_ICONS = {
    cafe: 'icon-cafe', restaurant: 'icon-food', market: 'icon-cart', grocery: 'icon-shop',
    bakery: 'icon-bread', produce: 'icon-leaf', credit: 'icon-plus', other: 'icon-pay',
  };
  const CATEGORY_NAMES = {
    cafe: 'Cafetería', restaurant: 'Restaurante', market: 'Supermercado', grocery: 'Almacén',
    bakery: 'Panadería', produce: 'Verdulería', credit: 'Abono', other: 'Compra',
  };

  function categoryIcon(item) {
    const category = CATEGORY_ICONS[item.category] ? item.category : (item.kind === 'abono' ? 'credit' : 'other');
    const badge = element('span', 'category-badge category-' + category);
    badge.setAttribute('aria-hidden', 'true');
    badge.title = CATEGORY_NAMES[category];
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'ui-icon');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', '#' + CATEGORY_ICONS[category]);
    svg.append(use);
    badge.append(svg);
    return badge;
  }

  function amountsUpdated() {
    document.dispatchEvent(new CustomEvent('portal:amounts-updated'));
  }

  function recentRows(items) {
    const holder = app.querySelector('[data-recent-movements]');
    if (!holder) return;
    holder.replaceChildren();
    if (!items.length) {
      holder.append(emptyState('Sin movimientos. La cuenta aún no tiene operaciones registradas.', 'movements'));
      return;
    }
    items.slice(0, 3).forEach(item => {
      const row = detailTrigger(item, 'movement-row movement-recent-trigger');
      const credit = item.kind === 'abono';
      const icon = categoryIcon(item);
      const description = element('div', 'movement-description');
      description.append(element('strong', '', item.description), element('small', '', api.date(item.date)));
      row.append(icon, description, privateMoney('span', 'movement-money' + (credit ? ' credit' : ''), (credit ? '+ ' : '− ') + api.money(item.amount)));
      holder.append(row);
    });
    amountsUpdated();
  }

  function tableRows(items, dayTotals = {}) {
    const holder = app.querySelector('[data-movement-rows]');
    if (!holder) return;
    holder.replaceChildren();
    if (!items.length) {
      placeholder('Sin movimientos para los filtros seleccionados.', 'movements');
      return;
    }
    let previousDay = null;
    items.forEach(item => {
      const day = item.date.slice(0, 10);
      if (day !== previousDay) {
        const headingRow = element('tr', 'movement-day-row');
        headingRow.setAttribute('role', 'row');
        const headingCell = element('td');
        headingCell.colSpan = 4;
        headingCell.setAttribute('role', 'cell');
        const heading = element('h3', '', api.date(day));
        headingCell.append(heading);
        const totals = dayTotals[day];
        if (totals) {
          const summary = element('p', 'movement-day-total');
          if (totals.debit) summary.append(privateMoney('span', 'day-total-debit', 'Compras − ' + api.money(totals.debit)));
          if (totals.credit) summary.append(privateMoney('span', 'day-total-credit', 'Abonos + ' + api.money(totals.credit)));
          headingCell.append(summary);
        }
        headingRow.append(headingCell);
        holder.append(headingRow);
        previousDay = day;
      }
      const row = element('tr', 'movement-table-entry');
      row.setAttribute('role', 'row');
      const credit = item.kind === 'abono';
      const type = element('td', 'movement-entry-kind');
      const kindLabel = element('span', 'movement-kind-label' + (credit ? ' is-credit' : ''));
      kindLabel.append(categoryIcon(item), element('span', '', credit ? 'Abono' : 'Compra'));
      type.append(kindLabel);
      const description = element('td', 'movement-entry-description');
      const trigger = detailTrigger(item, 'movement-detail-trigger');
      trigger.append(element('span', '', item.description));
      description.append(trigger);
      const occurred = element('time', '', api.dateTime(item.date));
      occurred.dateTime = item.date;
      const date = element('td', 'movement-entry-date');
      date.append(occurred);
      const cells = [
        description,
        date,
        type,
        privateMoney('td', 'amount-cell movement-entry-amount movement-money' + (credit ? ' credit' : ''),
          (credit ? '+ ' : '− ') + api.money(item.amount)),
      ];
      cells.forEach(cell => cell.setAttribute('role', 'cell'));
      row.append(...cells);
      holder.append(row);
    });
    amountsUpdated();
  }

  function emptyState(message, theme) {
    const box = element('div', 'empty-state');
    const illustration = theme ? document.getElementById('empty-' + theme + '-art') : null;
    if (illustration) box.append(illustration.content.cloneNode(true));
    box.append(element('p', '', message));
    return box;
  }

  function placeholder(message, theme = null) {
    const recent = app.querySelector('[data-recent-movements]');
    if (recent) recent.replaceChildren(emptyState(message, theme));
    const holder = app.querySelector('[data-movement-rows]');
    if (holder) {
      const row = element('tr', 'movement-table-placeholder');
      row.setAttribute('role', 'row');
      const cell = element('td');
      cell.setAttribute('role', 'cell');
      cell.colSpan = 4;
      cell.append(emptyState(message, theme));
      row.append(cell);
      holder.replaceChildren(row);
    }
  }

  function showMonthly(state, data = null) {
    const summary = app.querySelector('[data-monthly-summary]');
    if (!summary) return;
    const ready = state === 'ready' && data !== null;
    const notice = summary.querySelector('[data-monthly-notice]');
    const period = summary.querySelector('[data-monthly-period]');
    const detail = summary.querySelector('[data-monthly-purchase-detail]');
    const purchase = ready ? data.latest_purchase : null;
    summary.dataset.uiState = state;
    summary.setAttribute('aria-busy', String(state === 'loading'));
    summary.querySelector('[data-monthly-values]').hidden = !ready;
    notice.hidden = ready;
    notice.classList.toggle('notice-error', state === 'error');
    notice.classList.toggle('notice-info', state !== 'error');
    period.hidden = !ready;
    period.textContent = ready ? data.period : '';
    if (ready && monthSelect && Array.isArray(data.periods)) {
      monthSelect.replaceChildren(...data.periods.map(period => {
        const option = element('option', '', period.label);
        option.value = period.value;
        return option;
      }));
      monthSelect.value = data.month;
    }
    summary.querySelector('[data-monthly-retry]').hidden = state !== 'error';
    setText('[data-monthly-status]', state === 'loading' ? 'Consultando el resumen…'
      : state === 'expired' ? 'Vuelve a ingresar para consultar el resumen.' : 'El resumen no está disponible. Puedes reintentar.');
    setText('[data-monthly-credit]', ready ? api.money(data.credited) : '');
    setText('[data-monthly-spent]', ready ? api.money(data.spent) : '');
    setText('[data-monthly-purchase]', ready ? (purchase ? purchase.description : 'Sin compras este mes') : '');
    detail.hidden = !purchase;
    detail.replaceChildren();
    if (purchase) detail.append(privateMoney('span', '', api.money(purchase.amount)),
      document.createTextNode(' · ' + api.date(purchase.date)));
    showWeekly(ready && Array.isArray(data.weekly) ? data.weekly : null);
    amountsUpdated();
  }

  function showWeekly(weeks) {
    const chart = app.querySelector('[data-weekly-chart]');
    if (!chart) return;
    chart.hidden = !weeks;
    const bars = chart.querySelector('[data-weekly-bars]');
    bars.replaceChildren();
    if (!weeks) return;
    const max = Math.max(1, ...weeks.map(week => week.amount));
    const total = weeks.reduce((sum, week) => sum + week.amount, 0);
    const today = new Date();
    const todayIso = [today.getFullYear(), String(today.getMonth() + 1).padStart(2, '0'), String(today.getDate()).padStart(2, '0')].join('-');
    weeks.forEach(week => {
      const item = element('li');
      if (week.amount && week.amount === max) item.classList.add('is-top-week');
      if (week.from_date <= todayIso && todayIso <= week.to_date) item.classList.add('is-current-week');
      item.style.setProperty('--week-share', String(Math.round(week.amount / max * 100)));
      const link = element('a', 'weekly-bar-link');
      const query = new URLSearchParams({desde: week.from_date, hasta: week.to_date, tipo: 'cargo'});
      link.href = '/movimientos/?' + query.toString();
      link.setAttribute('aria-label', `Días ${week.label}. Ver compras.`);
      const meter = element('meter');
      meter.min = 0;
      meter.max = max;
      meter.value = week.amount;
      meter.setAttribute('aria-hidden', 'true');
      const share = total ? Math.round(week.amount / total * 100) : 0;
      const label = element('span', 'weekly-bar-label', 'Días ' + week.label);
      if (item.classList.contains('is-current-week')) label.append(element('span', 'weekly-bar-tag', 'Esta semana'));
      link.append(label,
        meter, privateMoney('strong', 'weekly-bar-amount', api.money(week.amount)),
        element('span', 'weekly-bar-share', share + ' % del mes'));
      item.append(link);
      bars.append(item);
    });
  }

  async function movements(page = 1) {
    if (movementsBusy || movementRetry.waiting() || api.isExpired()) return;
    movementsBusy = true;
    if (monthSelect) monthSelect.disabled = true;
    app.dataset.movementsBusy = 'true';
    queryMovementsButton?.setAttribute('aria-disabled', 'true');
    const buttons = [...movementRetryButtons, ...movementActions];
    buttons.forEach(button => { button.disabled = true; });
    errorBox('[data-movements-error]', '', false);
    showMonthly('loading');
    placeholder('Consultando los registros…');
    setText('[data-movement-count]', 'Consultando movimientos…');
    setText('[data-movements-updated]', '');
    const pagination = app.querySelector('[data-pagination]');
    if (pagination) pagination.hidden = true;
    const params = new URLSearchParams();
    if (view === 'dashboard') {
      params.set('resumen', 'mensual');
      if (monthSelect?.value) params.set('mes', monthSelect.value);
    }
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
      if (view === 'dashboard') {
        recentRows(items);
        if (result.data.monthly) showMonthly('ready', result.data.monthly);
        else showMonthly('error');
      } else tableRows(items, result.data.day_totals || {});
      currentPage = result.data.page || 1;
      totalPages = result.data.pages || 1;
      if (form && currentPage !== page) {
        const url = new URL(location.href);
        if (currentPage === 1) url.searchParams.delete('page');
        else url.searchParams.set('page', currentPage);
        history.replaceState(history.state, '', url);
      }
      const total = result.data.total || 0;
      setText('[data-movement-count]', total === 1 ? '1 movimiento encontrado' : `${total} movimientos encontrados`);
      setText('[data-movements-updated]', result.updated_at ? 'Consulta: ' + api.dateTime(result.updated_at) : '');
      setText('[data-page-label]', `Página ${currentPage} de ${totalPages}`);
      if (pagination) pagination.hidden = totalPages <= 1;
    } else {
      showMonthly(api.isExpired() || result.code === 401 ? 'expired' : 'error');
      placeholder(result.code === 401 ? 'La sesión finalizó. Es necesario ingresar nuevamente.' : 'La consulta no se completó. No se muestra un historial vacío como resultado.', 'pending');
      setText('[data-movement-count]', result.code === 400 ? 'Revisar los filtros' : 'Consulta pendiente');
      if (result.code !== 401) errorBox('[data-movements-error]', result.message || 'No fue posible recuperar el historial. Se puede reintentar.', true);
    }
    movementsBusy = false;
    if (monthSelect) monthSelect.disabled = api.isExpired();
    delete app.dataset.movementsBusy;
    queryMovementsButton?.removeAttribute('aria-disabled');
    buttons.forEach(button => { button.disabled = api.isExpired(); });
    const waiting = movementRetry.start(result.retryAfter, () => updateMovementControls(false));
    updateMovementControls(waiting);
  }

  async function retryBalance() {
    if (balanceBusy || balanceRetry.waiting()) return;
    await balance();
    await refreshQueryStatus();
  }

  async function retryMovements() {
    if (movementsBusy || movementRetry.waiting()) return;
    await movements(currentPage);
    await refreshQueryStatus();
  }

  balanceButton?.addEventListener('click', retryBalance);
  queryBalanceButton?.addEventListener('click', retryBalance);
  queryMovementsButton?.addEventListener('click', retryMovements);
  movementRetryButtons.forEach(button => button.addEventListener('click', retryMovements));
  if (queryStatus) {
    window.addEventListener('focus', refreshQueryStatus);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) clearTimeout(statusTimer);
      else refreshQueryStatus();
    });
    scheduleQueryStatusCheck();
  }
  const form = app.querySelector('[data-movement-filters]');
  let initialPage = 1;
  if (form) {
    const saved = new URLSearchParams(location.search);
    const filterPanel = app.querySelector('[data-movement-filter-panel]');
    const mobile = window.matchMedia('(max-width: 700px)');
    if (filterPanel) {
      const hasFilters = saved.has('desde') || saved.has('hasta') || ['abono', 'cargo'].includes(saved.get('tipo'));
      filterPanel.open = !mobile.matches || hasFilters;
      mobile.addEventListener('change', event => {
        if (!event.matches) filterPanel.open = true;
      });
    }
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
  if (prev) prev.addEventListener('click', () => movements(Math.max(1, currentPage - 1)));
  if (next) next.addEventListener('click', () => movements(Math.min(totalPages, currentPage + 1)));
  document.addEventListener('prototype:expired', () => {
    clearTimeout(statusTimer);
    balanceRetry.clear();
    movementRetry.clear();
    if (queryStatus) queryStatus.hidden = true;
    lastConfirmed = null;
    showBalance('expired', 'Sesión finalizada', null, 'Vuelve a ingresar para consultar el saldo.');
    showBalanceSummary();
    showMonthly('expired');
    if (balanceButton) balanceButton.textContent = 'Actualizar saldo';
    placeholder('La sesión finalizó. Es necesario ingresar nuevamente.');
    setText('[data-movement-count]', 'Acceso finalizado');
    all('button').forEach(button => { button.disabled = true; });
  });
  if (view === 'dashboard' || view === 'balance') balance();
  if (view === 'dashboard' || view === 'movements') movements(initialPage);
  monthSelect?.addEventListener('change', () => movements(1));
})();
