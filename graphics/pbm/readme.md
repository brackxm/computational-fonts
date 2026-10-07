# PBM image renderer

The font renders small black-and-white images from plain PBM (`P1`) text.
Open [playground.html](playground.html) or the editable [ODT specimen](pbm.odt).
The browser demo is at <http://localhost:8000/graphics/pbm/playground.html>
when serving the repository root.

```text
P1
4 4
1000
0100
0010
0001
```

This draws a black diagonal on white. `P1` identifies the format, the next two
numbers give width and height, and the remaining characters are pixels:
`0` is white and `1` is black. Pixels run left to right, then top to bottom.
Whitespace between raster bits is optional. See the
[official PBM specification](https://netpbm.sourceforge.net/doc/pbm.html).

## Using the font

The font accepts one comment-free, single-line image. Use one ASCII space
between the magic number, width, height and raster:

```text
P1 4 4 1000 0100 0010 0001
```

The playground removes `#` comments through the next CR or LF and folds ASCII
whitespace (space, tab, CR, LF, vertical tab and form feed) to single spaces.
It trims the resulting input and passes it to the font without interpreting
the dimensions or pixels. For a document, prepare the text in the same way,
apply **PBM Renderer**, and keep it in one shaping run with consistent formatting.
Copying the rendered image preserves the underlying PBM text.

The font parses the header and numbers the raster bits using GSUB.
Counting states are independent of the pixel colors. It renders
only after checking the final pixel against width × height. Invalid input
shows **INVALID PBM**, with no partial bitmap. GPOS positions index marks on a
board according to the parsed width, then attaches shared pixel glyphs to them.
One board per width shares positioning across all heights; a separate background
mark supplies the image height. COLR/CPAL supplies a white background and black
pixels; monochrome renderers draw black pixels on the host background.
The outlines and lettering are original; no base font is imported.

## Limits

- Plain PBM `P1` only; no raw PBM `P4`, grayscale `P2` or RGB `P3`.
- Width and height each range from 1 to 64. Decimal dimensions use one or two
  digits; two-digit dimensions with a leading zero are accepted.
- Exactly width × height raster bits. Extra bits and trailing non-whitespace
  data are rejected, although the PBM specification allows trailing junk
  separated from the raster by whitespace.
- The direct font input requires the prepared header spacing described above.
  It does not strip comments or combine separate paragraphs.
- The playground accepts at most 16,384 source characters and ASCII outside
  comments. Its fixed viewport reserves a 64 × 64 canvas; smaller images occupy
  the upper-left portion.
- The font needs required ligatures (`rlig`), mark-to-base positioning (`mark`)
  and mark-to-mark positioning (`mkmk`).
  Applications may differ in color-font and shaping support.

The bundled font is about 2.99 MB, with 4,096 available raster positions.
Its positioning tables cover only indices that fit each width.
Its thin builder uses the [shared Netpbm generator](../shared/readme.md),
also used by PGM.

## Build

From the repository root, with Python 3.10 or later and FontTools:

```bash
python3 graphics/pbm/build.py
python3 specimens/build.py --project graphics/pbm
```

`--output PATH` selects a font destination relative to the current directory.
`--max-size N` sets the maximum width and height (1–64; default 64):

```bash
python3 graphics/pbm/build.py --max-size 64 --output /tmp/pbm-64.ttf
```

The Python wrapper accepts `build_font(output, max_size=64)` too. See the
[shared builder documentation](../shared/readme.md) for custom-font metrics and
host layout requirements. The bundled font, playground and ODT retain their
64 × 64 default. Importing the builder does not write files.

## Tests

```bash
python3 -m unittest discover -s graphics/pbm -p 'test_*.py'
node --test graphics/pbm/test_pbm_controls.cjs
```

The shaping suite requires HarfBuzz's `hb-shape`. It checks every supported
dimension, raster order and positioning, compact and spaced bits, malformed
headers, incorrect pixel counts, monochrome outlines, color layers, metadata,
font-size budgets, positioning shared across heights, regenerated font behavior
and the embedded ODT input.
Controller tests cover lexical preparation, comments, whitespace, source
limits, loading failures and reading the font's validity signal.
