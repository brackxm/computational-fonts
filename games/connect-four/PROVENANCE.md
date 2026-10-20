# Strategy provenance and licensing

The complete opening graph and priority diagrams come from **2swap / WeakC4**,
revision **51dc8383472c63aa6e6796a9ef306662eb8bd4bf**:

- [Pinned source](https://github.com/2swap/WeakC4/tree/51dc8383472c63aa6e6796a9ef306662eb8bd4bf)
- [Strategy explanation](https://2swap.github.io/WeakC4/explanation/)
- [Unmodified upstream license](upstream/LICENSE)
- [Snapshot checksums](upstream/SHA256SUMS)

`upstream/` is the source/data subset supplied in the feasibility archive,
including the JSON solution, exhaustive validator, protobuf representation and
serialization tools. `REVISION` records its upstream commit. Files retain their
original contents. `SHA256SUMS` was added here. This is a reproducible snapshot,
not a Git checkout or a complete copy of the upstream website.

The snapshot contains 132 opening decision nodes, 522 diagram entry boards,
384 unique diagrams, and a 10,290-byte serialized protobuf. The pinned diagrams
use ten numeric priority levels; the current upstream website can describe a
newer strategy/language, so builds use only the bundled pinned data.

The prior feasibility experiment demonstrated a board-to-decision GSUB kernel.
This implementation adapts its column-major graph construction in `strategy.py`
and sparse glyph-register approach, and adds a complete history interpreter,
shared turn programs, guarded clocks, fixed register updates, grouped tactical
rules, artwork, status signals and tests. It does not bundle the empty-outline
probe fonts. Original code and artwork: Copyright 2026 Michael Brackx.
Strategy: 2swap and the WeakC4 contributors; retain upstream attribution.

## File licenses

| Material | License |
| --- | --- |
| `upstream/` source and strategy data | GPL-3.0; see its unmodified `LICENSE` |
| `build.py`, `gsub.py`, `strategy.py`, `reference.py`, `verify_longest.py`, `test_font.py` | GPL-3.0-only |
| Generated TTF, WOFF2, ABI and strategy-containing artifacts | GPL-3.0-only |
| `controls.js`, `start.js`, `test_controls.cjs`, `shaping.py`, playground HTML/CSS | Apache-2.0 |

The generated fonts **contain derived GPL strategy material** and are explicitly
identified as GPL in their name-table license metadata. They are not distributed
under the repository's default Apache-2.0 license. The full corresponding
sources needed to rebuild them are supplied in this folder, alongside the
upstream license. Original geometric outlines use no imported font or artwork.

The repository's other Apache-2.0 projects retain their existing licenses.
The root license and third-party notices identify this project's exception.
