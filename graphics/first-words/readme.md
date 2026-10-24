# First Words Pictures

Type `apple banana cat dog house ball` in **First Words Pictures** to display
six drawings. The font contains all 200 original illustrations as scalable
colour vectors, with stacked variants for countable plurals and monochrome
outline fallbacks.

Try [the font playground](playground.html), download the installable
[TTF](first-words-font.ttf), [WOFF2 webfont](first-words-font.woff2), or
[font bundle with vocabulary and notices](first-words-fonts.zip).

## Use the font

Install the TTF and choose **First Words Pictures**, Regular, with standard
ligatures enabled. A display size of 48–96 pt is a useful starting point.
Recognized whole words become pictures; unknown words retain their original
Roboto letters and capitalization. Copying preserves the original input.
No external images or script are needed to use the installed font.

- Matching is case-insensitive, including arbitrary mixed case.
- The 200 drawings accept 622 curated labels, including regional names, synonyms
  and plurals. For example, `sofa` / `couch`, `bicycle` / `bike`, `airplane` /
  `aeroplane` / `plane`, `fridge` / `refrigerator`, and `tooth` / `teeth`.
  Search either name in the word picker. See [primary labels](words.txt) and the
  [complete input-to-drawing mapping](aliases.tsv).
- Countable plurals use two diagonally stacked copies in the same glyph width:
  `apple` / `apples`, `cat` / `cats`, `chair` / `chairs`, `mouse` / `mice`,
  `foot` / `feet` and `tooth` / `teeth`. Plural synonyms use the same stack.
  Already grouped illustrations (`grapes`, `peas`, `blueberries`, `pancakes`)
  retain their existing layout. Uncountable words, `fish`, `sheep`, and
  plural-only names for one item (`trousers`, `pants`, `scissors`) also retain
  the original picture. Explicit countable units such as `loaves`,
  `cheese wedges` and `bars of soap` use stacks.
- Every spaced label accepts a single ordinary or non-breaking space, or
  hyphenated/joined spellings (`ice-cream`, `icecream`, `table-lamp`, `tablelamp`).
- Adjacent letters, digits, combining marks, underscores, apostrophes and hyphens
  block partial matches within a shaping run: `caterpillar`, `cat's`, `hot-dog`
  and `soapbox` stay text. Punctuation can surround a word: `(cat), apples!`.
- Keep words in one font/style run with standard ligatures (`liga`) enabled and
  no letter spacing. Some hosts split spaced compounds into separate runs; use
  a joined or hyphenated spelling there. Browser page text with explicit `liga`
  settings supports both spaced labels. Chrome canvas defaults can split them.
- Colour needs COLRv0 support. The same font includes monochrome line drawings
  when colour tables are unsupported. Other applications and PDF export are not
  guaranteed by the browser tests; avoid synthetic bold/italic for pictures.

Serve the repository root with `python3 -m http.server 8000` and open
`http://localhost:8000/graphics/first-words/playground.html`.
The page passes source text to the font unchanged. Its picture previews are font
glyphs, not substituted SVG or bitmap elements.

Open `index.html` in a browser to search by word, filter by category, enlarge an
illustration and download its SVG. The gallery works directly from disk with no
server, network requests or external dependencies.

## Files

- `first-words-font.ttf` / `.woff2`: installed and web versions of the same font.
- `first-words-font.fea`: generated, readable whole-word substitution program.
- `first-words-font.json`: font sizes, glyph/layer counts and content checksum.
- `build.py` / `svg_to_font.py`: word recognition and vector conversion builders.
- `bundles.py`: reproducible ZIP packaging with fixed entry metadata.
- `playground.html` / `font-controls.js`: actual-font demo and vocabulary picker.
- `words.txt` / `vocabulary.js`: labels and generated playground vocabulary.
- `aliases.json`: curated alternate labels and plurals for each drawing.
- `plurals.json`: explicit labels that select a stacked plural variant.
- `word_labels.py`: spelling expansion, plural selection and checks for ambiguous labels.
- `aliases.tsv`: every accepted input spelling, target drawing ID and layout.
- `artwork/`: 200 original SVGs with transparent backgrounds.
- `artwork/plurals/`: 191 derived SVGs, each with two diagonally stacked copies.
- `manifest.json`: labels, categories, palette, file names and source sizes.
- `previews/`: original drawings, stacked plurals and seven category sheets,
  all as SVG.
- `first-words-svg.zip`: SVG artwork, original gallery and artwork source only.
- `approved_samples.json`: the six original style studies approved in the chat.
- `generate_artwork.py`: the complete reproducible source geometry and exports.

## Vocabulary

| Category | Drawings |
| --- | ---: |
| Food | 40 |
| Animals | 40 |
| Home | 50 |
| Clothing and toys | 20 |
| Transport | 20 |
| Nature | 20 |
| Body | 10 |

