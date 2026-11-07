/* Las operaciones protegidas se autorizan en el servidor. No se guardan credenciales en el navegador. */
(() => {
  'use strict';
  const money = new Intl.NumberFormat('es-CL', {style: 'currency', currency: 'CLP', maximumFractionDigits: 0});
  const date = new Intl.DateTimeFormat('es-CL', {day: '2-digit', month: 'short', year: 'numeric'});
  const dateTime = new Intl.DateTimeFormat('es-CL', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit'});
  let expired = false;

  function expire(message) {
    if (expired) return;
    expired = true;
    const alert = document.querySelector('[data-session-alert]');
    if (alert) {
      alert.hidden = false;
      alert.querySelector('[data-session-message]').textContent = message || 'La sesión venció. Es necesario ingresar nuevamente para continuar.';
      alert.scrollIntoView({block: 'start', behavior: 'auto'});
    }
    document.dispatchEvent(new CustomEvent('prototype:expired'));
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
      return {ok: response.ok, code: response.status, ...payload};
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

  if (document.body.dataset.authenticated !== 'true') return;
  let lastSent = Date.now();
  let inFlight = false;
  async function activity(event) {
    if (!event.isTrusted || expired || inFlight || document.hidden || Date.now() - lastSent < 30000) return;
    lastSent = Date.now();
    inFlight = true;
    await request('/api/sesion/actividad/', {method: 'POST'});
    inFlight = false;
  }
  // No existe un temporizador que renueve la sesión de una persona ausente.
  ['pointerdown', 'keydown', 'scroll', 'touchstart'].forEach(type => document.addEventListener(type, activity, {passive: true}));
})();
