// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
import {normalizeInput, sha256, splitParagraphs} from './runtime.mjs';

const $ = id => document.getElementById(id);
const examples = {
  word: 'serendipity', phrase: 'after the rain',
  paragraph: 'There is a quiet hour before the city wakes. I open the window, let the cool air in, and wonder how many small things I walked past yesterday without noticing.',
  paragraphs: 'There is a quiet hour before the city wakes. I open the window, let the cool air in.\n\nLater, the rain stops. Someone is laughing in the street, and the whole afternoon feels new.'
};
let worker, manifest, poems, sources, current = [], ready = false, revision = 0, timer, nextId = 0;
const pending = new Map();
function request(action, data) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    pending.set(id, {resolve, reject});
    worker.postMessage({id, action, ...data});
  });
}
function status(message, error = false) {
  $('status').textContent = message;
  $('status').dataset.state = error ? 'error' : 'ready';
}
function clear(message) {
  current = [];
  $('poem-results').replaceChildren();
  $('poem-results').hidden = true;
  $('empty-result').hidden = false;
  $('disabled-text').hidden = true;
  $('placeholder').hidden = false;
  $('placeholder').textContent = message;
  $('copy-all').hidden = true;
  $('copy-all').disabled = true;
  $('reader').replaceChildren();
  $('reader').hidden = true;
  $('reader-prompt').hidden = false;
  $('poem-number').textContent = `— / ${manifest?.count ?? 2876}`;
  $('shaping-info').textContent = '';
  $('stage').setAttribute('aria-busy', 'false');
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function poemText(poem) {
  return `${poem.title}\n\n${poem.text}\n\n${poem.author}`;
}
async function copyText(text, message) {
  try {
    await navigator.clipboard.writeText(text);
    status(message);
  } catch {
    status('Clipboard unavailable. Open “Read as selectable text” to copy the poems.', true);
  }
}
function poemCard(result, poem, index, multiple) {
  const {panel} = result;
  const card = element('section', 'result');
  card.setAttribute('aria-label', `Poem for paragraph ${index+1}`);
  const heading = element('div', 'result-head');
  const label = element('span', '', multiple ? `Paragraph ${index+1}, revealed` : 'Your words, revealed');
  const dot = element('span', 'dot');
  dot.setAttribute('aria-hidden', 'true');
  label.prepend(dot);
  heading.append(label, element('span', 'poem-number', `${panel.index+1} / ${manifest.count}`));
  const stage = element('div', 'poem-stage');
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.classList.add('poem-svg');
  svg.setAttribute('role', 'img');
  svg.setAttribute('viewBox', `0 0 ${panel.width} ${panel.height}`);
  svg.style.width = `${panel.width*18/manifest.bodyCap}px`;
  const title = document.createElementNS(ns, 'title');
  title.id = `poem-title-${index+1}`;
  title.textContent = `${poem.title} — ${poem.author}`;
  const description = document.createElementNS(ns, 'desc');
  description.id = `poem-desc-${index+1}`;
  description.textContent = poem.text;
  svg.setAttribute('aria-labelledby', title.id);
  svg.setAttribute('aria-describedby', description.id);
  const group = document.createElementNS(ns, 'g');
  group.setAttribute('transform', `translate(0 ${panel.height}) scale(1 -1)`);
  const path = document.createElementNS(ns, 'path');
  path.setAttribute('d', result.path);
  group.append(path);
  svg.append(title, description, group);
  stage.append(svg);
  const footer = element('div', 'result-foot');
  const source = sources.find(s => s.id === poem.source_id);
  const link = element('a', '', 'Read the source ↗');
  link.href = source.text_url + (source.anchor_kind === 'id' ? `#${encodeURIComponent(poem.source_anchor)}` : '');
  link.target = '_blank'; link.rel = 'noopener';
  const copy = element('button', 'text-button', 'Copy poem text');
  copy.type = 'button';
  copy.setAttribute('aria-label', `Copy poem for paragraph ${index+1}`);
  copy.addEventListener('click', () => copyText(poemText(poem), `Poem ${index+1} copied.`));
  footer.append(link, copy);
  card.append(heading, stage, footer);
  return card;
}

async function render(turn) {
  if (!ready || turn !== revision) return;
  const text = $('seed').value;
  $('normalized').textContent = splitParagraphs(text).map(normalizeInput).join('\n\n');
  if (!text.trim()) {
    clear('A word is enough to begin.');
    status('Type a word or paragraph to reveal a poem.');
    return;
  }
  $('stage').setAttribute('aria-busy', 'true');
  try {
    const result = await request('shape', {text, enabled: $('enabled').checked});
    if (turn !== revision) return;
    if (!$('enabled').checked) {
      clear('');
      $('placeholder').hidden = true;
      $('disabled-text').hidden = false;
      $('disabled-text').textContent = result.paragraphs.map(p => p.text).join('\n\n');
      status('Font computation is off. No poem glyphs were produced.');
      return;
    }
    const selected = result.paragraphs.map(paragraph => {
      const {panel} = paragraph;
      const poem = panel && poems[panel.index];
      if (!poem || panel.poemId !== poem.id) throw new Error('The poem corpus and font differ. Reload the page.');
      return poem;
    });
    const multiple = selected.length > 1;
    const cards = result.paragraphs.map((paragraph, index) => poemCard(paragraph, selected[index], index, multiple));
    const reader = selected.map((poem, index) => {
      const block = element('section', 'reader-poem');
      if (multiple) block.append(element('p', 'small-label', `Paragraph ${index+1}`));
      block.append(element('p', 'reader-title', poem.title), element('pre', 'reader', poem.text),
                   element('p', 'reader-author', poem.author));
      return block;
    });
    current = selected;
    $('poem-results').replaceChildren(...cards);
    $('poem-results').dataset.multiple = String(multiple);
    $('poem-results').hidden = false;
    $('empty-result').hidden = true;
    $('stage').setAttribute('aria-busy', 'false');
    $('copy-all').hidden = !multiple;
    $('copy-all').disabled = false;
    $('reader').replaceChildren(...reader);
    $('reader').hidden = false;
    $('reader-prompt').hidden = true;
    $('shaping-info').textContent = result.paragraphs.map((paragraph, index) =>
      `Paragraph ${index+1}: ${paragraph.glyphCount} shaped glyphs → ${paragraph.panel.glyph}. HarfBuzz: ${paragraph.elapsed.toFixed(1)} ms.`).join(' ');
    status(multiple ? `${selected.length} paragraphs · ${selected.length} poems · selected by the font` :
      `${selected[0].author} · ${selected[0].line_count} lines · selected by the font`);
  } catch (error) {
    if (turn !== revision) return;
    clear('A little change is needed.');
    status(error.message, true);
  }
}
function schedule() {
  const turn = ++revision;
  clearTimeout(timer);
  $('seed').dataset.multiple = String(splitParagraphs($('seed').value).length > 1);
  $('length').textContent = `${[...normalizeInput($('seed').value)].length.toLocaleString()} / 4,096`;
  document.querySelectorAll('[data-example]').forEach(button => {
    button.setAttribute('aria-pressed', String(examples[button.dataset.example] === $('seed').value));
  });
  timer = setTimeout(() => render(turn), 100);
}
$('seed').addEventListener('input', schedule);
$('enabled').addEventListener('change', schedule);
document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => {
  $('seed').value = examples[button.dataset.example];
  schedule();
}));
$('copy-all').addEventListener('click', () => {
  if (current.length) copyText(current.map(poemText).join('\n\n\n'), 'All poem texts copied.');
});

