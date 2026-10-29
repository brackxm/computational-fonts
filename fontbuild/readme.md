# Font storage

`compact_glyphs(font)` reduces static TrueType outline storage without removing
characters, rules, states, artwork, features or execution capacity.

It replaces identical, unhinted glyph bodies with references to the first copy.
For eligible composite glyphs, frequently repeated pairs of identity components
at the origin share an appended helper. Original glyph names, IDs, advances,
bearings, contour order, points and curve flags are preserved. Helpers have zero
advance and no character mappings. Hint programs, overlap markers and delegated
component metrics stay at their original glyph level. Variable fonts are retained;
fonts with additional per-glyph metric/cache tables receive no appended helpers.
Helper allocation respects the TrueType glyph-count limit.

`compact_contours(font)` shares exact ordered contour runs. Participating
builders refine the resulting simple helpers with a second pass using
`rounds=8, min_uses=4`; profitable duplicate bodies and component pairs can then
share storage again. A final `rounds=8, min_uses=2` pass can reuse longer
remaining runs even when only two glyphs use them. The existing cost check
charges their full outline, name, location and metric overhead before accepting
a replacement. The final component pass uses `min_uses=8` and charges each
less frequent helper's outline, metric, long location, glyph-name/index and
alignment overhead. The default component threshold remains 16, preserving
existing callers. Every existing helper ID also stays intact. These passes
retain overlap flags, hinting and per-glyph cache exclusions. Build identities
are calculated before the additional storage passes in SMILES and visible SKI.

`compact_woff2(path)` compares the existing WOFF2 stream with standard Brotli
generic-mode compression and keeps only a smaller file. Its complete decoded
stream and table directory remain identical, including the existing transforms.
Metadata/private blocks retain their original encoding. Connect Four and Poem
Oracle opt in; their existing Brotli dependency also supplies this helper.

Game builders opt in through `GameFont.save(..., compact=True)`. The default
remains false; Gardner does not opt in. Other participating builders run the
pass before calculating their font identities and artifact hashes.
Copied standalone builders or shared directories still work without this
optional repository package, using their original uncompressed outlines.

Notakto additionally shares each board cell's cross and its closed-board label.
Poem Oracle's TTF shares the author attribution at its existing position. Both
append their artwork helpers after the original glyphs and retain their IDs.
Poem Oracle's webfont retains the original flat attribution sequences because
Brotli compresses them better; its TTF-only helpers are omitted. First Words
also uses different layout packing for TTF and WOFF2 to keep both files small.

FontTools can also share layout data across extension lookups when its optional
HarfBuzz repacker is installed. `requirements.txt` pins the general audit
environment; use each project's own requirements for its build. Backgammon and
Connect Four retain their explicit serializer settings. Vendored source fonts
remain unchanged, including their pinned checksums and licensing records.

Run the storage regressions from the repository root:

```sh
python -m pytest fontbuild/tests -q
```

The per-project results and individual font sizes are recorded in
[`font-size-audit.md`](../font-size-audit.md). The language circuit serializer's
separate block-sharing pass is documented in
[`languages/shared/readme.md`](../languages/shared/readme.md).

`compact_runs(font)` can share longer ordered component sequences in unhinted
static artwork. It changes only top-level composite glyphs that no other glyf component
references, retains exact positions and flags, charges full helper overhead,
and keeps composite depth at most 16. Variable fonts and per-glyph caches are
excluded. Poem Oracle opts in for TTF and restores its original glyphs for WOFF2.
