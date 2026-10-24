# Kayles: a perfect twelve-pin opponent in a font

[Play in your browser](playground.html). Each turn knocks down one standing
pin or two adjacent standing pins. The player taking the last pin wins.
Adjacency always means neighbors in the original row: fallen pins leave gaps
and never bring other pins together. These are [Berkeley's Kayles rules](https://gamescrafters.berkeley.edu/games/puzzles/software.php?game=kayles).

Start with `h` to move first or `b` for the font to start. Append only your
removals: `01S;` removes pin 01, `06D;` removes pins 06 and 07. Pin numbers
must be two digits, 01–12; `S` means single and `D` means double. Every move
ends with a semicolon. Spaces, tabs and line breaks are insignificant. Missing
pins, missing neighbors and `12D;` are invalid moves. Other syntax is malformed.
Errors retain the valid prefix. A finished game ignores trailing input.
The gold box marks the latest font removal; all original pin labels remain.

## Exact solution and font execution

The build enumerates all 4,096 occupancy patterns, with 7,815 reachable
occupancy/turn states. Exact minimax determines every outcome and terminal
distance. First player wins with perfect play, in 11 plies against optimal
delaying defense. The opponent takes the fastest forced win, delays a forced
loss, and breaks equal ties lexically. Both starting roles and every human
continuation against the selected policy are compiled.

The rules, validation, opponent replies, end detection and original pin artwork
run entirely in GSUB. The browser transports source and tracks Undo. There is
no runtime search, external strategy data or JavaScript board model. This is
normal-play twelve-pin Kayles; other sizes and misère rules are unsupported.
The shared forward-cursor compiler needs no repeated shaping clock.

The [Chomp transport/status protocol](../chomp/readme.md) applies: U+E000/U+E001
framing, ASCII or private-use aliases, one LTR run with `liga`, no kerning or
letter/word spacing. Advance is 1,800 units plus status 1–6. Color uses COLRv0
and monochrome outlines remain usable. The playground caps input at 1,024
characters; actual host shaping limits apply.

The bundled font contains 1,743 glyphs, 814 GSUB lookups and 519,064 bytes.

## Build and verification

Python 3.10+, FontTools, native HarfBuzz/`hb-shape`, and Node.js are required:

```sh
python3 games/kayles/build.py
python3 games/kayles/test_font.py -v
node games/kayles/test_controls.cjs
python3 -m http.server 8000
```

`--output` selects another destination; importing the builder writes nothing.
Independent tests compute Sprague–Grundy values for intact runs, XOR them
across gaps, and compare every state with the exact solver. Set-based move
generation checks every transition and guards against pins becoming adjacent
across a gap. Native HarfBuzz tests exercise every compiled removal, invalid
move, malformed input and stopped state, together with reachable policy
histories, terminal freezing, transport, metrics and disabled ligatures.
Controller tests exercise both roles and outcomes, Undo/reset, stale clearing,
and missing, rejected or incompatible fonts using actual font measurements.

Original implementation, generated policy and artwork; Apache 2.0.

Typography uses original, proportional [Game Sans](../shared/fonts/game-sans/readme.md)
Regular and Bold outlines, Copyright 2026 Michael Brackx, Apache 2.0.
Text is baked in at build time; no installed typeface or runtime font download
is required, and no third-party font outlines are used.
