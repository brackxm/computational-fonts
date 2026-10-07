# Enigma I — runtime rotors, positions and rings

**Type:** dynamic

Runtime Enigma rotor order, starting positions and Ringstellung; plugboard supplied to build.py.

## Editable document

Open [enigma-dynamic.odt](enigma-dynamic.odt) in LibreOffice Writer. It embeds the font
and shows the same editable sample text in an ordinary font and in this
computational font. Follow the document's "Try it" instructions to change
the result directly in the text.

## Bundled example

Underlying text:

```text
V-II-IV/QWE/BDF~SXWQHHBR
```

Expected visual output:

```text
ENIGMART
```

## Playground

From the repository root:

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000/decoders/enigma-dynamic/playground.html>.
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
python build.py --plugboard "AV BS CG DL FU HZ IN KM OW RX" --output enigma-dynamic-font.ttf --max-text 8
```

Without `--output`, the builder writes `enigma-dynamic-font.ttf` beside `build.py`,
which is the font loaded by the playground. An explicit relative `--output`
path is resolved from your current working directory.

## Notes

Syntax is `ROTORS/POSITIONS/RINGS~CIPHERTEXT`. The bundled
font was built with plugboard `AV BS CG DL FU HZ IN KM OW RX`, reflector B,
and an 8-character ciphertext limit. The configuration prefix disappears
visually. ASCII letter case is ignored throughout the runtime input; decoded
output is uppercase. `--delimiter` must be a single non-whitespace character
outside A-Z/a-z, `-`, and `/`. Use `--plugboard` when building to bake a different Steckerbrett
wiring into the font.

`playground.html` loads the bundled `enigma-dynamic-font.ttf` and gives a plain-text
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

Coverage includes runtime rotors, positions and rings, plugboard wiring,
turnover, invisible prefixes, letter case and the ciphertext limit.
See the [shared decoder test notes](../shared/readme.md#tests) for dependencies
and checks common to the builders.
