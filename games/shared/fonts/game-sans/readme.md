# Game Sans

Original proportional game lettering, Copyright 2026 Michael Brackx.
Licensed under [Apache License 2.0](LICENSE). No third-party font outlines,
traced letters, imported glyphs, spacing tables, or shaping rules are used.

The independently drawn source is [`game_sans.py`](../../game_sans.py). It
defines geometric stroke skeletons, expands them into quadratic outlines, and
merges overlapping stroke contours. Regular and Bold have identical advances
so changing weight does not reflow a label. The slashed zero, barred capital I,
and hooked lowercase l help distinguish counts and coordinates.
Regular uses 70-unit strokes and Bold 105-unit strokes on the 1000-unit em.

The initial set has **76 characters**: A–Z, a–z, 0–9, space, the ten punctuation
marks `! ' ( ) , - . / : ;`, and `è ō ū` for Misère Nim and Mū tōrere. This covers
the current games' titles, coordinates, counts, status labels, adventure prose,
and ODT instructions. Both complete Latin alphabets are retained. Unsupported
label characters fail explicitly instead of being silently dropped. This is a
small game alphabet, not a general-purpose multilingual font.

`GameSans-Regular.ttf` and `GameSans-Bold.ttf` are reusable base fonts with
1000 units per em, 700-unit cap height, and unrestricted editable embedding
(`fsType=0`). The game lettering helper reads these bundled originals at build
time; compiled game fonts contain their own outlines and need no runtime font
download. The Snake game outlines remain their existing original geometry;
their ODT instructions now use Game Sans as well.

Rebuild both base fonts from the repository root:

```bash
python3 -m pip install -r games/shared/fonts/game-sans/requirements.txt
python3 games/shared/game_sans.py
```

Then rebuild each consuming game's `build.py`. Ordinary game rebuilds only
need their existing FontTools/HarfBuzz dependencies; skia-pathops is needed
only when rebuilding Game Sans itself. Rebuild the three game documents with:

```bash
python3 specimens/build.py --project games/snake-fixed
python3 specimens/build.py --project games/snake-dynamic
python3 specimens/build.py --project games/text-adventure
```

Typography, base-font reproducibility, and embedded-document checks:

```bash
python3 -m unittest discover -s games/shared -p test_game_text.py
```

The [specimen](specimen.png) shows both weights, game names, coordinates, and
adventure prose. Regenerate it with `python3 games/shared/fonts/game-sans/specimen.py`
(requires Pillow). Add `--compare` to render the same game labels next to
Roboto Regular and Bold, with matched capital heights and baselines; see the
[comparison](comparison.png). These fonts replace Roboto only in the games. Other projects
and previously distributed Roboto-based fonts retain their upstream notices.
