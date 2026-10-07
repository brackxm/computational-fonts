# JSON formatting font

An inline JSON formatter implemented in OpenType GSUB. The font colors keys,
string values, numbers, `true`, `false`, `null` and structural punctuation.
It also normalizes spaces around punctuation. The browser supplies the text;
there is no JavaScript JSON parser or formatter. Copying preserves the source.

## Try it

Open [json.odt](json.odt) in LibreOffice Writer. Both the formatting font and
ordinary Roboto are embedded. Edit a blue block; its normal-font copy is
independent.

For the browser playground, serve the repository root:

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000/formatters/json/playground.html>.

Underlying text:

```json
{  "name" : "Ada  Lovelace" , "count":3,"active":true }
```

Visual spacing:

```json
{"name": "Ada  Lovelace", "count": 3, "active": true}
```

## Formatting rules

- Keys are brown, string values green, numbers blue, keywords purple and
  punctuation gray. A string followed by a colon is treated as a key.
- Quotes and escape sequences remain visible. Escaped quotes and paired
  backslashes keep the string state correct. Punctuation, keywords and all
  spaces inside strings remain literal, including `\uXXXX` sequences.
- Outside strings, repeated ASCII spaces collapse visually to one. Spaces
  before structural punctuation and after `{`, `[`, `:` or `,` disappear.
  Colons and commas supply one visual space after themselves through their
  glyph advances. Spaces separating other tokens remain visible.
- Numbers follow JSON's sign, leading-zero, fraction and exponent syntax.
  Keywords and numbers receive colors only as complete tokens at a boundary.
  Incomplete or malformed numeric tokens keep their ordinary appearance.
- Unfinished strings remain visible and receive string coloring through the
  end of the run. No text is repaired, evaluated or decoded.

Token rules follow [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259).
This is a visual formatter, not a JSON validator: highlighting does not
establish valid nesting, escape syntax, member structure or a complete value.

This first version keeps layout inline. It does not insert line breaks or
indent nested containers. Use single-line input with ASCII spaces in one
uninterrupted left-to-right shaping run and `rlig` enabled. Existing source
lines in the playground are displayed separately; state does not cross lines.
Avoid wrapping within a value. Use printable ASCII characters and JSON's
Unicode escapes (`\uXXXX`) for other characters. Browsers and document editors
can split scripts or fallback fonts into separate shaping runs, resetting the
font's string state even when Roboto contains the characters. Raw Unicode,
combining marks, tabs and other control characters are outside the supported
input model. The playground shows such input unchanged in an ordinary font
and explains how to make it eligible for formatting. Newlines separate preview
lines; the font does not process them. In Writer, follow the same ASCII and
escape restrictions; the document cannot enforce them.
There is no fixed token-length or nesting-depth clock; application limits
still apply.

COLR v0 and CPAL store the colors in the font. Applications without color
font support show the same outlines and spacing in monochrome. Copying,
searching and accessibility expose the original JSON, including its spacing.

## Build and check

Requires Python 3.10+, FontTools and, for shaping checks, HarfBuzz's `hb-shape`:

```bash
python3 -m pip install fonttools
python3 formatters/json/build.py
python3 specimens/build.py --project formatters/json
python3 -m unittest discover -s formatters/json -p 'test_*.py' -v
node formatters/json/test_playground.cjs
```

The default output is `json-font.ttf` beside the builder. `--output` selects
another path relative to your current directory; `--name` sets the family name.
Output cannot overwrite the source font. Importing the builder writes no files.

Tests shape bundled and fresh fonts against an independent lexer and spacing
reference. They cover escaped quotes, backslash parity, string contents,
key detection, full numeric tokens, keyword boundaries, malformed input,
long strings, nested values, embedded colors, fallback outlines and metadata.
The low-level Unicode glyph test deliberately forces one Latin shaping run;
it does not establish Unicode support in browsers or document editors.
The playground checks require Node.js. They exercise plain-text fallback for
Unicode and controls, source preservation, escaped ASCII input, editing back
to supported input, and font-loading races and failures.

The font derives from the pinned Apache-2.0 [Roboto 2 Regular](../../decoders/shared/fonts/roboto-2/).
Its license and attribution remain in the generated font; its metadata
identifies Michael Brackx's formatter changes. See the root
[LICENSE](../../LICENSE) and [third-party notices](../../THIRD_PARTY_NOTICES.md).
