# Connect Four — a font that plays

A complete first-player winning opponent on the standard 7 × 6 board. The
font is Red, starts in column 4, and reconstructs the entire game from human
moves in **one uninterrupted shaping call**. Python builds the font; OpenType
GSUB applies both players' moves, gravity, legality checks, strategy transitions,
tactical checks, priority selection, and four-in-a-row detection.

The opponent follows the complete pinned [WeakC4](PROVENANCE.md) strategy. It
is a first-player strategy from the empty board, not an arbitrary-position
solver, a second-player opponent, or a fastest-win solver. See the distinction
between upstream exhaustive verification and implementation testing below.

## Play

Serve the repository root:

```sh
python3 -m http.server 8000
```

Open <http://localhost:8000/games/connect-four/playground.html>.
Click a column or press **1–7**. **Undo** removes the last source character;
**New game** restores `b`. The history field is editable. Backspace outside
the field also undoes a move. In the field, ordinary text editing applies.

| Underlying history | Meaning |
| --- | --- |
| `b` | New game; Red has automatically played column 4 |
| `b1` | Yellow plays 1; Red automatically replies 5 |
| `b135` | Three human moves with replies; Red wins in 7 plies |
| `b4444` | Fourth human move is into a full column; it is rejected |
| `b65342431477741666255` | A longest reachable game: Red wins on ply 41 |

Only the initial `b` and human digits are required. Computer moves and board
serializations never appear in the source. Literal ASCII works with the font,
including `hb-shape connect-four-font.ttf b135`. Keep the text in one LTR font
run with standard ligatures (`liga`) enabled. The browser maps each source
character to a private-use **character alias**, preventing script/font fallback
from splitting malformed Unicode input into separate runs. It adds no framing,
move interpretation, intermediate boards, or computer choices.

The original geometric artwork uses filled Red and Yellow disks in color.
Without COLR/CPAL color, Yellow falls back to a hollow ring so the players
remain distinguishable. An arrow identifies
Red's last column. The font draws the board, column labels and status words.
The browser provides an accessible textual status and responsive sizing.
The font embeds its lettering and geometric artwork; there is no ODT specimen.

## Rejections and terminal positions

Replay stops at the first error. The visible board retains the valid prefix;
no subsequent input restarts the game. Undo or edit the history to continue.

- A full-column move changes neither board, strategy mode, nor Red's last move.
  It produces **COLUMN FULL**, with no computer reply. Later characters are
  ignored until the offending move is removed.
- Missing/incorrect `b`, another `b`, spaces, zero, digits outside 1–7,
  punctuation, and unsupported characters produce **BAD INPUT**. The board
  shows the opening or last successfully completed prefix. Whitespace is not
  insignificant. Empty text has no font output; the playground asks for `b`.
- A Red win produces **RED WINS**. Additional input retains that terminal board
  and produces **RED WINS – TRAILING INPUT**, even if the extra character would
  otherwise be malformed.
- **STRATEGY ERROR**, **YELLOW WINS**, **DRAW**, and **INPUT LIMIT** are defensive
  diagnostics; they are unreachable for legal histories following the verified
  strategy. They must not be treated as a successful game continuation.

The turn clock accommodates 21 human inputs, sufficient for the board's 42-ply
maximum. Exhaustive reference traversal finds that this policy always wins by
Red's 21st move (ply 41, after 20 human moves). Input after a finished game is
ignored deterministically. The playground additionally caps source length at
256 characters to bound arbitrary invalid pasted input; this does not exclude
any legal game. Other applications may impose their own shaping limits.

## Policy and execution architecture

The pinned strategy has 132 opening decision nodes and 522 entry boards pointing
to 384 unique priority diagrams. Mirrored transitions are included. No complete
board configurations or complete game histories are enumerated in the font.

For an active human turn, GSUB consumes the next digit, rejects a full column,
and applies Yellow's checker. It advances the opening graph when applicable,
loads the diagram's mirrored or unmirrored priorities into fixed cells, and
chooses Red's reply:

