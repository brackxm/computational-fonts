# Font size audit

Audit date: 2026-10-25. Reviewed all **42 demo projects** and **108 standalone font files**, including seven supporting fonts. **Gardner and its research variant remain excluded and untouched.**

Fonts decreased from **176,597,152 to 89,410,136 bytes**, saving **87,187,016 bytes (49.4%)**. No individual font grew. ODT/ZIP embedded copies are excluded from these totals.

## Optimization rounds

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

## Preservation and validation

All original glyph IDs/names, Unicode mappings, ordered outline points and flags, metrics, hints, overlap/delegated metric controls, color scenes, input bounds and computational behavior are retained. Supporting font files remain byte-identical. Each round checkpoints all 108 files, checks for growth and records hashes and individual validation in [font-size-audit.json](font-size-audit.json).

All 62 applicable hash-bearing manifests and 20 ODT specimens match current fonts. Layout-only changes retain complete logical GSUB data; outline-only changes retain every layout/color payload. Webfont stream recompression retains every decompressed byte, including existing transforms. Unsupported or unprofitable candidates retain their previous encoding.

Earlier completed checks remain recorded in the JSON project validations: all 2,876 poems, 56 language assets and V8 comparisons, language browser checks, image regressions, SKI subtests, complete Connect Four dispatch/priority tables and game histories. Optional Clang/Icarus skips remain unchanged.

- Webfont round: 17 storage tests, 6 Connect Four distribution tests and 8 Chrome pixel comparisons passed. Both smaller WOFF2 streams decode byte-for-byte identically.
- Contour round: 18 storage tests, 158 project checks across 16 projects, 262 SKI subtests and 64 Chrome pixel comparisons passed. Build identity mismatches in SMILES/SKI and Backgammon's missing source opt-in were repaired; the affected checks passed on rerun.
- Final outline round: 18 storage tests, 71 game checks across ten projects, 2 controller tests and 40 Chrome pixel comparisons passed. Exact glyph geometry, metrics, hints and layout/color payloads also match each round's checkpoint.
- These three rounds saved **262,424 additional bytes**. WOFF2 metric-transform trials grew all four webfonts, and further layout trials gave no acceptable improvement, so those candidates were discarded.

## Projects, reviewed one by one

