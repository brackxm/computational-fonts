# computational-fonts

Experiments in using fonts for computation through OpenType shaping,
substitutions, ligatures, and glyph composition.

## Projects

| Project | Mode | Input or configuration | Editable document |
| --- | --- | --- | --- |
| [Markdown-style formatter](formatters/markdown/) | text formatter | flat emphasis, inline code, strikethrough and heading markers | [ODT specimen](formatters/markdown/markdown.odt) |
| [Morse code](decoders/morse/) | code decoder | dots and hyphens; spaces between letters, `/` between words | [ODT specimen](decoders/morse/morse.odt) |
| [Playfair](decoders/playfair-static/) | static decoder | key baked into font | [ODT specimen](decoders/playfair-static/playfair-static.odt) |
| [Vigenère](decoders/vigenere-static/) | static decoder | key baked into font | [ODT specimen](decoders/vigenere-static/vigenere-static.odt) |
| [Vigenère](decoders/vigenere-dynamic/) | dynamic decoder | `KEY~CIPHERTEXT` | [ODT specimen](decoders/vigenere-dynamic/vigenere-dynamic.odt) |
| [Enigma I](decoders/enigma-static/) | static decoder | machine settings baked into font | [ODT specimen](decoders/enigma-static/enigma-static.odt) |
| [Enigma I](decoders/enigma-dynamic/) | dynamic decoder | `ROTORS/POSITIONS/RINGS~CIPHERTEXT`; plugboard baked at build time | [ODT specimen](decoders/enigma-dynamic/enigma-dynamic.odt) |
| [Lorenz SZ40/SZ42](decoders/lorenz-static/) | static decoder | machine/wheel settings baked into font | [ODT specimen](decoders/lorenz-static/lorenz-static.odt) |
| [Snake — dynamic board](games/snake-dynamic/) | game prototype | `10x5b` builds a board; append `w`, `a`, `s`, and `d` to move | [ODT specimen](games/snake-dynamic/snake-dynamic.odt) |
| [Snake — fixed board](games/snake-fixed/) | game prototype | fixed 20×11 board by default; `b` starts; WASD or `2`, `4`, `8`, `6` moves | [ODT specimen](games/snake-fixed/snake-fixed.odt) |
| [The Last Light — text adventure](games/text-adventure/) | escape-room game | `start;` begins; append commands such as `east;take key;` | [ODT specimen](games/text-adventure/text-adventure.odt) |
| [Turtle graphics](graphics/turtle/) | drawing interpreter | `b` starts; `f`, `l`, `r`, `u`, `d` move, turn, and control the pen; `0`–`5` select colors | [ODT specimen](graphics/turtle/turtle.odt) |
| [Multi-format validator](validators/multi-format/) | dynamic validator | `format:value?`; 16 formats including IBAN, ISBN, ORCID, payment references, dates, UUIDs, and passport MRZ | [ODT specimen](validators/multi-format/validator.odt) |

Each project folder includes a `build.py` font generator, a bundled `.ttf`,
a `playground.html` browser demo, and a `readme.md` with usage and build notes.
Each also includes an editable `.odt` document named after the font, without
the trailing `-font`.

## Trying a font in a document

Open a project's **ODT specimen in LibreOffice Writer**. It embeds both the
computational font and the ordinary Roboto font, so no font installation or
local web server is needed. Each example shows identical underlying text in
both fonts. Edit a blue block to change the decoded text, validation result,
Snake board, Turtle drawing, adventure scene, or text formatting. Each copy can be edited independently.

The documents contain ordinary editable text and no macros or JavaScript.
Copying a computed result preserves the original input. Keep each computational
example on one line with consistent formatting and standard ligatures enabled;
other applications may shape the text differently.

The [validator specimen](validators/multi-format/validator.odt) includes
identifiers embedded in a sentence, checksum failures, and leap-year examples.
See [specimen build notes](specimens/readme.md) to regenerate the documents
after changing a bundled font.
The [adventure specimen](games/text-adventure/text-adventure.odt) starts a
playable journey; append commands such as `east;take key;` to its blue block.

