# Vigenère — key in text

**Type:** dynamic

A single Vigenère font reads the key from the text at shaping time.

## Bundled example

Underlying text:

```text
LEMON~LXFOPVEFRNHR
```

Expected visual output:

```text
ATTACKATDAWN
```

## Build

Install the shared dependency:

```bash
python -m pip install fonttools
```

The default base is the bundled Apache-2.0 [Roboto 2 font](../shared/fonts/roboto-2/).
No system font is selected automatically. You can supply another TrueType font
with `--base`, subject to its own license. Generated fonts retain the base
attribution and license metadata and identify Michael Brackx’s modifications.

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

See the repository [test instructions](../../readme.md#tests). The shared
decoder suite checks this decoder's reference implementation, bundled font,
and fresh builds.
