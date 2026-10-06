# Snake — fixed 20×11 board

A second computational OpenType Snake prototype, with the board size baked
into its font: **20 columns × 11 rows (220 cells)** by default.
Choose a different size when building the font.

## Usage

Start the board with `b`. Append `w`, `a`, `s`, and `d` to move up, left,
down, and right. The font also accepts keypad digits `2`, `4`, `8`,
and `6` for the same moves. No dimensions are entered at runtime.

```text
b
bddwwa
```

The snake starts with three cells, heading right, with its head at `(2, 5)`.
Coordinates begin at `(0, 0)` in the bottom-left. The first food is at `(18, 9)`.
Eating it grows the snake and places the next food. Collect all eight targets
to win, ending with an eleven-cell snake. The targets follow this fixed route:

```text
(18, 9) → (1, 9) → (1, 1) → (18, 1)
→ (18, 9) → (1, 9) → (1, 1) → (18, 1)
```

The direct winning route takes **112 moves**: right 16, up 4, left 17,
down 8, right 17, up 8, left 17, down 8, right 17. Food sits one cell inside
the walls, leaving space to turn after a pickup.
If the next target is occupied, food waits until the snake clears that cell.

## Playground

From the repository root:

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000/games/snake-fixed/playground.html>.
Use arrow keys, WASD, keypad digits, or the on-screen buttons.
New game resets the input; Undo removes its last move.
Movement stops after a win, loss, or the move limit. Undo immediately returns
to the previous position without consuming ignored key presses.

## Build

```bash
python3 -m pip install fonttools
python3 games/snake-fixed/build.py
```

Optionally choose the board size at build time:

```bash
python3 games/snake-fixed/build.py --size 16x10
python3 games/snake-fixed/build.py --size 16x10 --output /path/to/snake-16x10.ttf
```

With no options, the generator builds the default 20×11 board and writes
`snake-fixed-font.ttf` beside its source. Other sizes get their own filename,
such as `snake-fixed-16x10-font.ttf`. `--output` overrides the destination.
The bundled playground continues to use the default 20×11 font.

Width must be at least 4 and height at least 1, with at most 1024 cells.
Sizes whose first food requires more than 128 moves are rejected. Dimensions,
initial position, border, collision rules, and font names all use the chosen
size; the size is fixed inside each generated font, with no runtime size input.
For a custom board, the head starts at `(2, height // 2)`. Boards at least
8×6 use the same circuit, adapted to their dimensions; the number of food
targets is capped at eight and reduced if the direct route would exceed
128 moves. Smaller boards retain one top-right food target, because they
cannot safely accommodate the growing snake's full circuit.

The generator uses original geometric glyph outlines and does not require
a base font.

With FontTools and HarfBuzz's `hb-shape` installed, run the builder and font
regression checks:

```bash
python3 -m unittest discover -s games/snake-fixed -p 'test_*.py'
```

With Node.js and `hb-shape`, check both playgrounds' shared controls against
the bundled fonts:

```bash
node games/shared/test_snake_controls.cjs
```

## Implementation and limits

- Board size fixed at build time (20×11 by default); up to **128 appended moves**
  in one uninterrupted run.
- Three-cell snake that grows after each pickup, with up to eight deterministic
  food targets. The final pickup ends the game with a crown. Food follows a
  fixed sequence; it is not random. Movement is controlled by the player.
- Walls, immediate reversals, and body collisions end the game with an X;
  there is no wrapping. Moving into a tail cell is allowed when it vacates
  on that move; eating keeps the tail in place.
- Standard OpenType ligatures (`liga`) must be enabled.
- The font performs board construction, movement, growth, food changes,
  collision, and win substitutions. Terminal glyphs report loss/win through
  one/two units of advance. JavaScript measures that signal to stop movement,
  display the result, and keep Undo aligned with the evaluated moves.

Fixing the board removes dimension parsing and runtime dimension state.
The border is one static glyph; coordinate body/head glyphs overlay it.
Head glyphs carry the current direction, allowing reversals and boundaries
to use direct ligatures. The food glyph tracks the pickup count; it selects
the tail length and next target. Body glyphs also serve as collision state.
Compact pass lookups call shared rule tables to keep repeated shaping within
engine validation limits. No complete board states or move histories are
enumerated.

## License

Apache License 2.0; see the root [LICENSE](../../LICENSE).
