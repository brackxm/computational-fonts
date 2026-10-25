# Shared font circuits and shaping runtimes

WebAssembly and Verilog compile to the same Boolean circuits and OpenType
glyph-register format. This folder contains their common implementation:

```text
languages/shared/
├── fontcircuit/            # Repository-local Python package
│   ├── gsub/circuit.py    # Boolean wires, operations and font emission
│   ├── gsub/tables.py     # Packed GSUB/GDEF serialization
│   ├── runtime.py         # Input encoding, shaping and output validation
│   └── harfbuzz.py        # System HarfBuzz binding
├── playground/
│   ├── runtime.mjs        # Browser register encoding and validation
│   └── worker.mjs         # HarfBuzz shaping worker used by both playgrounds
├── vendor/harfbuzzjs/      # Pinned browser engine and upstream licenses
└── tests/                 # Shared-package integration checks
```

The language packages expose `languages/shared` on Python's import path when
loaded, so their existing repository-local build and run commands work from any
working directory. Both frontends import `fontcircuit` directly. Standalone
callers can set `PYTHONPATH=languages/shared` from the repository root:

```sh
PYTHONPATH=languages/shared python3 -m fontcircuit.runtime program.ttf 123 77
```

The `wasmfont.runtime`, `wasmfont.harfbuzz` and `wasmfont.gsub` modules forward
existing imports to this package. They contain no separate backend or runtime.
The `wasm-gsub-registers-v1` ABI identifier, generated font names and serialized
font contents retain their existing meanings. Language frontends own source
parsing, lowering, execution bounds and port/function metadata. The shared
runtime serializes inputs and decodes shaped bits without interpreting source.

The GSUB serializer shares identical rule sets, coverages and class definitions
between chained contextual subtables. Headers precede their shared blocks in
bounded offset windows sized by their distinct stored blocks, keeping every
16-bit reference forward and in range. Both write lookups also share one scratch
coverage. Automatic layout selection compares separate and coalesced gate
subtables at each policy's smallest feasible batch size and keeps the smaller
serialized GSUB/GDEF pair. Singleton groups also compare glyph-based and
class-based rules, retaining the smaller encoding. Backtrack class zero is the
implicit wildcard; class one rejects uninitialized operands. Sparse class
definitions choose Format 1 or 2 by their actual size. Compatibility exceptions
retain glyph-based rules.

This reduces font bytes while preserving glyph IDs, gate evaluation order,
operand visibility, truth tables, execution bounds and the ABI. Both language
builders use the same packing pass, including for the bundled playground fonts.

Across the 56 bundled WebAssembly and Verilog fonts, block sharing reduces
the combined size from 106,231,740 to 29,388,232 bytes (72.3%). Examples:

| WebAssembly font | Before (bytes) | After (bytes) | Reduction |
| --- | ---: | ---: | ---: |
| `four_divs64` | 25,096,116 | 3,553,948 | 85.8% |
| `divmul64` | 6,552,468 | 1,841,152 | 71.9% |
| `expensive64` | 4,255,316 | 1,596,892 | 62.5% |
| `three_divs64` | 21,770,276 | 2,262,800 | 89.6% |

Python builds require FontTools; native execution additionally requires the
system HarfBuzz library. Each language documents its dependencies and tests.
The browser worker loads the pinned [HarfBuzzJS runtime](vendor/harfbuzzjs/)
from this folder, with no dependency on either language's folder.

From the repository root:

```sh
python3 -m pytest languages/shared/tests -q
node --test languages/wasm/tests/test_playground.mjs languages/verilog/tests/test_playground.mjs
```
