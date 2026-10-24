# First Words Pictures

Type `apple banana cat dog house ball` in **First Words Pictures** to display
six drawings. The font contains all 100 original illustrations as scalable
colour vectors, with monochrome outline fallbacks.

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
- Use the exact [100 labels](words.txt); plurals and synonyms are not inferred.
- `ice cream` and `teddy bear` accept a single ordinary or non-breaking space,
  or hyphenated/joined spellings (`ice-cream`, `icecream`, `teddy-bear`, `teddybear`).
- Adjacent letters, digits, combining marks, underscores, apostrophes and hyphens
  block partial matches within a shaping run: `caterpillar`, `cat's`, `hot-dog`
  and `pineapples` stay text. Punctuation can surround a word: `(cat), apple!`.
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
- `playground.html` / `font-controls.js`: actual-font demo and vocabulary picker.
- `words.txt` / `vocabulary.js`: labels and generated playground vocabulary.
- `artwork/`: 100 standalone, editable SVGs with transparent backgrounds.
- `manifest.json`: labels, categories, palette, file names and source sizes.
- `previews/`: a complete contact sheet and seven category sheets, all as SVG.
- `first-words-100-svg.zip`: SVG artwork, original gallery and artwork source only.
- `approved_samples.json`: the six original style studies approved in the chat.
- `generate_artwork.py`: the complete reproducible source geometry and exports.

## Vocabulary

| Category | Drawings |
| --- | ---: |
| Food | 20 |
| Animals | 20 |
| Home | 20 |
| Clothing and toys | 10 |
| Transport | 10 |
| Nature | 10 |
| Body | 10 |

These are manually curated familiar, drawable English nouns and noun phrases.
They are not a measured word-frequency ranking. Compound labels include
`ice cream` and `teddy bear`. Hyphens are used in their file names only.
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

The bundled font has 100 picture glyphs, 16 palette colours, 875 colour layers
and 4,358 total glyphs including retained Roboto text. The TTF is 745,880 bytes;
the WOFF2 is 222,312 bytes. See the generated JSON for exact build information.

The apple, banana, cat, dog, house and ball geometry is preserved from the
original approved six-drawing study.

## Build

Create a Python virtual environment and install the pinned build dependencies:

```sh
python3 -m venv /tmp/first-words-build
/tmp/first-words-build/bin/python -m pip install -r graphics/first-words/requirements.txt
/tmp/first-words-build/bin/python graphics/first-words/build.py
```

This builds TTF, WOFF2, feature source, metadata, vocabulary and the font ZIP.
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
inside the standalone illustrations.

## Verification

```sh
/tmp/first-words-build/bin/python -m unittest discover -s graphics/first-words -p 'test_font.py'
```

Requires HarfBuzz's `hb-shape`. Checks all 100 labels in lower, upper, title and
mixed case; compound aliases; punctuation; rejected substrings; disabled
ligatures; colour/fallback outlines; attribution; webfont equivalence; and a
byte-identical rebuild.

The optional `test_browser.cjs` requires Playwright and a browser, with the local
server running. Run it with `node graphics/first-words/test_browser.cjs`;
`BROWSER_CHANNEL=chrome` selects installed Chrome. An optional first argument
overrides the playground URL; a second writes a screenshot. It verifies all
100 actual labels in browser page text, compares every font picture against its
SVG pixels, and exercises input, filtering, examples and picture insertion.
For the two compound pixel checks, canvas uses the joined alias; original spaced
labels are independently checked in DOM text. Validation was completed in Chrome.

## License and provenance

The original artwork, source geometry, `generate_artwork.py` and annotations
are dedicated under **CC0-1.0**; see `LICENSE.txt`. This is a separate dedication
from the repository's default Apache license. No third-party illustrations or
icon collections were used. The drawings were authored directly as SVG geometry
with assistance from OpenAI Codex.

`build.py`, `svg_to_font.py`, font controls, tests and compiled fonts are
**Apache-2.0**. The compiled font retains Roboto text outlines, its copyright and
license metadata, with a new family name and original picture-word modifications.
See `FONT_LICENSE.txt`, `FONT_NOTICE.txt` and the root `THIRD_PARTY_NOTICES.md`.
