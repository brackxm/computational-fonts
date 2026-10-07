# Shared decoder build and test notes

The decoder projects share [base-font and attribution helpers](font_metadata.py)
and a [regression suite](test_decoders.py). Each decoder's README describes
its input syntax, settings, examples and limits.

## Base fonts

All decoder builders default to the bundled Apache-2.0
[Roboto 2 Regular](fonts/roboto-2/), pinned to upstream tag `v2.138`.
Use `--base /path/to/YourFont.ttf` to select another TrueType font with a
`glyf` table and the characters required by the decoder. Custom bases retain
their own license and attribution metadata. Generated fonts preserve those
records and identify Michael Brackx's modifications.

Builders reject output paths that would overwrite the base font. Start
markers and delimiters must be separate from the input alphabet and
whitespace; the relevant builder's `--help` describes its marker options.

The decoders are computational display fonts, not cryptographic security
tools. Copying, searching, accessibility APIs or software that bypasses
OpenType shaping can expose the underlying ciphertext and configuration.
Shaping engines can split text into runs that reset stateful decoders.
Keep each message in a consistent font and follow its project's shaping limits.

## Tests

From the repository root, with Python 3.10+ and FontTools:

```bash
python3 -m unittest discover -s decoders -p 'test_*.py' -v
```

Install HarfBuzz's `hb-shape` command for the font shaping checks; without
it those tests are reported as skipped. The suite tests reference decoders,
bundled fonts and fresh builds. Builds use a small original fixture font
and the bundled Roboto base in temporary directories, leaving shipped
assets unchanged.

Coverage includes known plaintext vectors, all Playfair letter pairs
(including the J/I alias), all Morse characters and whole-group boundaries,
runtime keys and machine settings, Enigma double stepping, Lorenz shift
controls and all three models, and text limits.

Shared builder checks cover font names and output paths, base integrity,
default selection, retained license metadata, marker validation, oversized
runtime keys, malformed base-font tables and wheel-pattern files, localized
names, reserved glyph collisions, custom-base spacing and protection against
overwriting the base.
