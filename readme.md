# computational-fonts

Experiments in using fonts for computation through OpenType shaping,
substitutions, ligatures, and glyph composition.

## Projects

| Project | Mode | Input or configuration | Editable document |
| --- | --- | --- | --- |
| [Mini BASIC](languages/mini-basic/) | programming language | numbered BASIC statements | [ODT specimen](languages/mini-basic/mini-basic.odt) |
| [JSON formatter](formatters/json/) | text formatter | JSON text | [ODT specimen](formatters/json/json.odt) |
| [Markdown-style formatter](formatters/markdown/) | text formatter | flat emphasis, inline code, strikethrough and heading markers | [ODT specimen](formatters/markdown/markdown.odt) |
| [Morse code](decoders/morse/) | code decoder | dots and hyphens; spaces between letters, `/` between words | [ODT specimen](decoders/morse/morse.odt) |
| [Playfair](decoders/playfair-static/) | static decoder | key baked into font | [ODT specimen](decoders/playfair-static/playfair-static.odt) |
| [Vigenère](decoders/vigenere-static/) | static decoder | key baked into font | [ODT specimen](decoders/vigenere-static/vigenere-static.odt) |
| [Vigenère](decoders/vigenere-dynamic/) | dynamic decoder | `KEY~CIPHERTEXT` | [ODT specimen](decoders/vigenere-dynamic/vigenere-dynamic.odt) |
| [Enigma I](decoders/enigma-static/) | static decoder | machine settings baked into font | [ODT specimen](decoders/enigma-static/enigma-static.odt) |
| [Enigma I](decoders/enigma-dynamic/) | dynamic decoder | `ROTORS/POSITIONS/RINGS~CIPHERTEXT` | [ODT specimen](decoders/enigma-dynamic/enigma-dynamic.odt) |
| [Lorenz SZ40/SZ42](decoders/lorenz-static/) | static decoder | machine/wheel settings baked into font | [ODT specimen](decoders/lorenz-static/lorenz-static.odt) |
| [Snake — dynamic board](games/snake-dynamic/) | game prototype | dimensions and movement history | [ODT specimen](games/snake-dynamic/snake-dynamic.odt) |
| [Snake — fixed board](games/snake-fixed/) | game prototype | movement history; board size baked into font | [ODT specimen](games/snake-fixed/snake-fixed.odt) |
| [The Last Light — text adventure](games/text-adventure/) | escape-room game | semicolon-terminated commands | [ODT specimen](games/text-adventure/text-adventure.odt) |
| [Turtle graphics](graphics/turtle/) | drawing interpreter | movement, pen and color commands | [ODT specimen](graphics/turtle/turtle.odt) |
| [Multi-format validator](validators/multi-format/) | dynamic validator | `format:value?` | [ODT specimen](validators/multi-format/validator.odt) |

Each project folder includes a `build.py` font generator, a bundled `.ttf`,
a `playground.html` browser demo, an editable `.odt` specimen, and a `readme.md`
with usage, build commands, tests and limitations.

## Trying a font in a document

Open a project's **ODT specimen in LibreOffice Writer**. It embeds both the
computational font and ordinary Roboto, so no font installation or local web
server is needed. Each example shows identical underlying text in both fonts.
Edit a blue block to change the computed result; each copy is independent.

The documents contain ordinary editable text and no macros or JavaScript.
Copying a computed result preserves the original input. Keep each example
on one line with consistent formatting and standard ligatures enabled;
other applications may shape the text differently.

See [specimen build notes](specimens/readme.md) to regenerate documents
after changing a bundled font.

## Running a playground

Serve the repository root so browsers can load the bundled fonts reliably:

```bash
python3 -m http.server 8000
```

Open the project's `playground.html` through <http://localhost:8000>.
Each project README gives its URL and controls.

## Building fonts

The generators use Python 3.10 or later and FontTools:

```bash
python3 -m pip install fonttools
```

Follow the build commands in the project's README. Builders write their font
beside `build.py` by default; `--output` selects another destination, relative
to your current directory. Font sources and attribution are documented in
the [Roboto provenance notes](decoders/shared/fonts/roboto-2/).

## Tests

Test commands and coverage live in each project's README. The
[shared decoder notes](decoders/shared/readme.md#tests) describe the decoder
regression suite. Font tests require FontTools and HarfBuzz's `hb-shape` for
shaping checks; browser controller tests use Node.js.

## AI disclosure

This project includes work developed with assistance from OpenAI GPT models
through ChatGPT and Codex.

## License

Licensed under the Apache License 2.0. See [`LICENSE`](LICENSE).
Bundled Roboto sources and fonts derived from them are also Apache-2.0.
Upstream font attribution and imported-code notices are retained in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
