// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
import {PoemFont} from './runtime.mjs';
const engine = import('../../languages/shared/vendor/harfbuzzjs/index.mjs');
let font;
self.onmessage = async ({data}) => {
  const {id, action} = data;
  try {
    if (action === 'load') {
      const hb = await engine;
      font = await PoemFont.create(hb, data.bytes, data.manifest);
      self.postMessage({id, version: hb.versionString()});
    } else if (action === 'shape') {
      if (!font) throw new Error('The font is still loading.');
      self.postMessage({id, ...font.shapeParagraphs(data.text, data.enabled)});
    }
  } catch (error) {
    self.postMessage({id, error: error.message});
  }
};
