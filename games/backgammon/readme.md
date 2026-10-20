# Backgammon SGF replay

A computational OpenType prototype that reads a bounded linear backgammon SGF
record and renders its resulting position. Python generates the font; GSUB
substitutions parse the record and update checker counts during shaping.
The browser has no board model or replay implementation.

## Playground

From the repository root:

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000/games/backgammon/playground.html>. Edit or paste SGF,
load an example, return to the starting position, or undo an edit. Examples
include the specification's White opening, both colors, a hit, bar entry, and
a roll without checker movement.

The original geometric artwork shows all 24 points, White as ivory rings and
Black as solid checkers, four separate bar/off counters, and the latest dice
with their player. Each occupied point shows its exact count (1–15), with up
to five checker outlines. Point numbers use White's orientation; uppercase
labels A–X refer to the input's lowercase coordinates. COLR/CPAL v0 supplies
color; monochrome outlines remain available. This project does not currently
include an ODT specimen.

## Supported SGF subset

This is a small subset of [SGF backgammon, GM[6]](https://www.red-bean.com/sgf/backgammon.html).
The starting position is always standard: White has 2 at x, 5 at m, 3 at h,
5 at f; Black has the mirrored arrangement.

```sgf
(;GM[6])
(;FF[4]GM[6]CA[UTF-8];W[31hefe];B[31qtst])
(;GM[6];B[66])
```

- One tree with an ordinary `(; ... )` wrapper. The root may be empty.
- Optional `GM[6]`, `FF[4]`, and `CA[UTF-8]` root properties, each at most once,
  in any order, before the first move. `GM` may be omitted; another game type
  is rejected. A move may occur on the root or in its own following node.
- One `W[...]` or `B[...]` per move node. Turns need not alternate.
- Two dice digits from 1–6, then zero to four source/destination pairs.
  Coordinates a–x are White's points 1–24 (Black's 24–1). Source `y` means
  that player's bar; destination `z` means that player's bear-off tray.
  The source cannot be `z`, and the destination cannot be `y`.
- ASCII spaces, tabs and line breaks are insignificant, including inside
  values. The host flattens tabs and line breaks for uninterrupted shaping.

`W[31hefe]` removes one White checker from h and one from f, placing both on e.
`B[66]` updates the dice without moving. Doubles accept up to four explicit
transfers. A transfer to an opponent blot hits it and increments the
opponent's bar. Entry removes a checker from the moving player's bar, and
bearing off increments only that player's off counter.

This is **replay, not legality checking**. “REPLAYED” means that the specified
transfers were applied. It does not mean the record is legal. Checks cover
source ownership/nonempty counts, blocked destinations, and counter capacity.
Dice distance and direction, mandatory use of both dice, the higher-die rule,
doubles usage, bar-entry priority, home-board eligibility, and oversize bearing
off are not checked. A recorded no-movement turn is accepted even when movement
would have been possible.

Unsupported constructs are rejected rather than silently ignored: variations,
multiple games, comments and escaped values, setup properties (`AW`, `AB`, etc.),
other root/game/match metadata, cube actions (`double`, `take`, `drop`), and pip
counts. `CA[UTF-8]` is a recognized declaration, not support for arbitrary
Unicode property values. Unsupported or malformed tails invalidate completion.

## Completion and limits

There are five visible terminal signals:

| Board label | Meaning | Advance beyond the 1800-unit board |
| --- | --- | --- |
| REPLAYED | Complete replay of the supported subset | 1 |
| MALFORMED | Syntax, coordinate, or framing error | 2 |
| UNSUPPORTED | An unsupported property, action, or construct | 3 |
| LIMIT | More than 128 turns | 4 |
| STATE ERROR | Inconsistent checker transfer or counter overflow | 5 |

Failures stop at the first detected problem. Their boards are partial replay
artifacts and must not be used as final positions; an error can occur after a
source decrement. Error classification is diagnostic, not a complete SGF
validator: for example, a malformed unknown property may be UNSUPPORTED, and
an occupancy error can be detected before a malformed tail. No incomplete or
rejected replay is labeled REPLAYED. Latest dice are absent at the starting
position. A rejected 129th turn does not update them or the board.

The practical limit is **128 turns**, including rolls with no movement: at most
512 explicit checker transfers. The font runs 1674 shared clock passes; a turn
with four transfers takes 13 passes, and supported framing/root properties
take at most eight more. Property duplicates cannot consume unbounded passes.
At the cap, the bundled font is about 1.2 MB. On the development machine a full
128-turn/512-transfer `hb-shape` invocation takes about 350 ms including process
startup; measurements vary by host. The same maximum record was checked in the
browser. The bound keeps interactive re-shaping practical without enumerating
board positions. A full game may exceed this prototype's limit.
Trial builds at 64 and 128 turns shaped successfully; an experimental 256-turn
build produced no replay signal in the local HarfBuzz engine. The bundled
font therefore uses the largest verified limit, 128 turns.

