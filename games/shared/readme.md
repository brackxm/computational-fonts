# Shared game infrastructure

The Snake playgrounds share `snake-controls.js` and `snake-controls.css`.

The exact-opponent games can use these independent helpers:

- `fontgame.py`: glyph and COLRv0 construction, ASCII/PUA cmap, register mark
  filtering, named GSUB stages, and repeated clock wrappers. Every stage is
  scheduled explicitly; imports do not build or write a font. Its optional
  forward cursor pipeline reads finite-state programs in one pass, then deletes
  old cursors and last-move marks, so loopy games need no fixed shaping clock.
  Optional preprocessors tokenize longer instructions before cursor execution.
  Drawing helpers cover original pixel lettering, circles, and components;
  individual games can extend their font palette. A clock schedule may reuse
  the same named lookup at multiple points; each call receives its own wrapper
  while sharing the underlying substitution tables.
- `game-controls.js`: one-run text transport, edit history, loading/shaping
  checks, status measurement, candidate submission, and stale-result clearing.
  The host supplies no board state or opponent strategy.
- `native_font.py`: persistent HarfBuzz binding for testing real font outputs.
- `controller-harness.cjs`: browser-controller test doubles whose measurements
  come from the actual font through `hb-shape`.

Games supply their own rules, exact strategy, notation, artwork, statuses, and
independent proofs. Bundled fonts are self-contained and do not load these
Python or JavaScript helpers at shaping time. Browser controllers require
their shared JavaScript file to be served alongside the playground.

All helpers are original and Apache 2.0 licensed. Font construction and Python
tests require FontTools; shaping tests additionally require native HarfBuzz and
`hb-shape`. Controller tests use Node.js and `hb-shape`.
