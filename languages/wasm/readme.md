# WebAssembly → native OpenType GSUB

This implementation compiles integer WebAssembly programs into glyph-register
circuits that execute during **one HarfBuzz shaping call**. It now supports
independent intermediate values, locals, internal calls, dynamic selection,
structured branches, bounded loops/recursion, and bounded linear memory.

For example, `(a + b) ^ (a - b)` is **three runtime arithmetic operations in the
font**, not an algebraic reduction to a single primitive or an input/output table.
The `examples/mix.wasm` demonstration was compiled from the accompanying C file
with Clang. Its exported functions have been differentially tested against V8.

This is a bounded integer compiler, **not complete WebAssembly compatibility**.
The scope and resource limits below are part of its execution contract.

## Browser playground

Serve the repository root:

```sh
python3 -m http.server 8000
```

Open <http://localhost:8000/languages/wasm/playground.html>. Twenty-six bundled examples
cover 32/64-bit expressions, wrapping addition, branches, loops, recursion,
memory, division, multiplication, bit counting and compiled C. Change arguments
to run them; decimal, hexadecimal and binary input retain all 64 bits. Results
include unsigned/signed decimal values, hexadecimal and binary registers.
The two constant-division examples return both quotient and remainder for
full-width i64 inputs, including signed division by a negative divisor.
Two dynamic-division examples let you change both full-width i64 arguments.
**Two 64-bit dividers + addition** computes `(a / b) + (c / d)` with four runtime
arguments, independent signed dividers and wrapping addition in one shaping call.
**Two 64-bit divisions → multiplication** feeds two runtime unsigned quotients
into a full-width wrapping multiplier. Both examples accept four arguments.
**Signed divisions → multiply → count bits** composes four runtime operations,
returning the signed-division product and the popcount of its 64-bit result.
**64-bit division → typed loop** produces a full-width quotient/remainder pair,
then carries both values through a loop to compute a checksum.
**Memory fill + overlapping copy** initializes a 16-byte window, fills its upper
half with a runtime byte, then copies a runtime range. The two i64 results expose
every byte; hexadecimal output shows the copy's overlap behavior.
**Passive data → memory** copies a selected range from an embedded data segment.
An optional early drop demonstrates how discarding the segment affects later
initialization, while preserving bytes already written into memory.
**Grow memory in the font** attempts two runtime growth steps, reports their
results and the current page count, and returns a stored i64 value unchanged.
**Choose a 64-bit function at runtime** selects addition, subtraction,
multiplication or division through a function table, then counts the result's
set bits. Extra indices demonstrate signature, null-entry and bounds traps.

The page uses the bundled HarfBuzzJS engine in a Web Worker to shape the actual
font once per invocation. It checks all scratch registers and status flags
before displaying a result. It never executes the example module in the
browser's WebAssembly VM or uses a JavaScript Wasm interpreter. Disabling font
computation produces an incomplete-shaping error. Traps and execution bounds
clear the previous result.

No Python dependencies, Node.js, CDN or compiler service are needed to use the
bundled playground. A modern browser with module workers, BigInt and WebAssembly
is required; use localhost or HTTPS for font-hash verification. Browser inputs
and locally selected files stay in the page. Source is displayed for reference;
to edit a program, compile it locally and select its matching TTF and JSON files
under **Load your own compiled program**. The page checks their SHA-256 pairing.

Rebuild the checked-in example assets after changing the compiler or examples,
using the Python dependencies below and Node.js:

```sh
python3 languages/wasm/build_playground.py
node --test languages/wasm/tests/test_playground.mjs
```

`playground/assets/` contains the generated fonts, ABI manifests, validated source
binaries and catalog. Fonts can also be invoked with `run.py`.
The browser engine's pinned version, licenses and checksums are documented in
[shared HarfBuzz runtime notes](../shared/vendor/harfbuzzjs/readme.md).

## Requirements and quick start

Python 3.10+, FontTools, a system HarfBuzz shared library, and Node.js are required.
Node provides independent binary validation and the differential oracle, not
font execution. No Wasmtime/WABT download or Python Wasm interpreter is needed.
The runtime discovers the system library, including Homebrew on macOS. Install
HarfBuzz with `brew install harfbuzz` on macOS or
`sudo apt install libharfbuzz0b` on Debian/Ubuntu. Make `node` available on `PATH`.

From the repository root:

