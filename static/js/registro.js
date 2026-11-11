(() => {
  const form = document.querySelector('[data-registration-form]');
  if (!form) return;

  const password = form.elements.namedItem('password1');
  const confirmation = form.elements.namedItem('password2');
  const criteria = Array.from(form.querySelectorAll('[data-criterion]'));
  const progress = form.querySelector('[data-password-progress]');

  function updateCriteria() {
    const value = password.value;
    const entered = Boolean(value || confirmation.value);
    const checks = {
      length: (item) => Array.from(value).length >= Number(item.dataset.minLength),
      letter: () => /\p{L}/u.test(value),
      digit: () => /\p{Nd}/u.test(value),
      symbol: () => /[^\p{L}\p{N}\s]/u.test(value),
      match: () => Boolean(value) && value === confirmation.value,
    };
    let passed = 0;
    for (const criterion of criteria) {
      const meets = entered && checks[criterion.dataset.criterion](criterion);
      const status = criterion.querySelector('[data-criterion-status]');
      criterion.toggleAttribute('data-passed', meets);
      status.hidden = !entered;
      status.textContent = meets ? 'Cumple' : 'Pendiente';
      passed += Number(meets);
    }

    const announcement = entered ? `${passed} de ${criteria.length} comprobaciones completadas.` : '';
    if (progress.textContent !== announcement) progress.textContent = announcement;
  }

  for (const input of [password, confirmation]) {
    input.addEventListener('input', updateCriteria);
    input.addEventListener('change', updateCriteria);
  }
  updateCriteria();
})();
