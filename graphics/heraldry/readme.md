# Heraldry

An OpenType font that turns a small, bracketed blazon into a colour shield.
The font recognises the words and composes field, device and rim glyphs during
shaping. The playground passes the source text to the font unchanged.

**[Try the playground](playground.html)** · [Installable TTF](heraldry-font.ttf) ·
[WOFF2](heraldry-font.woff2)

```text
[Azure, a chevron Or]
[Gules, three mullets Argent]
[Per pale Argent and Azure, a fleur-de-lis Or]
[Sable, a lion rampant Or]
[Quarterly Or and Gules]
```

## Grammar

```text
[FIELD]
[FIELD, a DEVICE TINCTURE]
[FIELD, three CHARGES TINCTURE]

FIELD = TINCTURE
      | DIVISION TINCTURE and TINCTURE
```

| Part | Supported vocabulary |
| --- | --- |
| Tinctures | Or (gold), Argent (silver), Azure (blue), Gules (red), Sable (black), Vert (green), Purpure (purple) |
| Divisions | per pale, per fess, per bend, per bend sinister, per chevron, per saltire, quarterly |
| Ordinaries | chief, fess, pale, bend, bend sinister, chevron, cross, saltire, bordure |
| Single charges | mullet, lozenge, crescent, heart, fleur-de-lis, lion rampant |
| Three charges | mullets, lozenges, crescents, hearts, fleurs-de-lis, lions rampant |

Each word accepts lowercase, an initial capital, or UPPERCASE. For example,
`[Per PALE Argent and AZURE, a Fleur-de-lis OR]` works. Arbitrary mixed case
within a word is outside the grammar. Use one to three ordinary spaces, or one
non-breaking space, between words. The comma is optional; it may be followed
by a gap or directly by `a` or `three`. Do not put spaces just inside brackets.

One ordinary or charge group is supported. Three charges are arranged two in
chief and one in base. The first field tincture is above the dividing line or
on the bearer's right (the viewer's left); quarterly uses it in the first and
fourth quarters, and per saltire in the top and bottom sections. The lions
face heraldic dexter, towards the viewer's left.

This is a restricted grammar, not a general blazon interpreter. It does not
include furs, line treatments, counterchanging, multiple charge groups,
different animal attitudes, crests, supporters, or free-form English.
It does not enforce the rule of tincture. Bracketed spans are recognised
independently; nesting brackets is not supported. Other text, including
malformed descriptions, retains its original outlines, case and advances.

The vocabulary and conventions follow the introductory account in the
[Heraldry Society's *Heraldry for Beginners*](https://www.theheraldrysociety.com/wp-content/uploads/2018/03/Heraldry-For-Beginners.pdf)
and the Society for Creative Anachronism's
[*A Grammar of Blazonry*](https://heraldry.sca.org/armory/bruce.html).
All artwork is original geometry in `build.py`; no source illustrations are imported.

## Use

Serve the repository root with `python3 -m http.server 8000`, then open
`http://localhost:8000/graphics/heraldry/playground.html`.

Or install the TTF, select **Heraldry Regular**, and enable standard ligatures.
Use 72–200 pt to see the details. Keep each description in a single font/style
run, with normal letter spacing. The playground selects the entire source when
you select its shield preview. **Copy blazon** copies the exact source, including
capitalization, repeated spaces and NBSP; if clipboard access fails, it selects
the full source in the editor for manual copying. In other applications, the
composed glyphs can have separate text clusters: select the complete bracketed
source before copying, rather than relying on selection within the drawing.
Colour requires COLRv0 support. The monochrome fallback shows the shield,
divisions and device outlines, without encoding tinctures. Application support
for ligatures containing spaces varies; the playground uses browser page text
with explicit `liga` settings. Cross-application and PDF export fidelity are
not guaranteed by the browser checks. Avoid synthetic bold or italic.

The editor's selectors synchronise with the supported word casing and gaps,
then construct source text when changed. They are disabled for unsupported
descriptions or multiple shields, so a selector cannot silently replace text
it cannot represent. Enter one supported blazon or choose an example to resume
using the builder. The shield and all example previews are font text; they
contain no replacement images, canvas drawing,
runtime SVG, or JavaScript heraldic renderer. Text outside supported spans
uses the bundled Roboto outlines.

## How it works

1. Lexical ligatures recognise words and retain their exact letter outlines and
   advances. Word-boundary guards prevent matching substrings.
2. A contextual GSUB lookup validates a whole bracketed production. Only a
   successful production changes its words into canonical, invisible tokens.
3. Ligatures reduce the field to one colour glyph and the optional ordinary or
   charge group to a second. Both have zero advance and share an origin.
4. The closing bracket becomes the shield rim, painted last, with a one-em
   advance. The font's COLRv0/CPAL tables supply the colour vectors.

There are 350 field glyphs and 147 device glyphs: **51,800 combinations**
including fields without devices. Complete coats of arms are composed, rather
than individually enumerated. Ordinary and division paths are clipped to the
shield during building. The generated `.fea` exposes the parser, and `.json`
records vocabulary, font size, counts and checksum.

## Build and verify

```sh
python3 -m venv /tmp/heraldry-build
/tmp/heraldry-build/bin/python -m pip install -r graphics/heraldry/requirements.txt
/tmp/heraldry-build/bin/python graphics/heraldry/build.py
/tmp/heraldry-build/bin/python -m unittest discover -s graphics/heraldry -p 'test_*.py'
```

`--output PATH` writes TTF, WOFF2, feature source and metadata beside PATH,
relative to the current directory. `--base PATH` selects a different TrueType
text base (including WOFF/WOFF2 containing TrueType outlines), subject to that
font's compatibility and terms. The TTF output is always uncompressed. Output
paths, including sidecars and filesystem aliases, must differ from the source
and from one another; collisions are rejected before any files are written.
Unchanged inputs produce byte-identical outputs, including WOFF2.

The tests shape all 51,800 compositions through HarfBuzz; cover casing,
spacing, optional commas, invalid grammar, exact text-outline preservation,
multiple shields, ligatures disabled, colour layers, geometry bounds, notices,
webfont equivalence, compressed bases, output-path collision protection and
reproducible building. FontTools and Skia PathOps are build dependencies;
uharfbuzz is used by the tests.

With Playwright and Chrome available, and the server running:

```sh
node graphics/heraldry/test_browser.cjs http://127.0.0.1:8000/graphics/heraldry/playground.html /tmp/heraldry.png
```

The browser suite checks 176 grammar layouts in real DOM text, the seven
palette colours, examples, source preservation, whitespace synchronisation,
mouse selection, actual clipboard contents, clipboard failure and stale-request
handling, protection of multi-shield text, restored editor settings, controls,
ligatures disabled, malformed input and mobile overflow. Canvas is used only by
the tests to sample the pixels of space-free solid fields; it does not render
playground shields.

## License

Code, original geometry and generated fonts are Apache-2.0. The font derives
its text outlines from the repository's pinned Roboto 2 Regular, copyright
2015 Google Inc. Roboto is a trademark of Google. Google's notices, the
Apache license metadata and Michael Brackx's modifications are retained in the
compiled font. See the [root license](../../LICENSE),
[third-party notices](../../THIRD_PARTY_NOTICES.md), and
[Roboto source and license](../../decoders/shared/fonts/roboto-2/readme.md).
