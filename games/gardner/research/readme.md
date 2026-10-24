# Gardner minichess: certified-corpus research variant

Master keeps the generator, runtime, tests, manifest and certification evidence.
The generated research font and binary build inputs are excluded from master and
ignored locally. Only the latest accepted Ke5/F08 font and its binary inputs are
kept on the branch `codex/gardner-research-artifacts-20261024`, based
on the source-only master. Earlier large-font versions are excluded from that
branch too. An ordinary clone fetches the artifacts under
`origin/codex/gardner-research-artifacts-20261024`; it does not check them out.
A master-only clone excludes the strategy corpus; fetch that branch explicitly
to reproduce this variant. Source and artifact updates must match: an older
artifact ref is rejected by the manifest. Local unpublished updates restore from
the local artifact branch; fetching cannot retrieve an unpublished variant.

After restoring and building below, [open the research playground](playground.html),
or use the always-bundled [lightweight default opponent](../playground.html).

The optional **42,139,072-byte font** extends the retained certified policy with
F02, F03, F04, F05, F12, F13, F14, F15, F18 and F19, alongside the earlier
F20, F23, F22, F00 and F01 continuations. It now also includes **F08 and the
11-piece …Ke5 continuation**, both certified at quiet clock zero. This is stronger
than the requested clock-one guarantee for …Ke5. It contains **24,518,928 policy
rows and 57,011 glyphs** using the original artwork.

**It is not a complete perfect opponent.** After White's A2–A3, Black's
**B4–A3** and **B4–B3** openings still display `UNPROVEN BRANCH` (status 6).
Four frontier gaps remain: F09, F11, F16 and F21. Try B5–C3 for a supported
branch. The original **4,463,004-byte playable font remains the default** and
continues on every legal branch using its opening book and heuristic.

The added strategies guarantee White nonloss from quiet clock zero, without
an exact draw/win classification. The two stopped openings prevent reaching
these continuations from the standard start. Guarantees apply to the certified
policy and its entry clocks.

## Play and transport

Restore the frozen inputs, build, and copy the output font as described below.
Then serve the repository root with `python3 -m http.server 8000` and open
<http://localhost:8000/games/gardner/research/playground.html>.
The separate research page loads the locally generated font; the default page
links to these instructions and keeps using the lightweight font.

Use `b` followed by uppercase Black moves and semicolons, e.g. `bB5C3;`.
Promotion adds Q, R, B, or N before the semicolon. `controls.js` inserts
256 inert padding tokens per source character, plus 256. **Do not use the
lightweight font's 64-token encoder.** Shape the complete history in one
left-to-right run, with `liga` on and kerning off. Input is limited to 512
source characters.

Status advances are 1: Black to move, 2: font checkmates, 3: Black checkmates,
4: illegal move, 5: malformed source, 6: unproved branch, 7: draw. The board is
1,800 units wide; status adds its code. The UI displays stopped histories and
allows undo. All legal moves, replies, draw handling and artwork execute in GSUB.

The policy supports intended fifty-move claims, automatic draws after 150 quiet
individual moves, and certified dead positions. It does not expose repetition
claims. Checkmate takes precedence over the automatic draw. Unsupported opening
branches have no heuristic fallback in this variant.

## Frozen, reproducible build

Use Python 3.11+, its standard `lzma` module, the pinned requirements, C++17
`clang++`, Node.js and `hb-shape`. From the repository root:

```sh
python3 games/gardner/research/test_restore_inputs.py
python3 games/gardner/research/restore_inputs.py
python3 -m pip install -r games/gardner/research/requirements.txt
python3 games/gardner/research/build.py
cp games/gardner/research/build/gardner-research.ttf games/gardner/research/gardner-research.ttf
python3 games/gardner/research/test_build.py
python3 games/gardner/research/test_font.py
node games/gardner/research/test_controls.cjs
node games/gardner/research/test_benchmark.cjs
node games/gardner/test_controls.cjs
```

`restore_inputs.py` first tries the local artifact branch, then its fetched
`origin` ref. It reads only local Git objects and checks each binary input
against the manifest before atomic replacement. It does not download data or
run proof searches. An explicit `--ref` selects exactly that local ref or commit,
without fallback. If no artifact ref exists (for example, after a master-only
clone), fetch it yourself before restoring:

```sh
git fetch origin refs/heads/codex/gardner-research-artifacts-20261024:refs/remotes/origin/codex/gardner-research-artifacts-20261024
```

The regression check uses a small temporary Git repository and requires no
research assets. It covers fetched-ref discovery, local-branch precedence,
explicit refs, checksum failures, missing inputs and failure preservation. The
generated root TTF and restored inputs remain ignored; do not force-add them
to master.

Build products go in ignored `build/`. Override with `--output-dir`; pass the
same populated directory to tests with `--build-dir` and optionally `--font`.
The build checks compressed input hashes, the decompressed classifier and
frozen timestamps. It serializes to a temporary file and verifies its hash
before atomically replacing the output TTF; failure preserves any existing font.
[Build-safety checks](evidence/build-safety.json) in `test_build.py` cover failure
preservation, cleanup and byte-exact success using
the real serialized font. The build must reproduce this exact archived font:

`098c54735981b0aa7f0061692d206ef49e16668ccff3fef2614a3d54e359ce4a`

