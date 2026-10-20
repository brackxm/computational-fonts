# computational-fonts

Experiments in using fonts for computation through OpenType shaping,
substitutions, ligatures, and glyph composition.

**[Try the interactive demos](https://brackxm.github.io/computational-fonts/)** —
explore all 38 playgrounds in your browser, with no installation needed.

## Projects

| Project | Mode | Input or configuration | Editable document |
| --- | --- | --- | --- |
| [PPM image renderer](graphics/ppm/) | text image format | plain PPM (`P3`) RGB | [ODT specimen](graphics/ppm/ppm.odt) |
| [PGM image renderer](graphics/pgm/) | text image format | plain PGM (`P2`) grayscale | [ODT specimen](graphics/pgm/pgm.odt) |
| [PBM image renderer](graphics/pbm/) | text image format | plain PBM (`P1`) bitmap | [ODT specimen](graphics/pbm/pbm.odt) |
| [Mini BASIC](languages/mini-basic/) | programming language | numbered BASIC statements | [ODT specimen](languages/mini-basic/mini-basic.odt) |
| [SKI evaluator](languages/ski/) | combinatory logic | `S`, `K`, `I`, lowercase atoms and application | [ODT specimen](languages/ski/ski.odt) |
| [WebAssembly](languages/wasm/) | bounded integer compiler | `.wat` or `.wasm` compiled to GSUB glyph registers | [Browser playground](languages/wasm/playground.html) |
| [Verilog](languages/verilog/) | bounded combinational compiler | signed/unsigned `.v` modules compiled to GSUB gates | [Browser playground](languages/verilog/playground.html) |
| [JSON formatter](formatters/json/) | text formatter | JSON text | [ODT specimen](formatters/json/json.odt) |
| [Markdown-style formatter](formatters/markdown/) | text formatter | flat emphasis, inline code, strikethrough and heading markers | [ODT specimen](formatters/markdown/markdown.odt) |
| [Arabizi Annotated](decoders/arabizi/) | transliteration font | Arabizi letters and digits; original shorthand above Arabic | [Browser playground](decoders/arabizi/playground.html) |
| [Morse code](decoders/morse/) | code decoder | dots and hyphens; spaces between letters, `/` between words | [ODT specimen](decoders/morse/morse.odt) |
| [Playfair](decoders/playfair-static/) | static decoder | key baked into font | [ODT specimen](decoders/playfair-static/playfair-static.odt) |
| [Vigenère](decoders/vigenere-static/) | static decoder | key baked into font | [ODT specimen](decoders/vigenere-static/vigenere-static.odt) |
| [Vigenère](decoders/vigenere-dynamic/) | dynamic decoder | `KEY~CIPHERTEXT` | [ODT specimen](decoders/vigenere-dynamic/vigenere-dynamic.odt) |
| [Enigma I](decoders/enigma-static/) | static decoder | machine settings baked into font | [ODT specimen](decoders/enigma-static/enigma-static.odt) |
| [Enigma I](decoders/enigma-dynamic/) | dynamic decoder | `ROTORS/POSITIONS/RINGS~CIPHERTEXT` | [ODT specimen](decoders/enigma-dynamic/enigma-dynamic.odt) |
| [Lorenz SZ40/SZ42](decoders/lorenz-static/) | static decoder | machine/wheel settings baked into font | [ODT specimen](decoders/lorenz-static/lorenz-static.odt) |
| [Snake — dynamic board](games/snake-dynamic/) | game prototype | dimensions and movement history | [ODT specimen](games/snake-dynamic/snake-dynamic.odt) |
| [Snake — fixed board](games/snake-fixed/) | game prototype | movement history; board size baked into font | [ODT specimen](games/snake-fixed/snake-fixed.odt) |
| [Connect Four](games/connect-four/) | first-player winning opponent | `b` plus human column digits; complete game in one shaping run | [Browser playground](games/connect-four/playground.html) |
| [Backgammon SGF replay](games/backgammon/) | replay prototype | bounded linear SGF; up to 128 turns | [Browser playground](games/backgammon/playground.html) |
| [Notakto](games/notakto/) | perfect first-player opponent | three boards; human-only move history | [Browser playground](games/notakto/playground.html) |
| [Wythoff’s Nim](games/wythoff/) | perfect opponent | two configurable heaps of 0–63 tokens; either player first | [Browser playground](games/wythoff/playground.html) |
| [Cram](games/cram/) | perfect first-player opponent | solved 6×5 board; human-only domino placements | [Browser playground](games/cram/playground.html) |
| [Mū tōrere](games/mu-torere/) | perfect win/loss/draw opponent | origin-point history; either first player and two puzzles | [Browser playground](games/mu-torere/playground.html) |
| [Hexapawn](games/hexapawn/) | perfect opponent on either side | standard 3×3 board; human-only coordinate moves | [Browser playground](games/hexapawn/playground.html) |
| [Nim](games/nim/) | perfect normal/misère opponent | three configurable 0–31 heaps; font-computed XOR display | [Browser playground](games/nim/playground.html) |
| [Chomp](games/chomp/) | perfect opponent on either side | complete 6×5 chocolate bar; human-only bites | [Browser playground](games/chomp/playground.html) |
| [Dodgem](games/dodgem/) | perfect opponent on either side | standard 3×3 car race; human-only moves | [Browser playground](games/dodgem/playground.html) |
| [Domineering](games/domineering/) | perfect opponent on either side | solved 4×4 board; vertical versus horizontal dominoes | [Browser playground](games/domineering/playground.html) |
| [Kayles](games/kayles/) | perfect opponent on either side | twelve pins; remove one or two original neighbors | [Browser playground](games/kayles/playground.html) |
| [Achi](games/achi/) | perfect win/loss/draw opponent | Berkeley three-counter variant; placement and sliding | [Browser playground](games/achi/playground.html) |
| [Dots and Boxes](games/dots-and-boxes/) | perfect score-maximizing opponent | 2×2 boxes; scoring and bonus turns inside the font | [Browser playground](games/dots-and-boxes/playground.html) |
| [Tic-tac-toe](games/tic-tac-toe/) | perfect opponent on either side | standard 3×3 board; complete policy in 150 KB | [Browser playground](games/tic-tac-toe/playground.html) |
| [The Last Light — text adventure](games/text-adventure/) | escape-room game | semicolon-terminated commands | [ODT specimen](games/text-adventure/text-adventure.odt) |
| [SMILES diagrams](graphics/smiles/) | molecular graph renderer | bounded SMILES with atoms, bonds, branches and rings | [ODT specimen](graphics/smiles/smiles.odt) |
| [Turtle graphics](graphics/turtle/) | drawing interpreter | movement, pen and color commands | [ODT specimen](graphics/turtle/turtle.odt) |
| [Multi-format validator](validators/multi-format/) | dynamic validator | `format:value?` | [ODT specimen](validators/multi-format/validator.odt) |

Most display-font project folders include a `build.py` font generator, a bundled `.ttf`,
a `playground.html` browser demo, an editable `.odt` specimen, and a `readme.md`
with usage, build commands, tests and limitations. SKI also includes a machine
font and CLI for inspecting results and the internal tree tape.

Connect Four reconstructs human-only histories such as `b135`, automatically
plays Red first, and follows the complete pinned WeakC4 winning strategy. Its
[playground](games/connect-four/playground.html) includes column controls, editable
history, undo and reset. All game logic runs in OpenType shaping. The strategy
and derived fonts are **GPL-3.0**, an exception to the repository default; see
[provenance, verification and limits](games/connect-four/readme.md).

Backgammon reads a documented linear SGF subset from the standard starting
position. Its font updates all 24 points, separate bars and off counters, hits,
entry, bearing off, and latest dice during shaping. Try its
[playground](games/backgammon/playground.html) after serving this repository.
Replay completion does not establish legality. The prototype supports 128 turns;
variations, setup positions, cube actions and full metadata are unsupported.
See the [subset, status signals and tests](games/backgammon/readme.md).

WebAssembly uses invisible glyph registers with a command-line HarfBuzz harness
and a [browser playground](languages/wasm/playground.html). The playground bundles
compiled examples and their matching ABI manifests. See its
[quick start and execution limits](languages/wasm/readme.md).

Verilog compiles a two-state combinational subset into the same
glyph-register backend, with combinational blocks, module hierarchy and dynamic
selects, integer division/remainder, unrolled loops/generate, functions and small
arrays. Its [playground](languages/verilog/playground.html)
includes an adder, ALU, multiplier and bit-routing circuit with editable input
ports. See the [supported syntax and build commands](languages/verilog/readme.md).
Both language compilers use the [shared circuit backend and shaping
runtimes](languages/shared/).

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
The [WebAssembly suite](languages/wasm/readme.md#validation) additionally uses
pytest and the system HarfBuzz shared library, with Node.js as an independent
WebAssembly validator and test oracle.

The [Verilog tests](languages/verilog/readme.md#tests) exercise both the system
HarfBuzz runtime and the browser engine, including width propagation, exhaustive
small multipliers, malformed source and disabled-shaping rejection.

The [SKI regression gate](languages/ski/readme.md#tests) uses HarfBuzz's shared
library directly and includes protocol, reproducibility, differential and
depth-six tests. Its project requirements pin FontTools for reproducible builds.

## AI disclosure

This project includes work developed with assistance from OpenAI GPT models
through ChatGPT and Codex.

## License

Licensed under the Apache License 2.0, except for the GPL-3.0 Connect Four
strategy, implementation files and derived fonts identified in its
[license notes](games/connect-four/PROVENANCE.md). See [`LICENSE`](LICENSE).
Bundled Roboto sources and fonts derived from them are also Apache-2.0.
Arabizi Annotated and its bundled Noto Naskh Arabic source are SIL OFL 1.1.
Upstream font attribution and imported-code notices are retained in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
