# Mū tōrere: a complete perfect opponent in a font

[Play in your browser](playground.html). Four solid red human counters, four
teal font rings, and one empty point. Slide into the empty point along a line.
**Trap the opponent so they have no legal move to win.** The font plays the
exact win/loss/draw solution, including winning after a human mistake.

The standard opening is a draw with perfect play. Choose who moves first, or
try a preset where you can beat a perfect opponent because its starting
position is already lost. The font prints the current perfect-play outcome.

## Rules used here

Outer points **1–8** run clockwise from the top; **9** is the centre, pūtahi.
Each outer point connects to its two ring neighbors and the centre. The centre
connects to every outer point. There is always exactly one empty point; pieces
slide, with no jumping or capturing.

An outer counter may enter the empty centre **only if at least one of its two
outer neighbors belongs to the opponent**. This restriction applies on every
centre entry. Ring slides and moves out of the centre have no such restriction.
The initial eight counters form two consecutive groups of four around the ring.

Several rulesets exist; see
[Browne, “Which Rules for Mu Torere?”](https://cris.maastrichtuniversity.nl/en/publications/which-rules-for-mu-torere/).
This font states its centre-entry rule explicitly and matches the standard
[Berkeley GamesCrafters solution totals](https://gamescrafters.berkeley.edu/analysis/gameanalysis.php?game=tore&variant=2).

## Source notation

Start with one of these headers, then append **only your moves**:

| Header | Starting position |
| --- | --- |
| `h` | Standard board, human first |
| `b` | Standard board, font first |
| `w` | Human can force a win in three human moves |
| `l` | Font can force a win within two replies |

Write the point you move **from**, a single digit 1–9. The unique empty point
determines the destination. The font checks your slide and inserts its own
reply. For example:

```text
h194289             a legal standard-game history
b4                  human point 4 after the font’s opening
w817                solve the winning puzzle
l91                 a terminal font win in the losing puzzle
h=                  agree a draw
```

Explanations after the spaces above are not input. ASCII spaces, tabs, and line
breaks are ignored. Other characters are malformed. A counter that cannot make
a legal slide is rejected. Error output shows the position before that error.
Finished games freeze and ignore trailing input. The gold ring marks the latest
font destination; the gold label records its origin and destination.

`=` **offers a draw by agreement**. The font accepts if it cannot force a win
from the current position, and declines if it can. A declined offer reports an
invalid action; the browser does not append it. The font does not automatically
declare a draw because a counter or turn limit was reached. Drawing play can
continue indefinitely, or the players can agree to stop.

The playground keeps text history for Undo and accepts up to **4,096 source
characters**. This is a browser input cap, not a turn counter inside the font.
Move buttons and compact mobile controls simply submit an origin digit to the
font; JavaScript has no board model, move generator, or opponent strategy.

## Complete solution and policy

`model.py` enumerates all **630 arrangements** of four counters of each color
and one empty point, with each player to move: **1,260 states**. Retrograde
analysis starts from stuck players, marks a state winning when it can reach a
loss for the opponent, and marks it losing once all its children are wins.
Unresolved cycles are draws. The solver records distance to a terminal result.

The AI wins as quickly as possible, delays a forced loss as long as possible,
and preserves a draw when it cannot win. Point number breaks equal ties.
An independent relative-bitboard solver uses a separate fixed-point algorithm
and verifies every legal move and outcome. Every finite remoteness also
satisfies the minimum-win / maximum-loss recurrence.

From the standard opening with a fixed first player, **1,180 states** are
reachable: **208 wins, 128 losses, and 844 draws**, matching Berkeley’s published
totals. The remaining valid arrangements are also solved for compilation and
verification. All strategy data is regenerated locally from these rules.

## A forward-reading font, with no shaping clock

The bundled TTF contains **4,469 glyphs, 676 GSUB lookups, and 541,676 bytes**.
Its six feature stages are:

1. Remove insignificant spaces.
2. Insert the initial board cursor and last-move register.
3. Read source characters from left to right. Each character becomes the next
   cursor and, when appropriate, a last-move marker. The next character sees
   this new cursor as its context.
4. Turn the explicit end sentinel into the final status.
5. Delete old last-move markers.
6. Delete old board cursors, leaving exactly one board and one last-move mark.

Stopped cursors delete trailing input in place. There is no repeated lookup
clock, runtime search, JavaScript engine, or fixed maximum number of game turns.
Native tests replay a **10,806-move drawing loop**, then agree a draw, and also
freeze terminal results across long tails. As with any font, actual text length
is subject to the host’s memory and shaping-engine limits.

Position art uses reusable counter components and colored layers. Separate
stop cursors reuse the same position art. Full old boards never accumulate in
the final output. The shared forward pipeline lives in
[`../shared/fontgame.py`](../shared/fontgame.py).

## Font protocol

Frame source with U+E000 / U+E001. The browser maps printable ASCII to U+E100
plus its ASCII code, so the whole program stays in one left-to-right run.
Unsupported Unicode and reserved transport characters become a DEL rejection
token. Direct ASCII is also mapped for command-line experiments:

```bash
hb-shape games/mu-torere/mu-torere-font.ttf --text=$'\ue000h194289\ue001'
```

Enable `liga`, with zero letter/word spacing and no kerning. The frame advances
1,800 units, and exactly one final status adds the following advance:

| Extra advance | Result |
| --- | --- |
| 1 | Human’s turn |
| 2 | Font wins |
| 3 | Human wins |
| 4 | Invalid slide or declined draw offer |
| 5 | Malformed source |
| 6 | Reserved internal error |
| 7 | Draw agreed |

The browser measures at 1,000 px, making one unit one CSS pixel. It verifies
actual shaping support before enabling play and clears stale results as soon
as editing begins. Color uses COLRv0; filled counters and rings remain distinct
in monochrome. Split shaping runs or disabled ligatures cannot run the game.

## Build and verify

Python 3.10+, FontTools, native HarfBuzz / `hb-shape`, and Node.js are needed:

```bash
python3 -m pip install fonttools
python3 games/mu-torere/build.py
python3 games/mu-torere/test_font.py -v
node games/mu-torere/test_controls.cjs
python3 -m http.server 8000
```

Open <http://localhost:8000/games/mu-torere/playground.html>. The builder writes
beside its source by default, independent of the current directory. `--output`
selects another file. Importing the builder writes no files.

Verification covers every compiled slide, illegal origin, malformed token,
draw-offer decision, and stopped cursor through native HarfBuzz, using temporary
test-only cmap aliases that are absent from the shipped font. Tests also visit
all positions reachable against the fixed AI policy from all four starts,
compare the complete graph with the independent solver, verify long loops and
terminal freezing, and exercise the actual controller/font integration.
Controller checks cover both point buttons and compact inputs. Browser checks
cover counter layers, controls, and draw offers. Rebuilt tables match apart
from timestamp fields. Shared-helper changes
are also checked against the Wythoff and Cram test suites.

All code, generated policy data, and geometric artwork are
original, licensed under Apache 2.0. No external strategy table is embedded.

Titles, coordinates, and status labels use smooth, proportional Roboto 2
outlines baked into the font by [`game_text.py`](../shared/game_text.py).
Roboto is Copyright 2015 Google Inc., Apache 2.0; the font metadata retains
its attribution. See the root [third-party notices](../../THIRD_PARTY_NOTICES.md).
