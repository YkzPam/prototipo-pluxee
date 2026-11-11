(() => {
  'use strict';
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const storageKey = 'portal_motion';
  const toggle = document.querySelector('[data-motion-toggle]');
  let paused = false;
  try { paused = localStorage.getItem(storageKey) === 'off'; } catch {}

  function motionAllowed() {
    return !paused && !reduced.matches && document.documentElement.dataset.motionLevel !== 'none';
  }

  function applyPreference() {
    document.documentElement.dataset.motion = motionAllowed() ? 'on' : 'off';
    if (toggle) {
      toggle.hidden = false;
      toggle.disabled = reduced.matches || document.documentElement.dataset.motionLevel === 'none';
      toggle.textContent = reduced.matches || document.documentElement.dataset.motionLevel === 'none' ? 'Movimiento reducido'
        : paused ? 'Activar animaciones' : 'Pausar animaciones';
      toggle.setAttribute('aria-pressed', String(paused || reduced.matches));
    }
    if (!motionAllowed()) document.getAnimations().forEach(animation => animation.cancel());
  }
  applyPreference();
  reduced.addEventListener('change', applyPreference);
  document.addEventListener('portal:preferences-updated', applyPreference);
  toggle?.addEventListener('click', () => {
    paused = !paused;
    try { localStorage.setItem(storageKey, paused ? 'off' : 'on'); } catch {}
    applyPreference();
  });

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        observer.unobserve(entry.target);
        if (motionAllowed()) entry.target.animate([
          {opacity: .6, translate: '0 13px'}, {opacity: 1, translate: '0 0'},
        ], {duration: 360, easing: 'cubic-bezier(.2,.7,.3,1)'});
      });
    }, {threshold: .08});
    document.querySelectorAll('.page-content :is(.surface, .balance-card, .payment-methods, .benefit-card-art)').forEach(card => {
      if (!card.parentElement.closest('.surface')) observer.observe(card);
    });
  }

  document.querySelectorAll('[data-tilt-card]').forEach(card => {
    let currentAnimation;
    let frame;
    let latest;
    function orient(transform) {
      currentAnimation?.cancel();
      currentAnimation = card.animate({transform}, {
        duration: 180, fill: 'forwards', easing: 'ease-out',
      });
    }
    card.addEventListener('pointermove', event => {
      if (!motionAllowed() || event.pointerType !== 'mouse') return;
      latest = event;
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = null;
        const box = card.getBoundingClientRect();
        const x = Math.max(-1, Math.min(1, (latest.clientX - box.left) / box.width * 2 - 1));
        const y = Math.max(-1, Math.min(1, (latest.clientY - box.top) / box.height * 2 - 1));
        const intensity = document.documentElement.dataset.motionLevel === 'soft' ? .4 : 1;
        orient(`perspective(800px) rotateX(${-y * 5 * intensity}deg) rotateY(${x * 7 * intensity}deg) translateY(-3px)`);
      });
    });
    card.addEventListener('pointerleave', () => {
      if (frame) cancelAnimationFrame(frame);
      frame = null;
      if (motionAllowed()) orient('perspective(800px) rotateX(0) rotateY(0) translateY(0)');
      else currentAnimation?.cancel();
    });
  });

  // Marcar un favorito recarga Comercios: se conserva la posición y se destaca el corazón cambiado.
  const favoriteKey = 'portal_favorite_return';
  try {
    const saved = JSON.parse(sessionStorage.getItem(favoriteKey) || 'null');
    sessionStorage.removeItem(favoriteKey);
    if (saved && saved.path === location.pathname && Number.isFinite(saved.scroll)) {
      window.scrollTo({top: saved.scroll, behavior: 'instant'});
      const form = [...document.querySelectorAll('form')].find(item => new URL(item.action).pathname === saved.action);
      const button = form?.querySelector('.favorite-button');
      if (button && motionAllowed()) {
        button.classList.add('just-toggled');
        button.addEventListener('animationend', () => button.classList.remove('just-toggled'), {once: true});
      }
    }
  } catch {}

  document.addEventListener('submit', event => {
    if (event.defaultPrevented || !event.submitter) return;
    event.target.setAttribute('aria-busy', 'true');
    event.submitter.classList.add('is-submitting');
    if (event.submitter.classList.contains('favorite-button')) {
      try {
        sessionStorage.setItem(favoriteKey, JSON.stringify({
          path: location.pathname, scroll: window.scrollY, action: new URL(event.target.action).pathname,
        }));
      } catch {}
    }
  });
  window.addEventListener('pageshow', () => {
    document.querySelectorAll('form[aria-busy]').forEach(form => form.removeAttribute('aria-busy'));
    document.querySelectorAll('.is-submitting').forEach(button => button.classList.remove('is-submitting'));
  });
})();
