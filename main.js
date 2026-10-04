// Minimal waitlist form handler with Formspree (or any endpoint that returns JSON on Accept: application/json)
(function () {
  const form = document.querySelector('form[data-formspree]');
  const status = document.getElementById('form-status');
  if (!form || !status) return;

  // Campaign attribution: ?source=tiktok overrides the hidden field's default.
  // Without this every signup reports as "landing" and no campaign can be measured.
  // The value ends up in a notification email, so it is allowlisted, never passed through.
  (function attributeSource() {
    const field = form.querySelector('input[name="source"]');
    if (!field) return;

    const sanitize = (raw) => {
      if (!raw) return null;
      const clean = raw.toLowerCase().slice(0, 32);
      return /^[a-z0-9_-]+$/.test(clean) ? clean : null;
    };

    const fromQuery = sanitize(new URLSearchParams(window.location.search).get('source'));

    // Remember it: a visitor who detours via privacy.html and comes back
    // would otherwise lose the parameter and fall back to the default.
    let remembered = null;
    try {
      if (fromQuery) window.sessionStorage.setItem('ir_source', fromQuery);
      else remembered = sanitize(window.sessionStorage.getItem('ir_source'));
    } catch (err) {
      // Private mode or blocked storage — the query parameter alone still works.
    }

    const source = fromQuery || remembered;
    // setAttribute, not .value: form.reset() after a successful submit restores
    // the attribute, so a second signup in the same session keeps the attribution.
    if (source) field.setAttribute('value', source);
  })();

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
