# Connect Four — a font that plays

A complete first-player winning opponent on the standard 7 × 6 board, using an
**independently generated and exhaustively verified Apache-2.0 strategy**.
The font plays Red, opens in column 4 and reconstructs the whole game from
human moves in one uninterrupted shaping call. Gravity, legality, opponent
choices, board updates and four-in-a-row detection all run inside GSUB.

This is a winning strategy from the empty board. It does not solve arbitrary
positions, play second or seek the fastest win.

## Play

Serve the repository root with `python3 -m http.server 8000`, then open
<http://localhost:8000/games/connect-four/playground.html>.
Click a column or press **1–7**. Undo removes the last character; New game
restores `b`. The editable field contains only `b` and the human's column digits.

| Input | Result |
| --- | --- |
| `b` | New game; Red has played column 4 |
| `b1` | Yellow plays column 1 and the font replies |
| `b1351` | Red wins after four human moves |
| `b4444` | Fourth human center-column move is rejected as full |
| `b11411123267755752776` | A certified longest game: Red wins on ply 41 |

Literal ASCII works, for example `hb-shape connect-four-font.ttf b1351`.
Use one LTR font run with standard ligatures enabled. The playground maps
characters to private-use aliases to keep malformed Unicode in the same font
run. It supplies no computer moves, intermediate boards or strategy decisions.

Full columns retain the valid board prefix and stop replay without a Red
reply. Bad input stops at the first error. Input after a Red win produces a
trailing-input diagnostic and retains the winning board. Undo or edit the
history to resume. Yellow wins, draws, internal errors and the 21-turn limit
are defensive diagnostics, unreachable in legal games under the proved policy.
The playground caps pasted input at 256 characters.

The board, labels, diagnostics and last-move arrow are embedded in the font.
COLR/CPAL paints the disks; the monochrome fallback draws Yellow as a ring.
Labels use proportional Roboto 2 outlines.

## Strategy and proof

The original native oracle and generator use only the game rules and an
included, independently generated seed of completed subgraphs. Neither builds
nor generation read WeakC4 data or code.

The certificate prescribes one Red move, covers every legal Yellow reply and
ends only in a Red win. Local policies first win, then block, then choose the
lowest-ranked legal landing cell under an independently synthesized strict
ordering of the 42 cells. A separate checker uses coordinate arrays and
geometric line tests; it does not trust or link the oracle.

The recorded complete proof checked **165,071 vertices, 192,256 explicit edges
and 86,689,995 local-policy states**, establishing a Red win by ply 41. See
[the proof report](research/winning-policy-verification.json) and
[provenance](PROVENANCE.md).

## Font execution

Offline compaction replaces internal subtrees with shared policies only after
exhaustive win checking. Lowering then preserves every cross-column comparison
between initially empty cells while sharing policies and minimizing control.
Alternatives in one column may share a priority because only one can be
playable at a time. The resulting controller has 58,765 modes, including
51,016 branch modes, and 37,747 shared priority maps. Mode IDs occupy two registers;
the number of modes therefore does not require that many glyphs.

A fixed 63-register tape stores the board, heights, mode pair and update
scratch, seven playable priorities, decision, last-move marker and parser.
Hierarchical dispatch selects by both mode registers. Self-contained lookup
blocks stay within OpenType's short-offset limits. A shared, guarded turn
program has 139 lookup records; 21 distinct clocks replay human digits.
Inactive or finished turns skip the program. Its largest driver context is
64 glyphs, including the next human input.

Branch dispatch encodes the human column and mode low register, then directly
replaces it with an encoded reply pair. Scratch registers are removed first
and restored afterward, keeping the temporary tape within the driver limit.
Unreachable construction lookups are removed and all references remapped.

Priority loading factors the 37,747 maps into reusable six-cell column
profiles. Seven column dictionaries share a 16,005-glyph alphabet. The loader
expands a policy into seven profiles, then decodes each against its column
height. Full columns decode to the original unplayable sentinel. The profile decoder preserves all 42 values
of every lowered map exactly. The separate lowering check establishes that
coalescing same-column alternatives preserves every reachable choice.

At 1000 units per em the advance is `1000 + status code`. The board contributes
1000; all registers contribute zero; the final diagnostic contributes the code.
The controller only measures this signal and presents accessible status text.

| Code | Status |
| --- | --- |
| 1 | Your turn |
| 2 | Red wins |
| 3 | Column full |
| 4 | Bad input |
| 5 | Red wins, trailing input |
| 6 | Strategy error |
| 7 | Yellow wins |
| 8 | Draw |
| 9 | Input limit |

The [ABI](connect-four-font.abi.json) documents register membership and source
fingerprints. It is not loaded by the playground.

## Build and validation

Python 3.10+ and the pinned requirements; a C++17 compiler is needed only to
rerun the exhaustive checker or offline search, not to rebuild the font.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r games/connect-four/requirements.txt
.venv/bin/python games/connect-four/build.py
.venv/bin/python games/connect-four/build.py --output /tmp/c4-fresh/font.ttf
.venv/bin/python games/connect-four/test_font.py
node games/connect-four/test_controls.cjs
```

Recheck the mathematical guarantee independently:

```sh
clang++ -O3 -std=c++17 games/connect-four/research/check_hybrid.cpp -o /tmp/c4-check
python3 games/connect-four/research/check_hybrid.py \
  games/connect-four/research/winning-policy.json.gz --checker /tmp/c4-check
```

Read back every compiled policy entry and compare real shaping with the separate
model, including the longest game and seeded complete legal games:

```sh
.venv/bin/python games/connect-four/research/verify_kernel.py \
  games/connect-four/connect-four-font.ttf \
  --controller games/connect-four/research/controller.json.gz \
  --proof games/connect-four/research/winning-policy-verification.json
```

All **621,348 dispatch entries and 1,585,374 priority entries** matched. The
recorded shaping run checked **3,286 histories and 500 complete games**, all
Red wins, using HarfBuzz 14.6.0. Median shaping was about 0.44 ms on the development
machine; timings depend on the machine, engine and history. The policy proof
is exhaustive; engine tests and binary readback are implementation validation,
not a formal proof of a font shaper. One uninterrupted LTR run is required.

The font is **5,150,264 bytes TTF / 1,304,292 bytes WOFF2** (about 1.30 MB
WOFF2). This is **38.5% smaller** than the previous 2.12 MB WOFF2 and **63.6%
smaller** than the first complete independent font at 3.58 MB. See the generated
[measurements](connect-four-font.json) and [verification](verification.json).
[Research instructions](research/README.md) describe complete regeneration.

## Why the old font was smaller

The historical GPL3 font was 46,020 bytes WOFF2. Its imported strategy used
132 opening branches and 384 steady-state diagrams. The first independent
controller instead needed 60,424 branch modes and 41,314 strict priority maps.
The current controller is smaller, but still represents a much larger strategy.
The difference is primarily the strategy representation and its lookup data,
rather than artwork or license text.

The current result is about 28 times the old WOFF2 size. Reaching 46 KB would
require a substantially smaller independently generated strategic rule set;
the storage and compaction work here does not establish that this target is
achievable. No old GPL code, diagrams or strategy data are used in the new
search, lowering or font.

## License

All current implementation code, strategy data and fonts in this folder are
Apache-2.0. Roboto 2 is Copyright 2015 Google Inc., Apache-2.0, with attribution
retained in the generated font. See [PROVENANCE.md](PROVENANCE.md). The removed
GPL strategy is not a dependency of builds, validation or play.
