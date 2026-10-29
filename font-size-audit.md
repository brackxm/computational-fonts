# Font size audit

Audit date: 2026-10-29. Reviewed all **42 projects** and **108 tracked standalone fonts** individually, including seven supporting fonts. **Gardner and its research variant remain excluded and untouched.**

This pass saves another **44,224 bytes**, reducing Poem Oracle's TTF from **7,638,988 to 7,594,764 bytes**. All other font files remain unchanged. The three 2026-10-29 reviews save **204,964 bytes** relative to commit `89ce29f`. Total font storage is **89,205,172 bytes**, down **87,391,980 bytes (49.5%)** from the original **176,597,152 bytes**. No font grew. Embedded ODT/ZIP copies are excluded from totals.

## Current review and validation

The component-run pass shares ordered groups of 3–8 existing components when actual non-overlapping uses cover helper storage, metrics, locations, names and alignment. It changes only unhinted top-level composites not referenced by other glyf components. Children remain untouched, offsets/flags retain their exact values, helpers have zero advance, and composite depth remains at most 16. Variable fonts, metric delegation, overlap controls, transforms, point attachments and per-glyph caches retain their existing safeguards. Only Poem Oracle opts into the pass.

- All 108 checkpoint comparisons passed. Every existing glyph ID/name, ordered point/curve flag, advance, bearing and hint program is retained; name, cmap, OS/2, layout and color payloads are unchanged. Helper names/statistics are updated.
- All 48 shared storage/circuit-packing tests passed, including run geometry, positioned data, root-only eligibility, cache/variation exclusions, hint/overlap/metric/transform guards, helper profitability, depth and glyph-count limits.
- Poem Oracle passed all 5 full corpus/native/rebuild tests. Its 8 browser-runtime tests reach every one of the 2,876 poems and check actual outlines.
- All 8 Chrome comparisons passed at two sizes for four poems whose glyphs actually changed. In total 2,088 poem panels share the new component runs.
- The other 41 projects retain byte-identical fonts and their preceding regression evidence. Their measured run-sharing prototypes totaled 448 bytes; those candidates were not adopted.
- All 62 hash-bearing manifests, 20 ODT specimens and 2 bundles match current fonts. All four WOFF2 files and all seven supporting fonts remain unchanged.

## Optimization history

| Round | Change | Saved (bytes) |
| ---: | --- | ---: |
| 1 | Initial language block sharing | 38,479,448 |
| 2 | Project-by-project glyph and format packing | 6,111,936 |
| 3 | Distinct-block windows, layout selection, shared write coverage and positioned poem components | 26,087,092 |
| 4 | Exact unhinted contour runs and COLRv1 layer reuse | 3,020,652 |
| 5 | Sparse wildcard classes, compact class definitions and shared singleton truth rules | 12,512,096 |
| 6 | Bounded pure-Python sharing between extension-subtable trees | 713,368 |
| 7 | WOFF2 Brotli stream selection without changing decoded data | 13,652 |
| 8 | Refine repeated contour runs inside existing outline helpers | 242,848 |
| 9 | Reuse duplicate outline bodies and component pairs exposed by contour factoring | 5,924 |
| 10 | Project-by-project review; profitable contour runs used twice | 77,220 |
| 11 | Costed eight-use component sharing after the contour passes | 83,520 |
| 12 | Top-level component-run sharing in Poem Oracle TTF | 44,224 |

## Projects, reviewed one by one

