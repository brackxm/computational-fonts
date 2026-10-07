// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {EXAMPLES, serialize, createPlayground} = require('./controls.js');

function harness(load) {
  const ids = ['source','terminal','raw','status','screen',...Object.keys(EXAMPLES)];
  const elements = Object.fromEntries(ids.map(id => [id, {
    value: '', textContent: '', hidden: false, events: {}, classes: new Set(),
    addEventListener(name, fn) { this.events[name] = fn; },
    classList: {add() {}, toggle() {}},
  }]));
  const document = {getElementById: id => elements[id], fonts: {load}};
  elements.source.value = EXAMPLES.count;
  return {elements, document};
}
test('serialization preserves string spelling, spaces and punctuation', () => {
  assert.equal(serialize(' 10 print "Hi;  there!" \r\n\r20 END\n'), 'RUN:10 print "Hi;  there!":20 END:!');
  assert.equal(serialize('\n  \n'), 'RUN:!');
  assert.equal(serialize('10 PRINT "A=";A\n20 PRINT ":;"'), 'RUN:10 PRINT "A=";A:20 PRINT ":;":!');
  for (const program of Object.values(EXAMPLES)) assert.match(serialize(program), /^RUN:.*:!$/);
});
test('input bounds reject run-splitting characters and excessive input', () => {
  for (const program of ['10 PRINT "é"','10\tEND','10 END\u200b','10 END\0']) {
    assert.throws(() => serialize(program), /printable ASCII/);
  }
  assert.doesNotThrow(() => serialize(Array.from({length:16},(_,i)=>`${i+1} END`).join('\n')));
  assert.throws(() => serialize(Array.from({length:17},(_,i)=>`${i+1} END`).join('\n')), /16/);
  assert.doesNotThrow(() => serialize('x'.repeat(128)));
  assert.throws(() => serialize('x'.repeat(129)), /128/);
});
test('loading completion renders the latest edit and example buttons change only source', async () => {
  let resolve;
  const h = harness(() => new Promise(r => {resolve = r;}));
  const {ready} = createPlayground(h.document);
  assert.equal(h.elements.screen.hidden,true);
  h.elements.source.value = '10 PRINT "Current"';
  h.elements.source.events.input();
  resolve([{}]); await ready;
  assert.equal(h.elements.screen.hidden,false);
  assert.equal(h.elements.terminal.textContent,'RUN:10 PRINT "Current":!');
  for (const [id,program] of Object.entries(EXAMPLES)) {
    h.elements[id].events.click();
    assert.equal(h.elements.source.value,program);
    assert.equal(h.elements.raw.textContent,serialize(program));
  }
});
test('invalid edits stay hidden when the font finishes loading, then recover', async () => {
  let resolve;
  const h = harness(() => new Promise(r => {resolve = r;}));
  const {ready} = createPlayground(h.document);
  h.elements.source.value = '10 PRINT "é"'; h.elements.source.events.input();
  resolve([{}]); await ready;
  assert.equal(h.elements.screen.hidden,true);
  assert.equal(h.elements.terminal.textContent,'');
  assert.match(h.elements.status.textContent,/ASCII/);
  h.elements.source.value = '10 END'; h.elements.source.events.input();
  assert.equal(h.elements.screen.hidden,false);
  assert.equal(h.elements.terminal.textContent,'RUN:10 END:!');
});
test('failed and missing fonts hide the result instead of exposing fallback input', async () => {
  for (const load of [async()=>[],async()=>{throw new Error('Network failed');}]) {
    const h = harness(load);
    await createPlayground(h.document).ready;
    assert.equal(h.elements.screen.hidden,true);
    assert.match(h.elements.status.textContent,/HTTP/);
    h.elements.greeting.events.click();
    assert.equal(h.elements.screen.hidden,true);
  }
});
