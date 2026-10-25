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

Open <http://localhost:8000/languages/wasm/playground.html>. Forty-three bundled examples
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
**Initialize before the export** uses a start function to grow and seed memory
before `run` changes a selected byte. Results show both memory halves, the page
count and the initializer counter.
**Choose a 64-bit function at runtime** selects addition, subtraction,
multiplication or division through a function table, then counts the result's
set bits. Extra indices demonstrate signature, null-entry and bounds traps.
**Compiled C · array loop** updates the first 0–4 entries of a four-element
unsigned array and returns their sum. Its 16-byte backed window starts at address
65536, matching the C linker's data placement after a 64-KiB stack.
**Compiled C · stack and globals** passes a local array to another function,
using two 16-byte regions separated by a 496-byte gap.
**Indexed byte in a 64-byte window** combines a runtime i64 store, a byte lookup
and bit counting. Offsets 0–63 succeed; other valid Wasm addresses reach the
font's memory bound.
**Pass function references through helpers** demonstrates typed selection,
reference-valued calls and blocks, and a mutable reference global.
**Computed module initialization** uses wrapping constant expressions, immutable
globals, a seeded table and active elements to prepare callbacks and data.
**Optional callback or strict null check** chooses fallback addition for an
empty callback, or reports a null-reference trap in strict mode.
**Call typed callbacks without a table** passes a nullable typed reference through
a helper and calls addition, XOR or unsigned division directly with `call_ref`.
**64-bit division → reference tail calls** carries a checksum and remainder through
`return_call_ref` using one ordinary call frame.
**Grow and call a non-null typed table** grows a dispatch table from a typed
callback library, then tail-calls the selected reference directly.
**Compiled C · function pointers** passes a runtime callback through a helper
to select full-width i64 addition, XOR or division.
**Compiled C · packet checksum** copies up to seven payload bytes into a local
stack buffer and computes a wrapping rolling checksum in a separate helper.
**Change and grow a function table** installs a passive segment, drops it,
selects a function reference, replaces a slot and grows another slot with that
reference. It calls the new slot and counts the result's set bits.

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

`python build_examples.py --recompile-c` additionally rebuilds all five C sources. It
requires Clang with a wasm32 target and `wasm-ld`; Apple's system Clang does not
provide this target. Without that option, the build uses the supplied,
compiled binaries `examples/mix.wasm`, `examples/array.wasm`,
`examples/sparse_array.wasm`, `examples/callbacks.wasm` and `examples/packet.wasm`.

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
Backtrack class zero is the implicit wildcard. Class one is reserved for
uninitialized operands, and initialized bits use distinct classes starting at
two. Only operand overrides need storage; class definitions choose the smaller
of Format 1 and Format 2. Singleton groups compare glyph-based Format 1 with
class-based Format 2 and retain the smaller complete encoding.
Gates still execute in tape order, so
dependencies within a batch are written before use. Type-7 extension wrappers
and lookup headers are placed in two waves to keep both Offset16 levels in range.
Truth rules inspect newest operands first and stop once their result is fixed.
Each rule's context ends at its oldest required operand, omitting older inputs
and unrelated cells before it. The resulting rules partition the truth table;
this changes serialization without adding registers or runtime arithmetic.

