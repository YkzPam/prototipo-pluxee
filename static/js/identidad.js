/* Detalles de identidad visual: tarjetas con brillo, copiar folios y valores de los gráficos.
   Solo presentación: no envía datos al servidor ni guarda información en el navegador. */
(() => {
  'use strict';
  const root = document.documentElement;
  const motionAllowed = () => root.dataset.motion !== 'off'
    && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Tarjetas con inclinación leve y un brillo que sigue al puntero (solo mouse o lápiz).
  const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
  document.querySelectorAll('[data-tilt]').forEach(card => {
    let frame = 0;
    const reset = () => {
      cancelAnimationFrame(frame);
      card.classList.remove('is-tilting');
      ['--tilt-x', '--tilt-y', '--glare-x', '--glare-y'].forEach(name => card.style.removeProperty(name));
    };
    card.addEventListener('pointermove', event => {
      if (!finePointer.matches || !motionAllowed() || event.pointerType === 'touch') return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const box = card.getBoundingClientRect();
        const x = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width));
        const y = Math.min(1, Math.max(0, (event.clientY - box.top) / box.height));
        card.classList.add('is-tilting');
        card.style.setProperty('--tilt-x', ((0.5 - y) * 5).toFixed(2) + 'deg');
        card.style.setProperty('--tilt-y', ((x - 0.5) * 7).toFixed(2) + 'deg');
        card.style.setProperty('--glare-x', (x * 100).toFixed(1) + '%');
        card.style.setProperty('--glare-y', (y * 100).toFixed(1) + '%');
      });
    });
    card.addEventListener('pointerleave', reset);
    card.addEventListener('focusin', reset);
  });

  // Copiar folios y referencias. El botón solo aparece si el navegador permite copiar.
  const live = document.createElement('p');
  live.className = 'sr-only';
  live.setAttribute('role', 'status');
  document.body.append(live);
  document.querySelectorAll('[data-copy]').forEach(button => {
    if (!navigator.clipboard || !window.isSecureContext) return;
    button.hidden = false;
    const label = button.querySelector('[data-copy-label]');
    let timer = 0;
    button.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(button.dataset.copy);
        button.classList.add('is-copied');
        if (label) label.textContent = 'Copiado';
        live.textContent = 'Copiado al portapapeles.';
      } catch {
        live.textContent = 'No fue posible copiar. Selecciona el texto manualmente.';
      }
      clearTimeout(timer);
      timer = setTimeout(() => {
        button.classList.remove('is-copied');
        if (label) label.textContent = 'Copiar';
      }, 2000);
    });
  });

  // Secciones que están bajo el borde de la pantalla aparecen con suavidad al llegar a ellas.
  if (motionAllowed() && 'IntersectionObserver' in window) {
    // Secciones principales (no las anidadas dentro de otra) que comienzan bajo el borde de la pantalla.
    const blocks = '.page-content :is(section, .surface)';
    const pending = [...document.querySelectorAll(blocks)]
      .filter(section => !section.parentElement.closest(blocks))
      .filter(section => section.getBoundingClientRect().top > window.innerHeight);
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-revealed');
      observer.unobserve(entry.target);
    }));
    pending.forEach(section => { section.classList.add('reveal-pending'); observer.observe(section); });
  }

  // Gráficos del servidor: valor exacto en un cuadro flotante al pasar el puntero.
  const charts = document.querySelectorAll('.bar-chart svg');
  if (charts.length) {
    const tip = document.createElement('div');
    tip.className = 'chart-tip';
    tip.setAttribute('aria-hidden', 'true');
    tip.hidden = true;
    document.body.append(tip);
    const hide = () => {
      tip.hidden = true;
      document.querySelectorAll('.bar-chart-bar.is-active').forEach(bar => bar.classList.remove('is-active'));
    };
    charts.forEach(svg => {
      svg.addEventListener('pointermove', event => {
        const bar = event.target.closest('.bar-chart-bar[data-tip]');
        if (!bar) { hide(); return; }
        svg.querySelectorAll('.bar-chart-bar.is-active').forEach(other => other !== bar && other.classList.remove('is-active'));
        bar.classList.add('is-active');
        svg.classList.add('has-active-bar');
        tip.textContent = bar.dataset.tip;
        tip.hidden = false;
        const width = tip.offsetWidth;
        const left = Math.min(window.innerWidth - width - 8, Math.max(8, event.clientX - width / 2));
        tip.style.setProperty('--tip-x', left + 'px');
        tip.style.setProperty('--tip-y', (event.clientY - tip.offsetHeight - 12) + 'px');
      });
      svg.addEventListener('pointerleave', () => { hide(); svg.classList.remove('has-active-bar'); });
    });
    window.addEventListener('scroll', hide, {passive: true});
  }
})();
