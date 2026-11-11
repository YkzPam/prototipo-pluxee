(() => {
  'use strict';
  // Los mensajes de éxito e información pasan a una pila flotante; los errores y advertencias quedan en la página.
  const notices = [...document.querySelectorAll('.messages > :is(.notice-success, .notice-info)')];
  if (!notices.length) return;
  const stack = document.createElement('div');
  stack.className = 'toast-stack';
  document.body.append(stack);

  function dismiss(toast) {
    if (toast.dataset.leaving) return;
    toast.dataset.leaving = 'true';
    const remove = () => toast.remove();
    const root = document.documentElement;
    if (root.dataset.motion === 'off' || root.dataset.motionLevel === 'none'
        || matchMedia('(prefers-reduced-motion: reduce)').matches) remove();
    else toast.addEventListener('animationend', remove, {once: true});
  }

  notices.forEach(notice => {
    const container = notice.parentElement;
    notice.classList.add('toast');
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'toast-close';
    close.setAttribute('aria-label', 'Cerrar aviso');
    close.textContent = '×';
    close.addEventListener('click', () => dismiss(notice));
    notice.append(close);
    stack.append(notice);
    if (!container.children.length) container.remove();

    let remaining = 5000;
    let started = performance.now();
    let timer = setTimeout(() => dismiss(notice), remaining);
    const pause = () => { clearTimeout(timer); remaining -= performance.now() - started; };
    const resume = () => { started = performance.now(); timer = setTimeout(() => dismiss(notice), Math.max(remaining, 1500)); };
    notice.addEventListener('mouseenter', pause);
    notice.addEventListener('mouseleave', resume);
    notice.addEventListener('focusin', pause);
    notice.addEventListener('focusout', resume);
  });
})();
