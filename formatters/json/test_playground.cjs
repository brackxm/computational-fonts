// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Execute the actual playground script against a small DOM fixture.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, 'playground.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const initial = html.match(/<textarea\b[^>]*>([\s\S]*?)<\/textarea>/)[1];

function harness() {
  function element() {
    const classes = new Set();
    return {
      value: '', textContent: '', children: [], attributes: {}, listeners: {},
      classList: {
        toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); },
        contains(name) { return classes.has(name); },
      },
      setAttribute(name, value) { this.attributes[name] = value; },
      replaceChildren(...children) { this.children = children; },
      addEventListener(name, listener) { this.listeners[name] = listener; },
    };
  }
  const elements = Object.fromEntries(
    ['source', 'preview', 'status', 'profile', 'nested', 'escaped', 'numbers'].map(id => [id, element()]));
  elements.source.value = initial;
  let resolve, reject;
  const loading = new Promise((accept, fail) => { resolve = accept; reject = fail; });
  const document = {
    querySelector: selector => elements[selector.slice(1)],
    getElementById: id => elements[id],
    createElement: element,
    fonts: {load: () => loading},
  };
  vm.runInNewContext(script, {document});
  return {
    elements, resolve, reject,
    input(value) { elements.source.value = value; elements.source.listeners.input(); },
    text() { return elements.preview.children.map(line => line.textContent).join('\n'); },
    plain() { return elements.preview.classList.contains('plain'); },
  };
}

const flush = () => new Promise(resolve => setImmediate(resolve));

(async () => {
  const h = harness();
  assert.ok(h.plain(), 'Loading previews use an ordinary font');
  h.resolve([{}]);
  await flush();
  assert.equal(h.plain(), false);
  assert.equal(h.text(), initial);
  const unsupported = [
    '{"name":"αβ:  true Привет","n":7,"ok":true}',
    '{"café":"Été"}', '{"name":"Привет"}', '{"name":"مرحبا"}',
    '{"name":"🙂"}', '{"name":"e\u0301"}', '{"name":"a\u200db"}',
    '{"name":"\u202etrue"}', '{\t"n":7}', '{"n":7}\r', '{"x":"\u0000"}',
    '{"name":"αβ"}\n{"n":7}',
  ];
  for (const source of unsupported) {
    h.input(source);
    assert.ok(h.plain(), JSON.stringify(source));
    assert.equal(h.text(), source, 'Fallback must preserve all characters and spaces');
    assert.equal(h.elements.source.value, source, 'Do not rewrite the editor');
    assert.match(h.elements.status.textContent, /without formatting.*Unicode escapes/);
    assert.equal(h.elements.preview.attributes['aria-label'], 'Original JSON without formatting');
  }
  for (const source of [initial, '', String.raw`{"name":"\u03b1\u03b2:  true \u041f","n":7}`,
    '{"text":"<b>literal</b>"}\n{"n":7}', '"unfinished  string']) {
    h.input(source);
    assert.equal(h.plain(), false, 'Supported input must recover automatically');
    assert.equal(h.text(), source);
    assert.equal(h.elements.status.classList.contains('error'), false);
    assert.equal(h.elements.preview.attributes['aria-label'], 'JSON drawn with the formatting font');
  }
  h.input(unsupported[0]);
  h.elements.profile.listeners.click();
  assert.equal(h.plain(), false, 'Example buttons must also clear fallback');
  assert.equal(h.text(), initial);

  const race = harness();
  race.input(unsupported[0]);
  race.resolve([{}]);
  await flush();
  assert.ok(race.plain(), 'Font loading must not override unsupported input');
  assert.equal(race.text(), unsupported[0]);
  assert.match(race.elements.status.textContent, /without formatting/);
  race.input(initial);
  assert.equal(race.plain(), false);

  for (const missing of [true, false]) {
    const failed = harness();
    missing ? failed.resolve([]) : failed.reject(new Error('Font load failed.'));
    await flush();
    assert.ok(failed.plain());
    assert.match(failed.elements.status.textContent, /Serve the repository/);
    failed.input(unsupported[0]);
    assert.match(failed.elements.status.textContent, /without formatting/);
    failed.input(initial);
    assert.ok(failed.plain(), 'Supported input cannot enable a missing font');
    assert.match(failed.elements.status.textContent, /Serve the repository/);
  }
  console.log('JSON playground: Unicode/control fallback, recovery, source preservation and font-loading checks passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