## Repository layout

```text
decoders/
  enigma-dynamic/
  enigma-static/
  lorenz-static/
  morse/
  playfair-static/
  shared/
    __init__.py
    font_metadata.py
    fonts/roboto-2/
    test_decoders.py
  vigenere-dynamic/
  vigenere-static/
formatters/
  markdown/
games/
  shared/
    snake-controls.css
    snake-controls.js
    test_snake_controls.cjs
  snake-dynamic/
  snake-fixed/
  text-adventure/
graphics/
  turtle/
validators/
  multi-format/
    iban_registry.json
```

## Running a playground

Serve the project root so browsers can load the bundled fonts reliably:

```bash
python3 -m http.server 8000
```

Then open a demo, for example:

- Dynamic-board Snake: <http://localhost:8000/games/snake-dynamic/playground.html>
- Fixed-board Snake: <http://localhost:8000/games/snake-fixed/playground.html>
- Text adventure: <http://localhost:8000/games/text-adventure/playground.html>
- Vigenère: <http://localhost:8000/decoders/vigenere-dynamic/playground.html>
- Morse code: <http://localhost:8000/decoders/morse/playground.html>
- Markdown-style formatter: <http://localhost:8000/formatters/markdown/playground.html>
- Turtle graphics: <http://localhost:8000/graphics/turtle/playground.html>
- Validator: <http://localhost:8000/validators/multi-format/playground.html>

## Building fonts

The generators use Python 3.10 or later and FontTools:

```bash
python3 -m pip install fonttools
```

Run a generator from its project folder, following that project's readme.
By default, builders write their named font beside `build.py`, matching the
playground's asset. Use `--output` on any builder
to choose another destination; relative paths use your current directory.
All decoder builders default to the bundled Apache-2.0
[Roboto 2 base](decoders/shared/fonts/roboto-2/), pinned to upstream tag `v2.138`.
For example, from the repository root:

```bash
python3 decoders/vigenere-static/build.py --key LEMON
```

Use `--base /path/to/YourFont.ttf` to select another TrueType font with a
`glyf` table. Custom bases retain their own license and attribution metadata.
Builders reject an output path that would overwrite the base. Start markers
and delimiters must be separate from the input alphabet and whitespace.

For dynamic-board Snake:

```bash
cd games/snake-dynamic
python3 build.py
```

For turtle graphics (21×21 canvas by default):

```bash
python3 graphics/turtle/build.py
```

Use `--size WIDTHxHEIGHT` to build a custom turtle canvas; each dimension
must be between 3 and 25. See its [readme](graphics/turtle/readme.md) for details.

Build the multi-format validator demo with `python3 validators/multi-format/build.py --color`.
It uses the bundled Roboto base and a checked-in SWIFT IBAN registry snapshot;
validation executes in the font. See its readme for the supported rules.

Build the Markdown-style formatter with `python3 formatters/markdown/build.py`.
It combines regular, bold and italic Roboto outlines with formatting rules.
See its [readme](formatters/markdown/readme.md) for the supported subset.

The bundled fonts derived from Roboto use its outlines under Apache
License 2.0. Each generated font retains Google’s copyright and identifies
the modifications by Michael Brackx. A custom base may require different terms.

## Tests

Run the decoder regression suite from the repository root:

```bash
python3 -m unittest discover -s decoders -p 'test_*.py' -v
```

The suite requires FontTools. Install HarfBuzz's `hb-shape` command to run
the font shaping checks; without it, those checks are reported as skipped.
Tests cover known plaintext vectors, all Playfair letter pairs (including
the J/I alias), all Morse characters and whole-group boundaries, runtime keys
and machine settings, Enigma double stepping,
Lorenz shift controls and all three models, text limits, font names, and
builder output paths. Both bundled fonts and fresh builds are shaped.
Builds use a small original fixture font and the bundled Roboto base in
temporary directories and leave the shipped assets unchanged. Tests also
verify base integrity, default selection, retained license metadata, marker
validation, oversized runtime keys, malformed base-font tables and wheel-pattern files,
localized font names, reserved
glyph collisions, custom-base spacing, and protection against overwriting the base.

