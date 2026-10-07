// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// This controller edits input text only. The font evaluates every game rule.
(function (root) {
  'use strict';
  const MAX_COMMANDS = 128;
  const MAX_LENGTH = 24;
  function normalizeCommand(value) {
    const command = String(value).trim().toLowerCase().replace(/ +/g, ' ');
    if (!command || command.length > MAX_LENGTH || !/^[\x20-\x7e]+$/.test(command) || command.includes(';')) {
      throw new Error('Enter one command of 1–24 ASCII characters, without a semicolon.');
    }
    return command;
  }
  function createAdventureSession({onRender = () => {}} = {}) {
    let commands = [];
    const text = () => `start;${commands.map(command => `${command};`).join('')}`;
    const render = () => onRender(text(), commands.length);
    const session = {
      text,
      enter(value) {
        const command = normalizeCommand(value);
        if (commands.length >= MAX_COMMANDS) throw new Error('This journey has reached 128 commands. Undo or start a new game.');
        commands.push(command); render();
      },
      undo() { commands.pop(); render(); },
      reset() { commands = []; render(); },
      restore(value) {
        const saved = String(value).trim();
        if (!/^start;/i.test(saved) || !saved.endsWith(';'))
          throw new Error('A journey must begin with start; and end with a semicolon.');
        const restored = saved.slice(6, -1);
        const next = saved.length === 6 ? [] : restored.split(';').map(normalizeCommand);
        if (next.length > MAX_COMMANDS) throw new Error('A journey can contain at most 128 commands.');
        commands = next; render();
      },
    };
    render();
    return session;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {createAdventureSession};
  else root.createAdventureSession = createAdventureSession;
})(typeof globalThis !== 'undefined' ? globalThis : this);
