// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const {BACKGAMMON_EXAMPLES, backgammonText, backgammonSignal, createBackgammonPlayground} = require('./controls.js');

const encoded = text => '\ue000'+Array.from(text, c => String.fromCharCode(0xe100+c.charCodeAt(0))).join('')+'\ue001';
assert.equal(backgammonText('(;GM[6])'), encoded('(;GM[6])'));
assert.equal(backgammonText('A\n\t\rB'), encoded('A   B'));
assert.equal(backgammonText('é\ue000🙂'), encoded('\x7f\x7f\x7f'));
assert.equal(backgammonText('\u0000\u200d\ue001\ud800'), encoded('\x7f'.repeat(4)));
assert.equal(backgammonText('!?#'), encoded('!?#'));
for (let code = 1; code <= 5; code++) assert.equal(backgammonSignal(1800+code), code);
for (const width of [0, 1800, 1806, 1801.4, NaN]) assert.equal(backgammonSignal(width), 0);

try { execFileSync('hb-shape', ['--version'], {stdio: 'pipe'}); }
catch (error) {
  if (error.code !== 'ENOENT') throw error;
  console.log('SKIP font/controller integration: install HarfBuzz hb-shape. Transport checks passed.');
  process.exit(0);
}

const font = path.join(__dirname, 'backgammon-font.ttf');
function harness({missing = false, incompatible = false, rejected = false} = {}) {
  const elements = {};
  function element() {
    return {value: '', textContent: '', dataset: {}, listeners: {}, attributes: {},
      append() {}, setAttribute(key, value) { this.attributes[key] = value; },
      addEventListener(key, callback) { this.listeners[key] = callback; },
      getBoundingClientRect() {
        if (incompatible) return {width: 0};
        const output = JSON.parse(execFileSync('hb-shape', [font, '--text='+this.textContent,
          '--output-format=json'], {encoding: 'utf8', timeout: 10000}));
        return {width: output.reduce((sum, glyph) => sum+glyph.ax, 0)};
      },
    };
  }
  for (const id of ['record', 'drawing', 'status', 'undo', 'reset', 'load', 'example']) elements[id] = element();
  elements.record.value = BACKGAMMON_EXAMPLES.opening;
  elements.example.value = 'entry';
  global.document = {body: {append() {}}, createElement: element,
    querySelector: selector => elements[selector.slice(1)],
    fonts: {load: async () => {
      if (rejected) throw new Error('Failed font load');
      return missing ? [] : [{}];
    }},
  };
  const session = createBackgammonPlayground();
  return {session, e: elements, setIncompatible(value) { incompatible = value; }};
}

(async () => {
  const h = harness(), {session, e} = h;
  await session.ready;
  for (const example of Object.values(BACKGAMMON_EXAMPLES)) {
    session.replace(example);
    assert.equal(e.status.dataset.signal, '1', example);
    assert.equal(e.drawing.textContent, backgammonText(example));
    assert.match(e.status.textContent, /legality was not checked/);
  }
  const cases = [
    ['(;GM[6]', '2'], ['(;GM[6];W[31h])', '2'], ['(;GM[6]C[comment])', '3'],
    ['(;GM[6];W[double])', '3'], ['(;GM[6])🙂', '3'],
    ['(;GM[6]'+ ';B[66]'.repeat(128) +')', '1'],
    ['(;GM[6]'+ ';B[66]'.repeat(127) +';W[31hefe])', '1'],
    ['(;GM[6]'+ ';B[66]'.repeat(129) +')', '4'], ['(;GM[6];W[11ab])', '5'],
  ];
  for (const [input, signal] of cases) {
    session.replace(input);
    assert.equal(e.status.dataset.signal, signal, input);
    assert.match(e.status.textContent, signal === '1' ? /Replay complete/ : /partial replay/);
  }
  e.reset.onclick();
  assert.equal(e.record.value, BACKGAMMON_EXAMPLES.start);
  e.load.onclick();
  assert.equal(e.record.value, BACKGAMMON_EXAMPLES.entry);
  e.undo.onclick();
  assert.equal(e.record.value, BACKGAMMON_EXAMPLES.start);
  // Input events and Undo use text history, without interpreting SGF.
  e.record.value = BACKGAMMON_EXAMPLES.both;
  e.record.listeners.input();
  assert.equal(e.status.dataset.signal, '0', 'Editing must invalidate the old completion signal immediately');
  assert.match(e.status.textContent, /Replaying edited input/);
  assert.equal(e.drawing.textContent, '');
  assert.equal(e.drawing.attributes['aria-label'], e.status.textContent);
  session.render();
  assert.equal(e.status.dataset.signal, '1');
  e.undo.onclick();
  assert.equal(e.record.value, BACKGAMMON_EXAMPLES.start);
  session.replace(BACKGAMMON_EXAMPLES.start.padEnd(4096, ' '));
  assert.equal(e.status.dataset.signal, '1', 'Exactly 4096 source characters must still replay');
  session.replace(' '.repeat(4097));
  assert.match(e.status.textContent, /Input limit reached/);
  assert.equal(e.drawing.textContent, '');
  assert.equal(e.status.dataset.signal, '0', 'An input limit must clear the previous success signal');
  assert.equal(e.drawing.attributes['aria-label'], e.status.textContent);
  e.reset.onclick();
  assert.equal(e.status.dataset.signal, '1');

  // Losing shaping support after initial loading must not leave a trusted board.
  h.setIncompatible(true);
  session.render();
  assert.equal(e.status.dataset.signal, '0');
  assert.equal(e.drawing.textContent, '');
  assert.equal(e.drawing.attributes['aria-label'], e.status.textContent);
  h.setIncompatible(false);
  session.render();
  assert.equal(e.status.dataset.signal, '1');

  for (const options of [{missing: true}, {incompatible: true}, {rejected: true}]) {
    const broken = harness(options);
    await broken.session.ready;
    assert.match(broken.e.status.textContent, /Could not load or shape/);
    assert.equal(broken.e.drawing.textContent, '');
    assert.equal(broken.e.status.dataset.signal, '0');
    assert.equal(broken.e.drawing.attributes['aria-label'], broken.e.status.textContent);
  }
  console.log('Backgammon transport and controller integration checks passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