The playground separately limits source text to 4096 characters and reports
that input limit explicitly. Keep the entire encoded program in one shaping
run, with no wrapping, style changes, character spacing, or font fallback.
Ligatures (`liga`) must be enabled. The playground probes success and error
signals before accepting the font as available, and reports load/shaping
failures separately from replay outcomes. Editing clears the previous board
and completion signal while replay is pending. Input limits and shaping
failures likewise clear the board, signal, and accessibility description;
they cannot retain a previous success result. Hostile/unbounded input outside this
transport contract is not supported; application/engine resource limits can
still interrupt shaping.

## Font protocol and implementation

`build.py` maps printable ASCII both directly and through private-use aliases.
For reliable browser shaping, `controls.js` performs only this transport:

1. Flatten ASCII tabs, CR and LF to spaces.
2. Map each printable ASCII code `c` to Unicode `U+E100+c`.
   Other characters map to the rejection token U+E17F.
3. Surround the text with U+E000 (initialize) and U+E001 (end of input).

This one-to-one encoding avoids browser script/font-run boundaries among SGF
letters, numbers, and punctuation. It does not tokenize, parse, validate,
extract moves, infer hits, or compute a position. The font parses the same
character glyphs in either encoding. The raw ASCII form between those two
sentinels also works with an uninterrupted HarfBuzz run:

```bash
python3 - <<'PY'
import subprocess
subprocess.run(['hb-shape', 'games/backgammon/backgammon-font.ttf',
                '\ue000(;GM[6];W[31hefe])\ue001', '--output-format=json'], check=True)
PY
```

Initialization expands into one board, 24 independent signed point registers,
two bar registers, two off registers, two dice registers, a turn counter, and
a parser cursor. Zero-width register outlines overlay the board. GSUB
ligatures consume grammar tokens and coordinates at the cursor. Shared
contextual lookups inspect and update registers, infer hits before replacing
blots, and advance the parser. Small wrappers give each clock pass distinct
lookup indices while sharing the large rule tables, following the Snake and
turtle builders. No complete board position or move history is enumerated.

The final glyph both draws the diagnostic and reports it through its advance.
JavaScript measures that signal at 1000 px per em; it also handles font loading,
input, example selection, and edit history. It never computes checker counts.
`reference.py` is an independent Python test oracle and is not imported by
the font builder or playground.

## Build and verify

```bash
python3 -m pip install fonttools
python3 games/backgammon/build.py
python3 games/backgammon/build.py --output /tmp/backgammon.ttf
python3 -m unittest discover -s games/backgammon -p 'test_*.py'
node games/backgammon/test_controls.cjs
```

The builder writes beside `build.py` by default; `--output` is relative to the
current directory, and missing output directories are created. Importing the
builder has no output side effects.

Tests compare both fresh and bundled fonts with the independent replay model,
including every point/counter/die register and conservation of 15 checkers per
player. They cover the start, specification opening, both colors, stack counts
up to 15, hits in both directions, simultaneous separate bars, both entries,
entries that hit, full 15-checker bars, separate off counts, doubles,
no-movement turns, malformed/unsupported inputs,
trailing data, 128/129-turn boundaries, maximal-length replay, random occupancy
records, transfers/hits/bar entry on the final supported turns,
raw/encoded transport, disabled ligatures, metadata, color/fallback
outlines, build paths, deterministic font tables, all opening-record truncations,
and deterministic mutations of short and maximum-length records. Some occupancy fixtures
deliberately isolate transfer mechanics and are not legal game records.

Shaping checks skip with an explicit message when `hb-shape` is unavailable;
builder/metadata/reference checks still run. Node integration checks use the
actual bundled font to test terminal signals, controls, Undo, unsupported
Unicode and reserved transport characters, the exact 4096-character input
boundary, stale-result clearing, and font loading/shaping failures. Native color, monochrome,
and browser boards were visually inspected during development.

## Prior art and license

Backgammon diagram fonts already exist, including
[eXtreme Gammon's font](https://www.extremegammon.com/font.aspx) and
[CTAN's bg package](https://www.ctan.org/pkg/bg). This experiment's focus is
SGF interpretation and position updates inside OpenType shaping. No claim of
being the first implementation is made; prior-art research is not exhaustive.
Their artwork and fonts are not bundled or reused.

Original board, checkers and pips; Copyright 2026 Michael Brackx.
Apache License 2.0; see the root [LICENSE](../../LICENSE). Font metadata permits
editable embedding (`fsType=0`).

Coordinates, counts, and diagnostics use smooth, proportional Roboto 2 outlines
baked into the font by [`game_text.py`](../shared/game_text.py). Roboto is
Copyright 2015 Google Inc., Apache 2.0; the font metadata retains its attribution.
See the root [third-party notices](../../THIRD_PARTY_NOTICES.md).
