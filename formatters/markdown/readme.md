# Markdown-style formatting font

This font draws a small Markdown-style subset through OpenType GSUB rules.
Bold and italic use actual Roboto style outlines; headings enlarge bold
outlines. Inline code centers regular outlines in fixed-width cells, and
strikethrough adds a continuous bar. The original markup remains editable
and is preserved when copied. No Markdown parser or document macros run.

## Try it

Open [markdown.odt](markdown.odt) in LibreOffice Writer. The formatting font
and ordinary Roboto are embedded. Edit a blue block to change its formatting;
the ordinary-font copy is independent.

For the browser playground, serve the repository root:

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000/formatters/markdown/playground.html>.

## Syntax

| Input | Visual result |
| --- | --- |
| `**bold**` | **bold** |
| `*italic*` | *italic* |
| `***both***` | ***both*** |
| `` `code` `` | fixed-width code |
| `~~removed~~` | ~~removed~~ |
| `# Heading` | large bold heading, 1.5× |
| `## Heading` | medium bold heading, 1.25× |
| `### Heading` | small bold heading, 1.1× |

- Inline spans must be nonempty and have matching delimiter runs. Bold,
  italic and strikethrough cannot start or end with spaces. Code allows them.
- Runs of four or more asterisks, three or more tildes, or two or more
  backticks are literal. Unfinished markers remain visible.
- A backslash escapes `*`, `~`, a backtick, `#` or another backslash.
  Inside matched code, both characters remain visible and other markup
  stays literal.
- Heading prefixes require an ASCII space and the beginning of a shaping
  run. The playground gives each line its own run; in Writer use separate
  paragraphs. Heading contents are literal, apart from backslash escapes.
- Formatting covers printable ASCII and Latin-1 letters, including accented
  letters such as é. Other characters retain Roboto's normal display but
  interrupt formatting spans. Use left-to-right text in a consistent font.

This is a flat experimental subset, not a CommonMark implementation. It
does not support nesting, lists, links, images, multiline spans, fences,
underscore emphasis or Markdown's punctuation-sensitive delimiter rules.
For example, `a*b*c` styles b. Use `***both***` for combined bold and italic.

Matched spans are validated by a reverse chaining GSUB lookup, following
the [OpenType GSUB specification](https://learn.microsoft.com/en-us/typography/opentype/otspec190/gsub).
There is no fixed span-length clock. Application shaping limits still apply;
keep spans in one uninterrupted run with `rlig` enabled. Avoid wrapping
inside a span. The playground preserves each source line and scrolls long
lines horizontally. Copying, searching and accessibility expose the markup,
rather than a semantic rich-text document.

## Build and check

Requires Python 3.10+, FontTools and, for shaping checks, HarfBuzz's `hb-shape`.

```bash
python3 -m pip install fonttools
python3 formatters/markdown/build.py
python3 specimens/build.py --project formatters/markdown
python3 -m unittest discover -s formatters/markdown -p 'test_*.py' -v
```

The tests shape bundled and fresh fonts, verify outlines against the source
styles, and cover headings, escapes, unfinished spans and long text.

The default output is `markdown-font.ttf` beside the builder. `--output`
selects another destination relative to your current directory; `--name`
sets the family name. Importing the builder generates no files. Output
paths that would overwrite any source font are rejected.

The font uses pinned Apache-2.0 [Roboto 2 source fonts](../../decoders/shared/fonts/roboto-2/)
from tag `v2.138`. Their attribution and license metadata remain in the
generated font; its metadata identifies Michael Brackx's formatter changes.
See the root [LICENSE](../../LICENSE) and
[third-party notices](../../THIRD_PARTY_NOTICES.md).
