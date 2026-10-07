# Shared Netpbm renderer

[PBM](../pbm/), [PGM](../pgm/) and [PPM](../ppm/) keep separate fonts, playgrounds, documents,
READMEs and tests. Their thin `build.py` wrappers choose a format and call
`netpbm.build_font(output, format, max_size=64)`.

`netpbm.py` shares font metadata, geometric glyphs, bounded dimensions, raster
counting, validation, grid positioning and color-cell attachment. `ImageFormat`
supplies the name, magic number, sample palette, cell names and optional fixed
maxval and channel count. The sample adapters handle P1's compact bits, P2's
whitespace-separated decimal samples, and P3's RGB triples. It does not provide
a general arbitrary-format command line.

Each sample carries two digits of a radix-`max_size` counter, independent of
color. The low digit wraps; the high digit stops at its limit, leaving excess
samples as validation barriers. Merging the pair produces one glyph per raster
position. This uses `2 * max_size` helper lookups instead of `max_size²`.
After whole-image validation, the position becomes an index mark; a separate
sample token becomes a shared color cell. Adding colors therefore does not
multiply the counting and positioning tables. One board per width shares positioning across
heights, and only indices that fit each width appear in its positioning subtable.

Header ligatures use one subtable per width to keep their internal offsets
within OpenType's 16-bit limit. Validation rules call one shared substitution
lookup, avoiding repeated implicit-substitution searches during feature compilation.
The 64 × 64 fonts use 147 GSUB lookups for PBM, 163 for PGM and 149 for PPM.

P3 recognizes bounded channel tokens, then groups three into one color token per
pixel. Unconsumed channels remain validation barriers, including after the last
complete triple. Its maxval 3 palette has 64 RGB colors, using the same pixel
counter and grid as PBM and PGM.

From the repository root, build each format with its wrapper:

```bash
python3 graphics/pbm/build.py
python3 graphics/pgm/build.py
python3 graphics/ppm/build.py
```

All three wrappers accept `--max-size N`, an integer from 1 to 64; the default
is 64. It sets the maximum width and height and supports up to `N²` pixels.
For example, build a separate font with the bundled 64 × 64 limit:

```bash
python3 graphics/ppm/build.py --max-size 64 --output /tmp/ppm-64.ttf
```

The Python API accepts the same limit as a keyword argument:

```python
build_font(output, PPM, max_size=64)  # shared generator
build_font(output, max_size=64)       # format-specific wrapper
```

Limits and derived metrics are local to each build. Cells remain 64 font units;
the font's em size and canvas height are `N * 64`, and its invalid-input advance
is `N * 64 + 1`. The bundled playgrounds and ODT specimens use the default 64 × 64
layout. A custom font needs a matching canvas, font-size validity probe and source
input limit in its host; `--output` can keep it separate from the bundled font.

When changing shared code, run all three projects' tests and rebuild their specimens:

```bash
python3 -m unittest discover -s graphics/pbm -p 'test_*.py'
python3 -m unittest discover -s graphics/pgm -p 'test_*.py'
python3 -m unittest discover -s graphics/ppm -p 'test_*.py'
node --test graphics/pbm/test_pbm_controls.cjs graphics/pgm/test_pgm_controls.cjs graphics/ppm/test_ppm_controls.cjs
python3 specimens/build.py --project graphics/pbm
python3 specimens/build.py --project graphics/pgm
python3 specimens/build.py --project graphics/ppm
```

Python requires FontTools; shaping tests require HarfBuzz's `hb-shape`.
`testing.py` shares temporary build and ODF text-extraction helpers.
Shared option tests cover custom CLI/API sizes, invalid options, scaled geometry,
sample counts and independent consecutive builds.
All three font suites cover dimensions through 64, pixel colors and positions,
header offsets, counter rollover and invalid sample counts. The playground
examples and ODT specimens use complete 64 × 64 rasters.
