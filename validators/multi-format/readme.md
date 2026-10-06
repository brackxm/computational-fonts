# Multi-format validator

A single computational OpenType font checks 16 formats. Python generates the
rules at build time; **the font performs validation at shaping time**. The
playground's JavaScript only selects examples and copies input into the preview.

## Usage

Enter a complete request as `format:value?`, with standard ligatures (`liga`)
enabled and each request in one uninterrupted shaping run:

```text
iban:BE68539007547034?       → BE68539007547034 ✓
iban:BE69539007547034?       → BE69539007547034 ✗
iban:BE6853900754703?        → BE6853900754703 ✗
issn:0317-8471?             → 0317-8471 ✓
date:2025-02-29?            → 2025-02-29 ✗
```

The font hides the recognized prefix, preserves the value's original casing
and separators, and replaces the final `?` with ✓ or ✗. Copying the rendered
value and symbol copies the underlying request. Unfinished requests keep their
value visible without a result. Unknown prefixes remain visible without a
result. Surrounding text, including question marks, stays visible and does not
change a request's result. Multiple requests in the same line validate independently:

```text
Calendar: date:2024-02-29? + date:2025-02-29? → Calendar: 2024-02-29 ✓ + 2025-02-29 ✗
```

The first `?` after a recognized prefix ends that request. Extra characters
inside the request are validated; characters after its terminator are ordinary text.
Another format prefix inside an open request is literal value text, preserving
its casing. For example, `gtin:date:2024-02-29?` renders `date:2024-02-29 ✗`.
Prefix names are reserved control syntax even when capitalized; use a label such
as `Calendar:` when you want ordinary surrounding text.

✓ means the implemented structure/checksum rules pass. It does not establish
assignment, account existence, ownership, legal status, or document authenticity.

## Supported formats

| Prefix | Rules |
| --- | --- |
| `iban` | Country, length, and BBAN character positions from SWIFT registry release 103; ISO MOD 97-10 checksum |
| `isbn` | ISBN-13: 13 digits, 978/979 prefix, alternating 1/3 weighted modulo-10 checksum |
| `gtin` | GTIN-8, GTIN-12/UPC-A, GTIN-13/EAN-13, GTIN-14; GS1 checksum |
| `gln` | 13 digits and GS1 checksum |
| `sscc` | 18 digits and GS1 checksum |
| `issn` | Seven digits plus digit or X; weights 8 through 1, modulo 11 |
| `orcid` | Fifteen digits plus digit or X; ISO MOD 11-2 checksum |
| `imei` | 15 digits and Luhn checksum; IMEISV is not supported |
| `rf` | RF, two check digits, 1–21 alphanumeric reference characters; ISO MOD 97-10 |
| `ogm` | Belgian 12-digit payment reference, plain or `+++123/4567/89002+++`; first ten digits modulo 97, with zero represented as 97 |
| `lei` | 18 alphanumeric characters followed by two digits; ISO MOD 97-10 |
| `isin` | Two letters, nine alphanumeric characters, final digit; Luhn after letter expansion |
| `uuid4` | Exact hexadecimal 8-4-4-4-12 layout, version 4 and RFC variant |
| `uuid7` | Exact hexadecimal 8-4-4-4-12 layout, version 7 and RFC variant |
| `date` | `YYYY-MM-DD`, valid month/day, Gregorian leap-year rules; four-digit astronomical years including year 0000 |
| `mrz` | TD3 passport's two 44-character lines separated by `\|`; character layout, document/date/optional-data check digits, and composite check digit |

ASCII lowercase is uppercased only for computation; the displayed value retains
its original casing. ASCII spaces are ignored in
checksum identifier modes. ISBN, ISSN, and ORCID additionally ignore hyphens
as print separators, wherever present. Other identifier modes reject hyphens,
slashes, and plus signs, except for OGM's exact decorated layout. UUIDs, dates,
and MRZ require exact layouts, with no spaces. MRZ checks date-field digits and
checksums; it does not check those fields' calendar validity or issuer codes.
An empty MRZ optional-data field may use `<` in place of a zero check digit.
ISBN allocation ranges, ISIN issuing-prefix lists, LEI issuers, national BBAN
checksums, and live registry records are outside the implemented checks.

## Playground

Serve the repository root:

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000/validators/multi-format/playground.html>.
The dropdown includes a passing example of every supported format. Edit a digit
to see a checksum failure, or remove a character to see a format failure.
The bundled demo font uses green ✓ and red ✗. Rebuild it with
`python3 validators/multi-format/build.py --color` to retain those colors.

## Build and tests

```bash
python3 -m pip install fonttools
python3 validators/multi-format/build.py
python3 -m unittest discover -s validators/multi-format -p 'test_*.py' -v
```