An alternative packing policy lets two adjacent gate groups share one Format 2 subtable and
extension wrapper. Each destination keeps its own input class and truth rules.
The shared backtrack class map distinguishes both groups' operands; rules
enumerate intervening operands from the other group as don't-care bits.
At most three extra bits may be enumerated, and a conservative 60,000-byte
subtable bound preserves its internal Offset16 fields. All earlier operand
registers must be initialized. Automatic serialization compares the smallest
feasible batch in each policy and keeps the smaller GSUB/GDEF encoding. Explicit
batch and coalescing options remain available. The coverage-cache singleton
exceptions remain separate.

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
| Stack / locals | `local.get`, `local.set`, `local.tee`, `drop`, untyped integer `select`, typed integer/reference selection, `nop`; non-null locals require definite initialization |
| Calls | Multiple internal functions, `call`, `call_indirect`, `call_ref`, all three corresponding `return_call*` forms, `return`, fresh locals per call and bounded ordinary/tail recursion; no host imports |
| Initialization | Optional void start function, after active data/table initialization and before the selected export; its calls, loops, state changes, traps and resource bounds follow the normal compiler rules |
| Function tables | Up to 16 mutable function-reference tables, each up to 256 slots; nullable/non-null generic or indexed types, matching active/passive/declarative segments, `table.get/set/size/grow/fill/copy/init`, `elem.drop`; structural signature checks |
| Control flow | `block`, `loop`, `if` / `else`, `br`, `br_if`, `br_table`; integer/reference parameters and multiple results, including type-index block signatures and loop backedge parameters |
| Memory | `i32`/`i64` loads/stores and narrow signed/unsigned variants, little-endian encoding, unaligned access, offsets, active data segments; `memory.copy` and `memory.fill` with dynamic addresses and lengths within configurable backed regions at absolute Wasm addresses |
| Data segments | Passive byte strings, `memory.init` with dynamic source/destination/length, and `data.drop`; segment lifetime follows branches, loops and internal calls |
| Memory growth | `memory.size` and `memory.grow`; dynamic page counts, old-size/−1 results, and bounds that follow growth through branches, loops and calls |
| Globals | Integer and nullable/non-null function-reference globals with constant expressions, `global.get`, mutable `global.set`; values persist within an invocation, including through calls |
| Traps | `unreachable`, integer divide-by-zero, i32/i64 signed division overflow, actual memory/data-segment bounds, and indirect-call table bounds/null/signature errors |

Unsupported instructions/module forms are rejected. Some otherwise supported
programs also exceed the configured circuit or font-layout capacity. A resource
rejection must not be interpreted as a successful compilation.

### WAT and binary modules

The new text frontend accepts flat and folded integer expressions, nested block
comments (including line comments adjacent to tokens), named
functions/locals/globals/labels, grouped unnamed parameters,
exports, function and block type uses, one memory, integer/funcref globals, active
constant-offset data segments, passive data segments, multiple function tables and
active/passive/declarative function-index or reference-expression elements, and a named/numeric start-function use.
Names and data-string escapes are resolved by
the frontend; integer literals are checked against their declared width,
including global initializers and data offsets. The resulting binary is
independently validated by V8.
Active data segments require a declared memory and an i32 constant expression
for their offset. Integer constant expressions support wrapping i32/i64
`add`, `sub` and `mul`, plus reads from previously defined immutable globals.
Element and data offsets can read any declared immutable global. Offset syntax
accepts a folded expression or an `(offset ...)` instruction sequence.
Nullable function-reference globals and reference-expression elements can also
read immutable globals of the matching type. Mutable globals, forward global
references in global initializers, mismatched operand types and runtime-only
instructions are rejected. Initializer instructions are retained in the emitted
binary for independent validation; declaration evaluation never calls the Wasm
reference interpreter.

The [computed-layout example](examples/constant_layout.wat) uses these expressions
to place an embedded seed and initialize a callback table. A table declaration
can supply `ref.func` or `ref.null func` as its initializer, in folded or flat
syntax: `(table 4 8 funcref (ref.func $callback))` seeds all four initial slots.
Active element segments then override those slots in declaration order.
Slots subsequently added by `table.grow` use that instruction's operand.
Table initializers cannot read module-defined globals; imports remain unsupported.
The example's runtime input chooses addition, or XOR followed by unsigned
division by seven.
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
bytes before loading them. Imports and exception tags are
explicitly rejected instead of being silently ignored. Tables support function-index elements in active, passive and declarative modes.
Active offsets must be constant i32 expressions. Nullable function references can
occupy operand stacks, locals, globals, internal function parameters/results and
block/loop signatures. `select (result funcref)` selects references; typed i32/i64
selection also works. `ref.as_non_null` preserves a reference or reports a
`null_reference` trap. `br_on_null` consumes the reference on its taken branch
and retains it on fallthrough; `br_on_non_null` passes the reference to its
target and discards null on fallthrough. Both support named or numeric targets,
multi-value branches, function returns and bounded loop backedges.
The [nullable-callback example](examples/nullable_callbacks.wat) selects a fallback
function with `br_on_non_null`, or asserts a non-null callback in strict mode.
The selected font entry must still have only i32/i64 inputs
and outputs; other exported functions can have reference signatures.
Data-count sections are supported in their specified position before code;
V8 validates their counts and all referenced data indices. Extended load/store
operands with an explicit memory index are rejected, including an explicit index
of zero. Bulk-memory binaries accept memory index zero.
Floating-point, SIMD, externref, GC types and recursive function type definitions
remain unsupported. Indexed function-reference signatures must form an acyclic
type graph. Ordinary and tail recursion between functions remain supported.
This is not an unrestricted implementation of the WAT grammar.

