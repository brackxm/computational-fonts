# Editable ODF specimens

Each project has an `.odt` document with editable sample text, its bundled
computational font, and the ordinary Roboto 2 font embedded in the package.
Open it in LibreOffice Writer and follow its "Try it" instructions. Font
installation, macros, JavaScript, and a web server are unnecessary.

Each example contains two independent copies of the same text: a normal-font
source block and an editable computational-font block. The font performs the
computation when the document is rendered. Copying a visual result still copies
the original input. Messages and validation requests are kept short to avoid
line wrapping that could split their shaping runs. Snake specimens contain
editable move histories and instructions for a complete winning route on the
dynamic board.
The Turtle specimen draws a square in four colors and explains how to edit
the path, lift the pen, and change the color.
The [Morse specimen](../decoders/morse/morse.odt) shows a greeting and digits
with punctuation, with editable dots, hyphens and separators.
The [Markdown-style specimen](../formatters/markdown/markdown.odt) shows
headings, emphasis, code and strikethrough drawn from editable markup.
The [text-adventure specimen](../games/text-adventure/text-adventure.odt)
contains a playable starting scene. Append semicolon-terminated commands to
its blue block, keeping the full history in one paragraph. Its font draws
the latest room, inventory and reply; no game interpreter or macros are used.
Its blue table cell bounds the visible scene, while a wide paragraph inside
the cell prevents Writer from breaking long command histories before shaping.

## Regenerate

From the repository root, using Python 3.10 or later and FontTools:

```bash
python3 -m pip install fonttools
python3 specimens/build.py
```

Build only one document:

```bash
python3 specimens/build.py --project validators/multi-format
```

Outputs always go beside each project's bundled font, using its filename without
the trailing `-font` and with an `.odt` extension. For example,
`validator-font.ttf` becomes `validator.odt`. The documents can be
downloaded into one directory.
Rebuild the relevant font first if its generator or settings changed. The
examples assume the bundled settings documented in each project's readme.
The builder validates that fonts permit editable embedding and packages the
font files without subsetting. Fixed ZIP timestamps keep unchanged documents
reproducible.

The ODF 1.3 packages contain font-face declarations in both `content.xml` and
`styles.xml`, embedded-font entries in `META-INF/manifest.xml`, and embedding
settings so Writer retains the fonts when saving. The `mimetype` member is
first and uncompressed. The repository's license and third-party notices are
included inside every package. The fonts retain their attribution metadata.

Rendering should be checked in Writer when changing sample text, fonts, or
styles. Other ODF readers may handle embedded fonts, ligatures, color glyphs,
and shaping runs differently. Rendered previews are not substitutes for the
editable document.
