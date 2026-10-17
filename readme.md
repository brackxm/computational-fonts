# computational-fonts

Experiments in using fonts for computation through OpenType shaping,
substitutions, ligatures, and glyph composition.

## Projects

| Project | Mode | Input or configuration | LibreOffice | Word (experimental) |
| --- | --- | --- | --- | --- |
| [PPM image renderer](graphics/ppm/) | text image format | plain PPM (`P3`) RGB | [ODT](graphics/ppm/ppm.odt) | [DOCX](graphics/ppm/ppm.docx) |
| [PGM image renderer](graphics/pgm/) | text image format | plain PGM (`P2`) grayscale | [ODT](graphics/pgm/pgm.odt) | [DOCX](graphics/pgm/pgm.docx) |
| [PBM image renderer](graphics/pbm/) | text image format | plain PBM (`P1`) bitmap | [ODT](graphics/pbm/pbm.odt) | [DOCX](graphics/pbm/pbm.docx) |
| [Mini BASIC](languages/mini-basic/) | programming language | numbered BASIC statements | [ODT](languages/mini-basic/mini-basic.odt) | [DOCX](languages/mini-basic/mini-basic.docx) |
| [SKI evaluator](languages/ski/) | combinatory logic | `S`, `K`, `I`, lowercase atoms and application | [ODT](languages/ski/ski.odt) | [DOCX](languages/ski/ski.docx) |
| [JSON formatter](formatters/json/) | text formatter | JSON text | [ODT](formatters/json/json.odt) | [DOCX](formatters/json/json.docx) |
| [Markdown-style formatter](formatters/markdown/) | text formatter | flat emphasis, inline code, strikethrough and heading markers | [ODT](formatters/markdown/markdown.odt) | [DOCX](formatters/markdown/markdown.docx) |
| [Morse code](decoders/morse/) | code decoder | dots and hyphens; spaces between letters, `/` between words | [ODT](decoders/morse/morse.odt) | [DOCX](decoders/morse/morse.docx) |
| [Playfair](decoders/playfair-static/) | static decoder | key baked into font | [ODT](decoders/playfair-static/playfair-static.odt) | [DOCX](decoders/playfair-static/playfair-static.docx) |
| [Vigenère](decoders/vigenere-static/) | static decoder | key baked into font | [ODT](decoders/vigenere-static/vigenere-static.odt) | [DOCX](decoders/vigenere-static/vigenere-static.docx) |
| [Vigenère](decoders/vigenere-dynamic/) | dynamic decoder | `KEY~CIPHERTEXT` | [ODT](decoders/vigenere-dynamic/vigenere-dynamic.odt) | [DOCX](decoders/vigenere-dynamic/vigenere-dynamic.docx) |
| [Enigma I](decoders/enigma-static/) | static decoder | machine settings baked into font | [ODT](decoders/enigma-static/enigma-static.odt) | [DOCX](decoders/enigma-static/enigma-static.docx) |
| [Enigma I](decoders/enigma-dynamic/) | dynamic decoder | `ROTORS/POSITIONS/RINGS~CIPHERTEXT` | [ODT](decoders/enigma-dynamic/enigma-dynamic.odt) | [DOCX](decoders/enigma-dynamic/enigma-dynamic.docx) |
| [Lorenz SZ40/SZ42](decoders/lorenz-static/) | static decoder | machine/wheel settings baked into font | [ODT](decoders/lorenz-static/lorenz-static.odt) | [DOCX](decoders/lorenz-static/lorenz-static.docx) |
| [Snake — dynamic board](games/snake-dynamic/) | game prototype | dimensions and movement history | [ODT](games/snake-dynamic/snake-dynamic.odt) | [DOCX](games/snake-dynamic/snake-dynamic.docx) |
| [Snake — fixed board](games/snake-fixed/) | game prototype | movement history; board size baked into font | [ODT](games/snake-fixed/snake-fixed.odt) | [DOCX](games/snake-fixed/snake-fixed.docx) |
| [The Last Light — text adventure](games/text-adventure/) | escape-room game | semicolon-terminated commands | [ODT](games/text-adventure/text-adventure.odt) | [DOCX](games/text-adventure/text-adventure.docx) |
| [Turtle graphics](graphics/turtle/) | drawing interpreter | movement, pen and color commands | [ODT](graphics/turtle/turtle.odt) | [DOCX](graphics/turtle/turtle.docx) |
| [Multi-format validator](validators/multi-format/) | dynamic validator | `format:value?` | [ODT](validators/multi-format/validator.odt) | [DOCX](validators/multi-format/validator.docx) |

Each project folder includes a `build.py` font generator, a bundled `.ttf`,
a `playground.html` browser demo, editable `.odt` and `.docx` specimens, and a `readme.md`
with usage, build commands, tests and limitations. SKI also includes a machine
font and CLI for inspecting results and the internal tree tape.

## Trying a font in a document

Open a project's **ODT specimen in LibreOffice Writer**. It embeds both the
computational font and ordinary Roboto, so no font installation or local web
server is needed. Each example shows identical underlying text in both fonts.
Edit a blue block to change the computed result; each copy is independent.

The documents contain ordinary editable text and no macros or JavaScript.
Copying a computed result preserves the original input. Keep each example
on one line with consistent formatting and standard ligatures enabled;
other applications may shape the text differently.

For desktop Microsoft Word, use the **DOCX specimen** beside the ODT. Both
fonts are embedded in full, with standard ligatures and contextual alternates
enabled in the computational examples. Recipients do not need to install the
fonts in applications that load DOCX embedded fonts. These files are Word
candidates: package checks and LibreOffice previews do not verify Word's
shaping engine. Word rendering, especially long programs, games and color
fonts, still needs testing on Windows and Mac. Word's ODT import may show only
the underlying text; use the native DOCX rather than converting the ODT in Word.

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

Most generators use Python 3.10 or later and FontTools:

```bash
python3 -m pip install fonttools
```

SKI uses Python 3.11 or later and its own
[pinned requirements](languages/ski/requirements.txt) for reproducible builds.

Follow the build commands in the project's README. Builders write their font
beside `build.py` by default; `--output` selects another destination, relative
to your current directory. Font sources and attribution are documented in
the [Roboto provenance notes](decoders/shared/fonts/roboto-2/).

## Tests

Test commands and coverage live in each project's README. The
[shared decoder notes](decoders/shared/readme.md#tests) describe the decoder
regression suite. Font tests require FontTools and HarfBuzz's `hb-shape` for
shaping checks; browser controller tests use Node.js.

The [SKI regression gate](languages/ski/readme.md#tests) uses HarfBuzz's shared
library directly and includes protocol, reproducibility, differential and
depth-six tests. Its project requirements pin FontTools for reproducible builds.

## AI disclosure

This project includes work developed with assistance from OpenAI GPT models
through ChatGPT and Codex.

## License

Licensed under the Apache License 2.0. See [`LICENSE`](LICENSE).
Bundled Roboto sources and fonts derived from them are also Apache-2.0.
Upstream font attribution and imported-code notices are retained in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