### Start functions

`(start $initialize)` or `(start 0)` names the optional start function. It must
take no parameters and return no results, and only one may be declared. Binary
start sections are decoded in their specified position before element and code
sections; invalid indices, signatures and encodings fail before font output.

Active data and function-table entries are initialized first, and active data
segments are already dropped when start executes. Start can call other functions,
dispatch through the table, grow memory, update globals, and copy or drop passive
data. Its resulting state is passed to the selected export. A start trap or
exhausted loop, call or backed-memory bound prevents the export from running.
The start call and export call each begin with an empty call stack and use the
same configured depth/loop limits. Choosing the start function itself as an
export executes it again as an ordinary explicit call.

Loading validates declarations and active-segment bounds without running start.
The native compiler lowers start followed by the export into the same circuit;
constant initialization may be folded by the existing circuit optimizer. It
never runs the reference interpreter to pre-execute start, and it does not need
a second shaping pass. Infinite initialization produces an execution-bound
status rather than hanging compilation. The legacy primitive lowerer rejects
all start sections instead of ignoring initialization.

For the reference API, `module.instantiate(fuel=...)` runs start once and returns
the initialized state. `module.invoke(..., state=state)` reuses it without
restarting. An invocation without a supplied state creates a fresh instance,
sharing its fuel between start and the export. Each font invocation similarly
begins with fresh initialized memory, globals and segment availability.

The [initialization example](examples/start_memory.wat) grows from zero pages,
copies bytes 1–16 from a passive segment and drops it before accepting arguments:

```sh
python build.py examples/start_memory.wat --export run -o start-memory.ttf
python run.py start-memory.ttf 3 0xaa
# (578437698537325057, 1157159078456920585, 1, 1)
# Memory: 0x08070605aa030201, 0x100f0e0d0c0b0a09; one page, one start call
```

