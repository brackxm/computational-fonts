# Third-party notices

The project is distributed under Apache License 2.0. Original notices for
imported decoder code and the bundled Roboto sources are retained below.
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

Fonts built from original geometric outlines do not incorporate Roboto.

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
