# Third-party notices

## Public-domain poetry research corpus

`literature/poem-oracle/poems.json` contains historical public-domain poem
texts, separate from the repository's code license. Source editions,
attribution, dates and checksums are recorded in that directory's
`sources.json` and `readme.md`. The unchanged compressed HTML source snapshots
retain their own Project Gutenberg credits and distribution notices.

The Poem Oracle TTF/WOFF2 fonts use modified, component-based Roboto 2 Regular
and Bold outlines under Apache-2.0, with the upstream Google notices and Michael
Brackx's modifications identified in their embedded metadata. The fonts contain
2876 historical public-domain poems. Their browser playground reuses the pinned
HarfBuzz runtime documented below; no additional runtime is imported.

The project code is distributed under Apache License 2.0; the Arabizi font
and its Noto source are distributed under SIL OFL 1.1 as noted below.
Original notices for imported decoder code and the bundled Roboto sources are retained below.
Fonts generated with a custom `--base` remain subject to that base’s terms.

## Imported decoder code

```text
MIT License

Copyright (c) 2026 computational-fonts-work contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of the software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Roboto 2 font outlines

The unmodified fonts in [decoders/shared/fonts/roboto-2](decoders/shared/fonts/roboto-2/)
are bundled from the official `googlefonts/roboto-2` repository, tag `v2.138`:
[source fonts](https://github.com/googlefonts/roboto-2/tree/v2.138/src/hinted).
They are licensed under **Apache License 2.0**; the upstream license is included
unchanged in [decoders/shared/fonts/roboto-2/LICENSE](decoders/shared/fonts/roboto-2/LICENSE).
See the [font provenance](decoders/shared/fonts/roboto-2/readme.md) for source checksums.

```text
Copyright 2015 Google Inc. All Rights Reserved.
Roboto is a trademark of Google.
```

Bundled computational fonts derived from these sources are modified derivatives
under Apache License 2.0, with distinct family names. Michael Brackx added
computational glyphs and OpenType substitution rules. Their embedded metadata
preserves Google’s copyright, trademark, and license records and identifies
these modifications and Michael Brackx’s copyright.

Fonts built solely from original geometric outlines do not incorporate Roboto.

## Game font typography

Game fonts built with `games/shared/game_text.py` now use original Game Sans
Regular and Bold outlines for their titles, coordinates, status labels, and
the text adventure's prose. The independently drawn source is
[`games/shared/game_sans.py`](games/shared/game_sans.py); see the
[font documentation](games/shared/fonts/game-sans/readme.md). Game Sans and the
board artwork are Copyright 2026 Michael Brackx, Apache-2.0. These game fonts
contain no Roboto outlines. Game ODT specimens also embed Game Sans for body
text. Earlier game-font editions used Roboto and retain their original
attribution requirements. Text is baked into the font at build time; no
installed typeface or runtime font download is required. Connect Four's
independently generated strategy and derived font are also Apache-2.0; see its
[provenance](games/connect-four/PROVENANCE.md).

## SKI evaluator

The visible `languages/ski/ski-font.ttf` uses decomposed outlines from the same
pinned Roboto Regular source described above. Its generated metadata retains
Google's copyright, Roboto attribution and Apache-2.0 license and identifies
Michael Brackx's SKI interpreter modifications. The separate invisible machine
font `languages/ski/ski.ttf` contains original empty outlines and no Roboto.

## HarfBuzz browser runtime

The WebAssembly and Verilog playgrounds share unmodified runtime files from
[harfbuzzjs 1.6.3](https://www.npmjs.com/package/harfbuzzjs/v/1.6.3), licensed
under MIT, including its HarfBuzz 14.6.0 WebAssembly engine. HarfBuzz uses the
Old MIT license. Both notices are retained in
[`languages/shared/vendor/harfbuzzjs`](languages/shared/vendor/harfbuzzjs/), with
upstream sources and checksums in its readme.

## First Words Pictures font

`graphics/first-words/first-words-font.ttf` and its WOFF2 retain the pinned
Roboto Regular text outlines described above. These modified derivatives use
the new family name **First Words Pictures** and preserve Google's copyright,
Roboto trademark and Apache-2.0 license metadata. Michael Brackx's modifications
add whole-word ligatures and 200 original vector pictures, with colour layers,
191 derived stacked plural variants and monochrome fallbacks.
The compiled fonts and font build code are Apache-2.0;
see that folder's `FONT_LICENSE.txt` and `FONT_NOTICE.txt`.

The illustration artwork and `generate_artwork.py` are original Apache-2.0
material; see `graphics/first-words/LICENSE.txt` and
`graphics/first-words/NOTICE.txt`.

## SMILES diagram font

The visible input and element labels in `graphics/smiles/smiles-font.ttf` use
decomposed outlines from the pinned Roboto Regular source above. Its metadata
retains Google's attribution and Apache-2.0 notices and identifies Michael
Brackx's original molecular graph interpreter and diagram modifications.
The smiles2svg repository was a visual reference only; no upstream code or
assets are incorporated and no smiles2svg or RDKit dependency is required.

## Arabizi Annotated / Noto Naskh Arabic

The unmodified variable font in [decoders/arabizi/fonts](decoders/arabizi/fonts/)
is Noto Naskh Arabic from the official Google Fonts repository. Its original
[SIL Open Font License 1.1](decoders/arabizi/fonts/OFL.txt), copyright, source
revision and checksums are retained beside it.

```text
Copyright 2022 The Noto Project Authors (https://github.com/notofonts/arabic)
```

`decoders/arabizi/arabizi-font.ttf` is a modified derivative named **Arabizi
Annotated**, distributed under **SIL OFL 1.1**. It uses Noto Arabic and Latin
outlines, with Michael Brackx’s Arabizi annotations, joining substitutions and
positioning rules. Embedded metadata preserves upstream copyright, identifies
Michael Brackx’s 2026 modifications, and specifies OFL 1.1. The build code and
tests remain Apache-2.0.

## Independent Connect Four strategy

The Connect Four policy, search generator, independent certificate checker and
GSUB interpreter are original Apache-2.0 work by Michael Brackx. They replace
the earlier WeakC4 derivative. No WeakC4 source, solution tables or derived
fonts are included in the current implementation. The policy is generated
solely from the standard game's rules. See its
[provenance and verification](games/connect-four/PROVENANCE.md).

## Gardner opening-book generation

The original move records in `games/gardner/book.json.gz` were generated using
an external Fairy-Stockfish executable. Fairy-Stockfish is GPL-3.0; its code and
executable are not bundled with the Gardner implementation or font. Font
rebuilds use the generated records and do not require that engine. See
[Gardner provenance](games/gardner/PROVENANCE.md) for the engine revision,
executable fingerprint, search budgets, and generation method.
