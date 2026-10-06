# Playfair — static key

**Type:** static

Playfair decryption with the key baked into the generated font.

## Editable document

Open [playfair-static.odt](playfair-static.odt) in LibreOffice Writer. It embeds the font
and shows the same editable sample text in an ordinary font and in this
computational font. Follow the document's "Try it" instructions to change
the result directly in the text.

## Bundled example

Underlying text:

```text
BMODZBXDNABEKUDMUIXMMOUVIF
```

Expected visual output:

```text
HIDETHEGOLDINTHETREXESTUMP
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
python build.py --key "PLAYFAIR EXAMPLE" --output playfair-static-font.ttf
```

Without `--output`, the builder writes `playfair-static-font.ttf` beside `build.py`,
which is the font loaded by the playground. An explicit relative `--output`
path is resolved from your current working directory.

## Notes

The bundled font uses the classic key `PLAYFAIR EXAMPLE`.
`build.py` accepts a different key at build time. The ciphertext is interpreted
as Playfair digraphs. The displayed plaintext is visual only; the underlying
text remains ciphertext.

`playground.html` loads the bundled `playfair-static-font.ttf` and gives a plain-text
input beside a font-rendered preview. OpenType shaping behavior can differ
between applications; modern browsers using HarfBuzz are a good test target.

These fonts are visual decoders, not secure encryption. The underlying text
generally remains the original ciphertext/configuration.

## Tests

See the repository [test instructions](../../readme.md#tests). The shared
decoder suite checks this decoder's reference implementation, bundled font,
and fresh builds.