| Project | Files | Review before | Review after | Saved this pass | Checks |
| --- | ---: | ---: | ---: | ---: | --- |
| [decoders/arabizi](decoders/arabizi/) | 1 | 362,772 | 362,772 | 0 | Passed; unchanged |
| [decoders/enigma-dynamic](decoders/enigma-dynamic/) | 1 | 805,252 | 805,252 | 0 | Passed; unchanged |
| [decoders/enigma-static](decoders/enigma-static/) | 1 | 1,332,148 | 1,332,148 | 0 | Passed; unchanged |
| [decoders/lorenz-static](decoders/lorenz-static/) | 1 | 789,732 | 789,732 | 0 | Passed; unchanged |
| [decoders/morse](decoders/morse/) | 1 | 466,396 | 466,396 | 0 | Passed; unchanged |
| [decoders/playfair-static](decoders/playfair-static/) | 1 | 531,604 | 531,604 | 0 | Passed; unchanged |
| [decoders/vigenere-dynamic](decoders/vigenere-dynamic/) | 1 | 642,216 | 642,216 | 0 | Passed; unchanged |
| [decoders/vigenere-static](decoders/vigenere-static/) | 1 | 536,396 | 536,396 | 0 | Passed; unchanged |
| [formatters/json](formatters/json/) | 1 | 1,202,772 | 1,202,772 | 0 | Passed; unchanged |
| [formatters/markdown](formatters/markdown/) | 1 | 663,408 | 663,408 | 0 | Passed; unchanged |
| [games/achi](games/achi/) | 1 | 361,576 | 361,576 | 0 | Passed; unchanged |
| [games/backgammon](games/backgammon/) | 1 | 777,252 | 777,252 | 0 | Passed; unchanged |
| [games/chomp](games/chomp/) | 1 | 95,496 | 95,496 | 0 | Passed; unchanged |
| [games/connect-four](games/connect-four/) | 2 | 5,964,128 | 5,964,128 | 0 | Passed; unchanged |
| [games/cram](games/cram/) | 1 | 84,260 | 84,260 | 0 | Passed; unchanged |
| [games/dodgem](games/dodgem/) | 1 | 293,572 | 293,572 | 0 | Passed; unchanged |
| [games/domineering](games/domineering/) | 1 | 167,876 | 167,876 | 0 | Passed; unchanged |
| [games/dots-and-boxes](games/dots-and-boxes/) | 1 | 378,348 | 378,348 | 0 | Passed; unchanged |
| [games/hexapawn](games/hexapawn/) | 1 | 124,208 | 124,208 | 0 | Passed; unchanged |
| [games/kayles](games/kayles/) | 1 | 464,356 | 464,356 | 0 | Passed; unchanged |
| [games/mu-torere](games/mu-torere/) | 1 | 460,588 | 460,588 | 0 | Passed; unchanged |
| [games/nim](games/nim/) | 1 | 200,708 | 200,708 | 0 | Passed; unchanged |
| [games/notakto](games/notakto/) | 1 | 196,676 | 196,676 | 0 | Passed; unchanged |
| [games/sim](games/sim/) | 1 | 4,677,768 | 4,677,768 | 0 | Passed; unchanged |
| [games/snake-dynamic](games/snake-dynamic/) | 1 | 216,432 | 216,432 | 0 | Passed; unchanged |
| [games/snake-fixed](games/snake-fixed/) | 1 | 176,064 | 176,064 | 0 | Passed; unchanged |
| [games/text-adventure](games/text-adventure/) | 1 | 443,732 | 443,732 | 0 | Passed; unchanged |
| [games/tic-tac-toe](games/tic-tac-toe/) | 1 | 139,992 | 139,992 | 0 | Passed; unchanged |
| [games/wythoff](games/wythoff/) | 1 | 273,132 | 273,132 | 0 | Passed; unchanged |
| [graphics/first-words](graphics/first-words/) | 2 | 2,054,048 | 2,054,048 | 0 | Passed; unchanged |
| [graphics/heraldry](graphics/heraldry/) | 2 | 784,036 | 784,036 | 0 | Passed; unchanged |
| [graphics/pbm](graphics/pbm/) | 1 | 2,604,848 | 2,604,848 | 0 | Passed; unchanged |
| [graphics/pgm](graphics/pgm/) | 1 | 2,664,752 | 2,664,752 | 0 | Passed; unchanged |
| [graphics/ppm](graphics/ppm/) | 1 | 2,643,020 | 2,643,020 | 0 | Passed; unchanged |
| [graphics/smiles](graphics/smiles/) | 1 | 6,065,592 | 6,065,592 | 0 | Passed; unchanged |
| [graphics/turtle](graphics/turtle/) | 1 | 2,198,656 | 2,198,656 | 0 | Passed; unchanged |
| [languages/mini-basic](languages/mini-basic/) | 1 | 3,594,292 | 3,594,292 | 0 | Passed; unchanged |
| [languages/ski](languages/ski/) | 2 | 870,596 | 870,596 | 0 | Passed; unchanged |
| [languages/verilog](languages/verilog/) | 13 | 205,504 | 205,504 | 0 | Passed; unchanged |
| [languages/wasm](languages/wasm/) | 43 | 29,182,728 | 29,182,728 | 0 | Passed; unchanged |
| [literature/poem-oracle](literature/poem-oracle/) | 2 | 9,168,556 | 9,124,332 | 44,224 | Passed; rerun |
| [validators/multi-format](validators/multi-format/) | 1 | 1,949,264 | 1,949,264 | 0 | Passed; unchanged |