```sh
python3 -m venv languages/wasm/.venv
. languages/wasm/.venv/bin/activate
cd languages/wasm
python -m pip install -r requirements.txt
python build.py examples/compose.wat --export run -o compose.ttf
python run.py compose.ttf 123 77
# 230: (123 + 77) XOR (123 - 77)

python build.py examples/add.wat --export add -o add.ttf
python run.py add.ttf 4294967295 1
# 0: i32 wrapping addition

python build.py examples/mix.wasm --export run64 -o c-mix64.ttf
python run.py c-mix64.ttf 123 77

python build.py examples/divide64_dynamic.wat --export run -o divide64.ttf
python run.py divide64.ttf 18446744073709551615 4294967297
# (4294967295, 0): quotient and remainder with both arguments supplied at runtime

python build.py examples/expensive64.wat --export run -o expensive64.ttf
python run.py expensive64.ttf 100 3 200 7
# 61: (100 / 3) + (200 / 7), using signed division

python build.py examples/divmul64.wat --export run -o divmul64.ttf
python run.py divmul64.ttf 100 3 200 7
# 924: (100 / 3) * (200 / 7), using unsigned division and wrapping multiplication

python build.py examples/divmulcount64.wat --export run -o divmulcount64.ttf
python run.py divmulcount64.ttf 100 3 200 7
# (924, 6): product and its set-bit count, using signed division

python build.py examples/three_divs64.wat --export run -o three_divs64.ttf
python run.py three_divs64.ttf 100 3 200 7 300 11
# 88: (100 / 3) + (200 / 7) + (300 / 11), using unsigned division

python build.py examples/four_divs64.wat --export run -o four_divs64.ttf
python run.py four_divs64.ttf 100 3 200 7 300 11 400 13
# 118: four independent unsigned quotients, combined with wrapping addition
```

`build.py` and `python -m wasmfont` expose the same native command-line entry point.
Each build writes a font and a matching `.json` ABI manifest. The manifest is
needed by the supplied input/output harness; keep it beside the font. The
machine glyphs are intentionally invisible. This is a glyph-token execution
ABI, not an ordinary decimal-text calculator or a document display font.

All demonstration fonts can be built locally:

```sh
python build_examples.py
python run.py examples/generated/sum_loop.ttf 6
# 21
python run.py examples/generated/memory_roundtrip.ttf 3 2309737967
# 2309737967
```

`python build_examples.py --recompile-c` additionally rebuilds the C source. It
requires Clang with a wasm32 target and `wasm-ld`; Apple's system Clang does not
provide this target. Without that option, the build uses the supplied,
Clang-produced `examples/mix.wasm`.

## Execution architecture

```text
WAT ── parse / resolve names ── binary encoding ──┐
                                              ├─ V8 validation
binary Wasm ───────────────────────────────────┘
           ↓
integer module + structured stack-machine instructions
           ↓
typed symbolic lowering / call inlining / bounded control-flow expansion
           ↓
immutable SSA bit registers + Boolean gates + trap and bound signals
           ↓
constant propagation / common-subexpression reuse / dead-wire elimination
           ↓
GSUB chained contextual substitutions + GDEF mark-filtering sets
           ↓
one HarfBuzz shaping call
           ↓
canonical output registers + status registers
```

A register bit has a fixed glyph-tape position. Argument cells are initialized
with input bits, constant cells with compiler-known bits, and scratch cells
with an **uninitialized** glyph. Gates read at most four dynamic bits and have
at most sixteen local truth-table rows before layout packing. A full-adder's
sum and carry can share a lookup because they read the same sources.

All register glyphs are GDEF marks. A lookup's mark-filtering set exposes its
source and destination cells, allowing it to read nonadjacent registers without
consuming or modifying operands. GSUB type-6 chained contexts call two shared
type-1 write lookups. Larger circuits pack several gate groups into one lookup:
Format 2 backtrack classes check each gate's own sources and accept any state
of unrelated cells exposed by the batch using one common wildcard class.
Sparse operand overrides keep class tables small even in wide batches.
Gates still execute in tape order, so
dependencies within a batch are written before use. Type-7 extension wrappers
and lookup headers are placed in two waves to keep both Offset16 levels in range.
Truth rules inspect newest operands first and stop once their result is fixed.
Each rule's context ends at its oldest required operand, omitting older inputs
and unrelated cells before it. The resulting rules partition the truth table;
this changes serialization without adding registers or runtime arithmetic.

If separate gate subtables cannot fit the lookup-offset windows, a second
packing tier lets two adjacent gate groups share one Format 2 subtable and
extension wrapper. Each destination keeps its own input class and truth rules.
The shared backtrack class map distinguishes both groups' operands; rules
enumerate intervening operands from the other group as don't-care bits.
At most three extra bits may be enumerated, and a conservative 60,000-byte
subtable bound preserves its internal Offset16 fields. All earlier operand
registers must be initialized. Existing layouts that fit retain separate
subtables; the coverage-cache singleton exceptions also remain separate.

Groups whose destination glyph IDs fall in `0x7f00..0x7fff` use singleton
Format 1 lookups. This avoids a false empty-cache hit in HarfBuzz 14.2.1's
Format 2 coverage cache. Every scratch register is still checked by the runtime;
the workaround changes only font layout and needs no host arithmetic or engine patch.

Multiplication fuses each partial-product mask into four-input conditional
sum/carry gates, retaining only the low result-width bits. This removes the
separate AND register for each partial product and bypasses already completed
low bits in later rows. The bundled i64 multiplier drops from 6,120 to 4,104 live
gates and from 18,620 to 12,572 glyphs. Its larger local truth tables increase
the standalone font from about 1.37 MB to 1.80 MB; the gain is fewer registers
and lookups, allowing more operations to fit under the glyph-count limit.

The compiler materializes results into **new, consecutive output cells using
GSUB copy operations**. Even identity, constant, conversion and constant-shift
results are written to these cells in the font; the decoder does not perform
an instruction-specific bit permutation or choose a source parameter.

