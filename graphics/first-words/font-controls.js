// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
'use strict';
(() => {
  const source = document.querySelector('#source');
  const drawing = document.querySelector('#drawing');
  const status = document.querySelector('#status');
  const size = document.querySelector('#size');
  const ligatures = document.querySelector('#ligatures');
  const words = document.querySelector('#words');
  const search = document.querySelector('#search');
  const category = document.querySelector('#category');
  const count = document.querySelector('#count');

  function update() {
    drawing.textContent = source.value;
    drawing.classList.toggle('ligatures-off', !ligatures.checked);
    drawing.style.setProperty('--picture-size', size.value + 'px');
    document.querySelector('#size-value').value = size.value + ' px';
  }
  function filter() {
    const query = search.value.trim().toLowerCase();
    let visible = 0;
    for (const card of words.children) {
      const item = window.FIRST_WORDS[Number(card.dataset.index)];
      card.hidden = !card.dataset.search.includes(query) ||
        (category.value !== '' && card.dataset.category !== category.value);
      const selected = item.spellings.includes(query) ? query : item.label;
      card.querySelector('.pictures').textContent = selected;
      card.querySelector('.label').textContent = selected;
      card.setAttribute('aria-label', 'Add ' + selected);
      if (!card.hidden) visible++;
    }
    count.textContent = visible + (visible === 1 ? ' drawing' : ' drawings');
  }
  source.addEventListener('input', update);
  size.addEventListener('input', update);
  ligatures.addEventListener('change', update);
  search.addEventListener('input', filter);
  category.addEventListener('change', filter);
  for (const button of document.querySelectorAll('[data-example]')) {
    button.addEventListener('click', () => {
      source.value = button.dataset.example;
      update();
    });
  }
  const categories = [...new Set(window.FIRST_WORDS.map(item => item.category))];
  for (const label of categories) {
    const option = document.createElement('option');
    option.value = option.textContent = label;
    category.append(option);
  }
  for (const [index, item] of window.FIRST_WORDS.entries()) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'word';
    button.dataset.index = index;
    button.dataset.search = item.spellings.join('\n');
    button.dataset.category = item.category;
    button.setAttribute('aria-label', 'Add ' + item.label);
    const picture = document.createElement('span');
    picture.className = 'pictures';
    picture.textContent = item.label;
    picture.setAttribute('aria-hidden', 'true');
    const label = document.createElement('span');
    label.className = 'label';
    label.textContent = item.label;
    button.append(picture, label);
    if (item.aliases.length) {
      const alternatives = document.createElement('span');
      alternatives.className = 'aliases';
      alternatives.textContent = 'Also: ' + item.aliases.join(', ');
      button.append(alternatives);
    }
    button.addEventListener('click', () => {
      const selectionStart = source.selectionStart;
      const selectionEnd = source.selectionEnd;
      const before = source.value.slice(0, selectionStart);
      const after = source.value.slice(selectionEnd);
      const query = search.value.trim().toLowerCase();
      const selected = item.spellings.includes(query) ? query : item.label;
      const inserted = (before && !/\s$/.test(before) ? ' ' : '') + selected +
        (after && !/^\s/.test(after) ? ' ' : '');
      source.setRangeText(inserted, selectionStart, selectionEnd, 'end');
      update();
      source.focus();
    });
    words.append(button);
  }
  update();
  filter();
  document.fonts.load('96px FirstWordsPictures', 'apple').then(faces => {
    if (!faces.length) throw new Error('Font was not available');
    const labels = window.FIRST_WORDS.reduce((total, item) => total + 1 + item.aliases.length, 0);
    status.textContent = 'Picture font ready · '+window.FIRST_WORDS.length+' drawings · '+labels+' labels · select “Show pictures” to compare text and images.';
  }).catch(() => {
    status.classList.add('error');
    status.textContent = 'The picture font could not load. Serve the repository with python3 -m http.server 8000, then open this page through localhost:8000.';
  });
})();
