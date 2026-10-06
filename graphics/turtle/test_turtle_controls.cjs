// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Integration checks read the terminal advance from the actual bundled font.
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const {turtleProgram, TURTLE_EXAMPLES, createTurtlePlayground} = require('./turtle-controls.js');

function harness({missingFont = false, incompatibleFont = false, rejectedFont = false} = {}) {
  const elements = {};
  function element() {
    return {value: '', textContent: '', attributes: {}, listeners: {},
      append() {}, setAttribute(name, value) { this.attributes[name] = value; },
      addEventListener(name, listener) { this.listeners[name] = listener; },
      getBoundingClientRect() {
        if (incompatibleFont) return {width: 0};
        const output = execFileSync('hb-shape', [path.join(__dirname, 'turtle-font.ttf'),
          this.textContent, '--output-format=json'], {encoding: 'utf8'});
        return {width: JSON.parse(output).reduce((total, glyph) => total + glyph.ax, 0)};
      },
    };
  }
  for (const id of ['program', 'drawing', 'raw', 'status', 'count', 'undo', 'reset', 'load-example', 'example']) {
    elements[id] = element();
  }
  elements.example.value = 'square';
  const buttons = [...'flrud012345'].map(command => ({dataset: {command}}));
  global.document = {
    body: {append() {}}, createElement: element,
    querySelector: selector => elements[selector.slice(1)],
    querySelectorAll: () => buttons,
    fonts: {load: async () => {
      if (rejectedFont) throw new Error('Font load failed');
      return missingFont ? [] : [{}];
    }},
  };
  let keydown;
  global.addEventListener = (_, listener) => { keydown = listener; };
  const session = createTurtlePlayground();
  return {session, elements, buttons,
    input(value) { elements.program.value = value; elements.program.listeners.input(); },
    key(key, {editable = false, focusedButton = false, ctrlKey = false, metaKey = false, altKey = false} = {}) {
      let prevented = false;
      keydown({key, ctrlKey, metaKey, altKey,
        target: {closest: selector => editable ||
          (focusedButton && selector.split(',').some(part => part.trim() === 'button')) ? {} : null},
        preventDefault() { prevented = true; },
      });
      return prevented;
    },
  };
}

(async () => {
  assert.equal(turtleProgram(' B F\nL\tR U D '), 'flrud');
  assert.equal(turtleProgram(''), '');
  assert.equal(turtleProgram('b'), '');
  assert.throws(() => turtleProgram('ffb'), /Use F/);
  assert.throws(() => turtleProgram('f6'), /Use F/);
  assert.equal(turtleProgram('B 1 F 2 F 0'), '1f2f0');
  assert.throws(() => turtleProgram('f'.repeat(129)), /at most 128/);
  assert.equal(turtleProgram('l'.repeat(128)).length, 128);

  const h = harness(), s = h.session, e = h.elements;
  s.move('f');
  assert.equal(e.program.value, '', 'Ignore commands while loading');
  await s.ready;
  assert.equal(s.state, 'ready');
  assert.equal(e.raw.textContent, 'b');
  assert.ok(e.undo.disabled);
  for (const guard of [{editable: true}, {ctrlKey: true}, {metaKey: true}, {altKey: true}]) h.key('F', guard);
  assert.equal(e.program.value, '');
  h.key('F'); h.key('ArrowLeft'); h.key('U');
  assert.equal(e.raw.textContent, 'bflu');
  h.buttons.find(button => button.dataset.command === 'd').onclick();
  assert.equal(e.raw.textContent, 'bflud');
  e.undo.onclick();
  assert.equal(e.raw.textContent, 'bflu');
  e.reset.onclick();
  assert.equal(e.raw.textContent, 'b');
  const buttonFocus = {focusedButton: true};
  h.buttons.find(button => button.dataset.command === '1').onclick();
  assert.equal(h.key('F', buttonFocus), true);
  h.key('ArrowLeft', buttonFocus); h.key('3', buttonFocus); h.key('F', buttonFocus);
  assert.equal(e.raw.textContent, 'b1fl3f', 'Shortcuts work with a focused color button');
  e.undo.onclick(); h.key('R', buttonFocus);
  assert.equal(e.raw.textContent, 'b1fl3r', 'Shortcuts work after clicking Undo');
  e.reset.onclick(); h.key('F', buttonFocus);
  assert.equal(e.raw.textContent, 'bf', 'Shortcuts work after clicking Reset');
  h.buttons.find(button => button.dataset.command === 'l').onclick();
  h.key('U', buttonFocus);
  assert.equal(e.raw.textContent, 'bflu', 'Shortcuts work with a focused movement button');
  assert.equal(h.key('Enter', buttonFocus), false, 'Preserve native button activation');
  assert.equal(h.key(' ', buttonFocus), false, 'Preserve native button activation');
  assert.equal(e.raw.textContent, 'bflu');
  for (const guard of [{editable: true}, {ctrlKey: true}, {metaKey: true}, {altKey: true}]) {
    assert.equal(h.key('F', {...buttonFocus, ...guard}), false);
  }
  assert.equal(e.raw.textContent, 'bflu', 'Keep editable and modifier guards');
  e.reset.onclick();
  h.buttons.find(button => button.dataset.command === '1').onclick();
  h.key('F'); h.key('2'); h.key('F');
  assert.equal(e.raw.textContent, 'b1f2f');
  e.undo.onclick(); e.undo.onclick();
  assert.equal(e.raw.textContent, 'b1f', 'Undo removes a color change as one command');
  e.reset.onclick();
  h.input('1'.repeat(128));
  assert.equal(s.state, 'limit', 'Color changes count toward the limit');
  e.undo.onclick();
  assert.equal(s.state, 'ready');
  e.reset.onclick();

  h.input('f'.repeat(11));
  assert.equal(s.state, 'blocked');
  assert.ok(h.buttons.every(button => button.disabled));
  s.move('l');
  assert.equal(e.program.value.length, 11);
  e.undo.onclick();
  assert.equal(s.state, 'ready');
  h.input('lr'.repeat(64));
  assert.equal(s.state, 'limit');
  s.move('f');
  assert.equal(e.program.value.length, 128);
  e.undo.onclick();
  assert.equal(s.state, 'ready');

  const previous = e.raw.textContent;
  h.input('f!');
  assert.equal(s.state, 'error');
  assert.equal(e.program.attributes['aria-invalid'], 'true');
  assert.equal(e.raw.textContent, previous, 'Invalid edits keep the last drawing');
  h.input('r'.repeat(129));
  assert.equal(s.state, 'error');
  e.reset.onclick();
  assert.equal(s.state, 'ready');
  h.input(' B F\nL U\tF D F ');
  assert.equal(e.raw.textContent, 'bflufdf');
  assert.equal(e.program.attributes['aria-invalid'], 'false');
  for (const name of Object.keys(TURTLE_EXAMPLES)) {
    e.example.value = name;
    e['load-example'].onclick();
    assert.equal(s.state, 'ready', `${name} stays within the canvas and limit`);
    assert.equal(e.raw.textContent, 'b' + turtleProgram(TURTLE_EXAMPLES[name]));
  }
  for (const options of [{missingFont: true}, {incompatibleFont: true}, {rejectedFont: true}]) {
    const broken = harness(options);
    await broken.session.ready;
    assert.equal(broken.session.state, 'error');
    assert.ok(broken.buttons.every(button => button.disabled));
    broken.session.move('f');
    assert.equal(broken.elements.program.value, '');
  }
  console.log('Turtle controls: input, examples, keyboard guards, focused-button shortcuts, boundary/limit locking, Undo, reset, and font failures passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
