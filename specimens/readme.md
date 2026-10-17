# Editable document specimens

Each project has an `.odt` document with editable sample text, its bundled
computational font, and the ordinary Roboto 2 font embedded in the package.
Open it in LibreOffice Writer and follow its "Try it" instructions. Font
installation, macros, JavaScript, and a web server are unnecessary.

Each project also has a native `.docx` specimen for desktop Microsoft Word.
It embeds the complete computational font and Roboto as obfuscated OpenType
parts, with explicit font relationships and font embedding settings. The
computational blocks enable standard and contextual ligatures and contextual
alternates, disable proofing, and preserve each input as one editable text run.
Fonts are not subsetted: new input needs glyphs and substitution rules that
may not appear in the initial example.

The DOCX specimens are candidates for Word compatibility, not a claim of
verified Word rendering. Automated checks cover the package, font recovery,
source text, settings and reproducibility. LibreOffice previews check layout
and computations in that engine. Microsoft Word on Windows and Mac still
needs separate testing, especially for long inputs and color glyphs. An intact
text run in the file does not guarantee an application shapes it as one run.
The image, BASIC, SKI and adventure canvases use a wide shaping paragraph
inside a page-width cell, as in the ODT builder. Word may normalize extreme
paragraph indents; these examples especially need testing in Word before
being distributed as working Word demonstrations.
The ODT files continue to target LibreOffice Writer.

Word can open ODT but may display the source if the embedded font or required
shaping is unavailable. Use the native DOCX for Word; simply saving an ODT as
DOCX does not add the embedded font parts and shaping settings generated here.
See Microsoft's [font embedding guidance](https://support.microsoft.com/en-us/office/fonts/benefits-of-embedding-custom-fonts)
and [DOCX font part documentation](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oi29500/ea097c57-5794-4624-b08e-017b47051b1d).

Each example contains two independent copies of the same text: a normal-font
source block and an editable computational-font block. The font performs the
computation when the document is rendered. Copying a visual result still copies
the original input. Messages and validation requests are kept short to avoid
line wrapping that could split their shaping runs. Snake specimens contain
editable move histories and instructions for a complete winning route on the
dynamic board.
The Turtle specimen draws a square in four colors and explains how to edit
the path, lift the pen, and change the color.
The [PPM specimen](../graphics/ppm/ppm.odt) draws color bars from an editable
P3 header and RGB triples. Change three samples to change a pixel color.
The [PGM specimen](../graphics/pgm/pgm.odt) draws sixteen shades from an editable
P2 header and decimal samples. Change a sample to change a shade.
The [PBM specimen](../graphics/pbm/pbm.odt) draws a bitmap from an editable
single-line P1 header and raster. Change a bit to change a pixel.
All three image specimens use 64 × 64 rasters. Their complete Roboto source
copies follow the rendered images and editing instructions in a plain-text appendix.
The [Morse specimen](../decoders/morse/morse.odt) shows a greeting and digits
with punctuation, with editable dots, hyphens and separators.
The [Markdown-style specimen](../formatters/markdown/markdown.odt) shows
headings, emphasis, code and strikethrough drawn from editable markup.
The [Mini BASIC specimen](../languages/mini-basic/mini-basic.odt) executes an
editable descending `FOR` loop with mixed text-and-number `PRINT` lists, final variables and
execution status.
Statements use colons and `PRINT` items use semicolons inside a single paragraph.
The [SKI specimen](../languages/ski/ski.odt) evaluates editable prefix expressions
such as `SKI;@Ia!`. Its font parses and reduces I/K/S, draws fully parenthesized
output, and reports status and unused fuel. Change the atoms or application
markers in a blue block; no host-language evaluator is used.
The [JSON specimen](../formatters/json/json.odt) shows token colors and normalized
punctuation spacing while preserving spaces inside string values.
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

Build Word documents, or both formats (the default remains ODT):

```bash
python3 -m pip install fonttools python-docx
python3 specimens/build.py --format docx
python3 specimens/build.py --format all --project decoders/morse
```

Run the DOCX regression checks:

```bash
python3 -m unittest discover -s specimens -p 'test_word.py'
```

Outputs always go beside each project's bundled font, using its filename without
the trailing `-font` and with an `.odt` or `.docx` extension. For example,
`validator-font.ttf` becomes `validator.odt` or `validator.docx`. The documents can be
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