## Individual fonts

| Font | Review before | Review after | Saved this pass |
| --- | ---: | ---: | ---: |
| `decoders/arabizi/arabizi-font.ttf` | 362,772 | 362,772 | 0 |
| `decoders/arabizi/fonts/NotoNaskhArabic.ttf` | 307,592 | 307,592 | 0 |
| `decoders/enigma-dynamic/enigma-dynamic-font.ttf` | 805,252 | 805,252 | 0 |
| `decoders/enigma-static/enigma-static-font.ttf` | 1,332,148 | 1,332,148 | 0 |
| `decoders/lorenz-static/lorenz-static-font.ttf` | 789,732 | 789,732 | 0 |
| `decoders/morse/morse-font.ttf` | 466,396 | 466,396 | 0 |
| `decoders/playfair-static/playfair-static-font.ttf` | 531,604 | 531,604 | 0 |
| `decoders/shared/fonts/roboto-2/Roboto-Bold.ttf` | 514,260 | 514,260 | 0 |
| `decoders/shared/fonts/roboto-2/Roboto-BoldItalic.ttf` | 532,860 | 532,860 | 0 |
| `decoders/shared/fonts/roboto-2/Roboto-Italic.ttf` | 533,388 | 533,388 | 0 |
| `decoders/shared/fonts/roboto-2/Roboto-Regular.ttf` | 515,100 | 515,100 | 0 |
| `decoders/vigenere-dynamic/vigenere-dynamic-font.ttf` | 642,216 | 642,216 | 0 |
| `decoders/vigenere-static/vigenere-static-font.ttf` | 536,396 | 536,396 | 0 |
| `formatters/json/json-font.ttf` | 1,202,772 | 1,202,772 | 0 |
| `formatters/markdown/markdown-font.ttf` | 663,408 | 663,408 | 0 |
| `games/achi/achi-font.ttf` | 361,576 | 361,576 | 0 |
| `games/backgammon/backgammon-font.ttf` | 777,252 | 777,252 | 0 |
| `games/chomp/chomp-font.ttf` | 95,496 | 95,496 | 0 |
| `games/connect-four/connect-four-font.ttf` | 4,653,232 | 4,653,232 | 0 |
| `games/connect-four/connect-four-font.woff2` | 1,310,896 | 1,310,896 | 0 |
| `games/cram/cram-font.ttf` | 84,260 | 84,260 | 0 |
| `games/dodgem/dodgem-font.ttf` | 293,572 | 293,572 | 0 |
| `games/domineering/domineering-font.ttf` | 167,876 | 167,876 | 0 |
| `games/dots-and-boxes/dots-and-boxes-font.ttf` | 378,348 | 378,348 | 0 |
| `games/hexapawn/hexapawn-font.ttf` | 124,208 | 124,208 | 0 |
| `games/kayles/kayles-font.ttf` | 464,356 | 464,356 | 0 |
| `games/mu-torere/mu-torere-font.ttf` | 460,588 | 460,588 | 0 |
| `games/nim/nim-font.ttf` | 200,708 | 200,708 | 0 |
| `games/notakto/notakto-font.ttf` | 196,676 | 196,676 | 0 |
| `games/shared/fonts/game-sans/GameSans-Bold.ttf` | 15,872 | 15,872 | 0 |
| `games/shared/fonts/game-sans/GameSans-Regular.ttf` | 15,572 | 15,572 | 0 |
| `games/sim/sim-font.ttf` | 4,677,768 | 4,677,768 | 0 |
| `games/snake-dynamic/snake-dynamic-font.ttf` | 216,432 | 216,432 | 0 |
| `games/snake-fixed/snake-fixed-font.ttf` | 176,064 | 176,064 | 0 |
| `games/text-adventure/text-adventure-font.ttf` | 443,732 | 443,732 | 0 |
| `games/tic-tac-toe/tic-tac-toe-font.ttf` | 139,992 | 139,992 | 0 |
| `games/wythoff/wythoff-font.ttf` | 273,132 | 273,132 | 0 |
| `graphics/first-words/first-words-font.ttf` | 1,587,588 | 1,587,588 | 0 |
| `graphics/first-words/first-words-font.woff2` | 466,460 | 466,460 | 0 |
| `graphics/heraldry/heraldry-font.ttf` | 601,576 | 601,576 | 0 |
| `graphics/heraldry/heraldry-font.woff2` | 182,460 | 182,460 | 0 |
| `graphics/pbm/pbm-font.ttf` | 2,604,848 | 2,604,848 | 0 |
| `graphics/pgm/pgm-font.ttf` | 2,664,752 | 2,664,752 | 0 |
| `graphics/ppm/ppm-font.ttf` | 2,643,020 | 2,643,020 | 0 |
| `graphics/smiles/smiles-font.ttf` | 6,065,592 | 6,065,592 | 0 |
| `graphics/turtle/turtle-font.ttf` | 2,198,656 | 2,198,656 | 0 |
| `languages/mini-basic/mini-basic-font.ttf` | 3,594,292 | 3,594,292 | 0 |
| `languages/ski/ski-font.ttf` | 603,584 | 603,584 | 0 |
| `languages/ski/ski.ttf` | 267,012 | 267,012 | 0 |
| `languages/verilog/playground/assets/adder.ttf` | 5,092 | 5,092 | 0 |
| `languages/verilog/playground/assets/alu.ttf` | 26,160 | 26,160 | 0 |
| `languages/verilog/playground/assets/array_lookup.ttf` | 16,236 | 16,236 | 0 |
| `languages/verilog/playground/assets/bit_routes.ttf` | 7,068 | 7,068 | 0 |
| `languages/verilog/playground/assets/division.ttf` | 41,172 | 41,172 | 0 |
| `languages/verilog/playground/assets/dynamic_routes.ttf` | 18,964 | 18,964 | 0 |
| `languages/verilog/playground/assets/generated_xor.ttf` | 4,040 | 4,040 | 0 |
| `languages/verilog/playground/assets/hierarchical_adder.ttf` | 6,020 | 6,020 | 0 |
| `languages/verilog/playground/assets/multiplier.ttf` | 6,648 | 6,648 | 0 |
| `languages/verilog/playground/assets/parameter_adder.ttf` | 7,424 | 7,424 | 0 |
| `languages/verilog/playground/assets/population_count.ttf` | 6,492 | 6,492 | 0 |
| `languages/verilog/playground/assets/procedural_alu.ttf` | 15,620 | 15,620 | 0 |
| `languages/verilog/playground/assets/signed_math.ttf` | 44,568 | 44,568 | 0 |
| `languages/wasm/playground/assets/add.ttf` | 14,548 | 14,548 | 0 |
| `languages/wasm/playground/assets/branch.ttf` | 33,072 | 33,072 | 0 |
| `languages/wasm/playground/assets/bulk_memory.ttf` | 161,456 | 161,456 | 0 |
| `languages/wasm/playground/assets/c-array.ttf` | 129,600 | 129,600 | 0 |
| `languages/wasm/playground/assets/c-callbacks.ttf` | 863,168 | 863,168 | 0 |
| `languages/wasm/playground/assets/c-mix32.ttf` | 49,636 | 49,636 | 0 |
| `languages/wasm/playground/assets/c-mix64.ttf` | 128,444 | 128,444 | 0 |
| `languages/wasm/playground/assets/c-packet.ttf` | 415,636 | 415,636 | 0 |
| `languages/wasm/playground/assets/c-sparse-array.ttf` | 186,720 | 186,720 | 0 |
| `languages/wasm/playground/assets/c-tail-callbacks.ttf` | 863,288 | 863,288 | 0 |
| `languages/wasm/playground/assets/compose.ttf` | 26,464 | 26,464 | 0 |
| `languages/wasm/playground/assets/compose64.ttf` | 51,264 | 51,264 | 0 |
| `languages/wasm/playground/assets/constant_layout.ttf` | 142,496 | 142,496 | 0 |
| `languages/wasm/playground/assets/count.ttf` | 95,036 | 95,036 | 0 |
| `languages/wasm/playground/assets/divide32.ttf` | 199,300 | 199,300 | 0 |
| `languages/wasm/playground/assets/divide64_constant.ttf` | 112,392 | 112,392 | 0 |
| `languages/wasm/playground/assets/divide64_dynamic.ttf` | 802,852 | 802,852 | 0 |
| `languages/wasm/playground/assets/divide64_dynamic_signed.ttf` | 952,216 | 952,216 | 0 |
| `languages/wasm/playground/assets/divide64_signed.ttf` | 165,156 | 165,156 | 0 |
| `languages/wasm/playground/assets/division_loop64.ttf` | 1,061,108 | 1,061,108 | 0 |
| `languages/wasm/playground/assets/divmul64.ttf` | 1,841,152 | 1,841,152 | 0 |
| `languages/wasm/playground/assets/divmulcount64.ttf` | 2,360,128 | 2,360,128 | 0 |
| `languages/wasm/playground/assets/expensive64.ttf` | 1,596,892 | 1,596,892 | 0 |
| `languages/wasm/playground/assets/four_divs64.ttf` | 3,553,948 | 3,553,948 | 0 |
| `languages/wasm/playground/assets/indexed_memory.ttf` | 127,288 | 127,288 | 0 |
| `languages/wasm/playground/assets/indexed_words.ttf` | 1,079,448 | 1,079,448 | 0 |
| `languages/wasm/playground/assets/indirect64.ttf` | 1,276,440 | 1,276,440 | 0 |
| `languages/wasm/playground/assets/memory_grow.ttf` | 50,232 | 50,232 | 0 |
| `languages/wasm/playground/assets/memory_roundtrip.ttf` | 225,772 | 225,772 | 0 |
| `languages/wasm/playground/assets/multiple_tables.ttf` | 851,080 | 851,080 | 0 |
| `languages/wasm/playground/assets/multiply64.ttf` | 521,116 | 521,116 | 0 |
| `languages/wasm/playground/assets/mutable_dispatch.ttf` | 914,152 | 914,152 | 0 |
| `languages/wasm/playground/assets/nullable_callbacks.ttf` | 825,708 | 825,708 | 0 |
| `languages/wasm/playground/assets/passive_data.ttf` | 91,528 | 91,528 | 0 |
| `languages/wasm/playground/assets/recursive_sum.ttf` | 171,116 | 171,116 | 0 |
| `languages/wasm/playground/assets/reference_flow.ttf` | 916,792 | 916,792 | 0 |
| `languages/wasm/playground/assets/start_memory.ttf` | 66,456 | 66,456 | 0 |
| `languages/wasm/playground/assets/sum_loop.ttf` | 173,912 | 173,912 | 0 |
| `languages/wasm/playground/assets/tail_calls.ttf` | 1,068,000 | 1,068,000 | 0 |
| `languages/wasm/playground/assets/tail_reference64.ttf` | 1,068,724 | 1,068,724 | 0 |
| `languages/wasm/playground/assets/three_divs64.ttf` | 2,262,800 | 2,262,800 | 0 |
| `languages/wasm/playground/assets/typed_callbacks.ttf` | 845,348 | 845,348 | 0 |
| `languages/wasm/playground/assets/typed_dispatch.ttf` | 840,844 | 840,844 | 0 |
| `literature/poem-oracle/poem-oracle.ttf` | 7,638,988 | 7,594,764 | 44,224 |
| `literature/poem-oracle/poem-oracle.woff2` | 1,529,568 | 1,529,568 | 0 |
| `validators/multi-format/validator-font.ttf` | 1,949,264 | 1,949,264 | 0 |

Original baselines, cumulative savings, hashes and per-project results are retained in [font-size-audit.json](font-size-audit.json).
