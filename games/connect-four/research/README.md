# Complete independent Connect Four strategy

The offline search produced a complete winning certificate from the empty
standard 7 × 6 board. The separate coordinate-based checker proved a Red win
by ply 41, checking 165,071 vertices, 192,256 edges and 86,689,995 leaf states.
The generated font performs every gameplay operation in GSUB. No WeakC4 source,
policy data or compiler is read. All current files here are Apache-2.0.

The [main documentation](../readme.md), [provenance](../PROVENANCE.md),
[certificate report](winning-policy-verification.json) and
[font verification](font-verification.json) describe the final result and limits.

## Complete generation path

- `native.cpp`: original bitboard oracle, exact AND/OR search, threat pruning,
  mirror canonicalization and collision-checked transposition entries.
- `generate.cpp`: complete opening extraction, retaining a proved Red move and
  every Yellow reply, with counterexample-guided strict cell-order leaves.
- `opening-seed.txt.gz`: original completed subgraphs that initialized the
  recorded search. These are rule-generated data, not an imported solution.
- `compact.cpp`: tries popular rule-generated leaf orders at internal vertices,
  retaining a replacement only after exhaustive checking. The recorded pass
  tested 256 popular candidates with a 10,000-state budget per attempt. Failed
  and budget-exhausted attempts retain the complete original subtree.
- `check_hybrid.cpp`: independent row-major/geometric exhaustive checker.
- `lower.py` / `group_policies.cpp`: share compatible orders of initially empty
  cells in different columns and minimize the controller. Alternatives in one
  column may share a level because only one is playable at a time. The lowering checks order preservation
  for every source leaf and both orientations.
- `kernel.py`: original fixed-register GSUB interpreter with two-register mode
  addressing, direct reply-pair substitutions, shared column profiles and guarded
  turn clocks. Unreachable construction lookups are removed and references remapped.
- `verify_kernel.py`: binary readback of every dispatch/priority entry plus
  independent model comparisons against real HarfBuzz shaping.

Reproduce the native extraction with the supplied independent seed:

```sh
clang++ -O3 -std=c++17 games/connect-four/research/generate.cpp -o /tmp/c4-generate
gzip -dc games/connect-four/research/opening-seed.txt.gz > /tmp/c4-opening.seed
/tmp/c4-generate --table-bits 25 --iterations 64 \
  --cache /tmp/c4-oracle.bin --seed /tmp/c4-opening.seed --output /tmp/c4-base-policy.json
python3 games/connect-four/research/check_hybrid.py /tmp/c4-base-policy.json \
  --export /tmp/c4-base.tape
clang++ -O3 -std=c++17 games/connect-four/research/compact.cpp -o /tmp/c4-compact
/tmp/c4-compact /tmp/c4-base.tape /tmp/c4-policy.json 256
clang++ -O3 -std=c++17 games/connect-four/research/check_hybrid.cpp -o /tmp/c4-check
python3 games/connect-four/research/check_hybrid.py /tmp/c4-policy.json \
  --checker /tmp/c4-check --report /tmp/c4-proof.json
clang++ -O3 -std=c++17 games/connect-four/research/group_policies.cpp -o /tmp/c4-group
python3 games/connect-four/research/lower.py /tmp/c4-policy.json \
  --grouper /tmp/c4-group --output /tmp/c4-controller.json
```

The cache contains only results computed by this oracle and is optional.
Unknown resource-limited searches are not accepted as wins. Only a complete
certificate passing the separate checker is a replacement strategy. The font
build checks the stored proof and controller fingerprints before compiling.

## Earlier experiments

`independent.py`, `test_independent.py` and `font_probe.py` retain the initial
standard-library solver, rank synthesis, counterexample tests and endgame-only
font probe. `results.json` and `font-results.json` record those limited tests;
they are not the complete proof report. All 5,040 fixed win/block/column-order
policies were refuted from the opening, with original counterexamples retained
in `tactical-witnesses.json.gz`.

`opening.py` retains slower and alternative synthesis experiments. Its optional
SMT methods use MIT-licensed Z3; Z3 is not required by the successful native
generation path or normal font builds. `pool.cpp` is an optional policy-sharing
experiment and is not part of the distributed certificate's generation path.
