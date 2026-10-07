# Enigma I — static machine

**Type:** static

A fixed-key historical Enigma-I decoder implemented as an OpenType state machine.

## Editable document

Open [enigma-static.odt](enigma-static.odt) in LibreOffice Writer. It embeds the font
and shows the same editable sample text in an ordinary font and in this
computational font. Follow the document's "Try it" instructions to change
the result directly in the text.

## Bundled example

Underlying text:

```text
~BDZGO
```

Expected visual output:

```text
AAAAA
```

## Playground

From the repository root:

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000/decoders/enigma-static/playground.html>.
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

From the repository root, with FontTools and HarfBuzz's `hb-shape`:

```bash
python3 -m unittest discover -s decoders -p 'test_*.py' -v
```

The shared suite checks this decoder's reference implementation, bundled
font and fresh builds.

Coverage includes known plaintext, reciprocity, rotor double stepping,
punctuation that must not step the rotors and the ciphertext limit.
See the [shared decoder test notes](../shared/readme.md#tests) for dependencies
and checks common to the builders.
