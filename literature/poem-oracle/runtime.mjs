// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// JavaScript supplies text and draws returned outlines. Selection is GSUB-only.
// Bound the number of outlines copied to the UI and rendered on each edit.
export const MAX_PARAGRAPHS = 16;

export function normalizeInput(text) {
  return String(text).replace(/\r\n|[\r\n\t]/g, ' ').normalize('NFC');
}

export function splitParagraphs(text) {
  return String(text).replace(/\r\n|\r/g, '\n')
    .split(/\n(?:[^\S\n]*\n)+/).filter(paragraph => paragraph.trim());
}

export async function sha256(bytes) {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2, '0')).join('');
}

export class PoemFont {
  static async create(hb, bytes, manifest) {
    if (await sha256(bytes) !== manifest.fontSha256) {
      throw new Error('Font and manifest differ. Rebuild or reload the matching files.');
    }
    return new PoemFont(hb, bytes, manifest);
  }

  constructor(hb, bytes, manifest) {
    this.hb = hb;
    this.manifest = manifest;
    this.alphabet = new Set(manifest.alphabet);
    this.panels = new Map(manifest.poems.map(p => [p.glyphId, p]));
    this.blob = new hb.Blob(bytes);
    this.face = new hb.Face(this.blob);
    this.font = new hb.Font(this.face);
    this.font.setScale(1000, 1000);
    this.buffer = new hb.Buffer();
    this.paths = new Map();
    for (const panel of manifest.poems) {
      if (this.font.glyphName(panel.glyphId) !== panel.glyph) {
        throw new Error('Font glyphs do not match the manifest.');
      }
    }
  }

  shapeParagraphs(raw, enabled = true) {
    const paragraphs = splitParagraphs(raw);
    if (!paragraphs.length) throw new Error('Type a word or paragraph to find a poem.');
    if ([...normalizeInput(raw)].length > this.manifest.maxInput) {
      throw new Error(`Use at most ${this.manifest.maxInput.toLocaleString()} characters in total.`);
    }
    if (paragraphs.length > MAX_PARAGRAPHS) {
      throw new Error(`Use at most ${MAX_PARAGRAPHS} paragraphs at a time.`);
    }
    const results = paragraphs.map((paragraph, index) => {
      try {
        return this.shape(paragraph, enabled);
      } catch (error) {
        throw new Error(`Paragraph ${index+1}: ${error.message}`);
      }
    });
    return {paragraphs: results};
  }

  shape(raw, enabled = true) {
    const text = normalizeInput(raw);
    if (!text.trim()) throw new Error('Type a word or paragraph to find a poem.');
    if ([...text].length > this.manifest.maxInput) {
      throw new Error(`Use at most ${this.manifest.maxInput.toLocaleString()} characters.`);
    }
    const unsupported = [...new Set([...text].filter(c => !this.alphabet.has(c)))];
    if (unsupported.length) {
      throw new Error(`This prototype supports Latin letters and common punctuation. Remove: ${unsupported.slice(0, 6).join(' ')}`);
    }
    const hb = this.hb;
    this.buffer.reset();
    this.buffer.addText(text);
    this.buffer.setDirection(hb.Direction.LTR);
    this.buffer.setScript('Latn');
    this.buffer.setLanguage('en');
    const start = performance.now();
    hb.shape(this.font, this.buffer, [new hb.Feature('rlig', enabled ? 1 : 0)]);
    const glyphs = this.buffer.getGlyphInfosAndPositions();
    const selected = glyphs.filter(g => this.panels.has(g.codepoint));
    const elapsed = performance.now()-start;
    if (!enabled) {
      if (selected.length) throw new Error('Disabling computation still produced a poem.');
      return {text, panel: null, glyphCount: glyphs.length, elapsed};
    }
    if (selected.length !== 1 || glyphs.some(g => !this.panels.has(g.codepoint) &&
        (this.font.glyphName(g.codepoint) !== 'ghost' || g.xAdvance !== 0))) {
      throw new Error('The font did not finish selecting a poem. Try a shorter input.');
    }
    const glyph = selected[0];
    if (!this.paths.has(glyph.codepoint)) {
      this.paths.set(glyph.codepoint, this.font.glyphToPath(glyph.codepoint));
    }
    return {text, panel: this.panels.get(glyph.codepoint),
      path: this.paths.get(glyph.codepoint), glyphCount: glyphs.length, elapsed};
  }
}
