(() => {
  'use strict';
  const forms = [...document.querySelectorAll('[data-notification-form]')];
  if (!forms.length) return;
  let submitting = false;
  const feedback = document.querySelector('[data-notification-feedback]');

  function markItem(item) {
    if (!item) return;
    item.classList.remove('notification-unread');
    const status = item.querySelector('[data-notification-read-status]');
    if (status) status.textContent = 'Leída';
    const form = item.querySelector('[data-notification-form]');
    if (form) form.hidden = true;
  }

  for (const form of forms) {
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (submitting) return;
      submitting = true;
      const buttons = forms.flatMap(item => [...item.querySelectorAll('button')]);
      buttons.forEach(button => { button.disabled = true; });
      try {
        const response = await fetch(form.action, {
          method: 'POST', body: new FormData(form), credentials: 'same-origin',
          headers: { Accept: 'application/json' },
        });
        if (response.redirected) {
          window.location.assign(response.url);
          return;
        }
        if (!response.ok) throw new Error('request');
        const result = await response.json();
        if (!Number.isSafeInteger(result.unread_count) || result.unread_count < 0) throw new Error('response');
        const count = result.unread_count;
        document.querySelectorAll('[data-notification-count]').forEach(badge => {
          badge.textContent = count;
          badge.hidden = count === 0;
        });
        const access = document.querySelector('[data-notification-access]');
        if (access) access.setAttribute('aria-label', count ? `Notificaciones, ${count} sin leer` : 'Notificaciones');
        const summary = document.querySelector('[data-notification-summary]');
        if (summary) summary.textContent = `${count} sin leer`;
        if (form.hasAttribute('data-read-all')) {
          document.querySelectorAll('[data-notification-item]').forEach(markItem);
          form.hidden = true;
        } else {
          markItem(form.closest('[data-notification-item]'));
          if (count === 0) {
            const readAll = document.querySelector('[data-read-all]');
            if (readAll) readAll.hidden = true;
          }
        }
        if (feedback) feedback.textContent = 'Se actualizó el estado de lectura.';
      } catch {
        if (feedback) {
          feedback.classList.remove('sr-only');
          feedback.classList.add('notice', 'notice-error');
          feedback.textContent = 'No fue posible marcar la notificación. Intenta nuevamente.';
        }
      } finally {
        submitting = false;
        buttons.forEach(button => { button.disabled = false; });
      }
    });
  }
})();