async function load() {
  try {
    if (location.protocol === 'file:') throw new Error('Serve the repository with python3 -m http.server 8000, then open http://localhost:8000/literature/poem-oracle/playground.html.');
    worker = new Worker(new URL('./worker.mjs', import.meta.url), {type: 'module'});
    worker.onmessage = ({data}) => {
      const promise = pending.get(data.id);
      if (!promise) return;
      pending.delete(data.id);
      if (data.error) promise.reject(new Error(data.error)); else promise.resolve(data);
    };
    worker.onerror = () => {
      const error = new Error('The shaping engine could not start. Reload the page from a local server.');
      for (const promise of pending.values()) promise.reject(error);
      pending.clear();
      ready = false;
      clear('The library could not open.');
      status(error.message, true);
    };
    const paths = ['poem-oracle.ttf', 'poem-oracle.json', 'poems.json', 'sources.json'];
    const responses = await Promise.all(paths.map(async path => {
      const response = await fetch(new URL(path, import.meta.url));
      if (!response.ok) throw new Error(`Could not load ${path} (${response.status}).`);
      return response.arrayBuffer();
    }));
    const decode = bytes => JSON.parse(new TextDecoder().decode(bytes));
    manifest = decode(responses[1]); poems = decode(responses[2]); sources = decode(responses[3]);
    if (await sha256(responses[2]) !== manifest.corpusSha256 || poems.length !== manifest.count) {
      throw new Error('The poem collection does not match the font. Rebuild or reload the page.');
    }
    await request('load', {bytes: responses[0], manifest});
    ready = true;
    $('poem-count').textContent = manifest.count;
    $('author-count').textContent = new Set(poems.map(p => p.author)).size;
    schedule();
  } catch (error) {
    clear('The library could not open.');
    status(error.message, true);
  }
}
load();
