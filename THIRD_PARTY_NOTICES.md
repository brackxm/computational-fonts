# Third-party notices

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

Game fonts built with `games/shared/game_text.py` use decomposed outlines from
the pinned Roboto Regular and Bold sources above for their titles, coordinates
and status labels. The generated fonts retain Google's copyright, trademark,
and Apache-2.0 attribution and identify Michael Brackx's modifications. Board
artwork remains original. Text is baked into the font at build time; no
installed typeface or runtime font download is required.

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

## WeakC4 / Connect Four

`games/connect-four/upstream/` contains GPL-3.0 strategy data and source from
[2swap/WeakC4](https://github.com/2swap/WeakC4), revision
`51dc8383472c63aa6e6796a9ef306662eb8bd4bf`. Its original license and attribution
are retained. The generated Connect Four TTF/WOFF2 fonts contain derived GPL
strategy material and are distributed as GPL-3.0-only, with corresponding
source. They are an exception to the repository's Apache-2.0 default. See the
[file-by-file provenance and license notes](games/connect-four/PROVENANCE.md).
