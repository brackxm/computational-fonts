// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const {test} = require('node:test');
const {pgmSource, PGM_EXAMPLES, PGM_MAX_SOURCE, createPGMPlayground} = require('./pgm-controls.js');

test('preparation strips comments and folds only PGM whitespace', () => {
  assert.equal(pgmSource(' \tP2\r\n# header\r\n2\v2\f15\t0 1\n1 0 # end'), 'P2 2 2 15 0 1 1 0');
  assert.equal(pgmSource('P2# comment\n2 2\n15\n0 1 1 0'), 'P2 2 2 15 0 1 1 0');
  assert.equal(pgmSource('P2 1 1 15 1# comment at EOF'), 'P2 1 1 15 1');
  assert.equal(pgmSource('P2 1 1 15 1 # Unicode comment ☃'), 'P2 1 1 15 1');
  assert.equal(pgmSource('# comment\n\r \t'), '');
  assert.equal(pgmSource(''), '');
  assert.equal(pgmSource('not a PGM'), 'not a PGM', 'Image validation belongs to the font');
  for (const source of ['☃', '\u00a0P2 1 1 15 1', 'P2 1 1 15 1\u00a0', 'P2\u00001 1 1']) {
    assert.throws(() => pgmSource(source), /ASCII/);
  }
  assert.equal(pgmSource(' '.repeat(PGM_MAX_SOURCE)), '');
  assert.throws(() => pgmSource(' '.repeat(PGM_MAX_SOURCE + 1)), /at most/);
});

test('all examples contain a complete 64 × 64 raster within the source limit', () => {
  for (const [name, example] of Object.entries(PGM_EXAMPLES)) {
    assert.ok(example.length <= PGM_MAX_SOURCE, name);
    const tokens = pgmSource(example).split(' ');
    assert.deepEqual(tokens.slice(0, 3), ['P2', '64', '64'], name);
    assert.equal(tokens[3], '15');
    const samples = tokens.slice(4);
    assert.equal(samples.length, 4096, name);
    assert.ok(samples.every(value => /^\d+$/.test(value) && Number(value) <= 15), name);
  }
});

function harness({missing = false, incompatible = false, rejected = false} = {}) {
  function element() {
    return {value: '', textContent: '', attributes: {}, listeners: {},
      append() {}, setAttribute(name, value) { this.attributes[name] = value; },
      addEventListener(name, listener) { this.listeners[name] = listener; },
      getBoundingClientRect() {
        if (incompatible) return {width: 0};
        const output = execFileSync('hb-shape', [path.join(__dirname, 'pgm-font.ttf'),
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
  const session = createPGMPlayground();
  return {session, elements,
    input(value) { elements.program.value = value; elements.program.listeners.input(); },
  };
}

test('controller uses the bundled font for examples, invalid images and edits', async () => {
  const h = harness(), e = h.elements;
  assert.equal(h.session.state, 'loading');
  await h.session.ready;
  assert.equal(h.session.state, 'ready');
  assert.equal(e.raw.textContent, pgmSource(PGM_EXAMPLES.gradient));
  for (const name of Object.keys(PGM_EXAMPLES)) {
    e.example.value = name;
    e['load-example'].onclick();
    assert.equal(h.session.state, 'ready', name);
    assert.equal(e.drawing.textContent, pgmSource(PGM_EXAMPLES[name]));
    assert.equal(e.raw.textContent, e.drawing.textContent);
  }
  h.input('P2\n2 2\n15\n0 5 10 15 # samples');
  assert.equal(h.session.state, 'ready');
  assert.equal(e.program.attributes['aria-invalid'], 'false');
  h.input('P2 2 2 15 0 1 1');
  assert.equal(h.session.state, 'error');
  assert.match(e.status.textContent, /Invalid PGM/);
  assert.equal(e.program.attributes['aria-invalid'], 'true');
  h.input('P2 33 1 15 ' + '0 '.repeat(33));
  assert.equal(h.session.state, 'ready', 'Widths above the old maximum are supported');
  h.input('P2 64 64 15 ' + '15 '.repeat(4096));
  assert.equal(h.session.state, 'ready', 'The full 64 × 64 raster is supported');
  h.input('P2 64 64 15 ' + '0 '.repeat(4097));
  assert.equal(h.session.state, 'error', 'Extra pixels are rejected at the new maximum');
  h.input('P2 65 1 15 ' + '0 '.repeat(65));
  assert.equal(h.session.state, 'error');
  h.input('P2 1 1 15 0');
  assert.equal(h.session.state, 'ready');
  h.input('☃');
  assert.equal(h.session.state, 'error');
  assert.equal(e.drawing.textContent, '', 'Rejected source clears stale output');
  assert.match(e.status.textContent, /ASCII/);
  h.input('0'.repeat(PGM_MAX_SOURCE + 1));
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
    h.input('P2 1 1 15 1');
    assert.equal(h.session.state, 'error');
    h.elements.clear.onclick();
    assert.equal(h.session.state, 'error');
  }
});
