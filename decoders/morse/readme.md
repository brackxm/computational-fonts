# Morse code decoding font

The font visually decodes International Morse code through OpenType GSUB
substitutions. Its output uses the bundled Roboto outlines; copying the text
preserves the original dots, hyphens and separators. No JavaScript decoder
or document macros are involved.

## Try it

Open [morse.odt](morse.odt) in LibreOffice Writer. Both the decoder and Roboto
are embedded, so no font installation is needed. Edit a blue block to change
the decoded message; the ordinary-font copy is independent.

For the browser playground, serve the repository root:

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000/decoders/morse/playground.html>.

Underlying text:

```text
.... . .-.. .-.. --- / .-- --- .-. .-.. -..
```

Visual result: **HELLO WORLD**.

## Input format

- ASCII `.` is a dot and ASCII `-` is a dash.
- One or more ASCII spaces separate letters; they disappear in the result.
- `/` separates words and becomes one ordinary space. Spaces around it are optional.
- No initializer or trailing separator is needed. `... --- ...` displays `SOS`.
- A valid whole group decodes; an unknown group stays visible. For example,
  `........ ...` displays `........S`, rather than partially decoding the eight dots.
- Literal `/`, `-` and `.` in the output are encoded as `-..-.`, `-....-` and `.-.-.-`.

The mapping includes A–Z, É, 0–9 and the punctuation below, following
[ITU-R M.1677-1, Annex 1](https://www.itu.int/rec/R-REC-M.1677-1-200910-I/en).
ASCII apostrophes, quotation marks and hyphens represent the printed variants.

| Character | Morse | Character | Morse |
| --- | --- | --- | --- |
| `.` | `.-.-.-` | `,` | `--..--` |
| `:` | `---...` | `?` | `..--..` |
| `'` | `.----.` | `-` | `-....-` |
| `/` | `-..-.` | `(` | `-.--.` |
| `)` | `-.--.-` | `"` | `.-..-.` |
| `=` | `-...-` | `+` | `.-.-.` |
| `@` | `.--.-.` | `É` | `..-..` |

Procedural signals, American Morse, and unofficial punctuation extensions
are not supported. The signal for X also represents multiplication in the
standard; this font displays X. There is no fixed message-length clock:
each group decodes independently. Application shaping and layout limits
still apply. Keep signals for a letter together in one font and text run;
avoid line wrapping inside a group. The playground preserves lines and
scrolls long messages horizontally.

The result is visual. Searching, copying and accessibility APIs expose the
Morse source, not a plaintext transcript.

## Build and check

Requires Python 3.10+ and FontTools. Install HarfBuzz's `hb-shape` to run
actual shaping checks.

```bash
python3 -m pip install fonttools
python3 decoders/morse/build.py --test '... --- ...'
python3 specimens/build.py --project decoders/morse
python3 -m unittest discover -s decoders -p 'test_*.py' -v
```

The default output is `morse-font.ttf` beside `build.py`. An explicit relative
`--output` is resolved from your current directory. Use `--base` to select
another glyf-based TrueType font, subject to its own license; it must cover
the supported characters. `--name` changes the family name. The builder
rejects missing characters, ambiguous input glyph aliases, reserved glyph
collisions and any output path that would overwrite the base. Importing it
does not generate files.

The shared decoder suite shapes the bundled font and fresh builds, including
a custom base with different advances. It checks every supported character,
all 510 dot/dash groups of lengths 1–8, invalid-group recovery, separators,
punctuation outputs, longer messages, metadata and output paths.

The base is the pinned Apache-2.0 [Roboto 2 font](../shared/fonts/roboto-2/).
Its license and attribution remain in the generated font; Michael Brackx's
Morse substitutions are identified in its metadata. See the root
[LICENSE](../../LICENSE) and [third-party notices](../../THIRD_PARTY_NOTICES.md).
