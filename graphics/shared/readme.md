# Shared Netpbm renderer

[PBM](../pbm/), [PGM](../pgm/) and [PPM](../ppm/) keep separate fonts, playgrounds, documents,
READMEs and tests. Their thin `build.py` wrappers choose a format and call
`netpbm.build_font(output, format)`.

`netpbm.py` shares font metadata, geometric glyphs, bounded dimensions, raster
counting, validation, grid positioning and color-cell attachment. `ImageFormat`
supplies the name, magic number, sample palette, cell names and optional fixed
maxval and channel count. The sample adapters handle P1's compact bits, P2's
whitespace-separated decimal samples, and P3's RGB triples. It does not provide
a general arbitrary-format command line.

The counting state has one glyph per raster position, independent of color.
After whole-image validation, it becomes an index mark; a separate sample token
becomes a shared color cell. Adding colors therefore does not multiply the
counting and positioning tables. One board per width shares positioning across
heights, and only indices that fit each width appear in its positioning subtable.

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
