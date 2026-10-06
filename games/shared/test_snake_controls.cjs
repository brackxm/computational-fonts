// Integration checks: the session reads terminal advances from the real fonts.
// Run with node games/shared/test_snake_controls.cjs; requires hb-shape on PATH.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const vm = require('node:vm');

function harness(kind, {missingFont = false, outdatedFont = false} = {}) {
  const font = path.join(__dirname, '..', `snake-${kind}`, `snake-${kind}-font.ttf`);
  const elements = [];
  const buttons = ['w', 'a', 's', 'd'].map(m => ({dataset: {m}}));
  const undo = {}, status = {};
  let keydown, rendered;
  const document = {
    body: {append() {}},
    createElement() {
      const element = {
        style: {}, textContent: '', append() {}, setAttribute() {},
        getBoundingClientRect() {
          if (outdatedFont) return {width: kind === 'fixed' ? 2000 : 0};
          const output = execFileSync('hb-shape', [font, this.textContent, '--output-format=json'], {encoding: 'utf8'});
          return {width: JSON.parse(output).reduce((total, glyph) => total + glyph.ax, 0)};
        },
      };
      elements.push(element);
      return element;
    },
    querySelector: selector => selector === '#undo' ? undo : null,
    querySelectorAll: () => buttons,
    fonts: {load: async () => missingFont ? [] : [{}]},
  };
  const context = {document, addEventListener: (_, fn) => { keydown = fn; }};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'snake-controls.js'), 'utf8'), context);
  const session = context.createSnakeSession({
    fontFamily: kind === 'fixed' ? 'SnakeFixed' : 'SnakeDynamic',
    maxMoves: kind === 'fixed' ? 128 : 8,
    onRender: (text, count) => { rendered = {text, count}; }, statusElement: status,
  });
  context.bindSnakeControls(session.move);
  session.reset(kind === 'fixed' ? 'b' : '10x5b', kind === 'fixed' ? 2000 : 0);
  return {session, buttons, undo, status, get rendered() { return rendered; },
    key(key, {editable = false, ctrlKey = false, metaKey = false, altKey = false} = {}) {
      keydown({key, ctrlKey, metaKey, altKey, target: {closest: () => editable ? {} : null}, preventDefault() {}});
    },
  };
}

(async () => {
  for (const kind of ['dynamic', 'fixed']) {
    const h = harness(kind), s = h.session;
    s.move('d');
    assert.equal(s.moves, '', 'Ignore movement before the font is ready');
    await s.ready;
    assert.equal(s.state, 'playing');
    assert.ok(h.undo.disabled);
    for (const guard of [{editable: true}, {ctrlKey: true}, {metaKey: true}, {altKey: true}]) h.key('6', guard);
    assert.equal(s.moves, '');
    h.key('4');
    assert.equal(s.state, 'lost');
    assert.ok(h.buttons.every(b => b.disabled));
    h.key('6'); s.move('w');
    assert.equal(s.moves, 'a', 'Do not record ignored commands after losing');
    s.undo();
    assert.equal(s.state, 'playing');
    assert.equal(s.moves, '');
    h.key('6');
    assert.equal(s.moves, 'd');
    s.reset(kind === 'fixed' ? 'b' : '10x5b', kind === 'fixed' ? 2000 : 0);
    const win = kind === 'fixed'
      ? 'd'.repeat(16) + 'w'.repeat(4) + 'a'.repeat(17) + 's'.repeat(8) + 'd'.repeat(17) + 'w'.repeat(8) + 'a'.repeat(17) + 's'.repeat(8) + 'd'.repeat(17)
      : 'd'.repeat(7) + 'w';
    for (const move of win) s.move(move);
    assert.equal(s.state, 'won');
    s.move('a');
    assert.equal(s.moves, win);
    assert.equal(h.rendered.count, win.length);
    s.undo();
    assert.equal(s.state, 'playing');
    s.move(win.at(-1));
    assert.equal(s.state, 'won');
    s.reset(kind === 'fixed' ? 'b' : '10x5b', kind === 'fixed' ? 2000 : 0);
    for (const move of 'dwas'.repeat(kind === 'fixed' ? 32 : 2)) s.move(move);
    assert.equal(s.state, 'limit');
    const limited = s.moves;
    s.move('d');
    assert.equal(s.moves, limited);
    s.undo();
    assert.equal(s.state, 'playing');
    for (const options of [{missingFont: true}, {outdatedFont: true}]) {
      const broken = harness(kind, options);
      await broken.session.ready;
      assert.equal(broken.session.state, 'error');
      broken.session.move('d');
      assert.equal(broken.session.moves, '');
      assert.ok(broken.buttons.every(b => b.disabled));
    }
    console.log(`${kind}: loading, keyboard guards, loss/win locking, Undo, reset, limits, and font failure checks passed`);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
