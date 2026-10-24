# Nim: normal and misère perfect play inside a font

[Play in your browser](playground.html). Three configurable heaps, **0–31 tokens
each**, and a perfect opponent that can move first or second. Take a positive
number from exactly one heap. At least one starting token is required.

- **Normal:** whoever takes the last token wins.
- **Misère:** whoever takes the last token loses.

The default, 3–5–7 with the font first in normal play, is a forced font win.
Starting a perfect opponent in a losing position gives you a chance to beat it.
Try 1–1–1 with the font first in misère play, then find the right replies.

The font checks takes, updates heaps, calculates its exact strategy, and draws
the tokens, decimal sizes, binary sizes, and current XOR. JavaScript transports
text, keeps edit history, and reads the font’s status. It has no board model,
move generator, XOR calculation, or opponent strategy.

## Input

Use a header containing the first player, rule, and three two-digit sizes:

```text
bN03,05,07;          font first, normal play
hN03,05,07;          human first, normal play
bM01,01,01;          font first, misère play
hM02,01,00;A01;      human takes 1 from A; the font replies
```

The explanations after the spaces above are not input. `b` means font first,
`h` human first; `N` normal, `M` misère. Append **only your takes**: `A02;`,
`B01;`, or `C04;`. Move amounts are 01–31. All amounts use two digits.

ASCII spaces, tabs, and line breaks are ignored, including between digits.
Empty setup fields are rejected rather than silently becoming zero. A take
exceeding the selected heap is invalid and consumes no tokens. Unsupported
syntax is malformed; the displayed board is the valid prefix, possibly a
partially read setup. Terminal games freeze and ignore trailing input.

Undo restores the previous source. The playground caps editable input at
**1,024 characters**, clears stale results immediately on edits, and appends a
button move only after the font accepts it. The gold reply label gives the size
left in a heap, or identifies the one-token fallback from a losing position.

## Exact strategy

For normal Nim, a position is losing exactly when `A XOR B XOR C = 0`. The font
tries to reduce A to `B XOR C`; if that is not smaller than A, it tries B to
`A XOR C`, then C to `A XOR B`. A winning position always has a legal reduction
of this form. From a forced loss, all moves lose against perfect resistance;
the deterministic fallback removes one from the first nonempty heap.

Misère play uses the same rule while at least two heaps exceed one token.
With exactly one large heap, it reduces that heap to zero or one so the
opponent receives an odd number of single tokens. With only single tokens,
even counts are winning and odd counts losing. Terminal detection reverses the
winner when the final token is taken. The classical proof is in
[Bouton’s original paper, including §6](https://paradise.caltech.edu/ist4/lectures/Bouton1901.pdf).

All **32,768 positions per rule** are compared with an independent dynamic
program built from legal removals, without using XOR. The model chooses the
first winning take in heap/amount order, or its legal fallback. No external
strategy table, learning, heuristic, or runtime search is used.

## Actual arithmetic in GSUB

Each heap is an independent register with 32 values. A 32-value scratch register
computes XOR through contextual class substitutions. The same XOR lookup
definitions are reused to obtain each candidate target. After replay, three
final arithmetic stages recompute the displayed XOR from the actual current
heaps. It is not a table for every complete board.

The binary columns use five bits, weighted **16, 8, 4, 2, 1**. The gold XOR row
shows both decimal and binary results. In normal play a zero XOR is losing for
the next mover. It is not a sufficient rule for the small misère endgame.

The bundled TTF contains **774 glyphs, 2,984 GSUB lookups, and 471,240 bytes**.
Forty-nine shaping passes cover every legal game: there are initially at most
93 tokens and every move removes at least one. End validation, final XOR
calculation, and source hiding run afterward. This is the complete bounded
three-heap game, rather than an arbitrary-heap or arbitrary-size implementation.

## Font protocol

Frame source with U+E000 / U+E001. The browser maps printable ASCII to U+E100
plus its ASCII code, keeping the whole program in one left-to-right run.
Unsupported Unicode and reserved transport characters become a DEL rejection
token. Direct ASCII is also mapped for command-line experiments:

```bash
hb-shape games/nim/nim-font.ttf --text=$'\ue000bN03,05,07;A01;\ue001'
```

Enable `liga`, zero letter/word spacing, and no kerning. The frame advances
1,800 font units and exactly one final status adds this extra advance:

| Extra advance | Meaning |
| --- | --- |
| 1 | Human’s turn |
| 2 | Font wins under the selected rule |
| 3 | Human wins under the selected rule |
| 4 | Invalid take or empty starting position |
| 5 | Malformed input |
| 6 | Reserved internal error |

The browser probes at 1,000 px, making one unit one CSS pixel, and checks actual
shaping before enabling play. Colors use COLRv0; monochrome outlines also work.
Hosts that split the program across runs or disable standard ligatures cannot
run the game.

## Build and verify

Python 3.10+, FontTools, native HarfBuzz / `hb-shape`, and Node.js are needed:

```bash
python3 -m pip install fonttools
python3 games/nim/build.py
python3 games/nim/test_font.py -v
node games/nim/test_controls.cjs
python3 -m http.server 8000
```

Open <http://localhost:8000/games/nim/playground.html>. The builder defaults to
the font beside its source, independent of the current directory; `--output`
selects another file. Imports write no files.

Native HarfBuzz checks the **unmodified bundled font on all 65,536 heap/mode
combinations**, including empty-setup rejection. Every test also verifies the
displayed XOR. Further checks cover every move amount and heap, both first
players, normal/misère terminal reversal, partial setup errors, 150 complete
seeded games, the longest legal history against each policy, terminal freezing,
disabled ligatures, and metadata. Controller tests use real font measurements
for rejected takes, both outcomes, rule changes, Undo, editing, limits, empty
fields, and failed font loading. Browser checks cover tokens, binary digits,
column spacing, and the displayed XOR.

The simplify pass reuses XOR tables through shared clock-stage definitions.
It also corrected a longest-history test selector, with the corresponding
Wythoff test rerun successfully. Rebuild comparisons preserve all non-timestamp
tables, and shared scheduling changes are checked against existing game fonts.

All code, generated arithmetic tables, and token artwork are
original and licensed under Apache 2.0. Shared helpers are in `../shared/`.

Titles, coordinates, and status labels use original, proportional
[Game Sans](../shared/fonts/game-sans/readme.md) Regular and Bold outlines, baked
into the font by [`game_text.py`](../shared/game_text.py). The lettering is
Copyright 2026 Michael Brackx, Apache 2.0; no third-party font outlines are used.
