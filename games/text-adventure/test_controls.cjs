// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
const assert = require('node:assert/strict');
const {createAdventureSession} = require('./controls.js');
const renders = [];
const game = createAdventureSession({onRender: (text, count) => renders.push({text, count})});
assert.deepEqual(renders.at(-1), {text: 'start;', count: 0});
game.enter('  TAKE   KEY  ');
game.enter('northgarbage'); // Semantic validation belongs entirely to the font.
assert.equal(game.text(), 'start;take key;northgarbage;');
game.undo();
assert.equal(game.text(), 'start;take key;');
game.restore('START;EAST;TAKE KEY;');
assert.equal(game.text(), 'start;east;take key;');
for (const value of ['', 'xstart;east;', 'start;north', 'start;;', 'start;;east;', 'start;north;é;', 'start;xxxxxxxxxxxxxxxxxxxxxxxxx;']) {
  const previous = game.text();
  assert.throws(() => game.restore(value));
  assert.equal(game.text(), previous, 'A rejected restore must preserve the journey');
}
for (const value of ['', 'north;south', 'é', 'x'.repeat(25), 'north\nsouth']) {
  const previous = game.text();
  assert.throws(() => game.enter(value));
  assert.equal(game.text(), previous);
}
game.restore('start;');
assert.equal(game.text(), 'start;');
for (let i = 0; i < 128; i++) game.enter('look');
assert.equal(renders.at(-1).count, 128);
assert.throws(() => game.enter('east'));
assert.throws(() => game.restore(`start;${'look;'.repeat(129)}`));
assert.equal(renders.at(-1).count, 128);
game.undo(); game.enter('east');
assert.equal(renders.at(-1).count, 128);
game.reset(); game.undo();
assert.deepEqual(renders.at(-1), {text: 'start;', count: 0});
console.log('Adventure controls: input, undo, restore and command-limit checks passed.');
