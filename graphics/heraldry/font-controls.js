// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
(() => {
  'use strict';
  const get = id => document.getElementById(id);
  const source = get('source'), drawing = get('drawing');
  const builderControls = ['division', 'first', 'second', 'device', 'device-color', 'count'];
  let builderEnabled = true, sourceRevision = 0, copyRequest = 0;
  const tinctures = ['Or', 'Argent', 'Azure', 'Gules', 'Sable', 'Vert', 'Purpure'];
  const plurals = {mullet:'mullets', lozenge:'lozenges', crescent:'crescents',
    heart:'hearts', 'fleur-de-lis':'fleurs-de-lis', 'lion rampant':'lions rampant'};
  const examples = [
    ['A golden chevron', '[Azure, a chevron Or]'],
    ['Three stars', '[Gules, three mullets Argent]'],
    ['A divided field', '[Per pale Argent and Azure, a fleur-de-lis Or]'],
    ['A rampant lion', '[Sable, a lion rampant Or]'],
    ['Four quarters', '[Quarterly Or and Gules]'],
    ['Three crescents', '[Vert, three crescents Argent]'],
    ['A saltire', '[Azure, a saltire Argent]'],
    ['A silver border', '[Purpure, a bordure Argent]'],
  ];
  for (const select of document.querySelectorAll('.tincture')) {
    for (const name of tinctures) select.add(new Option(name, name));
  }
  get('first').value = 'Azure'; get('second').value = 'Argent';
  get('device-color').value = 'Or';

  function render() {
    sourceRevision += 1;
    drawing.textContent = source.value;
    get('copy-status').textContent = '';
  }
  function updateAvailability() {
    for (const id of builderControls) get(id).disabled = !builderEnabled;
    get('builder-status').hidden = builderEnabled;
    get('second-row').hidden = !get('division').value;
    const device = get('device').value;
    get('device-color').disabled = !builderEnabled || !device;
    get('count').disabled = !builderEnabled || !Object.hasOwn(plurals, device);
    if (!Object.hasOwn(plurals, device)) get('count').value = '1';
  }
  function compose() {
    if (!builderEnabled) return;
    updateAvailability();
    const division = get('division').value, device = get('device').value;
    let text = division ? `${division} ${get('first').value} and ${get('second').value}` : get('first').value;
    if (device) {
      text += get('count').value === '3' ? `, three ${plurals[device]}` : `, a ${device}`;
      text += ` ${get('device-color').value}`;
    }
    source.value = `[${text}]`; render();
  }
  // Synchronising controls after typing never changes the user's source.
  function syncBuilder() {
    // Validate gaps and individual word casing before canonicalizing for controls.
    // The original source, including NBSP and repeated spaces, stays untouched.
    const gaps = source.value.match(/[ \u00a0]+/g) || [];
    if (gaps.some(gap => gap !== '\u00a0' && !/^ {1,3}$/.test(gap))) return false;
    const words = source.value.match(/[a-z-]+/gi) || [];
    if (words.some(word => ![word.toLowerCase(), word.toUpperCase(),
      word[0].toUpperCase()+word.slice(1).toLowerCase()].includes(word))) return false;
    const text = source.value.replace(/ {1,3}|\u00a0/g, ' ').toLowerCase();
    const match = text.match(/^\[(?:(per pale|per fess|per bend sinister|per bend|per chevron|per saltire|quarterly) )?(or|argent|azure|gules|sable|vert|purpure)(?: and (or|argent|azure|gules|sable|vert|purpure))?(?:(?:, ?| )(a|three) ([a-z -]+?) (or|argent|azure|gules|sable|vert|purpure))?\]$/);
    if (!match) return false;
    const [ , division, first, second, number, device, color] = match;
    const title = text => text[0].toUpperCase()+text.slice(1).toLowerCase();
    if (Boolean(division) !== Boolean(second)) return false;
    const singular = number?.toLowerCase() === 'three'
      ? Object.keys(plurals).find(key => plurals[key] === device.toLowerCase()) : device?.toLowerCase();
    if (device && ![...get('device').options].some(option => option.value === singular)) return false;
    get('division').value = division ? title(division) : '';
    get('first').value = title(first);
    if (second) get('second').value = title(second);
    get('device').value = singular || '';
    if (color) get('device-color').value = title(color);
    get('count').value = number === 'three' ? '3' : '1';
    return true;
  }
  function sourceChanged() {
    render();
    drawing.classList.toggle('off', !get('ligatures').checked);
    builderEnabled = syncBuilder();
    updateAvailability();
  }
  source.addEventListener('input', sourceChanged);
  for (const id of builderControls) {
    get(id).addEventListener('change', compose);
  }
  get('ligatures').addEventListener('change', () => {
    drawing.classList.toggle('off', !get('ligatures').checked);
  });
  get('copy').addEventListener('click', async () => {
    // Copy source directly: colour glyph components have separate text clusters.
    const text = source.value;
    const revision = sourceRevision, request = ++copyRequest;
    const current = () => revision === sourceRevision && request === copyRequest;
    try {
      await navigator.clipboard.writeText(text);
      if (current()) get('copy-status').textContent = 'Blazon copied.';
    } catch {
      if (!current()) return;
      source.focus(); source.select();
      get('copy-status').textContent = 'Blazon selected in the editor. Use your usual Copy command.';
    }
  });
  for (const [label, text] of examples) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'example';
    button.setAttribute('aria-label', `Edit ${label.toLowerCase()}: ${text}`);
    const shield = document.createElement('span'); shield.className = 'heraldry';
    shield.textContent = text; shield.setAttribute('aria-hidden', 'true');
    const title = document.createElement('strong'); title.textContent = label;
    const blazon = document.createElement('span'); blazon.className = 'blazon'; blazon.textContent = text;
    button.append(shield, title, blazon);
    button.addEventListener('click', () => {source.value = text; sourceChanged(); source.focus();});
    get('examples').append(button);
  }
  sourceChanged();
  window.addEventListener('pageshow', sourceChanged);
  document.fonts.load('200px Heraldry', '[Azure, a chevron Or]').then(fonts => {
    if (!fonts.length) throw new Error('Font unavailable');
    get('status').textContent = 'Heraldry font ready. Edit the blazon or choose an example.';
  }).catch(() => {
    get('status').classList.add('error');
    get('status').textContent = 'The font could not load. Serve the repository locally and reload.';
  });
})();
