# Vigenère — key in text

**Type:** dynamic

A single Vigenère font reads the key from the text at shaping time.

## Editable document

Open [vigenere-dynamic.odt](vigenere-dynamic.odt) in LibreOffice Writer. It embeds the font
and shows the same editable sample text in an ordinary font and in this
computational font. Follow the document's "Try it" instructions to change
the result directly in the text.

## Bundled example

Underlying text:

```text
LEMON~LXFOPVEFRNHR
```

Expected visual output:

```text
ATTACKATDAWN
```

## Playground

From the repository root:

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000/decoders/vigenere-dynamic/playground.html>.
The preview renders the input with the bundled font; the ordinary text copy
preserves the ciphertext and any runtime configuration.

## Build

Install the shared dependency:

```bash
python -m pip install fonttools
```

The default base is the bundled Apache-2.0 [Roboto 2 font](../shared/fonts/roboto-2/).
No system font is selected automatically. You can supply another TrueType font
with `--base`, subject to its own license. Generated fonts retain the base
attribution and license metadata and identify Michael Brackx’s modifications.

See the [shared decoder notes](../shared/readme.md#base-fonts) for base-font
validation and shaping precautions.

Example build command:

```bash
python build.py --output vigenere-dynamic-font.ttf --max-key 6 --max-text 24
```

Without `--output`, the builder writes `vigenere-dynamic-font.ttf` beside `build.py`,
which is the font loaded by the playground. An explicit relative `--output`
path is resolved from your current working directory.

## Notes

Syntax is `KEY~CIPHERTEXT`. The key and delimiter render
invisibly. The bundled font supports keys up to 6 letters and ciphertext up to
24 letters. Larger limits can be requested when running `build.py`, within
OpenType table limits. Keys exceeding the configured maximum remain visible
and leave the ciphertext undecoded. Use continuous ASCII letters; spaces and punctuation
after the delimiter break the decoding chain. `--delimiter` must be a single
non-whitespace character outside A-Z/a-z.

`playground.html` loads the bundled `vigenere-dynamic-font.ttf` and gives a plain-text
input beside a font-rendered preview. OpenType shaping behavior can differ
between applications; modern browsers using HarfBuzz are a good test target.

These fonts are visual decoders, not secure encryption. The underlying text
generally remains the original ciphertext/configuration.

## Tests

From the repository root, with FontTools and HarfBuzz's `hb-shape`:

```bash
python3 -m unittest discover -s decoders -p 'test_*.py' -v
```

The shared suite checks this decoder's reference implementation, bundled
font and fresh builds.

Coverage includes runtime keys and letter case, oversized keys, ciphertext
limits, invisible prefixes and rejected delimiters.
See the [shared decoder test notes](../shared/readme.md#tests) for dependencies
and checks common to the builders.
