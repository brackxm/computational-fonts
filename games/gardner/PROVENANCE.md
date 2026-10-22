# Gardner opening-book provenance

`book.json.gz` contains 8,192 original board-to-move records generated with
[Fairy-Stockfish](https://github.com/fairy-stockfish/Fairy-Stockfish), using its
Gardner variant. It contains moves, not imported engine source or a published
solution table. No claim of perfect play is attached to the data.

- Engine base revision: `9f778da667f6e07dae1e85d3e2ea204fc6dee94d`.
- Local executable SHA-256:
  `6c4baa890e283ce9254c093a8a6d88159fd852bb410d0a0c5cafcb0bbe5fe2b5`.
- Local diagnostic export and optional goal-probe hooks were present in that
  build. All `GARDNER_*` environment variables were removed before launching it,
  so those hooks were inactive. No external proof table or goal oracle was used.
- Variant `gardner`; one thread; 64 MiB hash; requested node budget 50,000 per
  position and 500,000 at the initial position.
- Boards are 25 characters, A1–E1 first, followed by ranks 2–5. Uppercase pieces
  are White. Moves use lowercase source/destination coordinates and an optional
  lowercase promotion letter.
- Expansion starts at the standard board, chooses one White engine move, and
  queues every legal Black response. Repeated boards are deduplicated.
- All book moves are rechecked with the repository's original Gardner rules
  during a font build and in the test suite.

The generation script runs a separately supplied UCI executable. Fairy-Stockfish
is GPL-3.0; no engine implementation or executable is included here. Obtain its
source and license from the upstream project when building that optional tool.
The generated move records and this repository's independent implementation
are distributed under the root Apache-2.0 license.