### What the host does—and does not do

The compiler resolves instruction order, types, labels, constant expressions,
call expansion and configured execution bounds. It never receives invocation
arguments. The runtime encoder serializes arguments to their low 32/64 bits and
initializes the fixed tape. It does not evaluate Wasm operations or branches.
Before shaping, the native runtime validates the ABI manifest's types, result
widths and wire references, then verifies its glyph order and character mapping
against the font. The font must also match the manifest's SHA-256 digest.

The harness calls HarfBuzz once, checks that **every live scratch cell was
initialized**, checks the font-produced status bits, then packs the canonical
output bits into Python integers. There is no Python execution between GSUB
stages and no call to the legacy interpreter. Disabling `calt` is tested to
produce `IncompleteShaping`, rather than a plausible zero or a host result.

## Native instruction support

| Area | Native implementation and qualifications |
| --- | --- |
| Integer values | `i32`, `i64`, constants, zero-initialized locals, parameters and multiple function return values |
| Arithmetic | Wrapping `add`, `sub`; full dynamic `mul` at both widths |
| Division | Full-width dynamic `i32`/`i64` `div_u`, `div_s`, `rem_u`, `rem_s`; constant divisors retain smaller specialized circuits. Zero divisors trap; signed `MIN / -1` traps, while `MIN % -1` is zero. |
| Bitwise operations | `and`, `or`, `xor` |
| Shifts / rotations | Dynamic and constant `shl`, `shr_s`, `shr_u`, `rotl`, `rotr`; low five/six count bits select the distance |
| Comparisons | `eqz`, `eq`, `ne`, and all signed/unsigned `lt`, `le`, `gt`, `ge`; i32 Boolean results can feed later operations |
| Counting | `clz`, `ctz`, `popcnt`; results are binary registers, not host-counted unary glyphs |
| Conversions | `i32.wrap_i64`, signed/unsigned `i64.extend_i32`, and integer sign-extension instructions |
| Stack / locals | `local.get`, `local.set`, `local.tee`, `drop`, untyped integer `select`, `nop` |
| Calls | Multiple internal functions, direct `call`, table-based `call_indirect`, `return`, fresh locals per call and bounded recursion; no host imports |
| Function tables | One immutable `funcref` table, up to 256 slots, active function-index element segments, table exports, null entries and structural integer-signature checks |
| Control flow | `block`, `loop`, `if` / `else`, `br`, `br_if`, `br_table`; integer parameters and multiple i32/i64 results, including type-index block signatures and loop backedge parameters |
| Memory | `i32`/`i64` loads/stores and narrow signed/unsigned variants, little-endian encoding, unaligned access, offsets, active data segments; `memory.copy` and `memory.fill` with dynamic addresses and lengths within the configured backed window |
| Data segments | Passive byte strings, `memory.init` with dynamic source/destination/length, and `data.drop`; segment lifetime follows branches, loops and internal calls |
| Memory growth | `memory.size` and `memory.grow`; dynamic page counts, old-size/−1 results, and bounds that follow growth through branches, loops and calls |
| Globals | Integer globals with constant initializers, `global.get`, mutable `global.set`; values persist within an invocation, including through calls |
| Traps | `unreachable`, integer divide-by-zero, i32/i64 signed division overflow, actual memory/data-segment bounds, and indirect-call table bounds/null/signature errors |

Unsupported instructions/module forms are rejected. Some otherwise supported
programs also exceed the configured circuit or font-layout capacity. A resource
rejection must not be interpreted as a successful compilation.

### WAT and binary modules

The new text frontend accepts flat and folded integer expressions, nested block
comments (including line comments adjacent to tokens), named
functions/locals/globals/labels, grouped unnamed parameters,
exports, function and block type uses, one memory, integer globals, active
constant-offset data segments, passive data segments, one function table and
active function-index element segments. Names and data-string escapes are resolved by
the frontend; integer literals are checked against their declared width,
including global initializers and data offsets. The resulting binary is
independently validated by V8.
Active data segments require a declared memory and exactly one integer
immediate in their constant offset expression.
Passive data strings require no memory declaration. Data-segment names and
numeric indices are supported by `memory.init` and `data.drop`.
Numeric type indices must be unsigned 32-bit values and refer to a declared
function type.
Export declarations must have exactly the required operands, and each function
may contain only one type-use clause. Multiple inline exports remain supported.
Inline and standalone exports preserve module-field order, including default
entry-function selection. Quoted strings are accepted only as names or data;
keywords, identifiers, types and numeric operands must be unquoted. Function
headers require exports, an optional type use, parameters, results and locals
in that order, followed by instructions. Block signatures accept an optional
type use followed by unnamed parameter and result declarations in that order;
inline declarations must match an explicit type use.

Both the frontend and direct `load_binary` entry point validate the original
bytes before loading them. Imports, start functions and exception tags are
explicitly rejected instead of being silently ignored. Tables support active
function-index elements with constant i32 offsets; passive/declarative elements
and reference-expression elements are rejected. `table.*`, `elem.drop`, and
reference-valued operand-stack instructions are not implemented.
Data-count sections are supported in their specified position before code;
V8 validates their counts and all referenced data indices. Extended load/store
operands with an explicit memory index are rejected, including an explicit index
of zero. Bulk-memory binaries accept memory index zero.
Floating-point and SIMD values, reference values on the operand stack, and
non-integer function signatures are not accepted. This is not an unrestricted
implementation of the WAT grammar.

