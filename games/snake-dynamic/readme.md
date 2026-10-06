# Snake — dynamic board

A Snake game prototype implemented as a computational OpenType font, with
board dimensions supplied in the input at runtime.

For a 20×11 board built into the font, see the second
[fixed-board Snake](../snake-fixed/) prototype.

Unlike a version that stores one glyph for every complete board state, this prototype uses reusable coordinate/cell glyphs and OpenType GSUB substitutions to mutate game state as movement characters are appended.

## Editable document

Open [snake-dynamic.odt](snake-dynamic.odt) in LibreOffice Writer. It embeds the font
and shows the same editable sample text in an ordinary font and in this
computational font. Follow the document's "Try it" instructions to change
the result directly in the text.

## Syntax

Start a game with:

```text
10x5b
```

The first number is the width, the second is the height, and `b` builds the board. Append `w`, `a`, `s`, and `d` to move:

```text
10x5bddwwa
```

## Current limits

- width: 4–10 cells
- height: 4–10 cells
- up to 8 appended moves are evaluated in this prototype
- one deterministic food/win target
- standard OpenType ligatures (`liga`) must be enabled
- the input must be shaped as one uninterrupted text run

The food is placed toward the top-right within eight moves of the initial head,
so every supported board has a winning route. On the default 10×5 board, seven
right moves followed by one up move win: `10x5bdddddddw`.
The playground rounds entered dimensions to whole cells and limits them to 4–10.
Both Snake playgrounds share the same directional pad: arrow keys, WASD, or
keypad digits `2` (up), `4` (left), `8` (down), and `6` (right). The playground
converts keypad input into movement letters; dimensions can still be edited normally.
Movement stops after a win, loss, or eight moves. Undo returns to the previous
position; key presses after the game ends do not enter the history.
The board scales to fit the available width, with cells up to 64 pixels across;
its SVG text viewport keeps the grid centered and reserves room for the crown.

The dimension range exists because OpenType cannot dynamically allocate new glyph records during shaping. The font predefines a coordinate grid up to 10×10, but does **not** enumerate every possible complete Snake board or move history.

## Files

- `snake-dynamic-font.ttf` — generated font
- `build.py` — font generation source
- `playground.html` — browser test interface
- `readme.md` — this file

## Build

The build script uses `fontTools`.

```bash
python3 build.py
python3 build.py --output /path/to/snake-dynamic.ttf
```

Without `--output`, the font is written beside `build.py`. Relative output
paths use the current working directory. Importing the builder does not
write files. The generated font embeds Michael Brackx’s copyright and
Apache License 2.0 metadata.

## Tests

From the repository root, with FontTools and `hb-shape` installed:

```bash
python3 -m unittest discover -s games/snake-dynamic -p 'test_*.py' -v
node games/shared/test_snake_controls.cjs
```

## License

Apache License 2.0; see the root [LICENSE](../../LICENSE).
