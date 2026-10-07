// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const {test} = require('node:test');
const {ppmSource, PPM_EXAMPLES, PPM_MAX_SOURCE, createPPMPlayground} = require('./ppm-controls.js');

test('preparation strips comments and folds only PPM whitespace', () => {
  assert.equal(ppmSource(' \tP3\r\n# header\r\n2\v2\f3\t3 0 0\n0 3 0\n0 0 3\n3 3 3 # end'), 'P3 2 2 3 3 0 0 0 3 0 0 0 3 3 3 3');
  assert.equal(ppmSource('P3# comment\n2 2\n3\n3 0 0 0 3 0 0 0 3 3 3 3'), 'P3 2 2 3 3 0 0 0 3 0 0 0 3 3 3 3');
  assert.equal(ppmSource('P3 1 1 3 3 0 0# comment at EOF'), 'P3 1 1 3 3 0 0');
  assert.equal(ppmSource('P3 1 1 3 3 0 0 # Unicode comment ☃'), 'P3 1 1 3 3 0 0');
  assert.equal(ppmSource('# comment\n\r \t'), '');
  assert.equal(ppmSource(''), '');
  assert.equal(ppmSource('not a PPM'), 'not a PPM', 'Image validation belongs to the font');
  for (const source of ['☃', '\u00a0P3 1 1 3 3 0 0', 'P3 1 1 3 3 0 0\u00a0', 'P3\u00001 1 1']) {
    assert.throws(() => ppmSource(source), /ASCII/);
  }
  assert.equal(ppmSource(' '.repeat(PPM_MAX_SOURCE)), '');
  assert.throws(() => ppmSource(' '.repeat(PPM_MAX_SOURCE + 1)), /at most/);
});

function harness({missing = false, incompatible = false, rejected = false} = {}) {
  function element() {
    return {value: '', textContent: '', attributes: {}, listeners: {},
      append() {}, setAttribute(name, value) { this.attributes[name] = value; },
      addEventListener(name, listener) { this.listeners[name] = listener; },
      getBoundingClientRect() {
        if (incompatible) return {width: 0};
        const output = execFileSync('hb-shape', [path.join(__dirname, 'ppm-font.ttf'),
          this.textContent, '--output-format=json'], {encoding: 'utf8'});
        return {width: JSON.parse(output).reduce((total, glyph) => total + glyph.ax, 0)};
      },
    };
  }
  const elements = Object.fromEntries(['program', 'drawing', 'raw', 'status', 'load-example', 'example', 'clear']
    .map(id => [id, element()]));
  global.document = {
    body: {append() {}}, createElement: element,
    querySelector: selector => elements[selector.slice(1)],
    fonts: {load: async () => { if (rejected) throw new Error('Load failed'); return missing ? [] : [{}]; }},
  };
  const session = createPPMPlayground();
  return {session, elements,
    input(value) { elements.program.value = value; elements.program.listeners.input(); },
  };
}

test('controller uses the bundled font for examples, invalid images and edits', async () => {
  const h = harness(), e = h.elements;
  assert.equal(h.session.state, 'loading');
  await h.session.ready;
  assert.equal(h.session.state, 'ready');
  assert.equal(e.raw.textContent, ppmSource(PPM_EXAMPLES.bars));
  for (const name of Object.keys(PPM_EXAMPLES)) {
    e.example.value = name;
    e['load-example'].onclick();
    assert.equal(h.session.state, 'ready', name);
    assert.equal(e.drawing.textContent, ppmSource(PPM_EXAMPLES[name]));
    assert.equal(e.raw.textContent, e.drawing.textContent);
  }
  h.input('P3\n2 2\n3\n3 0 0 0 3 0 0 0 3 3 3 3 # samples');
  assert.equal(h.session.state, 'ready');
  assert.equal(e.program.attributes['aria-invalid'], 'false');
  h.input('P3 2 2 3 3 0 0 0 3 0 0 0 3');
  assert.equal(h.session.state, 'error');
  assert.match(e.status.textContent, /Invalid PPM/);
  assert.equal(e.program.attributes['aria-invalid'], 'true');
  h.input('P3 17 1 3 ' + '0 0 0 '.repeat(17));
  assert.equal(h.session.state, 'ready', 'Widths above the old maximum are supported');
  h.input('P3 32 32 3 ' + '3 0 0 '.repeat(1024));
  assert.equal(h.session.state, 'ready', 'The full 32 × 32 raster is supported');
  h.input('P3 32 32 3 ' + '0 0 0 '.repeat(1025));
  assert.equal(h.session.state, 'error', 'Extra pixels are rejected at the new maximum');
  h.input('P3 33 1 3 ' + '0 0 0 '.repeat(33));
  assert.equal(h.session.state, 'error');
  h.input('P3 1 1 3 0 0 0');
  assert.equal(h.session.state, 'ready');
  h.input('☃');
  assert.equal(h.session.state, 'error');
  assert.equal(e.drawing.textContent, '', 'Rejected source clears stale output');
  assert.match(e.status.textContent, /ASCII/);
  h.input('0'.repeat(PPM_MAX_SOURCE + 1));
  assert.equal(h.session.state, 'error');
  assert.equal(e.raw.textContent, '');
  e.clear.onclick();
  assert.equal(h.session.state, 'empty');
  assert.equal(e.drawing.textContent, '');
});

test('font failures stay visible after edits and clearing', async () => {
  for (const options of [{missing: true}, {incompatible: true}, {rejected: true}]) {
    const h = harness(options);
    await h.session.ready;
    assert.equal(h.session.state, 'error');
    assert.match(h.elements.status.textContent, /font could not load or shape/);
    h.input('P3 1 1 3 3 0 0');
    assert.equal(h.session.state, 'error');
    h.elements.clear.onclick();
    assert.equal(h.session.state, 'error');
  }
});