| Project | Files | Before (bytes) | After (bytes) | Saved |
| --- | ---: | ---: | ---: | ---: |
| [decoders/arabizi](decoders/arabizi/) | 1 | 451,000 | 369,844 | 81,156 |
| [decoders/enigma-dynamic](decoders/enigma-dynamic/) | 1 | 838,584 | 805,252 | 33,332 |
| [decoders/enigma-static](decoders/enigma-static/) | 1 | 1,340,852 | 1,332,148 | 8,704 |
| [decoders/lorenz-static](decoders/lorenz-static/) | 1 | 789,732 | 789,732 | 0 |
| [decoders/morse](decoders/morse/) | 1 | 466,396 | 466,396 | 0 |
| [decoders/playfair-static](decoders/playfair-static/) | 1 | 531,604 | 531,604 | 0 |
| [decoders/vigenere-dynamic](decoders/vigenere-dynamic/) | 1 | 742,440 | 642,216 | 100,224 |
| [decoders/vigenere-static](decoders/vigenere-static/) | 1 | 536,396 | 536,396 | 0 |
| [formatters/json](formatters/json/) | 1 | 1,202,772 | 1,202,772 | 0 |
| [formatters/markdown](formatters/markdown/) | 1 | 665,180 | 663,408 | 1,772 |
| [games/achi](games/achi/) | 1 | 499,292 | 369,128 | 130,164 |
| [games/backgammon](games/backgammon/) | 1 | 1,232,224 | 778,144 | 454,080 |
| [games/chomp](games/chomp/) | 1 | 123,256 | 97,280 | 25,976 |
| [games/connect-four](games/connect-four/) | 2 | 6,470,820 | 5,964,128 | 506,692 |
| [games/cram](games/cram/) | 1 | 118,100 | 84,260 | 33,840 |
| [games/dodgem](games/dodgem/) | 1 | 405,392 | 301,612 | 103,780 |
| [games/domineering](games/domineering/) | 1 | 200,916 | 168,388 | 32,528 |
| [games/dots-and-boxes](games/dots-and-boxes/) | 1 | 469,656 | 383,796 | 85,860 |
| [games/hexapawn](games/hexapawn/) | 1 | 147,856 | 130,304 | 17,552 |
| [games/kayles](games/kayles/) | 1 | 519,064 | 465,768 | 53,296 |
| [games/mu-torere](games/mu-torere/) | 1 | 535,348 | 462,752 | 72,596 |
| [games/nim](games/nim/) | 1 | 471,240 | 206,556 | 264,684 |
| [games/notakto](games/notakto/) | 1 | 1,243,792 | 197,592 | 1,046,200 |
| [games/sim](games/sim/) | 1 | 8,565,276 | 4,708,068 | 3,857,208 |
| [games/snake-dynamic](games/snake-dynamic/) | 1 | 281,696 | 216,432 | 65,264 |
| [games/snake-fixed](games/snake-fixed/) | 1 | 202,476 | 176,064 | 26,412 |
| [games/text-adventure](games/text-adventure/) | 1 | 525,152 | 474,964 | 50,188 |
| [games/tic-tac-toe](games/tic-tac-toe/) | 1 | 149,080 | 140,580 | 8,500 |
| [games/wythoff](games/wythoff/) | 1 | 674,032 | 275,912 | 398,120 |
| [graphics/first-words](graphics/first-words/) | 2 | 2,076,620 | 2,054,048 | 22,572 |
| [graphics/heraldry](graphics/heraldry/) | 2 | 917,752 | 784,036 | 133,716 |
| [graphics/pbm](graphics/pbm/) | 1 | 2,992,608 | 2,604,848 | 387,760 |
| [graphics/pgm](graphics/pgm/) | 1 | 3,052,504 | 2,664,752 | 387,752 |
| [graphics/ppm](graphics/ppm/) | 1 | 3,034,524 | 2,643,020 | 391,504 |
| [graphics/smiles](graphics/smiles/) | 1 | 6,606,788 | 6,069,724 | 537,064 |
| [graphics/turtle](graphics/turtle/) | 1 | 2,265,516 | 2,198,656 | 66,860 |
| [languages/mini-basic](languages/mini-basic/) | 1 | 3,594,292 | 3,594,292 | 0 |
| [languages/ski](languages/ski/) | 2 | 1,218,336 | 871,628 | 346,708 |
| [languages/verilog](languages/verilog/) | 13 | 342,796 | 205,504 | 137,292 |
| [languages/wasm](languages/wasm/) | 43 | 105,888,944 | 29,182,728 | 76,706,216 |
| [literature/poem-oracle](literature/poem-oracle/) | 2 | 9,790,688 | 9,211,496 | 579,192 |
| [validators/multi-format](validators/multi-format/) | 1 | 1,981,516 | 1,949,264 | 32,252 |

## Individual fonts

