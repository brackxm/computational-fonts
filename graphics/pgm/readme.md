# PGM image renderer

The font renders small grayscale images from plain PGM (`P2`) text.
Open [playground.html](playground.html) or the editable [ODT specimen](pgm.odt).
The browser demo is at <http://localhost:8000/graphics/pgm/playground.html>
when serving the repository root.

```text
P2
4 4
15
0 1 2 3
4 5 6 7
8 9 10 11
12 13 14 15
```

`P2` identifies the format. Width and height come next, followed by the maximum
sample value (`15` in this font), then one decimal sample per pixel. `0` is black
and `15` is white. Samples run left to right, then top to bottom. Whitespace
separates samples: `10` is one gray pixel, while `1 0` is two pixels.
See the [official PGM specification](https://netpbm.sourceforge.net/doc/pgm.html).

## Using the font

Use one comment-free, single-line image with one ASCII space between header
fields and the raster:

```text
P2 4 4 15 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15
```

The playground removes `#` comments through the next CR or LF and folds ASCII
whitespace (space, tab, CR, LF, vertical tab and form feed) to single spaces.
It trims the prepared input and passes it to the font without interpreting the
header or samples. For a document, prepare text the same way, apply **PGM
Renderer**, and keep it in one shaping run with consistent formatting.
Copying the image preserves the underlying PGM text.

GSUB reads the header, recognizes sample boundaries and counts pixels. Only a
complete image with exactly width × height samples renders; invalid input shows
**INVALID PGM** without a partial image. Counting states are independent of
sample colors. GPOS positions index marks on a board according to the width
and attaches shared shade glyphs. Height determines a separate white background.
COLR/CPAL supplies solid grays; monochrome renderers use a small ordered-dither
pattern on the host background. The outlines and lettering are original.

## Limits

- Plain PGM `P2` only; no raw PGM `P5`, PBM `P1` or RGB `P3`.
- Width and height each range from 1 to 64. Dimensions use one or two decimal
  digits; two-digit dimensions with a leading zero are accepted.
- Fixed maxval `15`. Other maximum sample values are unsupported.
- Samples are decimal integers `0`–`15`, without signs or leading zeros.
  They must be separated by ASCII spaces in direct font input; repeated raster
  spaces and trailing spaces are accepted.
- Exactly width × height samples. Extra samples and trailing non-whitespace
  data are rejected.
- Gray palette values are evenly spaced sRGB display levels (`0`, `17`, …,
  `255`), a common PGM display convention. The font does not apply the true PGM
  specification's BT.709 transfer function.
- Direct font input needs the prepared header spacing above. It does not remove
  comments or combine paragraphs.
- The playground accepts up to 16,384 source characters and ASCII outside comments.
  Its viewport reserves a 64 × 64 canvas; smaller images occupy the upper-left.
- Required ligatures (`rlig`), mark-to-base (`mark`) and mark-to-mark (`mkmk`)
  positioning are needed. Applications may differ in color-font support.

The bundled font is about 3.05 MB, with 4,096 raster positions and 16 shades.
It uses the [shared Netpbm generator](../shared/readme.md), also used by PBM.

## Build

From the repository root, with Python 3.10 or later and FontTools:

```bash
python3 graphics/pgm/build.py
python3 specimens/build.py --project graphics/pgm
```

`--output PATH` selects a font destination relative to the current directory.
`--max-size N` sets the maximum width and height (1–64; default 64):

```bash
python3 graphics/pgm/build.py --max-size 64 --output /tmp/pgm-64.ttf
```

The Python wrapper accepts `build_font(output, max_size=64)` too. See the
[shared builder documentation](../shared/readme.md) for custom-font metrics and
host layout requirements. The bundled font, playground and ODT retain their
64 × 64 default. Importing the builder does not write files.

## Tests

```bash
python3 -m unittest discover -s graphics/pgm -p 'test_*.py'
node --test graphics/pgm/test_pgm_controls.cjs
```

The font suite requires HarfBuzz's `hb-shape`. It checks every supported dimension,
random samples, all shades, token boundaries, extreme rasters, malformed headers,
incorrect sample counts, palette values, color-independent counting, metadata,
font-size budgets, regenerated tables and embedded ODT input. Controller tests
cover lexical preparation, examples, input limits, errors and loading failures.
Run the PBM suite too when changing the shared builder.