### Function tables and indirect calls

Declare a table with `(table $ops 6 funcref)` and initialize slots using an
active segment such as `(elem (i32.const 0) $add $subtract)`. Slots start null;
later segments overwrite earlier entries. Active initialization must fit the
table, including empty segments. The compiler rejects invalid initialization
before writing a font. Minimum and optional maximum table limits are 0–256.
The table remains fixed throughout an invocation.

`call_indirect $ops (type $binary)` takes its i32 slot index from the top of the
stack, above the callee's arguments. The table name/index can be omitted for
table zero. Named/numeric type uses and unnamed inline integer `(param ...)` / `(result
...)` signatures are supported, including mixed widths and multiple results.
An omitted signature means no parameters or results. Function signatures match
structurally, so equivalent declared type indices are compatible.

An out-of-range unsigned index reports `WasmTrap('table_out_of_bounds')`; a null
slot reports `uninitialized_element`; a different signature reports
`indirect_call_type_mismatch`. These checks precede call-depth accounting.
Only the selected function's traps and side effects apply. Memory, globals,
page counts and segment availability pass through the call. Recursive indirect
calls use the existing call-depth bound. Repeated slots targeting the same
function share one compiled callee per indirect-call instruction.

The [64-bit dispatch example](examples/indirect64.wat) uses slots 0–3 for addition,
subtraction, multiplication and unsigned division. It returns the selected result
and its set-bit count. Slot 4 has a different signature, slot 5 is null, and slot
6 or greater is out of bounds. Division by zero traps only when slot 3 is selected.

```sh
python build.py examples/indirect64.wat --export run -o indirect64.ttf
python run.py indirect64.ttf 100 7 3
# (14, 3): unsigned quotient and its set-bit count
python run.py indirect64.ttf 100 7 2
# (700, 6): product and its set-bit count
```

