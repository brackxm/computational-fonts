# Computational fonts

Fonts that play games, run programs, draw pictures, decode messages and format
text. The computation happens during OpenType shaping, using substitutions,
ligatures and glyph composition.

**[Explore the 41 interactive demos](https://brackxm.github.io/computational-fonts/)**
in your browser, with no installation needed.

## Try the fonts

### Running a playground

Use the [hosted demo gallery](https://brackxm.github.io/computational-fonts/), or
serve this repository locally so the browser can load its bundled fonts:

```sh
python3 -m http.server 8000
```

Open <http://localhost:8000> and choose a project. Each playground provides
controls and examples; the project README documents its input and limits.

### Trying a font in a document

Many projects also include an **editable ODT specimen**. Open it in LibreOffice
Writer: the computational font and an ordinary text font are embedded, so no font
installation or web server is needed. Each example shows the same underlying
text in both fonts. Edit a blue block to change the computed result.
Game specimens use our original [Game Sans](games/shared/fonts/game-sans/readme.md);
other specimens use Roboto.

The documents contain ordinary text and no macros or JavaScript. Copying a
result preserves the original input. Keep each example on one line with
consistent formatting and standard ligatures enabled. Rendering can vary
between applications.

## Projects

Browse [games](#games), [programming languages](#programming-languages),
[graphics and pictures](#graphics-and-pictures), [literature](#literature),
[decoders and transliteration](#decoders-and-transliteration), or
[formatters and validators](#formatters-and-validators).

Project names link to documentation and source. **Demo** opens a browser
playground; **ODT** links to an editable document specimen.

### Games

#### Winning strategies and solved games

These fonts choose the opponent's moves during shaping. Their guarantees apply
to the boards, rules and starting positions described in each project.

| Project | Rules and scope | Try it |
| --- | --- | --- |
| [Connect Four](games/connect-four/) | Guaranteed Red win from the empty 7×6 board; `b` plus human column digits | [Demo](games/connect-four/playground.html) |
| [Notakto](games/notakto/) | Perfect first-player opponent on three boards; human-only history | [Demo](games/notakto/playground.html) |
| [Wythoff’s Nim](games/wythoff/) | Perfect opponent; two configurable heaps of 0–63 tokens; either player first | [Demo](games/wythoff/playground.html) |
| [Cram](games/cram/) | Perfect first-player opponent on a 6×5 board; domino placements | [Demo](games/cram/playground.html) |
| [Mū tōrere](games/mu-torere/) | Perfect win/loss/draw opponent; either first player and two puzzles | [Demo](games/mu-torere/playground.html) |
| [Hexapawn](games/hexapawn/) | Perfect opponent on either side of the standard 3×3 board | [Demo](games/hexapawn/playground.html) |
| [Nim](games/nim/) | Perfect normal/misère opponent; three configurable 0–31 heaps and a computed XOR display | [Demo](games/nim/playground.html) |
| [Chomp](games/chomp/) | Perfect opponent on either side of a complete 6×5 chocolate bar | [Demo](games/chomp/playground.html) |
| [Dodgem](games/dodgem/) | Perfect opponent on either side of the standard 3×3 car race | [Demo](games/dodgem/playground.html) |
| [Domineering](games/domineering/) | Perfect opponent on either side of a solved 4×4 board | [Demo](games/domineering/playground.html) |
| [Kayles](games/kayles/) | Perfect opponent with twelve pins; remove one or two original neighbors | [Demo](games/kayles/playground.html) |
| [Achi](games/achi/) | Perfect win/loss/draw opponent for the Berkeley three-counter placement-and-sliding variant | [Demo](games/achi/playground.html) |
| [Dots and Boxes](games/dots-and-boxes/) | Perfect score-maximizing opponent on 2×2 boxes; scoring and bonus turns inside the font | [Demo](games/dots-and-boxes/playground.html) |
| [Tic-tac-toe](games/tic-tac-toe/) | Perfect opponent on either side of the standard 3×3 board | [Demo](games/tic-tac-toe/playground.html) |

Connect Four's implementation, independently generated strategy and fonts are
Apache-2.0. Its [proof and provenance](games/connect-four/PROVENANCE.md) document
the guaranteed win and the removal of the previous GPL strategy dependency.

#### Other games and replays

| Project | Rules and scope | Try it |
| --- | --- | --- |
| [Gardner minichess](games/gardner/) | 5×5 chess with font-generated legal moves, an opening book and an imperfect heuristic opponent | [Demo](games/gardner/playground.html) |
| [Backgammon SGF replay](games/backgammon/) | Replay a bounded linear SGF subset from the standard start; up to 128 turns | [Demo](games/backgammon/playground.html) |
| [Snake — dynamic board](games/snake-dynamic/) | Game prototype with dimensions and movement history supplied as text | [Demo](games/snake-dynamic/playground.html) · [ODT](games/snake-dynamic/snake-dynamic.odt) |
| [Snake — fixed board](games/snake-fixed/) | Game prototype with a movement history and board size baked into the font | [Demo](games/snake-fixed/playground.html) · [ODT](games/snake-fixed/snake-fixed.odt) |
| [The Last Light](games/text-adventure/) | Escape-room text adventure with semicolon-terminated commands | [Demo](games/text-adventure/playground.html) · [ODT](games/text-adventure/text-adventure.odt) |

Backgammon replay updates points, bars, off counters, hits, entry, bearing off
and latest dice. Replay completion does not establish move legality. See its
[supported SGF subset and limitations](games/backgammon/readme.md).

### Programming languages

| Project | Input and execution | Try it |
| --- | --- | --- |
| [Mini BASIC](languages/mini-basic/) | Numbered BASIC statements executed through font shaping | [Demo](languages/mini-basic/playground.html) · [ODT](languages/mini-basic/mini-basic.odt) |
| [SKI evaluator](languages/ski/) | Combinatory logic with `S`, `K`, `I`, lowercase atoms and application | [Demo](languages/ski/playground.html) · [ODT](languages/ski/ski.odt) |
| [WebAssembly](languages/wasm/) | Bounded integer programs compiled from `.wat` or `.wasm` into glyph registers | [Demo](languages/wasm/playground.html) |
| [Verilog](languages/verilog/) | Bounded two-state combinational `.v` modules compiled into GSUB gates | [Demo](languages/verilog/playground.html) |

WebAssembly and Verilog share a [circuit backend and shaping runtimes](languages/shared/).
Their playgrounds include compiled examples with matching ABI manifests.
SKI also includes a machine font and CLI for inspecting results and its
internal tree tape. Each project's documentation describes its supported
syntax and execution bounds.

### Graphics and pictures

| Project | What the font draws | Try it |
| --- | --- | --- |
| [First Words Pictures](graphics/first-words/) | 622 familiar word labels mapped to 200 original colour vector drawings | [Demo](graphics/first-words/playground.html) |
| [Turtle graphics](graphics/turtle/) | Movement, pen and colour commands interpreted as a drawing | [Demo](graphics/turtle/playground.html) · [ODT](graphics/turtle/turtle.odt) |
| [SMILES diagrams](graphics/smiles/) | Molecular connectivity from bounded SMILES with atoms, bonds, branches and rings | [Demo](graphics/smiles/playground.html) · [ODT](graphics/smiles/smiles.odt) |
| [PPM image renderer](graphics/ppm/) | Plain PPM (`P3`) RGB images | [Demo](graphics/ppm/playground.html) · [ODT](graphics/ppm/ppm.odt) |
| [PGM image renderer](graphics/pgm/) | Plain PGM (`P2`) grayscale images | [Demo](graphics/pgm/playground.html) · [ODT](graphics/pgm/pgm.odt) |
| [PBM image renderer](graphics/pbm/) | Plain PBM (`P1`) bitmaps | [Demo](graphics/pbm/playground.html) · [ODT](graphics/pbm/pbm.odt) |

First Words Pictures includes ordinary Roboto text for other words, monochrome
picture fallbacks and countable plurals drawn as two stacked pictures. Its
original SVG artwork, review gallery, contact sheets and generators are
included under Apache-2.0.

### Literature

[Poem Oracle](literature/poem-oracle/) turns each paragraph into one of 2,876
short public-domain poems by sixteen authors. The font hashes the input and
displays the selected poem with stanza breaks and attribution. The same input
selects the same poem.

**[Try Poem Oracle](literature/poem-oracle/playground.html)**, or read the
[corpus and shaping notes](literature/poem-oracle/readme.md).

### Decoders and transliteration

Fixed-key fonts have their key or machine settings built in. Editable-key
variants accept settings alongside the ciphertext.

| Project | Input or configuration | Try it |
| --- | --- | --- |
| [Arabizi Annotated](decoders/arabizi/) | Arabizi letters and digits; original shorthand appears above joined Arabic | [Demo](decoders/arabizi/playground.html) |
| [Morse code](decoders/morse/) | Dots and hyphens; spaces between letters, `/` between words | [Demo](decoders/morse/playground.html) · [ODT](decoders/morse/morse.odt) |
| [Playfair — fixed key](decoders/playfair-static/) | Key baked into the font | [Demo](decoders/playfair-static/playground.html) · [ODT](decoders/playfair-static/playfair-static.odt) |
| [Vigenère — fixed key](decoders/vigenere-static/) | Key baked into the font | [Demo](decoders/vigenere-static/playground.html) · [ODT](decoders/vigenere-static/vigenere-static.odt) |
| [Vigenère — editable key](decoders/vigenere-dynamic/) | `KEY~CIPHERTEXT` | [Demo](decoders/vigenere-dynamic/playground.html) · [ODT](decoders/vigenere-dynamic/vigenere-dynamic.odt) |
| [Enigma I — fixed settings](decoders/enigma-static/) | Machine settings baked into the font | [Demo](decoders/enigma-static/playground.html) · [ODT](decoders/enigma-static/enigma-static.odt) |
| [Enigma I — editable settings](decoders/enigma-dynamic/) | `ROTORS/POSITIONS/RINGS~CIPHERTEXT` | [Demo](decoders/enigma-dynamic/playground.html) · [ODT](decoders/enigma-dynamic/enigma-dynamic.odt) |
| [Lorenz SZ40/SZ42](decoders/lorenz-static/) | Machine and wheel settings baked into the font | [Demo](decoders/lorenz-static/playground.html) · [ODT](decoders/lorenz-static/lorenz-static.odt) |

### Formatters and validators

| Project | Supported input | Try it |
| --- | --- | --- |
| [JSON formatter](formatters/json/) | JSON text | [Demo](formatters/json/playground.html) · [ODT](formatters/json/json.odt) |
| [Markdown-style formatter](formatters/markdown/) | Flat emphasis, inline code, strikethrough and heading markers | [Demo](formatters/markdown/playground.html) · [ODT](formatters/markdown/markdown.odt) |
| [Multi-format validator](validators/multi-format/) | `format:value?` across sixteen formats | [Demo](validators/multi-format/playground.html) · [ODT](validators/multi-format/validator.odt) |

## How it works

A shaping engine turns text into glyphs. These fonts use OpenType substitution
rules to implement computation, then show the result through glyph outlines,
positioning and composition. Display fonts can reconstruct state from an input
history; the circuit compilers build fonts containing glyph registers and
gates. The result's appearance changes while the underlying text stays intact.

The playgrounds provide controls and prepare input for shaping. Some projects
use native browser text shaping; others bundle HarfBuzz and draw the shaped
outlines. Supported input sizes and behavior depend on the font and engine;
each project documents its constraints.

## Development

### Building fonts

Most project folders include a `build.py` generator, bundled font, browser
playground and README with usage, build commands, tests and limitations.
Many also include an ODT specimen.

Most generators use Python 3.10 or later and FontTools. SKI requires Python
3.11 or later. Follow the project's build instructions and use its pinned
requirements where provided. Builders usually write the font beside `build.py`;
`--output` selects another destination relative to your current directory.

### Tests

Run the commands in the relevant project README. Shaping tests use HarfBuzz's
`hb-shape` executable or shared library; browser controller tests use Node.js.
Additional dependencies and coverage are documented with each suite:

| Suite | Validation notes |
| --- | --- |
| [Decoders](decoders/shared/readme.md#tests) | Shared decoder regressions and dependencies |
| [SKI](languages/ski/readme.md#tests) | Protocol, reproducibility, differential and depth-six regression gate |
| [WebAssembly](languages/wasm/readme.md#validation) | pytest and system HarfBuzz, with Node.js as an independent WebAssembly validator and oracle |
| [Verilog](languages/verilog/readme.md#tests) | System and browser runtimes, width propagation, exhaustive small multipliers and malformed source |
| [Connect Four](games/connect-four/readme.md#build-and-validation) | Exhaustive strategy proof, binary policy readback and complete games through real shaping |

### Shared code and specimens

| Directory | Purpose |
| --- | --- |
| [Decoder helpers](decoders/shared/) | Shared generation, typography and decoder test utilities |
| [Graphics helpers](graphics/shared/) | Shared PBM, PGM and PPM font renderer |
| [Game helpers](games/shared/) | Shared game font, text and playground utilities |
| [Circuit backend](languages/shared/) | Glyph-register backend and shaping runtimes for WebAssembly and Verilog |
| [Specimens](specimens/readme.md) | Build notes for regenerating documents after changing a bundled font |

## AI disclosure

This project includes work developed with assistance from OpenAI GPT models
through ChatGPT and Codex.

## License

Repository code is licensed under [Apache License 2.0](LICENSE). The independent
Connect Four strategy and fonts, and the original First Words artwork and
generators, also use Apache-2.0.

Bundled Roboto sources and fonts derived from them are Apache-2.0; see the
[Roboto provenance notes](decoders/shared/fonts/roboto-2/). Arabizi Annotated and
its bundled Noto Naskh Arabic source are SIL OFL 1.1. Font attribution and
imported-code notices are retained in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