| Font | Before (bytes) | After (bytes) | Saved |
| --- | ---: | ---: | ---: |
| `decoders/arabizi/arabizi-font.ttf` | 451,000 | 369,844 | 81,156 |
| `decoders/arabizi/fonts/NotoNaskhArabic.ttf` | 307,592 | 307,592 | 0 |
| `decoders/enigma-dynamic/enigma-dynamic-font.ttf` | 838,584 | 805,252 | 33,332 |
| `decoders/enigma-static/enigma-static-font.ttf` | 1,340,852 | 1,332,148 | 8,704 |
| `decoders/lorenz-static/lorenz-static-font.ttf` | 789,732 | 789,732 | 0 |
| `decoders/morse/morse-font.ttf` | 466,396 | 466,396 | 0 |
| `decoders/playfair-static/playfair-static-font.ttf` | 531,604 | 531,604 | 0 |
| `decoders/shared/fonts/roboto-2/Roboto-Bold.ttf` | 514,260 | 514,260 | 0 |
| `decoders/shared/fonts/roboto-2/Roboto-BoldItalic.ttf` | 532,860 | 532,860 | 0 |
| `decoders/shared/fonts/roboto-2/Roboto-Italic.ttf` | 533,388 | 533,388 | 0 |
| `decoders/shared/fonts/roboto-2/Roboto-Regular.ttf` | 515,100 | 515,100 | 0 |
| `decoders/vigenere-dynamic/vigenere-dynamic-font.ttf` | 742,440 | 642,216 | 100,224 |
| `decoders/vigenere-static/vigenere-static-font.ttf` | 536,396 | 536,396 | 0 |
| `formatters/json/json-font.ttf` | 1,202,772 | 1,202,772 | 0 |
| `formatters/markdown/markdown-font.ttf` | 665,180 | 663,408 | 1,772 |
| `games/achi/achi-font.ttf` | 499,292 | 369,128 | 130,164 |
| `games/backgammon/backgammon-font.ttf` | 1,232,224 | 778,144 | 454,080 |
| `games/chomp/chomp-font.ttf` | 123,256 | 97,280 | 25,976 |
| `games/connect-four/connect-four-font.ttf` | 5,159,328 | 4,653,232 | 506,096 |
| `games/connect-four/connect-four-font.woff2` | 1,311,492 | 1,310,896 | 596 |
| `games/cram/cram-font.ttf` | 118,100 | 84,260 | 33,840 |
| `games/dodgem/dodgem-font.ttf` | 405,392 | 301,612 | 103,780 |
| `games/domineering/domineering-font.ttf` | 200,916 | 168,388 | 32,528 |
| `games/dots-and-boxes/dots-and-boxes-font.ttf` | 469,656 | 383,796 | 85,860 |
| `games/hexapawn/hexapawn-font.ttf` | 147,856 | 130,304 | 17,552 |
| `games/kayles/kayles-font.ttf` | 519,064 | 465,768 | 53,296 |
| `games/mu-torere/mu-torere-font.ttf` | 535,348 | 462,752 | 72,596 |
| `games/nim/nim-font.ttf` | 471,240 | 206,556 | 264,684 |
| `games/notakto/notakto-font.ttf` | 1,243,792 | 197,592 | 1,046,200 |
| `games/shared/fonts/game-sans/GameSans-Bold.ttf` | 15,872 | 15,872 | 0 |
| `games/shared/fonts/game-sans/GameSans-Regular.ttf` | 15,572 | 15,572 | 0 |
| `games/sim/sim-font.ttf` | 8,565,276 | 4,708,068 | 3,857,208 |
| `games/snake-dynamic/snake-dynamic-font.ttf` | 281,696 | 216,432 | 65,264 |
| `games/snake-fixed/snake-fixed-font.ttf` | 202,476 | 176,064 | 26,412 |
| `games/text-adventure/text-adventure-font.ttf` | 525,152 | 474,964 | 50,188 |
| `games/tic-tac-toe/tic-tac-toe-font.ttf` | 149,080 | 140,580 | 8,500 |
| `games/wythoff/wythoff-font.ttf` | 674,032 | 275,912 | 398,120 |
| `graphics/first-words/first-words-font.ttf` | 1,609,992 | 1,587,588 | 22,404 |
| `graphics/first-words/first-words-font.woff2` | 466,628 | 466,460 | 168 |
| `graphics/heraldry/heraldry-font.ttf` | 734,928 | 601,576 | 133,352 |
| `graphics/heraldry/heraldry-font.woff2` | 182,824 | 182,460 | 364 |
| `graphics/pbm/pbm-font.ttf` | 2,992,608 | 2,604,848 | 387,760 |
| `graphics/pgm/pgm-font.ttf` | 3,052,504 | 2,664,752 | 387,752 |
| `graphics/ppm/ppm-font.ttf` | 3,034,524 | 2,643,020 | 391,504 |
| `graphics/smiles/smiles-font.ttf` | 6,606,788 | 6,069,724 | 537,064 |
| `graphics/turtle/turtle-font.ttf` | 2,265,516 | 2,198,656 | 66,860 |
| `languages/mini-basic/mini-basic-font.ttf` | 3,594,292 | 3,594,292 | 0 |
| `languages/ski/ski-font.ttf` | 882,872 | 604,616 | 278,256 |
| `languages/ski/ski.ttf` | 335,464 | 267,012 | 68,452 |
| `languages/verilog/playground/assets/adder.ttf` | 6,748 | 5,092 | 1,656 |
| `languages/verilog/playground/assets/alu.ttf` | 34,912 | 26,160 | 8,752 |
| `languages/verilog/playground/assets/array_lookup.ttf` | 17,952 | 16,236 | 1,716 |
| `languages/verilog/playground/assets/bit_routes.ttf` | 7,728 | 7,068 | 660 |
| `languages/verilog/playground/assets/division.ttf` | 72,036 | 41,172 | 30,864 |
| `languages/verilog/playground/assets/dynamic_routes.ttf` | 22,444 | 18,964 | 3,480 |
| `languages/verilog/playground/assets/generated_xor.ttf` | 4,252 | 4,040 | 212 |
| `languages/verilog/playground/assets/hierarchical_adder.ttf` | 7,940 | 6,020 | 1,920 |
| `languages/verilog/playground/assets/multiplier.ttf` | 12,508 | 6,648 | 5,860 |
| `languages/verilog/playground/assets/parameter_adder.ttf` | 9,340 | 7,424 | 1,916 |
| `languages/verilog/playground/assets/population_count.ttf` | 8,292 | 6,492 | 1,800 |
| `languages/verilog/playground/assets/procedural_alu.ttf` | 21,868 | 15,620 | 6,248 |
| `languages/verilog/playground/assets/signed_math.ttf` | 116,776 | 44,568 | 72,208 |
| `languages/wasm/playground/assets/add.ttf` | 22,968 | 14,548 | 8,420 |
| `languages/wasm/playground/assets/branch.ttf` | 55,172 | 33,072 | 22,100 |
| `languages/wasm/playground/assets/bulk_memory.ttf` | 241,812 | 161,456 | 80,356 |
| `languages/wasm/playground/assets/c-array.ttf` | 193,420 | 129,600 | 63,820 |
| `languages/wasm/playground/assets/c-callbacks.ttf` | 1,645,468 | 863,168 | 782,300 |
| `languages/wasm/playground/assets/c-mix32.ttf` | 80,900 | 49,636 | 31,264 |
| `languages/wasm/playground/assets/c-mix64.ttf` | 219,696 | 128,444 | 91,252 |
| `languages/wasm/playground/assets/c-packet.ttf` | 692,528 | 415,636 | 276,892 |
| `languages/wasm/playground/assets/c-sparse-array.ttf` | 263,836 | 186,720 | 77,116 |
| `languages/wasm/playground/assets/c-tail-callbacks.ttf` | 1,645,468 | 863,288 | 782,180 |
| `languages/wasm/playground/assets/compose.ttf` | 43,564 | 26,464 | 17,100 |
| `languages/wasm/playground/assets/compose64.ttf` | 86,924 | 51,264 | 35,660 |
| `languages/wasm/playground/assets/constant_layout.ttf` | 186,684 | 142,496 | 44,188 |
| `languages/wasm/playground/assets/count.ttf` | 134,164 | 95,036 | 39,128 |
| `languages/wasm/playground/assets/divide32.ttf` | 385,444 | 199,300 | 186,144 |
| `languages/wasm/playground/assets/divide64_constant.ttf` | 145,168 | 112,392 | 32,776 |
| `languages/wasm/playground/assets/divide64_dynamic.ttf` | 1,565,080 | 802,852 | 762,228 |
| `languages/wasm/playground/assets/divide64_dynamic_signed.ttf` | 1,744,268 | 952,216 | 792,052 |
| `languages/wasm/playground/assets/divide64_signed.ttf` | 221,684 | 165,156 | 56,528 |
| `languages/wasm/playground/assets/division_loop64.ttf` | 2,707,680 | 1,061,108 | 1,646,572 |
| `languages/wasm/playground/assets/divmul64.ttf` | 6,552,468 | 1,841,152 | 4,711,316 |
| `languages/wasm/playground/assets/divmulcount64.ttf` | 11,183,344 | 2,360,128 | 8,823,216 |
| `languages/wasm/playground/assets/expensive64.ttf` | 4,255,316 | 1,596,892 | 2,658,424 |
| `languages/wasm/playground/assets/four_divs64.ttf` | 25,096,116 | 3,553,948 | 21,542,168 |
| `languages/wasm/playground/assets/indexed_memory.ttf` | 177,024 | 127,288 | 49,736 |
| `languages/wasm/playground/assets/indexed_words.ttf` | 2,703,188 | 1,079,448 | 1,623,740 |
| `languages/wasm/playground/assets/indirect64.ttf` | 3,674,088 | 1,276,440 | 2,397,648 |
| `languages/wasm/playground/assets/memory_grow.ttf` | 62,908 | 50,232 | 12,676 |
| `languages/wasm/playground/assets/memory_roundtrip.ttf` | 276,936 | 225,772 | 51,164 |
| `languages/wasm/playground/assets/multiple_tables.ttf` | 1,631,988 | 851,080 | 780,908 |
| `languages/wasm/playground/assets/multiply64.ttf` | 1,799,776 | 521,116 | 1,278,660 |
| `languages/wasm/playground/assets/mutable_dispatch.ttf` | 1,721,688 | 914,152 | 807,536 |
| `languages/wasm/playground/assets/nullable_callbacks.ttf` | 1,596,056 | 825,708 | 770,348 |
| `languages/wasm/playground/assets/passive_data.ttf` | 124,776 | 91,528 | 33,248 |
| `languages/wasm/playground/assets/recursive_sum.ttf` | 254,828 | 171,116 | 83,712 |
| `languages/wasm/playground/assets/reference_flow.ttf` | 1,724,852 | 916,792 | 808,060 |
| `languages/wasm/playground/assets/start_memory.ttf` | 76,312 | 66,456 | 9,856 |
| `languages/wasm/playground/assets/sum_loop.ttf` | 271,244 | 173,912 | 97,332 |
| `languages/wasm/playground/assets/tail_calls.ttf` | 2,706,688 | 1,068,000 | 1,638,688 |
| `languages/wasm/playground/assets/tail_reference64.ttf` | 2,706,448 | 1,068,724 | 1,637,724 |
| `languages/wasm/playground/assets/three_divs64.ttf` | 21,770,276 | 2,262,800 | 19,507,476 |
| `languages/wasm/playground/assets/typed_callbacks.ttf` | 1,623,176 | 845,348 | 777,828 |
| `languages/wasm/playground/assets/typed_dispatch.ttf` | 1,617,520 | 840,844 | 776,676 |
| `literature/poem-oracle/poem-oracle.ttf` | 8,248,064 | 7,681,928 | 566,136 |
| `literature/poem-oracle/poem-oracle.woff2` | 1,542,624 | 1,529,568 | 13,056 |
| `validators/multi-format/validator-font.ttf` | 1,981,516 | 1,949,264 | 32,252 |
