# PPM image renderer

The font renders small RGB images from plain PPM (`P3`) text.
Open [playground.html](playground.html) or the editable [ODT specimen](ppm.odt).
The browser demo is at <http://localhost:8000/graphics/ppm/playground.html>
when serving the repository root.

```text
P3
2 2
3
3 0 0   0 3 0
0 0 3   3 3 3
```

This draws red and green above blue and white. `P3` identifies the format.
Width and height come next, followed by the maximum channel value (`3` in this
font). Each pixel has three decimal samples in **red, green, blue** order.
Pixels run left to right, then top to bottom. Every sample needs whitespace
between it and the next: `3 0 0` is one red pixel; `300` is invalid.
See the [official PPM specification](https://netpbm.sourceforge.net/doc/ppm.html).

## Using the font

Use one comment-free, single-line image with one ASCII space between header
fields and the raster:

```text
P3 2 2 3 3 0 0 0 3 0 0 0 3 3 3 3
```

The playground removes `#` comments through the next CR or LF and folds ASCII
whitespace (space, tab, CR, LF, vertical tab and form feed) to single spaces.
It trims the prepared input and passes it to the font without interpreting the
header, samples or colors. For a document, prepare text the same way, apply
**PPM Renderer**, and keep it in one shaping run with consistent formatting.
Copying the image preserves the underlying PPM text.

GSUB reads the header, recognizes individual channel samples, groups them into
RGB triples and counts pixels. Only a complete image with exactly width × height
triples renders; invalid input shows **INVALID PPM** without a partial image.
Leftover channels stay as validation barriers, so one or two extra samples cannot
silently disappear. Counting states are independent of the 64 colors. GPOS
positions index marks and attaches shared color cells to them; height determines
a separate white background. COLR/CPAL supplies RGB output. Monochrome renderers
use ordered dithering based on weighted display brightness (0.299 R + 0.587 G +
0.114 B), on the host background. The outlines and lettering are original.

## Limits

- Plain PPM `P3` only; no raw PPM `P6`, PBM `P1` or PGM `P2`.
- Width and height each range from 1 to 32. Dimensions use one or two decimal
  digits; two-digit dimensions with a leading zero are accepted.
- Fixed maxval `3`, giving four values per channel and 64 RGB colors.
  Other maximum values are unsupported.
- Channel samples are single decimal digits `0`–`3`, without signs or leading
  zeros. Separate every sample with ASCII spaces in direct font input; repeated
  raster spaces and trailing spaces are accepted. Extra separation between
  pixels is optional.
- Exactly width × height × 3 samples. Incomplete triples, extra samples and
  trailing non-whitespace data are rejected.
- Palette channels use evenly spaced sRGB display values (`0`, `85`, `170`,
  `255`). This is the common sRGB PPM variant; the font does not apply the true
  PPM specification's BT.709 transfer function.
- Direct font input needs the prepared header spacing above. It does not remove
  comments or combine paragraphs.
- The playground accepts up to 8,192 source characters and ASCII outside comments.
  This accommodates a full 32 × 32 image with single spaces between samples.
  Its viewport reserves a 32 × 32 canvas; smaller images occupy the upper-left.
- Required ligatures (`rlig`), mark-to-base (`mark`) and mark-to-mark (`mkmk`)
  positioning are needed. Color-font support is needed for RGB output.

The bundled font is about 591 KB. It uses the [shared Netpbm generator](../shared/readme.md), also used by
PBM and PGM. Its palette does not multiply the counting or positioning states.

## Build

From the repository root, with Python 3.10 or later and FontTools:

```bash
python3 graphics/ppm/build.py
python3 specimens/build.py --project graphics/ppm
```

`--output PATH` selects a font destination relative to the current directory.
Importing the builder does not write files.

## Tests

```bash
python3 -m unittest discover -s graphics/ppm -p 'test_*.py'
node --test graphics/ppm/test_ppm_controls.cjs
```

The font suite requires HarfBuzz's `hb-shape`. It checks every supported dimension,
random RGB pixels, all 64 colors, channel order, separators, extreme rasters,
incomplete and extra triples, malformed headers, invalid channels, palette
values, monochrome primary-color dithers, color-independent counting, font-size
budgets, regenerated tables and embedded ODT input. Controller tests cover
lexical preparation, examples, input limits, errors and loading failures.
Run PBM and PGM tests too when changing the shared builder.