These are manually curated familiar, drawable English nouns and noun phrases.
They are not a measured word-frequency ranking. Compound labels include
`ice cream`, `teddy bear`, `table lamp` and `bar of soap`. The 422 alternate
labels reuse these 200 original drawings. Countable plurals select 191
additional stacked picture glyphs. Alternate labels are explicitly curated in
`aliases.json`; `plurals.json` selects which ones use the stacked layout.
Space, hyphen, joined and non-breaking-space forms give 977 accepted spellings.
Some concepts are represented by conventional symbols (for example, a heart).
Recognition by children has not been empirically tested.

## Style

Every drawing uses a 160 × 160 viewBox, a shared 16-colour palette, and rounded
5-unit outlines. Decorative marks sometimes use narrower strokes. Assets use
flat colours, vector paths and primitive shapes; they contain no raster images,
gradients, embedded fonts, script or external resources. The canvas background
is transparent. The cream cards and labels belong to the previews only.

Most illustrations use only a small subset of the palette. Source SVGs retain
editable strokes. The font builder expands strokes into filled outlines using
Skia PathOps, applies SVG group transformations, and converts curves into
TrueType outlines while preserving fill/stroke paint order. No rasterization
is used in the font. Glyph geometry is shared where identical. The monochrome
fallback subtracts later fills from earlier ink and retains visible outlines.

The bundled font has 200 original picture glyphs and 191 stacked plural glyphs,
16 palette colours, 5,307 colour layers and 9,025 total glyphs including retained
Roboto text. The TTF is 1,609,992 bytes; the WOFF2 is 466,628 bytes. See the
generated JSON for exact build information. Plural words remain one glyph wide;
the stack is drawn as ordered vector layers, including an occluded monochrome
outline fallback. No raster images are embedded.

The apple, banana, cat, dog and house geometry is preserved from the original
approved six-drawing study. The ball is a revised striped beach ball: each
coloured panel and its outline share the same curves, without a centre button.

## Build

Create a Python virtual environment and install the pinned build dependencies:

```sh
python3 -m venv /tmp/first-words-build
/tmp/first-words-build/bin/python -m pip install -r graphics/first-words/requirements.txt
/tmp/first-words-build/bin/python graphics/first-words/build.py
```

This builds TTF, WOFF2, feature source, metadata, vocabulary and the font ZIP.
Both distribution ZIPs have fixed timestamps, permissions and entry ordering,
so unchanged inputs produce identical bundles.
`--output PATH` selects a different output TTF. `--base PATH` can select another
TrueType text base; its terms and compatibility must be checked separately.
The bundled build uses the pinned Apache-2.0 Roboto Regular in this repository.
It sets unrestricted font-embedding permissions and content-derived identity.

## Regenerate the artwork

With Python 3.10 or newer, from the repository root:

```sh
python3 graphics/first-words/generate_artwork.py
```

No Python packages are needed. `--output PATH` writes an independent export
folder. The generator checks the expected category and total counts, parses
every SVG, and rejects raster image, text, script or foreignObject elements
inside the standalone illustrations. Label validation runs before writing
assets. Obsolete derived plural SVGs and retired preview sheets are removed;
only current generated assets enter the bundle.

## Verification

```sh
/tmp/first-words-build/bin/python -m unittest discover -s graphics/first-words -p 'test_*.py'
```

Requires HarfBuzz's `hb-shape`. Checks all 622 labels in lower, upper, title and
mixed case; compound aliases; punctuation; rejected substrings; disabled
ligatures; colour/fallback outlines; attribution; webfont equivalence; and a
byte-identical rebuild. Export checks cover reproducible bundles, removed
plurals, invalid labels and retention of current notices in the font bundle.

The optional `test_browser.cjs` requires Playwright and a browser, with the local
server running. Run it with `node graphics/first-words/test_browser.cjs`;
`BROWSER_CHANNEL=chrome` selects installed Chrome. An optional first argument
overrides the playground URL; a second writes a screenshot. It verifies all
977 accepted spellings in browser page text, compares all 391 original/plural
font pictures against their SVG pixels, and exercises input, filtering, examples
and picture insertion, including the accessible names of synonym results.
For compound pixel checks, canvas uses the joined alias; original spaced
labels are independently checked in DOM text. Validation was completed in Chrome.

## License and provenance

The original artwork, source geometry, `generate_artwork.py` and annotations
are licensed under **Apache-2.0**; see `LICENSE.txt` and `NOTICE.txt`.
No third-party illustrations or icon collections were used. The drawings were
authored directly as SVG geometry with assistance from OpenAI Codex.

`build.py`, `svg_to_font.py`, font controls, tests and compiled fonts are
**Apache-2.0**. The compiled font retains Roboto text outlines, its copyright and
license metadata, with a new family name and original picture-word modifications.
See `FONT_LICENSE.txt`, `FONT_NOTICE.txt` and the root `THIRD_PARTY_NOTICES.md`.
