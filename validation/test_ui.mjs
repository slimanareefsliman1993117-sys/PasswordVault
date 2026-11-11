import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import test from 'node:test';
import {JSDOM} from 'jsdom';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const fixtures = JSON.parse(execFileSync(path.join(root, '.venv/bin/python'), ['validation/export_ui_fixture.py'], {cwd: root, encoding: 'utf8'}));
const script = fs.readFileSync(path.join(root, 'static/js/vault.js'), 'utf8');
const literalPassword = '<img src="x" onerror="alert(1)">"&-Synthetic-123!';
const tick = () => new Promise(resolve => setImmediate(resolve));
function open(html) {
  const dom = new JSDOM(html, {url: 'http://localhost/', runScripts: 'outside-only'});
  const {window} = dom;
  const calls = [];
  let copied;
  window.fetch = async (url, options) => {
    assert.equal(options.method, 'POST');
    assert.ok(options.headers['X-CSRFToken']);
    calls.push({url, data: new URLSearchParams(options.body)});
    let result;
    if (url.includes('/reveal/')) result = {success: true, password: literalPassword};
    else if (url.includes('/generate/')) result = {success: true, password: 'Generated-Password-147!'};
    else if (url.includes('/check-strength/')) result = {success: true, strength: 'strong', feedback: 'Good length.'};
    else result = {success: true};
    return {ok: true, redirected: false, json: async () => result};
  };
  Object.defineProperty(window.navigator, 'clipboard', {value: {writeText: async text => { copied = text; }}});
  const dialog = window.document.querySelector('dialog');
  if (dialog) {
    dialog.showModal = () => dialog.setAttribute('open', '');
    dialog.close = value => { dialog.returnValue = value; dialog.removeAttribute('open'); dialog.dispatchEvent(new window.Event('close')); };
  }
  window.eval(script);
  return {dom, window, document: window.document, calls, copied: () => copied};
}

test('reveal preserves HTML and quotes as literal text, and hide clears the value', async () => {
  const ui = open(fixtures.dashboard);
  try {
    const button = ui.document.querySelector('[data-reveal-url]');
    const input = ui.document.getElementById(button.dataset.target);
    assert.equal(input.value, '');
    button.click(); await tick();
    assert.equal(input.value, literalPassword);
    assert.equal(input.type, 'text');
    assert.equal(button.textContent, 'Hide');
    assert.equal(ui.document.querySelectorAll('img').length, 0);
    button.click();
    assert.equal(input.type, 'password');
    assert.equal(input.value, '');
  } finally { ui.dom.window.close(); }
});

test('copy uses the returned value without exposing it in the page', async () => {
  const ui = open(fixtures.dashboard);
  try {
    ui.document.querySelector('[data-copy-url]').click(); await tick();
    assert.equal(ui.copied(), literalPassword);
    assert.equal(ui.document.querySelector('[data-entry-id] input').value, '');
    assert.match(ui.document.getElementById('vaultStatus').textContent, /copied/);
  } finally { ui.dom.window.close(); }
});

test('search and category filters show matching rows and the empty state', () => {
  const ui = open(fixtures.dashboard);
  try {
    const search = ui.document.getElementById('passwordSearch');
    const row = ui.document.querySelector('[data-entry-id]');
    search.value = 'missing'; search.dispatchEvent(new ui.window.Event('input'));
    assert.equal(row.hidden, true);
    assert.equal(ui.document.getElementById('noMatches').hidden, false);
    search.value = 'EXAMPLE'; search.dispatchEvent(new ui.window.Event('input'));
    assert.equal(row.hidden, false);
    const select = ui.document.getElementById('categoryFilter');
    select.value = row.dataset.category; select.dispatchEvent(new ui.window.Event('change'));
    assert.equal(row.hidden, false);
  } finally { ui.dom.window.close(); }
});

test('delete opens confirmation and cancellation sends no delete request', async () => {
  const ui = open(fixtures.dashboard);
  try {
    ui.document.querySelector('[data-delete-kind="category"]').click();
    const dialog = ui.document.getElementById('deleteDialog');
    assert.equal(dialog.hasAttribute('open'), true);
    assert.match(ui.document.getElementById('deleteMessage').textContent, /every password/);
    dialog.close('cancel'); await tick();
    assert.equal(ui.calls.length, 0);
  } finally { ui.dom.window.close(); }
});

test('generator submits selected options, fills the form, checks strength, and copies', async () => {
  const ui = open(fixtures.form);
  try {
    ui.document.getElementById('passwordLength').value = '24';
    ui.document.getElementById('useSpecial').checked = false;
    ui.document.getElementById('generatePassword').click(); await tick();
    const input = ui.document.querySelector('[name=password]');
    assert.equal(input.value, 'Generated-Password-147!');
    assert.equal(ui.calls[0].data.get('length'), '24');
    assert.equal(ui.calls[0].data.get('use_special'), 'false');
    assert.match(ui.document.getElementById('strengthFeedback').textContent, /strong/);
    ui.document.getElementById('toggleFormPassword').click();
    assert.equal(input.type, 'text');
    ui.document.getElementById('copyPassword').click(); await tick();
    assert.equal(ui.copied(), input.value);
  } finally { ui.dom.window.close(); }
});

test('network errors are visible and the reveal button is re-enabled', async () => {
  const ui = open(fixtures.dashboard);
  try {
    ui.window.fetch = async () => { throw new Error('offline'); };
    const button = ui.document.querySelector('[data-reveal-url]');
    button.click(); await tick();
    assert.equal(button.disabled, false);
    assert.equal(ui.document.getElementById('vaultStatus').textContent, 'offline');
  } finally { ui.dom.window.close(); }
});