This ordering follows WebAssembly's
[module instantiation semantics](https://webassembly.github.io/spec/core/exec/modules.html#instantiation).

### Function tables and indirect calls

Declare a table with `(table $ops 6 funcref)` and initialize slots using an
active segment such as `(elem (i32.const 0) $add $subtract)`. Slots start null;
later segments overwrite earlier entries. Active initialization must fit the
table, including empty segments. The compiler rejects invalid initialization
before writing a font. Minimum and optional maximum table limits are 0–256.
`table.get` and `table.set` read or replace runtime-selected references.
`ref.func $name` produces a declared function reference; `ref.null func` produces
null, distinct from function index zero. `ref.is_null` tests either kind. A
`(local $chosen funcref)` starts null and can carry references through branches.
References cannot be used as integer operands.

`call_indirect $ops (type $binary)` takes its i32 slot index from the top of the
stack, above the callee's arguments. The table name/index can be omitted for
table zero. Named/numeric type uses and unnamed inline integer/funcref `(param ...)` / `(result
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

Passive segments such as `(elem $functions func $add $divide)` remain available
until `elem.drop $functions`. `table.init $ops $functions` copies a selected
range into the table; dropping a segment preserves entries already installed.
Active and declarative segments are unavailable to `table.init` after startup.
A declarative segment, `(elem declare func $add)`, can declare a `ref.func` target
without installing it. `table.copy` preserves the source snapshot for overlaps;
`table.fill` repeats a function reference. Both operations check unsigned bounds,
including zero-length endpoints, and compose through starts, calls and loops.

`table.size` reports the current number of slots. `table.grow` takes a function
reference followed by an unsigned i32 delta, initializes new slots with that
reference, and returns the previous size. Failure returns `0xffffffff` without
changing the table. With no declared maximum, this bounded implementation allows
allocation up to 256 slots; larger requests fail allocation. A declared maximum
must also be at most 256. Table slots consume circuit resources, especially when
runtime mutation makes many possible call targets reachable.

Modules can declare up to sixteen function tables. Each has its own entries,
current size and maximum. Table instructions take a named or numeric table index;
omitting it selects table zero. Active elements use `(elem (table $ops)
(i32.const 0) $add $divide)` to select a destination table. Binary element modes
2 and 6 preserve that table index for function-index and reference-expression
initializers respectively.

`table.copy $destination $source` copies between tables as well as within one
table. Its destination and source ranges are checked against their respective
current sizes, including zero-length endpoints. `table.init $destination $segment`
can initialize any table from a passive segment. Segment availability belongs to
the module: dropping a segment makes it unavailable to every table without
changing installed entries. All tables retain mutations through starts, calls,
branches and loops; each fresh font invocation resets them together.

The [multiple-table example](examples/multiple_tables.wat) copies addition, XOR
or unsigned division from a library into a separate dispatch table. It grows only
the dispatch table and calls its new slot. The library stays at three slots.

```sh
python build.py examples/multiple_tables.wat --export run -o tables.ttf
python run.py tables.ttf 100 7 2
# (14, 3, 2): quotient, library slots, dispatch slots
python run.py tables.ttf 100 7 0
# (107, 3, 2): sum, independent table sizes
```

```sh
python build.py examples/mutable_dispatch.wat --export run -o mutable.ttf
python run.py mutable.ttf 100 7 1
# (14, 3, 3): quotient, set bits, current table size
```

Dispatch, mutation and segment lifetimes follow WebAssembly's
[table instruction semantics](https://webassembly.github.io/spec/core/exec/instructions.html#table-instructions).

### Tail calls

`return_call $function` and `return_call_indirect $table (type $signature)`
replace the current function frame. They pass only the callee arguments,
discard the old operand stack and locals, and return the callee's results to
the original caller. Callee locals start at zero or null. Memory, globals,
tables, page counts and segment lifetimes carry through the transition.
Indirect tail calls use the same table bounds, null and structural signature
checks as ordinary indirect calls, including nonzero table indices.

Tail transitions do not consume `--call-depth`. The separate `--tail-calls`
budget defaults to eight transitions per ordinary call frame and accepts 0–64;
zero disallows tail transitions. Every ordinary child call gets its own tail
budget. A transition beyond the budget reports
`ExecutionBoundExceeded('tail_call')`. Invalid indirect targets trap before
that transition bound is applied. Loop bounds remain independent, and start
and export invocations have separate call frames and tail budgets.

The compiler lowers tail transitions with a worklist rather than recursive
Python calls. The reference VM likewise replaces frames iteratively, sharing
its instruction fuel across ordinary and tail calls. Neither uses a host Wasm
executor for font execution. The behavior follows the specification's
[tail-call semantics](https://webassembly.github.io/spec/core/exec/instructions.html#exec-return-call).
`return_call_ref $type` applies the same frame replacement and budgets to a
typed function reference. A null reference traps before the transition bound.

The [tail-recursive example](examples/tail_calls.wat) divides two i64 inputs,
then carries the quotient and remainder through a recursive helper in table
one. Its entry tail-calls that helper, and each round performs another indirect
tail call, so rounds 0–7 fit the default budget using just one ordinary frame.

```sh
python build.py examples/tail_calls.wat --export run --call-depth 1 -o tails.ttf
python run.py tails.ttf 100 7 3
# (23, 5): checksum, remainder plus rounds
python build.py examples/tail_calls.wat --export run --call-depth 1 --tail-calls 16 -o tails.ttf
```

### Function-reference values

Explicit `(ref func)`, `(ref null func)`, `(ref $type)` and `(ref null $type)`
declarations work in internal signatures, locals, globals, block/loop signatures,
typed selection, tables and reference-expression elements. Named and numeric heap
types are checked against the declared type-index space. Binary value types use
the nullable/non-null prefixes and signed heap-type indices; `call_ref` and
`return_call_ref` use unsigned type indices. Structurally equal type aliases
match, including aliases nested inside higher-order function signatures.
Non-null locals have no observable default: V8 validates definite initialization
before circuit lowering. A non-null table requires an explicit initializer,
including a table with zero initial slots.

`call_ref $type` pops a typed function reference above its arguments and calls it
directly. Nullable references report `null_reference`; non-null references can
be called without a preceding assertion. Calls share state and consume the
ordinary call-depth budget. `return_call_ref $type` uses the tail-call budget.
The [table-free callback example](examples/typed_callbacks.wat),
[reference-tail example](examples/tail_reference64.wat), and
[typed-table example](examples/typed_dispatch.wat) exercise these forms.

Reference-expression elements can contain explicit null entries:

```wat
(table 3 funcref)
(elem (i32.const 0) funcref (ref.func $add) (ref.null func) (ref.func $divide))
(elem $passive funcref (ref.func $add) (ref.null func))
(elem declare funcref (ref.func $divide))
(global $chosen (mut funcref) (ref.null func))
(func $choose (param funcref funcref i32) (result funcref)
  local.get 0 local.get 1 local.get 2 select (result funcref))
```

The binary loader accepts all eight element encodings, including explicit table
zero and padded indices. Reference initializers accept `ref.func`,
`ref.null` with a function heap type, and reads from immutable globals; table-declaration initializers
support the first two forms. References retain their type through calls, returns, branches,
loop backedges and state merges; integer operations cannot consume them. Internal
`call_indirect` signatures can include references and still match structurally.
The reference VM represents null separately from function index zero.

The [reference-flow example](examples/reference_flow.wat) selects a table entry
or fallback addition, passes the reference through a helper and typed block,
stores it in a mutable global, then installs and calls it. With slot 1 selected,
the null entry traps; fallback addition works when selection is disabled. The
table read still checks its bounds even when its value is discarded.

```sh
python build.py examples/reference_flow.wat --export run -o references.ttf
python run.py references.ttf 100 7 2 1
# (14, 3): division result and set bits
python run.py references.ttf 100 7 1 0
# (107, 5): fallback addition and set bits
```

### Multi-value structured control flow

`block`, `loop` and `if` accept integer/funcref signatures such as
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
Floating-point and externref signatures and named block-parameter bindings remain
unsupported. Integer/funcref block types in binaries use signed LEB128 type indices.

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

### Backed memory placement and compiled C arrays

`--memory-base` selects the first backed byte's absolute Wasm address. The
default is zero; `--memory-bytes` still controls the window size, up to 256
bytes. Both bounds must fit the unsigned 32-bit address space. The compiler
does not relocate the module's addresses: it maps the selected region to font
registers. A manifest with no `memory_base` setting uses the default zero base.

Loads and stores require their entire effective range to fit the window.
`memory.copy` checks both source and destination; `memory.fill` and `memory.init`
check the destination. Passive segment offsets remain relative to the segment.
The compiler checks actual Wasm memory and segment bounds first, so invalid
accesses trap rather than reporting a font resource bound. Valid empty bulk
ranges can lie outside the backed window. Active data segments initialize their
intersection with the window in segment order. The window can cross page
boundaries; growth exposes zeroed bytes within it while preserving existing data.

The bundled [`examples/array.c`](examples/array.c) uses a volatile array to
retain actual loads and stores, and a bounded loop updates and sums its first
`count` entries. The source uses unsigned arithmetic, so both the updates and
sum wrap at 32 bits. Counts greater than four trap. Each shaping invocation
starts with `[3, 5, 7, 11]` again.

```sh
python build.py examples/array.wasm --export run --memory-base 0x10000 \
  --memory-bytes 16 -o array.ttf
python run.py array.ttf 4 10
# 66: (3+10) + (5+10) + (7+10) + (11+10)
python run.py array.ttf 2 -1
# 6: (3-1) + (5-1)
```

The linker places the array after its 65536-byte stack. Rebuild it with Clang
and the [WebAssembly linker](https://lld.llvm.org/WebAssembly.html):

```sh
clang --target=wasm32 -O2 -fno-unroll-loops -nostdlib -ffreestanding \
  -Wl,--no-entry -Wl,--export=run -Wl,--strip-all \
  -Wl,--stack-first -Wl,-z,stack-size=65536 examples/array.c -o examples/array.wasm
```

The bundled array binary was built with `zig cc` from Zig 0.17.0 using
`-target wasm32-freestanding` and the same optimization/stack options, omitting
`--stack-first` because that linker already places its stack first. Rebuilding
the font from the supplied binary requires neither C toolchain.

### Multiple backed regions and indexed access

Repeat `--memory-region BASE:BYTES` to select up to sixteen disjoint regions
instead of the single `--memory-base` / `--memory-bytes` window. Decimal and
hexadecimal values are accepted. The combined size must be at most 256 bytes;
regions are sorted, adjacent ones merge, and overlaps are rejected. Python callers
use `Limits(memory_regions=((65024, 16), (65536, 16)))`. Explicit regions replace
the single-window setting and appear in the ABI manifest.

Loads and stores must fit entirely in a region. A nonempty bulk range may cross
adjacent merged regions but cannot cross an unbacked gap. `memory.copy` can copy
between different regions, preserving its original source for overlaps. Actual
Wasm/data bounds are checked before backed-region bounds; valid zero-length
ranges require no backed bytes. Initialization and memory growth follow the same
rules as the single window.

The [`sparse_array.c`](examples/sparse_array.c) example allocates a 512-byte frame,
uses only its first sixteen bytes at address 65024, and reads sixteen bytes of
globals at address 65536. Its non-inlined helper sums the local array.
Only 32 bytes consume font registers despite the 496-byte gap:

```sh
python build.py examples/sparse_array.wasm --export run \
  --memory-region 65024:16 --memory-region 0x10000:16 -o sparse.ttf
python run.py sparse.ttf 4 10
# 66
```

Rebuild this C binary with the same compiler/linker options as `array.c`, changing
both source and output names to `sparse_array`. The supplied binary uses Zig 0.17.0.
`build_examples.py --recompile-c` rebuilds all C fixtures using Clang/LLD.

Dynamic reads in windows larger than sixteen bytes use a shared multiplexer tree;
stores share address decoding. Indexed eight-bit selection among 32, 64 and 128
independent bytes constructs 248, 504 and 1,016 gates, compared with 688, 1,333 and
2,619 for repeated full-address comparisons. Sparse regions use the same compact
arrays, so the gaps do not add selection cells. Address/bounds checks remain
separate from those selection counts. Smaller legacy windows retain their
existing layout.

Wide loads from runtime-valued windows of at least 32 bytes share one selection
of an overlapping block using the high address bits, then shift within that
small block using the low bits. Known alignment bits shorten the block and
remove unnecessary shifts. This avoids repeating a full byte lookup and address
addition for every byte of an i32/i64 load. Constant-only windows and narrow
loads retain their existing selection path. Actual Wasm bounds and backed-region
bounds still guard the complete load, including unaligned and signed variants.

For a 128-byte buffer populated by sixteen runtime i64 inputs, a dynamic i64
read drops from 4,261 to 2,185 gates and from 1,153,092 to 600,176 font bytes
(49% fewer gates and 48% smaller font). The read now fits a 2,500-gate construction
budget. Two unaligned reads feeding addition, XOR and a full-width unsigned
divider drop from 8,937 to 7,243 gates and from 3,247,904 to 2,703,188 font bytes.
The [indexed-word example](examples/indexed_words.wat) fits an 8,000-gate budget
and backs 64 bytes at address zero. Both read offsets must be 0–56.
Before/after metrics are recorded in
[wide_memory_capacity.json](benchmarks/wide_memory_capacity.json).

```sh
python build.py examples/indexed_words.wat --export run --memory-bytes 64 --max-gates 8000 -o words.ttf
python run.py words.ttf 0x0807060504030201 0x1122334455667788 3 29 7
```

```sh
python build.py examples/indexed_memory.wat --export run --memory-bytes 64 -o indexed.ttf
python run.py indexed.ttf 34 0x0807060504030201
# (3, 13): selected byte and seed set bits
```

### Compiled C callbacks and packet processing

[`callbacks.c`](examples/callbacks.c) loads a volatile function pointer from
three initialized globals and passes it to a non-inlined helper. Its Wasm binary
contains actual `call` and `call_indirect` instructions. Operations 0, 1 and 2
perform unsigned i64 addition, XOR and division. Other operations trap; division
by zero traps only for operation 2. The twelve pointer bytes start at 65536.

[`callbacks_tail.wasm`](examples/callbacks_tail.wasm) compiles the same C source
with `-mtail-call`. Its export uses `return_call` to the helper, which uses
`return_call_indirect` to the callback. Both calls reuse one frame; the bundled
**Compiled C · tail-call callbacks** playground example sets `call_depth=1`.
`build_examples.py --recompile-c` rebuilds this variant alongside the ordinary
callback fixture.

[`packet.c`](examples/packet.c) checks a runtime count against an embedded packet
header, copies and adjusts up to seven payload bytes into a local array, then
computes a wrapping 32-bit rolling checksum in a non-inlined helper. The checksum
uses XOR and multiplication, and both loops remain in the compiled Wasm. Two
eight-byte regions back its stack buffer at 65504 and packet data at 65536.

```sh
python build.py examples/callbacks.wasm --export run --memory-region 65536:12 -o callbacks.ttf
python run.py callbacks.ttf 100 7 2
# 14
python build.py examples/packet.wasm --export run \
  --memory-region 65504:8 --memory-region 65536:8 -o packet.ttf
python run.py packet.ttf 7 10
# 1610677118
```

Both supplied binaries were compiled with Zig 0.17.0 using the same options as
the array fixtures. To rebuild with Clang/LLD, use `build_examples.py --recompile-c`.
Changing the compiler/linker layout may require updating the backed regions.

### Circuit and execution budgets

CLI limits are 1–64 loop iterations, 1–32 ordinary call frames, 0–64 tail
transitions per frame, 0–256 backed memory bytes,
and 1–32,000 constructed gates. Serialization finds the smallest batch size
from 1–64 gate groups that fits the lookup headers and extension offsets in each
of two policies: separate subtables and bounded subtable coalescing. It chooses
the smaller serialized GSUB/GDEF pair from the feasible policies.
It rejects layouts that cannot fit. Every source/constant/result/trap cell also
counts toward the OpenType glyph limit of fewer than 65,535 glyphs. Constructed
gates can be pruned before emission, so the construction budget is not a promise
that every circuit of that size fits. Capacity remains program-dependent.

Capacity failures raise `CompilationCapacity`, a `ResourceLimit` subclass, with
`resource` set to `gates`, `glyphs`, `lookup_offsets` or `instructions`. Its
`details` include constructed gates, the gate budget, backed bytes/regions, the
lowered instruction count and its fixed 100,000-instruction budget. Instruction
exhaustion reports that count and suggests reducing loop/call bounds or simplifying
the program; `--max-gates` does not change the lowering instruction limit. The
message preserves the original failure and suggests which bounds to reduce. Raising `--max-gates` can help a construction-budget failure; it cannot
raise OpenType glyph or lookup-offset limits.

Indirect dispatch selects one encoded reference through the shared lookup tree,
then compares it with compatible targets. Duplicate slots share the same callee
and no longer need full-width comparisons for each slot. A 256-slot table whose
entries all reference one dynamic i64 divider drops from 5,680 to 4,322 gates and
from 2,078,972 to 1,532,548 font bytes (24% fewer gates and 26% smaller font).
It now fits a 4,500-gate construction budget. Null, signature and unsigned bounds
checks still precede call-depth accounting. This is a measured program-specific
reduction; other compositions retain their own capacity limits. Full before/after
metrics are recorded in [dispatch_capacity.json](benchmarks/dispatch_capacity.json).

The previous default was 12,000 gates with approximately 5,400 unbatched gate
groups. Packing and smaller arithmetic circuits now support these full-width
runtime compositions, without increasing the current construction or glyph caps:

| Bundled composition | Live gates | Glyphs | Physical lookups | Font size |
| --- | ---: | ---: | ---: | ---: |
| Two signed divisions + addition | 10,174 | 31,038 | 4,808 | 1.6 MB |
| Two unsigned divisions → multiplication | 12,549 | 38,163 | 5,258 | 1.8 MB |
| Two signed divisions → multiplication → popcount | 14,927 | 45,297 | 4,059 | 2.4 MB |
| Three unsigned divisions + addition | 12,995 | 39,757 | 4,285 | 2.3 MB |
| Four unsigned divisions + addition | 17,347 | 53,069 | 4,293 | 3.6 MB |

The four-operation example previously exceeded the glyph limit; compact truth
rules and shared storage now reduce its font from 17.6 MB to 2.4 MB. The
three-divider example's 12,677 gate groups exceeded the previous maximum batch
size of sixteen with separate subtables. Coalescing fits batches of three groups
and reduces the font from 16.8 MB to 2.3 MB while retaining all glyph IDs, truth
functions and execution bounds. Larger batches reduce header overhead but add
backtrack context, so gate count, lookup count and file size need not move together. Playground
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
Memory-placement regressions compare nonzero, unaligned and page-crossing
windows with V8 and the reference interpreter. They cover every integer
load/store width, effective offsets, overlapping copies, fills, initialization,
active segment intersections, dropped segments, growth, zero-length operations,
and trap/resource-bound precedence. The supplied C array binary runs through
both Python/system HarfBuzz and browser HarfBuzzJS.
Start-function regressions cover initialization ordering, globals, memory growth,
passive-segment drops, indirect calls, startup traps and execution bounds,
separate call stacks, shared reference fuel, repeated reference instances and
fresh shaping invocations. Independent binary encodings include padded unsigned
start indices through 128. Loading/compilation tests forbid reference-VM execution;
legacy tests require explicit rejection of both harmless and trapping starts.

Sparse-memory regressions cover separate regions, gaps, adjacent merging,
active overlays, cross-region bulk transfers, growth/start initialization,
unsigned offsets, CLI configuration and actual memory traps before resource
bounds. Selection benchmarks check every index against circuit evaluation;
a 64-byte dynamic lookup checks a reduced construction budget. Capacity errors
are checked for gate, glyph and lookup-offset classification.
Mutable-table regressions cover references and locals, dynamic get/set,
non-power-of-two bulk alignment, overlapping copies, fill/init bounds, passive
and declarative segment lifetimes, repeated drops, growth success/failure/nulls,
state through starts/calls/loops, fresh invocations and indirect trap precedence.
Independent binary fixtures cover all eight element encodings and padded table,
reference and typed-select operands. Function-reference tests also cover mixed
reference/integer signatures, direct and indirect calls, typed blocks and loop
backedges, globals initialized before start, null entries and fresh invocations.
Multiple-table regressions cover independent storage and growth, cross-table
copies with different sizes, shared segment lifetimes, nonzero table indices in
binary instructions and elements, and reference-valued indirect calls. Their
results and traps are compared with V8, the reference VM and actual HarfBuzz.
Tail-call regressions cover direct/indirect and mutual recursion, frame and
local replacement, mixed/reference results, loop exits, shared mutable state,
independent frame budgets, trap precedence and padded binary immediates. Maximum
ordinary/tail bounds and long reference-VM tail chains check that host stack
growth does not replace the declared execution budgets. Both tail-call
playground examples run in browser HarfBuzzJS against fresh V8 instances.
Wide-read regressions check every padded lookup index, non-power-of-two arrays,
known and partial alignment, repeated runtime bytes, every signed/unsigned wide
load, sparse gaps, growth, unaligned endpoints and reduced construction budgets.
C fixtures verify actual callback dispatch and packet loops against V8, the
reference VM and HarfBuzz. Both new memory examples and mutable dispatch also run in browser
HarfBuzzJS against fresh V8 instances.
Constant-expression regressions cover both integer widths, wrapping arithmetic,
immutable-global aliases, computed data/element offsets, nullable reference
initializers, retained binary instructions and edits to resolved module values.
Null-control regressions check distinct successor stacks, multi-value branches,
function labels, loop bounds, inactive assertions and trap order. Table-seeding
tests cover empty and 256-slot tables, active overlays, independent instances,
growth operands, start functions and padded initializer immediates. The computed
layout and optional-callback examples also run in browser HarfBuzzJS against V8.
Typed-reference regressions cover nullable/non-null values and definite local
initialization, generic/indexed aliases, higher-order signatures, signed heap
indices, unsigned call indices, and compact reference block types. Direct and
tail-reference calls check null/bound precedence, frame replacement, mutable
state and reference-valued results. Typed-table tests cover nullable/non-null
seeding, all element modes, alias-compatible copies, growth/fill/init/drop,
start functions and invalid static type combinations.

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
Browser-engine tests compare all thirty-eight bundled programs with V8. Capacity regressions cover
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
│   ├── memory.py, tables.py         # Backed regions and mutable table circuits
│   ├── selection.py, capacity.py    # Shared selection circuits and diagnostics
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

Further reference support would include externref, recursive function type
definitions, recursive groups, explicit subtype declarations and GC heap types.
Those forms currently fail closed. Generic and acyclic indexed function-reference
values, direct reference calls/tail calls, typed mutable tables, typed elements,
null-control instructions and table initializers are implemented within the
bounds above. Font entry parameters/results remain integers.

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