1. Take an immediate Red win (leftmost if several).
2. Otherwise block an immediate Yellow win (leftmost if several).
3. In an opening decision node, follow its stored Red move.
4. For a diagram, inspect levels **0–9 in ascending order**. Use the first level
   with **exactly one playable cell**. Skip a tied level entirely.

The upstream graph has no tactical ambiguity at its opening nodes; applying
the tactical checks before the stored branch move preserves its behavior.
Full columns have no playable priority cell. Heights are derived from checker
cells in the font. Red's reply is applied to the same board registers, followed
by win/draw detection and restoration of the parser for the next human digit.

A 104-glyph tape holds one frame, 42 three-state checker cells, strategy mode,
42 priority cells, seven heights, seven playable priorities, a tie-cancellation
counter, a decision, last-move marker, and parser/status. Cell outlines overlap
the frame; invisible scratch registers have zero advance. Mark filtering sets
provide sparse access to register operands.

Five explicit **shared** stage programs—input, human drop, strategy, computer
drop, and turn completion—use contextual lookup records addressed to named
register slots. `gsub.py` owns register layout, helper lookup construction, and
guarded clocks; `build.py` defines the game rules and artwork. The largest matched driver window is 61 glyphs, below HarfBuzz's 64-glyph
context limit. Each turn has five tiny distinct clock wrappers; helper and
strategy tables are shared across all 21 turns. Guards skip inactive and
finished turns. Tactical patterns and win detection are grouped, keeping the
longest histories within the engine's operation budget. This uses the same
shared-helper/clock principle as the repository's stateful games; a Boolean
circuit or cloned per-turn strategy kernel is unnecessary.

`connect-four-font.abi.json` documents slot memberships and shared instruction
indices for diagnostic tests. It is **not** loaded by the playground. Tests
expose those same font tables to isolated board-register queries in temporary
fonts; the distributed user interface accepts human histories only.

## Status signal for presentation

At 1000 units per em, a successfully completed shaping run advances by
`1000 + status code`. The frame contributes 1000, the terminal status contributes
the code, and all registers contribute zero. The outline at that status glyph
also prints the corresponding words. No JavaScript board model is involved.

| Code | Status |
| --- | --- |
| 1 | YOUR TURN |
| 2 | RED WINS |
| 3 | COLUMN FULL |
| 4 | BAD INPUT |
| 5 | RED WINS – TRAILING INPUT |
| 6 | STRATEGY ERROR |
| 7 | YELLOW WINS |
| 8 | DRAW |
| 9 | INPUT LIMIT |

The controller measures this signal at 1000px and accepts only a near-integer
advance in the documented range. It checks `b1`, `b135`, and `b!` when loading.
Missing font support, disabled ligatures, empty input, a failed/incomplete
shaping run, and oversized input clear the drawing and disable column buttons.
Raw input glyphs cannot form a plausible successful board without computation.

## Build