The 35,736,552-byte `inputs/policy.tree.xz` freezes a shared binary classifier
with 8,901,562 nodes and maximum depth 45. It uses six-bit XY coordinates for
32 piece-location registers and reflects positions only at five pieces or fewer.
The compiler keeps 48,000-slot low banks, partitions banks twice by child-bank
IDs, and shares reused outputs while retaining explicit maps elsewhere.
Temporary dictionary IDs overlap existing glyph IDs and are consumed immediately
in nested lookups with LookupFlag 0. The compiler and game runtime are unchanged.

The separately restored `inputs/game-base.ttf` and `.gamepack` freeze the
legal-move shell and linker layout independently of the lightweight generator.
After restoring the binary inputs, normal builds need no engine, corpus
extraction, table generation or proof search. The generator compiles the frozen
classifier; source alone cannot reconstruct the certified strategy corpus.
The full mathematical certificates and table dependencies remain in separate
archives outside Git.

## Certification and verification

The retained **23,129,338 rows** include every policy in D, with all earlier
F20, F23, F22, F00, F01 and ten-root frontier extensions unchanged. Their
historical evidence remains in [evidence/](evidence/), including the
[earlier D certificate](evidence/frontier-extension.json). The new
[Ke5/F08 certificate](evidence/ke5-f08.json) adds **1,389,590 rows**. Shared
support means these costs are not separate per-branch sizes.

The new fixed-policy closure checks **7,519,306 legal Black replies**, with
**3,387,432 safe exits**, **77,527 terminal edges** and **zero missing
continuations**. Reachability expands every selected policy at its encoded
entry clock; the complete new delta has guard zero. A fresh verification-only
host independently replayed the full supporting certificate DAG. Another fresh
host checked the actual **2,480,486-row joint delta** (D plus Ke5/F08), every
encoded guard and all **12 roots at zero**, directly against original pre-F02
basis93. Neither validation process ran proof search. Archive inventory and
critical certificate/executable recovery hashes were independently checked.
The admitted primary basis is:

`cbc351294ae5db00b3bae17c897a6f4711466044c7ce49c03c6b2de2f1dadded`

Encoded joint runtime certificate SHA256:

`188a73e056a87ddd57cc24187d4d156698ced252fb506ae6ef406822b004ffb2`

The runtime can coalesce winning labels into nonloss labels with the same move,
retaining safe-entry and reset/immediate-mate bounds. It can prefer a legal draw
claim to pursuing a win outside the original bound.

Packaged tests check **162 full-history prefixes and 1,206 clock boundaries**,
including the new roots and every first Black reply at quiet clocks 0, 98, 99,
100, 149 and 150. They compare cells, last move and status against Python legality
and the frozen policy, including underpromotions, reflection, malformed source,
stalemates and stopped openings. All **17,803,124 binary-node/input pairs** run
through the actual TTF lookups. HarfBuzz additionally executes **38,344 dictionary
checks** and **29,061 route-class checks**, including `.notdef` and GDEF overlaps.
Four corrupt classifiers check early rejection of invalid structure.

## Size and performance limits

These are preserved measurements of these exact Ke5/F08 font bytes on the validation
host. They do not guarantee every device or load state. Native timings rerun
locally; the [browser benchmark](benchmark.html) measures load and complete replay.

| Gate | Accepted measurement | Limit |
| --- | ---: | ---: |
| TTF size | 42,139,072 bytes | 50,000,000 bytes |
| Glyphs | 57,011 | 65,535 |
| Browser load + first shape | 169.2 ms | 2,000 ms |
| Renderer RSS growth | 357.98 MiB | 512 MiB |
| Browser reply p95 | 28.0 ms | 250 ms |
| Browser 150-live-ply maximum | 93.4 ms | 1,000 ms |
| Native reply p95 | 44.16 ms | 250 ms |
| Native 150-live-ply maximum | 93.54 ms | 1,000 ms |

The benchmark keeps each result, including load errors and failed timings, in
a per-document trial history. A successful rerun preserves earlier failures;
load errors allow retry and release rejected font faces. Copy the history JSON
before closing or reloading the page. Load/replay attempt counters distinguish
retries; open a fresh document for cold-load measurements. Failure-injection
checks run with `test_benchmark.cjs`; the [historical workflow evidence](evidence/benchmark-history.json)
preserves D's injected failure and recovery tests. Current Ke5/F08 measurements
are in [browser.json](evidence/browser.json) and [memory.json](evidence/memory.json);
the unchanged failure-injection checks run against the current benchmark.

The first fresh-document Ke5/F08 browser trial passed. It checks 77 complete-history
prefixes, a longest live history of 153 plies, and 150 executed plies after the
opening while still live. Twenty inert-padding suffixes prevent cached text
runs. Memory sums positive RSS growth over all host renderers across 240 samples,
counting new renderers in full.

There are **7,860,928 bytes and 8,524 glyphs of headroom**. Future additions must
pass every gate again. The independent proof archive preserves the earlier F02
font's failed timing trial and passing isolated retry, the scratch-artifact guard
stop and recovery, and the corrected archive/replay packaging issues.

[Integration evidence](evidence/integration.json) binds this release to the
validated archive and repository checks. [Consistency evidence](evidence/consistency.json)
checks original artwork and frozen code. [Earlier representation](evidence/representation.json)
and [encoding reports](evidence/encoding.json) retain their historical counts and
hashes; `manifest.json` identifies the current font. Proof searches stay stopped.

This variant and its original artwork are Apache-2.0, like the default Gardner
implementation. See [the default provenance](../PROVENANCE.md) for its earlier
engine-generated book; this variant uses the frozen policy instead.