Add `--color` to generate green ✓ and red ✗ symbols inside the font:

```bash
python3 validators/multi-format/build.py --color --output validators/multi-format/validator-color-font.ttf
```

The default build remains monochrome. Only the result symbols receive colors;
the entered value uses the application's text color. Colored builds use
[OpenType COLR v0 and CPAL tables](https://learn.microsoft.com/en-us/typography/opentype/spec/colr)
and retain monochrome symbol outlines for applications without color-font support.
They have a separate font family and identity so both variants can coexist.

The default base is the repository's Apache-2.0 Roboto 2 font. `--base` accepts
another TrueType font with distinct printable ASCII glyphs and no reserved
validator glyph names; its original license still applies.
`--output` selects another path and cannot overwrite the base. Defaults resolve
beside the builder, while explicit relative paths resolve from the current
directory. Imports do not generate or overwrite fonts.

Tests require FontTools. HarfBuzz's `hb-shape` is required for shaping checks;
without it those tests are skipped. Tests exercise fresh monochrome and color
builds and the bundled font, every country example in the IBAN snapshot, checksum mutations,
invalid lengths/characters, X check digits, generated checksum vectors,
Gregorian century boundaries, unfinished requests, surrounding text, independent
adjacent requests, nested prefixes, and changes to font identity when outlines or metrics change.

## Implementation and limits

First, the font recognizes prefix candidates and scans forward to protect each
value until its first `?`. Nested candidates are restored as literal text, and
only candidates outside an open request start a validator. The font then splits
each value character into a visible copy and an invisible computation token. Contextual substitutions
recognize a complete format ending in `?`. Finite-state ligatures consume the
invisible tokens and evaluate the checksum while leaving visible copies intact.
The final lookup writes the result at the terminator's position, after the value,
and removes the remaining computation tokens. Valid values receive ✓; both
format and checksum failures receive ✗.
IBAN and RF save their first four characters as a remainder, calculate the
body's remainder, then append the saved prefix numerically. No large integer or
enumeration of complete account numbers is needed. Other modes share modulo-10,
modulo-97, or Luhn arithmetic where their rules permit it.

Small calling lookups invoke shared transition tables for 100 bounded passes.
Direct table construction avoids feaLib's expensive overlap checks on large
rule sets. The full MRZ request is the longest supported payload: 89 characters.
Shaping engines can impose their own operation limits. Excessive separator
padding can exhaust the 100-pass computation budget; unfinished/unsupported text
must never be read as a passing result. Line wrapping, separate styled spans,
and application text segmentation can reset computation.

## Rule sources and provenance

The IBAN country patterns and examples in `iban_registry.json` are extracted
from [SWIFT's IBAN registry release 103, September 2026](https://www.swift.com/swift-resource/9606/download).
The snapshot includes 89 country formats and Brazil's updated alphanumeric bank
identifier. Builds use this checked-in snapshot and do not access the network.
Updating it requires rebuilding and retesting the font.

Other sources:

- [International ISBN Agency: ISBN structure and check digit](https://www.isbn-international.org/index.php/content/what-isbn/10)
- [GS1: check digit calculation](https://www.gs1.org/services/how-calculate-check-digit-manually)
- [Library of Congress: ISSN check digit](https://www.loc.gov/issn/basics/basics-checkdigit.html)
- [ORCID: identifier structure and checksum](https://support.orcid.org/hc/en-us/articles/360006897674-Structure-of-the-ORCID-Identifier)
- [GSMA: IMEI allocation and check digit](https://www.gsma.com/newsroom/wp-content/uploads/TS.06-v16.0.pdf)
- [Finance Finland: RF creditor reference](https://www.finanssiala.fi/wp-content/uploads/2024/04/structure-of-the-rf-creditor-reference-iso-11649.pdf)
- [Febelfin: Belgian structured payment reference](https://febelfin.be/en/themes/digitalization-innovation/regulations/conditions-for-offering-credit-transfers)
- [ISO TC68: LEI structure and checksum](https://committee.iso.org/sites/tc68/home/articles/content-left-area/articles/what-is-lei.html)
- [ANNA: ISIN structure](https://anna-web.org/identifiers/)
- [RFC 9562: UUID layout, versions, and variants](https://www.rfc-editor.org/rfc/rfc9562.html)
- [RFC 3339: Gregorian calendar rules](https://www.rfc-editor.org/rfc/rfc3339.html)
- [ICAO Doc 9303 Part 3: MRZ check digits](https://www.icao.int/sites/default/files/publications/DocSeries/9303_p3_cons_en.pdf)

## License

Apache License 2.0; see the root [LICENSE](../../LICENSE) and
[third-party notices](../../THIRD_PARTY_NOTICES.md). Generated fonts retain the
Roboto copyright and license records and identify the validator modifications.