Dispatch and signature checks follow WebAssembly's
[indirect-call semantics](https://www.w3.org/TR/wasm-core-1/).

### Multi-value structured control flow

`block`, `loop` and `if` accept integer signatures such as
`(param i32 i64) (result i64 i64)`, or a named/numeric `(type ...)` use.
A branch to a block or `if` carries its result values. A branch back to a loop
carries its parameter values into the next iteration. Parameters and results
can have different counts and widths. The stack below the control frame is
preserved; branch temporaries are discarded. The reference interpreter and
native compiler use the same resolved signatures.

The [typed-loop example](examples/division_loop64.wat) computes unsigned
quotient `q = a / b` and remainder `r = a % b` in a multi-value block. Its loop
carries `(rounds remaining, checksum, remainder)` and updates the checksum by
adding the remainder, then incrementing the remainder, each round. The two
results are `q + n*r + n*(n-1)/2` and `r + n`, with i64 wrapping. Division and
all loop arithmetic execute in the font. A zero divisor traps even for zero
rounds. The default loop bound accepts `n = 0..7`; `n = 8` reports a bound.

```sh
python build.py examples/division_loop64.wat --export run -o division-loop.ttf
python run.py division-loop.ttf 100 7 3
# (23, 5): checksum and remainder plus rounds
```

The implementation follows WebAssembly's [structured control semantics](https://webassembly.github.io/spec/core/exec/instructions.html#control-instructions)
and [text block signatures](https://webassembly.github.io/spec/core/text/instructions.html#control-instructions).
Floating-point/reference signatures and named block-parameter bindings remain
unsupported. Integer block types in binaries use signed LEB128 type indices.

### Bulk memory

`memory.copy` takes destination, source and byte count; overlapping ranges use
the original source bytes, like `memmove`. `memory.fill` takes destination,
fill value and byte count, repeating the low eight bits of the fill value.
Both accept flat or folded WAT syntax and binary instructions for memory zero.
The copy circuit aligns a snapshot with a barrel rotation, so its mux count
grows with `window * log2(window)` instead of enumerating every address pair.
These operations execute in the same shaping call as surrounding instructions.

Both complete ranges are checked against the declared Wasm memory before any
writes. Endpoint addition does not wrap at 32 bits. An empty range may start
at the declared memory's end, but not past it. Empty ranges require no backed
bytes, so a valid zero-length operation beyond the configured window succeeds.
Nonempty ranges inside Wasm memory but outside the backed window report the
memory execution bound. The gate, glyph and lookup limits still apply.

The [bulk-memory example](examples/bulk_memory.wat) stores a seed in bytes 0–7,
fills bytes 8–15, copies the chosen range, and returns both little-endian halves:

```sh
python build.py examples/bulk_memory.wat --export run -o bulk-memory.ttf
python run.py bulk-memory.ttf 0x0807060504030201 2 0 8 0xaa
# (433757350076154369, 12297829382472992775)
# Hexadecimal: (0x0605040302010201, 0xaaaaaaaaaaaa0807)
```

Range checks and overlap behavior follow the WebAssembly
[bulk-memory semantics](https://github.com/WebAssembly/spec/blob/main/proposals/bulk-memory-operations/Overview.md).

### Passive data and initialization

`(data $bytes "ABC")` declares a passive segment. `memory.init $bytes` copies a
runtime range from it into memory, taking destination, source offset and length
from the stack. The source range is checked against the segment, including
when length is zero. Source bytes may lie beyond the backed memory window:
only the destination consumes backed bytes. Large segments or dynamic lookups
can still exceed circuit or font capacity. Constant addresses only materialize
the bytes needed in the window.

`data.drop $bytes` empties that segment for the rest of the invocation and may
be repeated. Existing memory contents survive the drop. An empty segment permits
only source offset zero with length zero; the destination must still be a valid
empty memory range. Active segments are copied into memory during instantiation
and are already dropped when the entry function starts. Dropping one again is
valid. Segment availability is merged across control flow and passed through
internal calls. Each shaping invocation starts with fresh passive segments.

The [passive-data example](examples/passive_data.wat) embeds bytes 1–16 and
returns the two little-endian halves of memory after initialization:

```sh
python build.py examples/passive_data.wat --export run -o passive-data.ttf
python run.py passive-data.ttf 0 4 8 0
# (867798387104613893, 0): bytes 5–12 copied into memory
# Hexadecimal: (0x0c0b0a0908070605, 0x0000000000000000)
python run.py passive-data.ttf 0 0 1 1
# WasmTrap: memory_out_of_bounds (segment dropped before initialization)
```

### Memory growth

`memory.grow` takes an unsigned i32 page delta. Successful growth returns the
previous page count; failure returns `0xffffffff` (signed −1) and preserves the
current size. `memory.size` reports the current count. A 33-bit sum checks the
growth limit before retaining the new page count, so large deltas cannot wrap
into a successful request. Page counts follow branches, loops and calls, and
all loads, stores and bulk-memory operations use the updated size.

Growth succeeds up to the loader's effective maximum. Explicit memory limits
remain capped at 256 pages. When the maximum is omitted, the existing loader
and text-frontend policy uses `max(16, minimum)` as the growth cap. Failure is
an ordinary Wasm result; it does not set a trap or execution-bound status.
This is a deterministic embedding policy within WebAssembly's permitted
[memory-growth behavior](https://www.w3.org/TR/wasm-core/).

Newly accessible bytes in the backed window are zeroed. Existing bytes and data
segment availability survive growth. The backed window remains at the configured
size: growing to more pages does not add font registers for those pages. An access
inside the current Wasm memory but outside that window still reports the memory
execution bound. Each shaping call starts again at the declared initial size.

The [growth example](examples/memory_grow.wat) starts at one page with a maximum
of three, stores a value, then attempts two growth steps:

```sh
python build.py examples/memory_grow.wat --export run -o memory-grow.ttf
python run.py memory-grow.ttf 1 2 42
# (1, 4294967295, 2, 42): first growth succeeds, second fails, data survives
python run.py memory-grow.ttf 1 1 42
# (1, 2, 3, 42): both growth steps succeed
```

## Bounds and semantic guarantees

Defaults are eight loop-body executions per loop, eight active call frames
including the entry call, a 16-byte backed memory window starting at address
zero, and a 24,000-gate construction budget. Configure them with:

```sh
python build.py program.wasm --export run -o program.ttf \
  --loop-bound 12 --call-depth 8 --memory-bytes 64 --max-gates 10000
```

CLI limits are 1–64 loop iterations, 1–32 call frames, 0–256 backed memory bytes,
and 1–32,000 constructed gates. Serialization chooses the smallest batch size
from 1–64 gate groups that fits the lookup headers and extension offsets.
If none fits, it tries those batch sizes with bounded subtable coalescing.
It rejects layouts that cannot fit. Every source/constant/result/trap cell also
counts toward the OpenType glyph limit of fewer than 65,535 glyphs. Constructed
gates can be pruned before emission, so the construction budget is not a promise
that every circuit of that size fits. Capacity remains program-dependent.

The previous default was 12,000 gates with approximately 5,400 unbatched gate
groups. Packing and smaller arithmetic circuits now support these full-width
runtime compositions, without increasing the current construction or glyph caps:

| Bundled composition | Live gates | Glyphs | Physical lookups | Font size |
| --- | ---: | ---: | ---: | ---: |
| Two signed divisions + addition | 10,174 | 31,038 | 3,206 | 4.3 MB |
| Two unsigned divisions → multiplication | 12,549 | 38,163 | 2,131 | 6.6 MB |
| Two signed divisions → multiplication → popcount | 14,927 | 45,297 | 972 | 11.2 MB |
| Three unsigned divisions + addition | 12,995 | 39,757 | 395 | 21.8 MB |
| Four unsigned divisions + addition | 17,347 | 53,069 | 4,293 | 25.1 MB |

The four-operation example previously exceeded the glyph limit; compact truth
rules now reduce its font from 17.6 MB to 11.2 MB. The three-divider example's
12,677 gate groups exceeded the previous maximum batch size of sixteen. It now
fits with batches of up to forty-one groups, keeping both levels of Offset16
within range. Larger batches reduce header overhead but add backtrack context,
so gate count, lookup count and file size need not move together. Playground
uploads accept fonts up to 32 MiB and manifests up to 10 MiB.
Four independent dynamic dividers exceed the separate-wrapper capacity even
with batches of sixty-four groups. Coalescing reduces their 16,903 gate groups
to 8,779 gate subtables, fitting with batches of four groups. The playground's
eight-argument example computes 118 from `(100/3)+(200/7)+(300/11)+(400/13)`;
each division truncates and any zero divisor traps.
Chained division/remainder and conditional compositions are also tested.
Larger programs can still hit gate, glyph or offset limits; composition remains
bounded. Expensive fonts can take seconds to shape; the browser runs them in a
worker to keep the page responsive.

**Loops are not native OpenType jumps.** Their bodies are expanded a bounded
number of times. Runtime predicates determine the taken path, register merges,
and exits. A still-active backedge after the last expansion sets `limit.loop`.
An attempted call beyond the configured depth sets `limit.call`. Neither is a
WebAssembly trap or a valid result: the decoder raises `ExecutionBoundExceeded`.
For example, the sum-loop example with bound eight succeeds for `n = 0..7`;
`n = 8` requires a ninth body entry to take the exit test and reports a bound.

**The memory window is not a smaller Wasm memory.** `memory.size` returns the
current number of 64-KiB pages. An address outside the current memory produces
`WasmTrap('memory_out_of_bounds')`. An address inside that memory but outside the
backed window produces `ExecutionBoundExceeded('memory')`. Effective address
addition with an instruction offset is checked without i32 wrapping. Memory
page declarations are currently capped at 256 pages by the module loader.

Each shaping call starts a fresh module instance. Memory/globals persist across
instructions and internal calls, but **not across separate shaping calls**.
WASI, imported functions, shared memory, threads, atomics, and host I/O are not
implemented. Native growth and memory operations execute in the font; the
reference interpreter is only used for independent comparisons.

## Validation

```sh
python -m pytest -q
python -m pytest -q tests/test_compiler.py
node --test tests/test_playground.mjs
python benchmark.py --repeats 20 --output benchmarks/latest.json
```

The current tests cover independent multi-instruction expressions, arbitrary
32/64-bit operands, signed boundaries, dynamic shifts/count masking, binary
conversion results, multi-result calls, branching/stack unwinding, `br_table`,
loop and call bounds, mutable state, narrow loads/stores, memory offset overflow,
conditional traps, malformed modules and font/manifest errors.
Bulk-memory regressions check every valid source/destination/length combination
in the default 16-byte window, overlapping copies, low-byte fills, 33-bit
endpoint overflow, zero-length ranges, windows up to 256 bytes, and composition
through internal calls and bounded loops. Each successful case compares the
actual shaped font with V8 and the reference interpreter.
Passive-data regressions also cover active segments being dropped at startup,
conditional and repeated drops, source ranges beyond the backed window,
call/return and loop lifetime merges, fresh invocations, data-count ordering,
multi-byte indices, and malformed declarations/instructions. Constant-address
and zero-window cases retain small circuits even with large data segments.
Growth regressions cover unsigned deltas, limits and overflow, failed-growth
recovery, zero-filled bytes, preserved memory/data segments, fresh invocations,
page-count merges through calls and loops, and dynamic bounds for all integer
loads/stores and bulk operations. Binary tests include padded zero memory indices.
Indirect-call regressions cover dynamic targets, equivalent type aliases,
multi-value arguments/results, active-element overlays, null/bounds/type traps,
inactive calls, side effects, loop-carried results, recursion and call-depth
precedence. A 256-slot table sharing one dynamic i64 divider checks that aliases
do not duplicate the expensive circuit. Independent binaries cover unsigned type
indices through 128, padded table operands and element encodings with an explicit
table index of zero. Unsupported table/element forms fail closed.

Reduced four-bit circuits are exhaustively checked across all 256 operand pairs
for 13 operations. Addition, subtraction and multiplication also run all 256
pairs through actual HarfBuzz shaping. Complete 32/64-bit Wasm programs are
compared with V8, including both exports from the Clang-produced example.
The C source is recompiled in a separate test when Clang has a wasm32 target
and `wasm-ld` is available. Otherwise only that optional test is skipped;
the supplied C-produced binary is always tested.

Run this suite independently from the other projects, whose test modules use
their own imports and build entry points. From the repository root the command
is `python -m pytest -q languages/wasm`.
Browser-engine tests compare all twenty-six bundled programs with V8. Capacity regressions cover
packed truth tables, interleaved paired outputs, two independent signed i64
dividers, division/multiplication, two multipliers, chained division/remainder,
and two quotients feeding a multiplier on both active and inactive branches.
The four-operation signed example also checks popcount, wrapping, traps in
either divider and inactive branches. A separate circuit test checks divisor
bit-length boundaries across all 64 bit positions within a 4,500-gate budget.
The three-divider regression checks full-width inputs, wrapping and all three
zero-divisor traps, and confirms the same circuit fails with the old maximum
batch size. Exhaustive truth-rule partitions and full sixty-four-group batches
are checked separately, including four-input gates with paired outputs.
The four-divider example also checks wrapping, all four zero-divisor traps,
disabled shaping and active/inactive branches against V8. The same circuits
fail without subtable coalescing. Reduced dividers and mixed four-input truth
tables run exhaustively through HarfBuzz with coalescing enabled and disabled,
including full sixty-four-group batches and noncontiguous paired outputs.
Gate, glyph and offset-limit failures and disabled shaping are checked too.
Review regressions check explicit-memory operand rejection and integer-literal
bounds, plus reference-interpreter counting instructions, branches across
`if`/`else`, and stack unwinding for loops, function labels and returns.
Execution cases compare the reference interpreter and native fonts with V8,
including returns with zero or multiple results.
Legacy compilation also checks original binary validation and unsupported
module rejection. Data declarations are checked before encoding, and legacy
reference returns are compared with V8 for zero, one and multiple results.
Validation-boundary regressions cover malformed native ABI manifests, font
glyph-order/cmap mismatches, direct module loading and numeric type-index bounds.
Native manifest checks preserve generic integer circuit widths, including the
reduced-width circuits used in exhaustive tests.
Command-line regressions cover both the script entry points and package module
execution using the relocated examples.
Text-frontend regressions cover attached line comments with LF, CR and CRLF
endings, comment delimiters inside strings, malformed declarations, duplicate
type uses and valid multiple exports. Additional regressions verify export
order across inline and standalone declarations, duplicate export rejection,
quoted token rejection, function-declaration phases, Unicode export names,
raw data bytes and implicit type-use parameters with named locals.
Multi-value control regressions cover mixed-width block inputs/results,
conditional and table branches, stack unwinding, loop backedge merges, calls,
traps, iteration bounds and malformed signatures. Binary tests independently
construct type indices 0, 63, 64, 127 and 128 to verify signed index encoding.
The new division-to-loop example is checked against V8 in Python and the
browser, including bounds, divide-by-zero, disabled shaping and recovery.
The expensive-operation playground examples were checked for successful
results, divide-by-zero or signed-overflow traps, disabled computation and recovery. Native shaping used
HarfBuzz 14.2.1; the browser used the bundled HarfBuzz 14.6.0 engine.

The uploaded validation and benchmark reports are historical evidence from the
ChatGPT handoff; they are not results from the current checkout. See
[handoff provenance](history/readme.md).

## Performance

The uploaded `benchmarks/latest.json` records the environment, exact inputs, verified outputs,
font size, live wires, gates, lookups, compile time, HarfBuzz-only median time,
and end-to-end median/p95 latency. Twenty repetitions follow three warmups.
These are local observations with a cached font face, not cross-platform speed
or browser compatibility guarantees. Large division/multiplication circuits
are much more expensive than simple compositions.

See `benchmarks/README.md` for the measured summary.

## Source layout and repository integration

```text
languages/wasm/
├── build.py, run.py                 # Compile programs and invoke fonts
├── build_examples.py               # Rebuild local demonstration fonts
├── build_playground.py             # Rebuild the bundled browser assets
├── benchmark.py                    # Run reproducible native benchmarks
├── wasmfont/                       # Python package
│   ├── compiler.py                 # Structured instructions → bit circuits
│   ├── frontend.py, module.py       # WAT encoding and binary module loading
│   ├── validation.py               # Shared V8 validation and section policy
│   ├── ir.py, opcodes.py            # Integer instructions and function IR
│   ├── conversions.py, state.py     # Integer conversions and module state
│   ├── runtime.py, harfbuzz.py      # Compatibility imports for shared runtime
│   ├── oracle.py, oracle.js         # Independent V8 differential oracle
│   ├── gsub/                       # Compatibility imports for shared backend
│   └── reference/                  # Primitive backends and reference VM
├── tests/                          # Python regressions and browser-engine tests
├── examples/                       # WAT, C and the supplied C-produced Wasm
├── playground/                     # Browser controls
│   └── assets/                     # Bundled fonts, manifests and modules
├── playground.html                 # Stable gallery entry point
├── benchmarks/                     # Historical reports
└── history/                        # Original handoff provenance
```

The Boolean-circuit backend, Python shaping runtime, browser runtime/worker and
pinned HarfBuzzJS engine live in [`languages/shared`](../shared/). Both Wasm and
Verilog use that implementation directly.

Python callers import `compile_source` from `wasmfont.compiler` and `NativeFont`
from `fontcircuit.runtime`. Import `wasmfont` first when working from
`languages/wasm/` so its package initialization exposes the repository-local
shared package. Existing `wasmfont.runtime`, `wasmfont.harfbuzz` and
`wasmfont.gsub` imports remain available as forwarding modules, including
`python -m wasmfont.runtime`.

The original primitive compiler, encoders, symbolic lowering and Python reference
VM remain under `wasmfont.reference` for regression testing. The reference
`compile_module` entry point uses the same validated module loader as native
compilation.
[The legacy history](history/LEGACY_HISTORY.md) preserves the old
append-only notes; its historical limitations are not a current support matrix.

This project lives under `languages/wasm/` and is listed in the root project
table. The browser playground bundles compiled examples in `playground/assets/`;
other generated fonts and demo-build reports stay local. The source tree includes
their builders and the C-produced Wasm input. Register glyphs have no display
outlines, so this project has no editable ODT specimen. Use the playground or
`run.py` to encode arguments, execute the font and read its output.
The [handoff history](history/readme.md) retains
the original integration notes and source manifest.

## Further compatibility investigation

Tables and `call_indirect` would require bounded table storage, runtime index
and null checks, signature checks, and predicated calls to all possible internal
targets. The register/control-flow machinery provides building blocks, but this
is not implemented or validated yet. Table sections currently fail closed.

Floating-point support would need actual IEEE-754 bit circuits, including
rounding, NaN behavior and conversion traps. Integer bit operations alone are
not evidence of floating-point compatibility. Those instructions are rejected.

### Full-width dynamic 64-bit division

Dynamic divisors use a restoring divider whose remainder grows one bit per
dividend bit. After processing k dividend bits, only k remainder bits are needed.
Suffix-OR gates detect any divisor bits above that width: such a divisor cannot
be subtracted. A borrow chain determines whether subtraction succeeds, and
four-input gates directly select the difference or unchanged remainder. No
separate difference register or mux register is needed. The quotient decision
and top remainder bit share their four sources and can share a lookup.

The previous non-restoring design used a signed 65-bit partial remainder at
every step. The new dynamic unsigned quotient/remainder example drops from
8,650 to **4,423 live gates**, and the signed example from 9,602 to **5,377**.
The same construction applies to i32. Constant divisors keep their narrower
restoring or power-of-two specializations.

Signed operations divide unsigned magnitudes and restore signs inside GSUB.
Division truncates toward zero; the remainder keeps the dividend's sign.
Both widths retain zero-divisor traps. Signed `MIN / -1` reports overflow;
signed `MIN % -1` returns zero without an overflow trap. No runtime division or
operand-dependent instruction execution is delegated to Python or JavaScript.

`tests/test_dynamic_i64_division.py` exhausts reduced-width inputs in both the circuit
oracle and actual HarfBuzz, compares all four full-width operators with V8,
checks four-input lookup packing, and covers composition and conditional traps.

### Constant-divisor remainder bounds

For any known nonzero divisor `d`, a completed restoring-division step has
`0 <= remainder < d`. The compiler keeps only `d.bit_length()` remainder bits,
plus one temporary bit for the next shift. This reduces division circuitry for
small constants while preserving all 32/64 dividend bits. It covers non-power-of-two
divisors such as 3, 7, 10, 255 and 1000, including negative signed divisors.
Signed division still truncates toward zero; signed remainder retains the
dividend's sign. Zero and `MIN / -1` traps remain in the Wasm lowering layer.

The compiler inspects only the divisor's constant wires, never runtime inputs.
Every quotient and remainder is materialized into new output registers by GSUB.
Large constants and dynamic dividers remain subject to the existing
gate, glyph and layout limits. `tests/test_constant_divisor.py` exhausts reduced-width
inputs, compares full-width results with V8 through actual HarfBuzz shaping,
and checks division by zero and constants near signed boundaries.

### Constant power-of-two division specialization (October 2026)

Native `i32`/`i64` `div_u`, `rem_u`, `div_s`, and `rem_s` by nonzero
power-of-two literals now compile to bit-routing circuits, with signed
magnitude and sign restoration. This avoids the expensive general restoring
network for this subset, including negative signed power-of-two divisors.
The signed `MIN / -1` overflow trap is retained; dynamic divisors continue
through the general divider, subject to the gate/lookup resource limits.
See `tests/test_native_const_division.py` for HarfBuzz versus V8 differential tests.

### Signed power-of-two division optimization

Native `i32`/`i64` signed division by constant positive or negative powers of
two uses sign-dependent bias followed by an arithmetic shift. Signed remainder
is recovered by subtracting the truncated quotient multiplied by the positive
divisor. This reduces conditional-negation circuitry while retaining runtime
arithmetic in the font. `tests/test_native_const_division.py` includes randomized
differential cases and signed-boundary checks.

### Zero-extended dynamic division specialization (October 2026)

The GSUB circuit builder detects structurally known-zero high bits in both
unsigned division operands and emits only the necessary lower-width
divider, padding the quotient and remainder back to the original Wasm width.
This enables dynamic `i64.div_u`/`i64.rem_u` of two `i64.extend_i32_u` values
without a full 64-bit divider. No runtime inputs are examined at compile time.
The native HarfBuzz regression is `tests/test_division_narrowing.py`. Full-width
dynamic operands use the growing-width restoring divider above.

### Division wire-identity optimization (October 2026)

The native Boolean-circuit divider recognizes three structural identities:
`x / 1`, `0 / x`, and `x / x` (and their unsigned remainders). These
specializations inspect only wire identity or compile-time constants, never
runtime argument values. The Wasm lowering layer still guards zero divisors,
so `0 / 0` and `x / x` with x=0 correctly trap. No whole-program input/output
enumeration is performed. Run `pytest -q tests/test_division_wire_identities.py`.
