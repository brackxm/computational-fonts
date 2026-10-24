# Independent strategy provenance and licensing

The current Connect Four implementation, policy data and generated fonts are
**Apache-2.0**. They replace the previous GPL-licensed WeakC4 derivative.
No WeakC4 source, opening graph, diagrams, validator or derived font is included
in the current implementation. Historical Git revisions retain their original
licenses.

## Origin of the strategy

Copyright 2026 Michael Brackx. The native exact oracle and opening generator
were written from the standard 7 × 6 game rules. Their inputs are legal board
positions, resource settings and an included independently generated seed of
completed subgraphs. They do not read any external solution book or policy.

- [`research/native.cpp`](research/native.cpp): original bitboard AND/OR oracle.
- [`research/generate.cpp`](research/generate.cpp): opening extraction and
  counterexample-guided synthesis of strict cell-order policies.
- [`research/opening-seed.txt.gz`](research/opening-seed.txt.gz): original,
  rule-generated completed subgraphs used to initialize the recorded search.
- [`research/winning-policy.json.gz`](research/winning-policy.json.gz): complete
  certificate from the empty board, covering every legal Yellow reply.
- [`research/compact.cpp`](research/compact.cpp): replaces internal subtrees
  with shared rule-generated policies only after exhaustive win verification.
  It reads the original independent certificate, never external strategy data.
- [`research/check_hybrid.cpp`](research/check_hybrid.cpp): separate exhaustive
  checker using row-major cells and geometric line tests; it does not link the
  oracle or trust its scores.
- [`research/lower.py`](research/lower.py) and
  [`research/group_policies.cpp`](research/group_policies.cpp): preserve relative
  cross-column order of initially empty cells while sharing policies and minimizing
  control. Same-column alternatives may share a priority level.
- [`research/controller.json.gz`](research/controller.json.gz): minimized font
  controller; its metadata identifies the verified certificate.
- [`research/kernel.py`](research/kernel.py): original GSUB register interpreter;
  no old feasibility/probe code or GPL strategy compiler is imported.

The complete certificate has 165,071 vertices and 192,256 explicit edges. The
independent checker exhaustively checked 86,689,995 leaf-policy states and
proved a Red win by ply 41. The font table readback checked every dispatch and
priority entry. See the recorded [verification](verification.json) and
[source fingerprints](research/generation.json).

## File licenses

All current source code, independently generated strategy/certificate data,
ABI, TTF and WOFF2 artifacts in this folder use Apache-2.0. Search and proof
checking happen offline; ordinary font builds need neither a search engine nor
an external service. The optional SMT experiments use MIT-licensed Z3; the
recorded complete generator and normal font build do not require Z3.

Board and checker artwork is original. The generic
[`fontgame.py`](../shared/fontgame.py), typography helper and shaping harness are
Apache-2.0. Labels use original [Game Sans](../shared/fonts/game-sans/readme.md)
outlines, generated from independently drawn stroke skeletons in
[`game_sans.py`](../shared/game_sans.py). Copyright 2026 Michael Brackx,
Apache-2.0; no third-party font outlines are used. No installed typeface or
runtime font download is needed.

This records independently written code and rule-generated data. It is not a
claim of a formal clean-room process or a relicensing of the removed upstream
material.
