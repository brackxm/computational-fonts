// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
import {RegisterFont} from './runtime.mjs';

// Install the message handler before HarfBuzz's asynchronous Wasm startup.
// A static import with top-level await can otherwise lose the first message.
const engine = import('../vendor/harfbuzzjs/index.mjs');
let font;
self.onmessage = async ({data}) => {
  const {id, action} = data;
  try {
    const hb = await engine;
    if (action === 'load') {
      font = await RegisterFont.create(hb, data.bytes, data.manifest);
      self.postMessage({id, action, version: hb.versionString()});
    } else if (action === 'run') {
      if (!font) throw new Error('Load a font before running it.');
      self.postMessage({id, action, ...font.invoke(data.args, data.enabled)});
    }
  } catch (error) {
    self.postMessage({id, action, error: {name: error.name, message: error.message}});
  }
};
