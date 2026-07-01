// Minimal waitlist form handler with Formspree (or any endpoint that returns JSON on Accept: application/json)
(function () {
  const form = document.querySelector('form[data-formspree]');
  const status = document.getElementById('form-status');
  if (!form || !status) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    status.classList.remove('error');
    status.textContent = 'Sending…';

    const data = new FormData(form);
    try {
      const res = await fetch(form.action, {
        method: 'POST',
        headers: { Accept: 'application/json' },
        body: data,
      });
      if (res.ok) {
        form.reset();
        status.textContent = "You're in. Check your inbox for confirmation.";
      } else {
        const body = await res.json().catch(() => ({}));
        status.classList.add('error');
        status.textContent = body.errors?.[0]?.message || 'Something went wrong. Try again?';
      }
    } catch (err) {
      status.classList.add('error');
      status.textContent = 'Network hiccup. Please try again.';
    }
  });
})();
