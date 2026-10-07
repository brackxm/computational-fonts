// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const {test} = require('node:test');
const {pbmSource, PBM_EXAMPLES, PBM_MAX_SOURCE, createPBMPlayground} = require('./pbm-controls.js');

test('preparation strips comments and folds only PBM whitespace', () => {
  assert.equal(pbmSource(' \tP1\r\n# header\r\n2\v2\f\t0 1\n1 0 # end'), 'P1 2 2 0 1 1 0');
  assert.equal(pbmSource('P1# comment\n2 2\n0110'), 'P1 2 2 0110');
  assert.equal(pbmSource('P1 1 1 1# comment at EOF'), 'P1 1 1 1');
  assert.equal(pbmSource('P1 1 1 1 # Unicode comment ☃'), 'P1 1 1 1');
  assert.equal(pbmSource('# comment\n\r \t'), '');
  assert.equal(pbmSource(''), '');
  assert.equal(pbmSource('not a PBM'), 'not a PBM', 'Image validation belongs to the font');
  for (const source of ['☃', '\u00a0P1 1 1 1', 'P1 1 1 1\u00a0', 'P1\u00001 1 1']) {
    assert.throws(() => pbmSource(source), /ASCII/);
  }
  assert.equal(pbmSource(' '.repeat(PBM_MAX_SOURCE)), '');
  assert.throws(() => pbmSource(' '.repeat(PBM_MAX_SOURCE + 1)), /at most/);
});

test('all examples contain a complete 64 × 64 raster within the source limit', () => {
  for (const [name, example] of Object.entries(PBM_EXAMPLES)) {
    assert.ok(example.length <= PBM_MAX_SOURCE, name);
    const tokens = pbmSource(example).split(' ');
    assert.deepEqual(tokens.slice(0, 3), ['P1', '64', '64'], name);
    const bits = tokens.slice(3).join('');
    assert.equal(bits.length, 4096, name);
    assert.match(bits, /^[01]+$/);
  }
});

function harness({missing = false, incompatible = false, rejected = false} = {}) {
  function element() {
    return {value: '', textContent: '', attributes: {}, listeners: {},
      append() {}, setAttribute(name, value) { this.attributes[name] = value; },
      addEventListener(name, listener) { this.listeners[name] = listener; },
      getBoundingClientRect() {
        if (incompatible) return {width: 0};
        const output = execFileSync('hb-shape', [path.join(__dirname, 'pbm-font.ttf'),
          this.textContent, '--output-format=json'], {encoding: 'utf8', maxBuffer: 8 * 1024 * 1024});
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
  const session = createPBMPlayground();
  return {session, elements,
    input(value) { elements.program.value = value; elements.program.listeners.input(); },
  };
}

test('controller uses the bundled font for examples, invalid images and edits', async () => {
  const h = harness(), e = h.elements;
  assert.equal(h.session.state, 'loading');
  await h.session.ready;
  assert.equal(h.session.state, 'ready');
  assert.equal(e.raw.textContent, pbmSource(PBM_EXAMPLES.heart));
  for (const name of Object.keys(PBM_EXAMPLES)) {
    e.example.value = name;
    e['load-example'].onclick();
    assert.equal(h.session.state, 'ready', name);
    assert.equal(e.drawing.textContent, pbmSource(PBM_EXAMPLES[name]));
    assert.equal(e.raw.textContent, e.drawing.textContent);
  }
  h.input('P1\n2 2\n01 10 # pixels');
  assert.equal(h.session.state, 'ready');
  assert.equal(e.program.attributes['aria-invalid'], 'false');
  h.input('P1 2 2 011');
  assert.equal(h.session.state, 'error');
  assert.match(e.status.textContent, /Invalid PBM/);
  assert.equal(e.program.attributes['aria-invalid'], 'true');
  h.input('P1 33 1 ' + '0'.repeat(33));
  assert.equal(h.session.state, 'ready', 'Widths above the old maximum are supported');
  h.input('P1 64 64 ' + '1'.repeat(4096));
  assert.equal(h.session.state, 'ready', 'The full 64 × 64 raster is supported');
  h.input('P1 64 64 ' + '1'.repeat(4097));
  assert.equal(h.session.state, 'error', 'Extra pixels are rejected at the new maximum');
  h.input('P1 65 1 ' + '0'.repeat(65));
  assert.equal(h.session.state, 'error');
  h.input('P1 1 1 0');
  assert.equal(h.session.state, 'ready');
  h.input('☃');
  assert.equal(h.session.state, 'error');
  assert.equal(e.drawing.textContent, '', 'Rejected source clears stale output');
  assert.match(e.status.textContent, /ASCII/);
  h.input('0'.repeat(PBM_MAX_SOURCE + 1));
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
    h.input('P1 1 1 1');
    assert.equal(h.session.state, 'error');
    h.elements.clear.onclick();
    assert.equal(h.session.state, 'error');
  }
});
