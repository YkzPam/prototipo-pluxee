/* Las operaciones protegidas se autorizan en el servidor. No se guardan credenciales en el navegador. */
(() => {
  'use strict';
  const money = new Intl.NumberFormat('es-CL', {style: 'currency', currency: 'CLP', maximumFractionDigits: 0});
  const date = new Intl.DateTimeFormat('es-CL', {day: '2-digit', month: 'short', year: 'numeric'});
  const dateTime = new Intl.DateTimeFormat('es-CL', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit'});
  let expired = false;
  const warning = document.querySelector('[data-session-warning]');
  const announcer = document.querySelector('[data-session-announcer]');
  const warningTitle = warning?.querySelector('[data-session-warning-title]');
  const warningMessage = warning?.querySelector('[data-session-warning-message]');
  const continueButton = warning?.querySelector('[data-session-continue]');
  let clock;
  let timer;
  let inFlight = false;
  let checking = false;
  let lastSent = performance.now();

  function expire(message) {
    if (expired) return;
    expired = true;
    clearTimeout(timer);
    if (warning) warning.hidden = true;
    const alert = document.querySelector('[data-session-alert]');
    if (alert) {
      alert.hidden = false;
      alert.querySelector('[data-session-message]').textContent = message || 'La sesión venció. Es necesario ingresar nuevamente para continuar.';
      const link = alert.querySelector('a');
      const target = new URL(link.href);
      target.searchParams.set('next', location.pathname + location.search);
      link.href = target.href;
      alert.scrollIntoView({block: 'start', behavior: 'auto'});
      if (!document.hidden) link.focus({preventScroll: true});
    }
    document.dispatchEvent(new CustomEvent('prototype:expired'));
  }

  function remaining() {
    return Math.min(clock.idle, clock.absolute) - clock.now - (performance.now() - clock.received);
  }

  function receiveClock(value) {
    if (!warning || expired || !value) return false;
    let next;
    try { next = JSON.parse(value); } catch { return false; }
    if (!next || !['now', 'idle', 'absolute', 'warning'].every(key => Number.isFinite(next[key]))) return false;
    if (!clock || next.now >= clock.now) {
      clock = {...next, received: performance.now()};
      updateWarning();
    }
    return true;
  }

  function describeWarning(message, title = 'La sesión está por vencer') {
    if (warningMessage.textContent === message && warningTitle.textContent === title) return;
    warningTitle.textContent = title;
    warningMessage.textContent = message;
    announcer.textContent = title + '. ' + message;
  }

  async function checkExpiry() {
    if (checking) return;
    checking = true;
    // Esta consulta comprueba el vencimiento sin contar como actividad.
    const result = await request(warning.dataset.activityUrl);
    checking = false;
    if (expired || document.hidden) return;
    if (result.ok && result.sessionClock && remaining() > 0) {
      updateWarning();
    } else {
      warning.hidden = false;
      continueButton.hidden = true;
      describeWarning('Se volverá a comprobar cuando se recupere la conexión.', 'No se pudo comprobar la sesión');
      timer = setTimeout(updateWarning, 5000);
    }
  }

  function updateWarning() {
    clearTimeout(timer);
    if (!clock || expired || document.hidden) return;
    const timeLeft = remaining();
    if (timeLeft <= 0) {
      if (inFlight) timer = setTimeout(updateWarning, 250);
      else checkExpiry();
      return;
    }
    warning.hidden = timeLeft > clock.warning;
    if (!warning.hidden) {
      const absoluteLimit = clock.absolute <= clock.idle;
      continueButton.hidden = absoluteLimit;
      const message = absoluteLimit
        ? 'Se acerca el límite de duración. Cuando venza, vuelve a ingresar para continuar.'
        : 'Si sigues usando el prototipo, confirma para continuar con la sesión.';
      describeWarning(message);
    } else {
      warningMessage.textContent = '';
      announcer.textContent = '';
    }
    timer = setTimeout(updateWarning, Math.max(50, warning.hidden ? timeLeft - clock.warning : timeLeft));
  }

  async function request(url, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    const headers = new Headers(options.headers || {});
    headers.set('Accept', 'application/json');
    if (options.method && options.method.toUpperCase() !== 'GET') {
      const token = document.querySelector('input[name="csrfmiddlewaretoken"]');
      if (token) headers.set('X-CSRFToken', token.value);
    }
    try {
      const response = await fetch(url, {...options, headers, credentials: 'same-origin', cache: 'no-store', signal: controller.signal});
      let payload;
      try { payload = await response.json(); }
      catch { payload = {status: 'error', message: 'El servidor no entregó una respuesta válida. La consulta no se ha actualizado.'}; }
      if (response.status === 401 || payload.status === 'expired') expire(payload.message);
      const sessionClock = receiveClock(response.headers.get('X-Session-Clock'));
      const retryAfter = [429, 503].includes(response.status) ? Number(response.headers.get('Retry-After')) : 0;
      return {ok: response.ok, code: response.status, ...payload, sessionClock, retryAfter};
    } catch {
      return {ok: false, code: 0, status: 'pending', message: 'No fue posible conectar con el servidor. La consulta sigue pendiente; se puede reintentar cuando vuelva la conexión.'};
    } finally {
      clearTimeout(timeout);
    }
  }

  window.Pluxee = {
    request,
    money: value => Number.isFinite(Number(value)) ? money.format(Number(value)) : '—',
    date: value => { const parsed = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? value + 'T12:00:00' : value); return Number.isNaN(parsed.getTime()) ? 'Fecha no disponible' : date.format(parsed); },
    dateTime: value => { const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? '' : dateTime.format(parsed); },
    isExpired: () => expired
  };

  if (!warning) return;
  receiveClock(warning.dataset.clock);
  async function activity(event, explicit = false) {
    if (!event.isTrusted || expired || inFlight || document.hidden) return;
    if (!explicit && (event.target === continueButton || performance.now() - lastSent < 30000)) return;
    lastSent = performance.now();
    inFlight = true;
    const result = await request(warning.dataset.activityUrl, {method: 'POST'});
    inFlight = false;
    if (explicit && !expired) {
      if (!result.ok) describeWarning('No se pudo confirmar la actividad. Puedes intentarlo de nuevo mientras la sesión siga vigente.');
      else if (warning.hidden) {
        announcer.textContent = 'La sesión continúa vigente.';
        document.getElementById('contenido')?.focus({preventScroll: true});
      }
    }
  }
  // No existe un temporizador que renueve la sesión de una persona ausente.
  ['pointerdown', 'keydown', 'scroll', 'touchstart'].forEach(type => document.addEventListener(type, activity, {passive: true}));
  continueButton.addEventListener('click', event => activity(event, true));
  document.addEventListener('visibilitychange', updateWarning);
})();
