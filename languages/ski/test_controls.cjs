// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const assert = require('node:assert/strict');
const SKI = require('./controls.js');

assert.equal(SKI.serialize('S K K a'), 'SKI32;@@@SKKa!' + '.'.repeat(191));
assert.equal(SKI.serialize('S (I a) b (I c)', 1), 'SKI1;@@@S@Iab@Ic!' + '.'.repeat(191));
assert.equal(SKI.inspect('@@@SKKa', 0).prefix, '@@@SKKa');
assert.equal(SKI.inspect('S (I a)', 32).nodes, 5);
assert.equal(SKI.inspect('a').depth, 0);
for (const {source, fuel} of Object.values(SKI.EXAMPLES)) assert.ok(SKI.serialize(source, fuel).endsWith('!'+'.'.repeat(191)));
for (const text of ['', '()', '(', ')', 'I (a', 'a)', '@', '@I', '@Iab', '@Ia b', '@Ia(a)', 'a$', 'E', '123', 'I '.repeat(1000), 'a'.repeat(16385)]) {
  assert.throws(() => SKI.serialize(text), undefined, text);
}
for (const fuel of [-1, 33, 1.5, true, null, undefined, '1']) {
  if (fuel !== undefined) assert.throws(() => SKI.serialize('a', fuel));
}
assert.throws(() => SKI.serialize(null));

function fakeDocument(load) {
  const elements = new Map();
  for (const id of ['source','fuel','terminal','raw','screen','status','capacity',...Object.keys(SKI.EXAMPLES)]) {
    const classes = new Set();
    elements.set(id, {value: id === 'source' ? 'S K K a' : id === 'fuel' ? '32' : '', textContent:'', hidden:false,
      listeners: {}, addEventListener(event, handler) {this.listeners[event] = handler;},
      classList: {add(name) {classes.add(name);}, toggle(name, value) {value ? classes.add(name) : classes.delete(name);}, contains(name) {return classes.has(name);}},
    });
  }
  return {fonts:{load}, getElementById(id) {assert.ok(elements.has(id), id); return elements.get(id);}};
}

(async () => {
  let finish;
  const document = fakeDocument(() => new Promise(resolve => {finish = resolve;}));
  const app = SKI.createPlayground(document);
  const get = id => document.getElementById(id);
  assert.equal(get('screen').hidden, true);
  finish([{}]); await app.ready;
  assert.equal(get('screen').hidden, false);
  assert.equal(get('terminal').textContent, SKI.serialize('S K K a'));
  assert.equal(get('raw').textContent, get('terminal').textContent);
  get('budget').listeners.click();
  assert.equal(get('fuel').value, '1');
  assert.equal(get('terminal').textContent, SKI.serialize('S a b (K c d)', 1));
  get('source').value = '('; get('source').listeners.input();
  assert.equal(get('screen').hidden, true);
  assert.equal(get('terminal').textContent, '');
  assert.ok(get('status').classList.contains('error'));
  get('source').value = 'a'; get('source').listeners.input();
  assert.equal(get('screen').hidden, false);
  assert.equal(get('status').classList.contains('error'), false);
  get('fuel').value = ''; get('fuel').listeners.input();
  assert.equal(get('screen').hidden, true);
  for (const load of [async () => [], async () => {throw new Error('font unavailable');}]) {
    const broken = fakeDocument(load);
    await SKI.createPlayground(broken).ready;
    assert.equal(broken.getElementById('screen').hidden, true);
    assert.ok(broken.getElementById('status').classList.contains('error'));
  }
  console.log('PASS: SKI notation, workspace, examples, input validation, font loading and UI states');
})().catch(error => {console.error(error); process.exitCode = 1;});
