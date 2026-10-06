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

See the repository [test instructions](../../readme.md#tests). The shared
decoder suite checks this decoder's reference implementation, bundled font,
and fresh builds.
