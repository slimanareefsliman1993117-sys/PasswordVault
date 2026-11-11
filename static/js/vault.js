'use strict';
(() => {
  const csrf = () => document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  async function post(url, data = {}) {
    const response = await fetch(url, {method: 'POST', credentials: 'same-origin',
      headers: {'X-CSRFToken': csrf(), 'Content-Type': 'application/x-www-form-urlencoded'},
      body: new URLSearchParams(data)});
    if (response.redirected) { window.location.assign(response.url); throw new Error('Please sign in again.'); }
    if (!response.ok) throw new Error(response.status === 403 ? 'Request rejected. Refresh the page and try again.' : 'Unable to complete the request.');
    const result = await response.json();
    if (!result.success) throw new Error(result.error || 'Unable to complete the request.');
    return result;
  }
  const status = document.getElementById('vaultStatus') || document.getElementById('strengthFeedback');
  function announce(message) { if (status) status.textContent = message; }
  async function copy(value) {
    if (!navigator.clipboard) throw new Error('Clipboard unavailable. Show the password and copy it manually.');
    await navigator.clipboard.writeText(value);
    announce('Password copied.');
  }
  const dashboard = document.getElementById('vaultDashboard');
  if (dashboard) {
    const filter = () => {
      const query = document.getElementById('passwordSearch').value.toLowerCase();
      const category = document.getElementById('categoryFilter').value;
      let visible = 0;
      for (const row of document.querySelectorAll('[data-entry-id]')) {
        row.hidden = !row.dataset.search.includes(query) || Boolean(category && row.dataset.category !== category);
        if (!row.hidden) visible++;
      }
      document.getElementById('noMatches').hidden = visible > 0 || !document.querySelector('[data-entry-id]');
    };
    document.getElementById('passwordSearch').addEventListener('input', filter);
    document.getElementById('categoryFilter').addEventListener('change', filter);
    let pendingDelete = null;
    const dialog = document.getElementById('deleteDialog');
    dialog?.addEventListener('close', async () => {
      if (dialog.returnValue !== 'confirm' || !pendingDelete) return;
      const button = pendingDelete;
      button.disabled = true;
      try { await post(button.dataset.deleteUrl); window.location.reload(); }
      catch (error) { announce(error.message); button.disabled = false; }
      pendingDelete = null;
    });
    dashboard.addEventListener('click', async event => {
      const button = event.target.closest('button');
      if (!button) return;
      if (dialog && button.dataset.deleteUrl) {
        pendingDelete = button;
        document.getElementById('deleteMessage').textContent = button.dataset.deleteKind === 'category'
          ? 'This deletes the category and every password in it. This cannot be undone.'
          : 'This permanently deletes the saved password.';
        dialog.returnValue = '';
        dialog.showModal();
        return;
      }
      const url = button.dataset.revealUrl || button.dataset.copyUrl;
      if (!url) return;
      const input = document.getElementById(button.dataset.target);
      if (button.dataset.revealUrl && input.type === 'text') {
        input.type = 'password'; input.value = ''; button.textContent = 'Show'; return;
      }
      button.disabled = true;
      try {
        const {password} = await post(url);
        if (button.dataset.copyUrl) await copy(password);
        else {
          input.value = password; input.type = 'text'; button.textContent = 'Hide';
          setTimeout(() => { input.value = ''; input.type = 'password'; button.textContent = 'Show'; }, 30000);
        }
      } catch (error) { announce(error.message); }
      finally { button.disabled = false; }
    });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) for (const button of dashboard.querySelectorAll('[data-reveal-url]')) {
        const input = document.getElementById(button.dataset.target);
        input.value = ''; input.type = 'password'; button.textContent = 'Show';
      }
    });
  }
  const form = document.getElementById('passwordForm');
  if (form) {
    const password = form.querySelector('[name=password]');
    const feedback = document.getElementById('strengthFeedback');
    let timer, generation = 0;
    async function strength() {
      const current = ++generation;
      try {
        const result = await post(form.dataset.strengthUrl, {password: password.value});
        if (current === generation) feedback.textContent = `${result.strength}: ${result.feedback}`;
      } catch (error) { feedback.textContent = error.message; }
    }
    password.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(strength, 250); });
    document.getElementById('toggleFormPassword').addEventListener('click', event => {
      password.type = password.type === 'password' ? 'text' : 'password';
      event.target.textContent = password.type === 'password' ? 'Show password' : 'Hide password';
    });
    document.getElementById('generatePassword').addEventListener('click', async () => {
      try {
        const result = await post(form.dataset.generateUrl, {
          length: document.getElementById('passwordLength').value,
          use_uppercase: document.getElementById('useUppercase').checked,
          use_numbers: document.getElementById('useNumbers').checked,
          use_special: document.getElementById('useSpecial').checked,
        });
        password.value = result.password;
        await strength();
      } catch (error) { feedback.textContent = error.message; }
    });
    document.getElementById('copyPassword').addEventListener('click', async () => {
      try { await copy(password.value); } catch (error) { feedback.textContent = error.message; }
    });
  }
})();