Run the game suites and browser control checks:

```bash
python3 -m unittest discover -s games/snake-dynamic -p 'test_*.py' -v
python3 -m unittest discover -s games/snake-fixed -p 'test_*.py' -v
node games/shared/test_snake_controls.cjs
python3 -m unittest discover -s games/text-adventure -p 'test_*.py' -v
node games/text-adventure/test_controls.cjs
```

The dynamic Snake suite checks all 49 supported board sizes, fresh builds,
loss/win signals, and safe imports. The fixed suite also covers custom sizes,
growth, collisions, food placement, and move limits. Node.js and `hb-shape`
are required for the shared control checks.

Run the turtle font and playground checks:

```bash
python3 -m unittest discover -s graphics/turtle -p 'test_*.py' -v
node graphics/turtle/test_turtle_controls.cjs
```

These verify paths against an independent interpreter, turns, pen state,
boundaries, command limits, custom canvas builds, and playground controls.
FontTools is required; shaping checks require `hb-shape`.

Run the validator suite with:

```bash
python3 -m unittest discover -s validators/multi-format -p 'test_*.py' -v
```

It checks fresh and bundled fonts with HarfBuzz, all 89 IBAN registry examples,
the other 15 formats, checksum mutations, malformed input, and incomplete runs.

## Limitations

Validator results establish only the implemented structure and checksum checks.
They do not establish registration, account existence, ownership, or document
authenticity. Keep requests in one shaping run with standard ligatures enabled;
copying a visual verdict preserves its underlying request. See the validator
readme for format-specific coverage and shaping limits.

The decoders are computational/display fonts, not cryptographic security
tools. Copying, searching, accessibility APIs, or software that bypasses
OpenType shaping can expose the underlying ciphertext/configuration.
Shaping engines can split text into runs in ways that reset stateful decoders.

Dynamic-board Snake supports boards from 4×4 to 10×10 cells, evaluates up to eight appended
moves, and uses one deterministic food/win target. Standard ligatures (`liga`)
must be enabled and the input must be shaped as one uninterrupted text run.

The second [Snake prototype](games/snake-fixed/) uses a board fixed at build
time (20×11 by default, configurable with `--size WIDTHxHEIGHT`), evaluates
up to 128 moves, and grows the snake through up to eight deterministic food
targets. Walls, reversals, and body collisions end the game.
Food waits if its next cell is occupied. Both playgrounds stop accepting moves
after a win, loss, or their move limit, and Undo restores the previous position.

[The Last Light](games/text-adventure/) has eight rooms, four collectible items,
and puzzles involving a locked door, a lamp, a generator and an exit gate.
Its font evaluates up to 128 semicolon-terminated commands of at most 24 ASCII
characters each, in one uninterrupted run. It displays the latest scene as
glyph outlines; copying or accessibility APIs expose the command history.
The browser controller edits that history and provides Undo and save/restore.

[Turtle graphics](graphics/turtle/) uses single-cell steps and 90° turns on a
fixed canvas, six pen colors, and up to 128 commands. A boundary stops execution;
pen-up moves leave no strokes. It requires `liga` and one uninterrupted
left-to-right run.

## AI disclosure

This project includes work developed with assistance from OpenAI GPT models
through ChatGPT and Codex.

## License

Licensed under the Apache License 2.0. See [`LICENSE`](LICENSE).
The bundled Roboto sources and fonts derived from them are also
Apache-2.0; Snake, turtle and text-adventure fonts use original outlines.
Google’s font attribution and the required original MIT notice for imported decoder code
are retained in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