Python 3.10+; FontTools with Brotli for WOFF2. Protobuf is used only for the
optional upstream serialization round trip. The recorded environment used
Python 3.14, FontTools 4.67.0, Brotli 1.2.0 and HarfBuzz 14.2.1.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r games/connect-four/requirements.txt
.venv/bin/python games/connect-four/build.py
# Relative to your current directory; creates parent directories:
.venv/bin/python games/connect-four/build.py --output /tmp/c4-check/font.ttf
```

The default destination is beside `build.py`. Each build writes a TTF, WOFF2,
measurements `.json`, and diagnostic `.abi.json`. Importing the builder does
not generate files. Font tables are deterministic, including fixed timestamps;
embedded metadata identifies the GPL strategy derivative and permits editable
embedding (`fsType=0`).

## Verification

```sh
.venv/bin/python games/connect-four/upstream/solution/validate_solution.py --jobs 4
.venv/bin/python games/connect-four/upstream/representations/protobuf/render.py
.venv/bin/python games/connect-four/upstream/representations/protobuf/decode.py
.venv/bin/python games/connect-four/verify_longest.py
.venv/bin/python games/connect-four/test_font.py
node games/connect-four/test_controls.cjs
```

HarfBuzz's system shared library and `hb-shape` are required. The tests fail
explicitly if the shaping dependency is absent; they do not silently claim
verification. Node.js is needed for controller tests. The font suite creates
fresh fonts in a temporary directory and compares their tables and results
with the bundled artifacts. Typical runs take around a minute, plus about a
minute for the optional exhaustive longest-game traversal.

There are **two separate kinds of evidence**:

- **Upstream exhaustive strategy verification:** all nine checks in the
  unmodified pinned validator pass, including all opponent continuations from
  every diagram entry. Its recorded result is [upstream-validation.md](upstream-validation.md).
  The additional independent length traversal explores the actual canonical
  orientation transitions from `b`, exhaustively finds longest suffixes for
  reachable entries, and records the 41-ply witness in [longest.json](longest.json).
- **GSUB implementation verification:** fresh and bundled fonts are shaped by
  real HarfBuzz and compared with a separate row-major Python model. Tests cover
  every legal opening edge in both orientations (1,822), all 26 full-column
  opening edges, and every oriented diagram entry (1,044). Six hundred complete
  deterministic games check every intermediate board, height, strategy mode,
  last move, and status using **human-only histories**. These include tactical
  wins, blocks, and hundreds of tied-priority cancellations. Exhaustive length
  traversal also supplies 64 adversarial terminal histories; all their distinct
  prefixes are checked. Reset, undo, malformed and reserved Unicode input,
  terminal tails, disabled computation, deterministic font tables, WOFF2 table
  round trips, metadata, color and monochrome outlines are covered.

Node tests exercise controls against actual font-produced HarfBuzz advance
signals, including keyboard input, editing, stale-result clearing, full-column
recovery, terminal disabling, longest history, and font/shaping failures, including absent or synchronously failing font APIs.
Undo removes a complete Unicode character, including unsupported astral input.
Regression tests also check native shaping resource cleanup and the reference
model under optimized Python (`-O`); board updates do not depend on assertions.
The actual browser playground was visually inspected and exercised with the
41-ply history, undo, reset, and rejected input. Color and monochrome views
were inspected separately.

**Finite differential tests do not prove the GSUB port correct on every possible
history.** The exhaustive proof applies to the pinned strategy/reference; the
font is its tested implementation. No exhaustive proof of all OpenType
execution paths or every shaping engine is claimed. The font is designed for
one uninterrupted run; inserting formatting/script breaks can split its state.

## Measurements

The generated [font measurements](connect-four-font.json) and recorded
[verification report](verification.json) give exact sizes and timings. The font
has **1,855 glyphs**, **1,567 physical GSUB lookups**, five shared stage programs
and 312 shared instruction records. It is approximately **424.4 KiB TTF** or
**44.9 KiB WOFF2**. These are measured sizes, not minimum-size claims.

On this development machine, shaping across tested human histories, including
intermediate prefixes, takes **2.73 ms median**; the 41-ply witness takes
**13.24 ms median** with a persistent HarfBuzz font during the multi-suite test
run. Timing includes Python result extraction and varies by machine,
engine, cache and history. It excludes font loading and process startup.

## License

This folder includes a **GPL-3.0 strategy and derived font**, an explicit
exception to the repository's Apache-2.0 default. Strategy-bearing Python and
font artifacts are GPL-3.0-only. Presentation/controller code and the generic
shaping harness are Apache-2.0. See [PROVENANCE.md](PROVENANCE.md) for the exact
file scope and the preserved [upstream license](upstream/LICENSE).

Column numbers, player labels, and diagnostics use smooth, proportional
Roboto 2 outlines baked into the font by [`game_text.py`](../shared/game_text.py).
Roboto is Copyright 2015 Google Inc., Apache 2.0. The generated fonts retain
this attribution and their GPL-3.0-only license; see [PROVENANCE.md](PROVENANCE.md).
