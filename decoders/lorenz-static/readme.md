# Lorenz SZ42a — static machine

**Type:** static

Lorenz SZ40/SZ42 teleprinter decoding with wheel state baked into the font.

## Bundled example

Underlying text:

```text
~CH58USOQWRTRIMW/OGXR3Q5P//GDVYO3I4TWE3VTVISYIAGQ5H3ULPI4PASLA4JOINJRK3AMT485KRL3D3VFIXZGDQFKYQA
```

Expected visual output:

```text
HELLO CYBERCHEF USER, IF YOU CAN READ THIS, YOU HAVE RECEIVED A MESSAGE SUCCESSFULLY.
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
python build.py --model SZ42a --preset BREAM --starts "20,32,9,51,47,2,18,26,6,29,16,4" --output lorenz-static-font.ttf --max-symbols 128
```

Without `--output`, the builder writes `lorenz-static-font.ttf` beside `build.py`,
which is the font loaded by the playground. An explicit relative `--output`
path is resolved from your current working directory.

## Notes

The bundled example uses the BREAM wheel pattern and an
SZ42a configuration. Input is raw ITA2 notation; `~` is the invisible machine
initializer. `build.py` supports SZ40, SZ42a and SZ42b and can take custom
wheel-pattern JSON.

`playground.html` loads the bundled `lorenz-static-font.ttf` and gives a plain-text
input beside a font-rendered preview. OpenType shaping behavior can differ
between applications; modern browsers using HarfBuzz are a good test target.
The preview stays on one line and scrolls horizontally because line wrapping
can split the shaping run and leave the remaining symbols undecoded. Keep
ciphertext on one line; ASCII grouping spaces are supported. The bundled font
supports up to 128 raw ITA2 symbols per run.

These fonts are visual decoders, not secure encryption. The underlying text
generally remains the original ciphertext/configuration.

## Tests

See the repository [test instructions](../../readme.md#tests). The shared
decoder suite checks this decoder's reference implementation, bundled font,
and fresh builds.
