# Enigma I — static machine

**Type:** static

A fixed-key historical Enigma-I decoder implemented as an OpenType state machine.

## Bundled example

Underlying text:

```text
~BDZGO
```

Expected visual output:

```text
AAAAA
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
python build.py --key "I-II-III/AAA/AAA/B" --output enigma-static-font.ttf
```

Without `--output`, the builder writes `enigma-static-font.ttf` beside `build.py`,
which is the font loaded by the playground. An explicit relative `--output`
path is resolved from your current working directory.

## Notes

The bundled font uses rotors I-II-III, start AAA, rings
AAA, reflector B, and no plugboard. Start each independently-shaped message
with `~`; it becomes an invisible machine initializer. `build.py` can bake
different rotor settings and plugboard wiring into a new font.

`playground.html` loads the bundled `enigma-static-font.ttf` and gives a plain-text
input beside a font-rendered preview. OpenType shaping behavior can differ
between applications; modern browsers using HarfBuzz are a good test target.

These fonts are visual decoders, not secure encryption. The underlying text
generally remains the original ciphertext/configuration.

## Tests

See the repository [test instructions](../../readme.md#tests). The shared
decoder suite checks this decoder's reference implementation, bundled font,
and fresh builds.
