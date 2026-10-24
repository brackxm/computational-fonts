// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import test from 'node:test';
import * as hb from '../../languages/shared/vendor/harfbuzzjs/index.mjs';
import {MAX_PARAGRAPHS, normalizeInput, PoemFont, splitParagraphs} from './runtime.mjs';

const root = new URL('./', import.meta.url);
const bytes = await fs.readFile(new URL('poem-oracle.ttf', root));
const manifest = JSON.parse(await fs.readFile(new URL('poem-oracle.json', root), 'utf8'));
const font = await PoemFont.create(hb, bytes, manifest);
// Reference fixtures are calculated by Python, independently of browser code.
const oracle = spawnSync('python3', ['-c', `
import itertools,json,string,sys
sys.path.insert(0,sys.argv[1])
from model import select_index
count=int(sys.argv[2]); seeds={}
for a,b in itertools.product(string.ascii_letters+string.digits+string.punctuation,repeat=2):
 s=a+b; seeds.setdefault(select_index(s,count),s)
print(json.dumps([[s,i] for i,s in seeds.items()]))
`, new URL('.', root).pathname, String(manifest.count)], {encoding: 'utf8'});
assert.equal(oracle.status, 0, oracle.stderr);
const fixtures = JSON.parse(oracle.stdout);

test('browser HarfBuzz reaches every poem and returns real font outlines', () => {
  assert.equal(fixtures.length, manifest.count);
  for (const [seed, index] of fixtures) {
    const result = font.shape(seed);
    assert.equal(result.panel.index, index, seed);
    assert.equal(result.panel.poemId, manifest.poems[index].poemId);
    assert.match(result.path, /[MLQC]/);
    assert.ok(result.path.length > 100);
  }
});

test('word, multiline paragraph, accents and the maximum length shape deterministically', () => {
  for (const seed of ['hope', 'There is a quiet hour.\nI open the window.\tLet the air in.',
    'café — déjà vu', 'a'.repeat(4096)]) {
    const first = font.shape(seed);
    assert.equal(first.panel.index, font.shape(seed).panel.index);
    assert.equal(first.text, normalizeInput(seed));
    assert.equal(font.shape(seed, false).panel, null);
  }
  assert.equal(font.shape('café').panel.index, font.shape('cafe\u0301').panel.index);
  assert.equal(font.shape('a\nb').panel.index, font.shape('a b').panel.index);
});

test('empty, unsupported and overlong input fail explicitly', () => {
  assert.throws(() => font.shape(' \n\t '), /Type a word/);
  assert.throws(() => font.shape('hello 🌷'), /Remove: 🌷/);
  assert.throws(() => font.shape('a'.repeat(4097)), /4,096/);
});

test('a mismatched font is rejected before shaping', async () => {
  await assert.rejects(PoemFont.create(hb, bytes, {...manifest, fontSha256: '0'.repeat(64)}), /differ/);
});

test('blank lines separate paragraphs while single newlines stay in one paragraph', () => {
  assert.deepEqual(splitParagraphs('first line\nsecond line\n\nlast paragraph'),
    ['first line\nsecond line', 'last paragraph']);
  assert.deepEqual(splitParagraphs('\r\n\r\nfirst\r\n \t\r\n\r\nsecond\r\n\r\n'), ['first', 'second']);
  assert.deepEqual(splitParagraphs(' \n\t\n '), []);
});

test('each paragraph is shaped independently, in order, and repeated paragraphs are retained', () => {
  const result = font.shapeParagraphs('hope\n\ncafé\n\nhope');
  assert.equal(result.paragraphs.length, 3);
  for (const [index, seed] of ['hope', 'café', 'hope'].entries()) {
    assert.equal(result.paragraphs[index].panel.index, font.shape(seed).panel.index);
    assert.equal(result.paragraphs[index].path, font.shape(seed).path);
  }
  const changed = font.shapeParagraphs('a different first paragraph\n\ncafé\n\nhope');
  assert.equal(changed.paragraphs[1].panel.index, result.paragraphs[1].panel.index);
  assert.equal(changed.paragraphs[2].panel.index, result.paragraphs[2].panel.index);
  assert.equal(font.shapeParagraphs('a\nb').paragraphs.length, 1);
  assert.equal(font.shapeParagraphs('a\nb').paragraphs[0].panel.index, font.shape('a b').panel.index);
});

test('paragraph batches preserve boundaries with computation off and report errors by paragraph', () => {
  const result = font.shapeParagraphs('a\nb\n\nc', false);
  assert.deepEqual(result.paragraphs.map(p => p.text), ['a b', 'c']);
  assert.ok(result.paragraphs.every(p => p.panel === null));
  assert.throws(() => font.shapeParagraphs('hope\n\n🌷'), /Paragraph 2:.*Remove: 🌷/);
  assert.throws(() => font.shapeParagraphs(' \n\n '), /Type a word/);
  assert.throws(() => font.shapeParagraphs('a'.repeat(2048)+'\n\n'+'b'.repeat(2048)), /4,096.*total/);
});

test('paragraph limit accepts the boundary and rejects oversized batches before shaping', t => {
  const atLimit = Array(MAX_PARAGRAPHS).fill('a').join('\n\n');
  assert.equal(font.shapeParagraphs(`\n\n${atLimit}\n\n`).paragraphs.length, MAX_PARAGRAPHS);
  assert.equal(font.shapeParagraphs(atLimit, false).paragraphs.length, MAX_PARAGRAPHS);

  const shape = t.mock.method(font, 'shape', () => assert.fail('Oversized batches must not shape any paragraphs'));
  for (const count of [MAX_PARAGRAPHS + 1, 1365]) {
    const text = Array(count).fill('a').join('\n\n');
    assert.ok(text.length <= manifest.maxInput);
    for (const enabled of [true, false]) {
      assert.throws(() => font.shapeParagraphs(text, enabled),
        {message: `Use at most ${MAX_PARAGRAPHS} paragraphs at a time.`});
    }
  }
  assert.equal(shape.mock.callCount(), 0);
});
