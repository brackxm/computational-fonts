# computational-fonts

Experiments that use fonts as computation rather than only presentation.
This project combines classical-cipher decoders, Snake games, and identifier
validators implemented with OpenType shaping, substitutions, ligatures, and
glyph composition.

## Projects

| Project | Mode | Input or configuration |
| --- | --- | --- |
| [Playfair](decoders/playfair-static/) | static decoder | key baked into font |
| [Vigenère](decoders/vigenere-static/) | static decoder | key baked into font |
| [Vigenère](decoders/vigenere-dynamic/) | dynamic decoder | `KEY~CIPHERTEXT` |
| [Enigma I](decoders/enigma-static/) | static decoder | machine settings baked into font |
| [Enigma I](decoders/enigma-dynamic/) | dynamic decoder | `ROTORS/POSITIONS/RINGS~CIPHERTEXT`; plugboard baked at build time |
| [Lorenz SZ40/SZ42](decoders/lorenz-static/) | static decoder | machine/wheel settings baked into font |
| [Snake — dynamic board](games/snake-dynamic/) | game prototype | `10x5b` builds a board; append `w`, `a`, `s`, and `d` to move |
| [Snake — fixed board](games/snake-fixed/) | game prototype | fixed 20×11 board by default; `b` starts; WASD or `2`, `4`, `8`, `6` moves |
| [Multi-format validator](validators/multi-format/) | dynamic validator | `format:value?`; 16 formats including IBAN, ISBN, ORCID, payment references, dates, UUIDs, and passport MRZ |

Each project folder includes a `build.py` font generator, a bundled `.ttf`,
a `playground.html` browser demo, and a `readme.md` with usage and build notes.

## Repository layout

```text
decoders/
  enigma-dynamic/
  enigma-static/
  lorenz-static/
  playfair-static/
  shared/
    __init__.py
    font_metadata.py
    fonts/roboto-2/
    test_decoders.py
  vigenere-dynamic/
  vigenere-static/
games/
  shared/
    snake-controls.css
    snake-controls.js
    test_snake_controls.cjs
  snake-dynamic/
  snake-fixed/
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
- Vigenère: <http://localhost:8000/decoders/vigenere-dynamic/playground.html>
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

Build the multi-format validator demo with `python3 validators/multi-format/build.py --color`.
It uses the bundled Roboto base and a checked-in SWIFT IBAN registry snapshot;
validation executes in the font. See its readme for the supported rules.

The bundled decoder and validator fonts use Roboto outlines under Apache
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
the J/I alias), runtime keys and machine settings, Enigma double stepping,
Lorenz shift controls and all three models, text limits, font names, and
builder output paths. Both bundled fonts and fresh builds are shaped.
Builds use a small original fixture font and the bundled Roboto base in
temporary directories and leave the shipped assets unchanged. Tests also
verify base integrity, default selection, retained license metadata, marker
validation, oversized runtime keys, malformed base-font tables and wheel-pattern files,
localized font names, reserved
glyph collisions, custom-base spacing, and protection against overwriting the base.

Run the Snake suites and shared control checks:

```bash
python3 -m unittest discover -s games/snake-dynamic -p 'test_*.py' -v
python3 -m unittest discover -s games/snake-fixed -p 'test_*.py' -v
node games/shared/test_snake_controls.cjs
```

The dynamic Snake suite checks all 49 supported board sizes, fresh builds,
loss/win signals, and safe imports. The fixed suite also covers custom sizes,
growth, collisions, food placement, and move limits. Node.js and `hb-shape`
are required for the shared control checks.

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

## AI disclosure

This project includes work developed with assistance from OpenAI GPT models
through ChatGPT and Codex.

## License

Licensed under the Apache License 2.0. See [`LICENSE`](LICENSE).
The bundled Roboto base and generated decoder and validator fonts are also Apache-2.0;
Snake fonts use original outlines. Google’s font attribution and the required
original MIT notice for imported decoder code are retained in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
