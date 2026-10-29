# LLVM IR to executable OpenType

This compiler translates a bounded integer subset of LLVM IR into the shared
GSUB Boolean-circuit backend. Python encodes argument bits and uninitialized
scratch glyphs, HarfBuzz executes ordered substitutions, and the decoder reads
the computed result. The same font accepts different runtime inputs without
recompilation. No complete-program input/output enumeration is used.

This is a working compiler for the subset below, **not general LLVM
compatibility**. Examples include actual Clang and Rust LLVM IR and bitcode,
forty-seven executable fonts, paired manifests and benchmark results.

## Quick start

Use Python 3.10–3.14 with a llvmlite 0.46 wheel available for your platform.
Tested: Python 3.12, LLVM 20.1.8, FontTools 4.63, HarfBuzz 15.
A system HarfBuzz shared library is required (macOS: `brew install harfbuzz`;
Debian/Ubuntu: `apt install libharfbuzz0b`).

From the repository root:

~~~sh
python3.12 -m venv /tmp/llvmfont-env
/tmp/llvmfont-env/bin/pip install -r languages/llvm/requirements.txt

/tmp/llvmfont-env/bin/python languages/llvm/build.py \
  languages/llvm/examples/max.ll -o /tmp/max.ttf
/tmp/llvmfont-env/bin/python languages/llvm/run.py /tmp/max.ttf -5 -2 --signed
# -2
/tmp/llvmfont-env/bin/python languages/llvm/run.py /tmp/max.ttf 123 77
# 123

/tmp/llvmfont-env/bin/python languages/llvm/build.py \
  languages/llvm/examples/clang.bc --function indexed -o /tmp/indexed.ttf
/tmp/llvmfont-env/bin/python languages/llvm/run.py /tmp/indexed.ttf 2 100
# 111

/tmp/llvmfont-env/bin/python languages/llvm/build.py \
  languages/llvm/examples/rust.bc --function rust_mix -o /tmp/rust.ttf
/tmp/llvmfont-env/bin/python languages/llvm/run.py /tmp/rust.ttf 2 3
# 643

# Optimized Clang: lifetimes, memcpy from an immutable global, dynamic indices.
/tmp/llvmfont-env/bin/python languages/llvm/build.py \
  languages/llvm/examples/clang-intrinsics.bc --function copied_array -o /tmp/copy.ttf
/tmp/llvmfont-env/bin/python languages/llvm/run.py /tmp/copy.ttf 2 100
# 110

# Optimized Rust: checked arithmetic returns the wrapped result plus bit 32.
/tmp/llvmfont-env/bin/python languages/llvm/build.py \
  languages/llvm/examples/rust-intrinsics.bc --function rust_checked_add -o /tmp/checked.ttf
/tmp/llvmfont-env/bin/python languages/llvm/run.py /tmp/checked.ttf 4294967295 1
# 4294967296

# Saturation, global side effects across calls, and copied pointer arrays.
/tmp/llvmfont-env/bin/python languages/llvm/run.py \
  languages/llvm/fonts/rust_sat_add.ttf 4294967295 1
# 4294967295
/tmp/llvmfont-env/bin/python languages/llvm/run.py \
  languages/llvm/fonts/clang_global_calls.ttf 1 100
# 108
/tmp/llvmfont-env/bin/python languages/llvm/run.py \
  languages/llvm/fonts/rust_pointer_copy.ttf 1 100
# 101

# Runtime callback selection and constructor-initialized state.
/tmp/llvmfont-env/bin/python languages/llvm/run.py \
  languages/llvm/fonts/rust_dispatch.ttf 2 10 3
# 31
/tmp/llvmfont-env/bin/python languages/llvm/run.py \
  languages/llvm/fonts/clang_constructors.ttf 5
# 27

# Alias-aware tables and Rust's metadata-constrained callbacks.
/tmp/llvmfont-env/bin/python languages/llvm/run.py \
  languages/llvm/fonts/alias_table.ttf 1 50
# 37
/tmp/llvmfont-env/bin/python languages/llvm/run.py \
  languages/llvm/fonts/rust_merged_aliases.ttf 0 35
# 42

# Clang struct returns and by-value struct arguments.
/tmp/llvmfont-env/bin/python languages/llvm/run.py \
  languages/llvm/fonts/clang_triple.ttf 10 3
# 13 9 7
/tmp/llvmfont-env/bin/python languages/llvm/run.py \
  languages/llvm/fonts/clang_byval.ttf 13 9 7
# 26
~~~

Keep the `.json` manifest beside each `.ttf`. Its digest binds the ABI to that
exact font. These machine fonts use invisible glyph registers, not decimal text
or visible output. `run.py` only serializes bits, shapes once, validates the
tape and decodes integers. Without GSUB, scratch/output glyphs remain
uninitialized and decoding fails.

Default output is unsigned bit patterns. `--signed` displays two's-complement
integers; LLVM integer types themselves are signless. Arguments are reduced
modulo their declared width by the shared encoder. Aggregate results are
flattened in element order. Entry parameters are individual integers or the
flattened integer fields of a `byval` parameter. An `sret` entry's hidden result
pointer is supplied by the font and its stored fields become the outputs.

Python API:

~~~python
import sys
sys.path.insert(0, "languages/llvm")
from llvmfont import build, Limits
from fontcircuit.runtime import NativeFont

build("define i32 @f(i32 %a) { %r = add i32 %a, 1\nret i32 %r }",
      "/tmp/f.ttf", limits=Limits(max_steps=16))
with NativeFont("/tmp/f.ttf") as font:
    assert font.invoke(41) == 42
~~~

`build`/`compile_ir` accept IR strings, textual/bitcode bytes, or `Path` objects.
A plain string always means source text. `compile_ir` exposes the circuit for
tests and further backend work.

## Supported LLVM subset

| Area | Implemented behavior |
| --- | --- |
| Input | LLVM-verified `.ll` and `.bc` using llvmlite; opaque pointers |
| Integers | `i1`, `i8`, `i16`, `i32`, `i64` |
| Arithmetic | `add`, `sub`, `mul`, `udiv`, `sdiv`, `urem`, `srem` |
| Bits | `and`, `or` (including `disjoint`), `xor`, `shl`, `lshr`, `ashr` |
| Comparison | All ten integer `icmp` predicates; pointer `eq`/`ne` |
| Conversion | `trunc`, `zext`, `sext`; `trunc nsw/nuw` and `zext nneg` |
| Values | SSA, integer/null/zero/undef/poison constants, literal integer aggregates and byte strings, `freeze`, `select` |
| Control | Blocks, conditional/unconditional `br`, `switch`, parallel `phi`, `ret`, `unreachable` |
| Functions | Matching `ccc`/`fastcc` direct calls; integer/pointer/aggregate internal arguments and returns; bounded recursion; void returns |
| Indirect calls | Signature/CC-checked dispatch over a bounded, closed set of address-taken definitions; parameters, returns, selects, phis and pointer memory |
| Function tables | Constant/mutable function-pointer tables and globals, copied callbacks, global/data-pointer identity separation, guarded side effects |
| Aliases | Defined strong function/data aliases, alias chains, interior data GEP aliases, aliased entries and constructors; shared storage/code identity |
| Callback metadata | `!callees` restricts compatible targets, deduplicating aliases; executed violations produce an invalid-call diagnostic |
| Constructors | Priority-ordered `llvm.global_ctors`; recognized immutable ELF/Mach-O initializer-section cells/arrays; initialization before entry on every shape |
| Aggregates | Nested structures/arrays; `insertvalue`/`extractvalue`; aggregate load/store; flattened integer results |
| Aggregate ABI | `sret(T)` result buffers and `byval(T)` private copies, direct/indirect ABI matching, flattened integer entry adapters |
| Memory | Constant entry-block `alloca`, ordinary `load`/`store`, dynamic byte addressing, aliasing, pointer `select`/`phi`, caller memory passed to callees |
| Addressing | `getelementptr`, named/packed structs, array indices, LLVM ABI size/padding; `inbounds` and `inbounds nuw`; constant GEP expressions |
| Immutable globals | Defined constant integers, nested arrays/structures, byte strings and zero initializers; checked writes |
| Mutable globals | Defined integer, aggregate and pointer storage; ordered writes shared across calls/loops in one fresh module instance |
| Pointer memory | Typed pointer load/store, pointer fields/arrays, nulls, global relocations (including cyclic graphs), full copies through `memcpy`/`memmove`, internal pointer returns |
| Intrinsics | `llvm.smin/smax/umin/umax`, `ctpop`, `ctlz`, `cttz`, `abs`, `fshl`, `fshr` |
| Checked arithmetic | All six `llvm.[su]{add,sub,mul}.with.overflow` intrinsics at supported widths, returning `{integer,i1}` |
| Saturation | `llvm.[su]{add,sub,shl}.sat` at i1/i8/i16/i32/i64, including poison for oversized shift amounts |
| Bulk memory | `llvm.memcpy`, `memmove`, `memset`, `memcpy.inline`, `memset.inline`; nonvolatile, default address space, i32/i64 byte counts |
| Lifetimes | `llvm.lifetime.start/end.p0` for proven local allocation bases and whole-object sizes |
| Attributes | Integer parameter/return `range`, `noundef`; pointer parameter/return `nonnull`, `align`, `dereferenceable`, `dereferenceable_or_null`; load `!noundef`/`!nonnull` |
| Optimization | Optional LLVM SROA, instruction combining and CFG simplification; circuit folding/sharing always enabled |

Explicitly rejected: external calls/addresses, weak/linkonce/available-externally,
thread-local, partitioned and non-default-space aliases, ifuncs,
indirect branches, floating point, vectors, other
integer widths (including `i33`), global declarations without definitions,
`externally_initialized`/thread-local/absolute-address globals,
module destructors, unsupported startup-section formats, constant
expressions other than GEP, ordinary pointer entry parameters/results and pointer
fields in entry `byval`/`sret` storage, pointer/integer casts, dynamic or
non-entry allocas, atomics, volatile memory, exceptions, inline assembly,
varargs, calling conventions other than `ccc`/`fastcc`, other ABI attributes such
as `byref`, `inalloca`, `preallocated`, `inreg` and Swift-specific parameters, semantic
metadata such as `!range`, standalone GEP `nuw/nusw`, `icmp samesign`,
partial-object or unproven lifetime markers, and volatile/atomic memory intrinsics.

Validation covers all blocks of the selected entry and its direct callees
before optimization, including runtime-unreachable blocks. Uncalled functions
are not compiled. Frontend output depends on version/options: optimized C loops
may introduce `i33`, which remains rejected. The original C examples use `-O0`
to retain loops/local memory; `intrinsics.c` and `intrinsics.rs` are compiled
at `-O1` and exercise immutable arrays, copies, lifetimes and checked arithmetic.
Not every LLVM intrinsic/runtime call is lowered.
`state.c` and `state.rs` add optimized saturation, mutable-global calls and
pointer-table/copy examples. Unsupported pointer representations are diagnosed
at execution rather than being presented as ordinary computed values.
`dispatch.c` and `dispatch.rs` add runtime callbacks, copied function tables,
repeated indirect calls and constructor initialization. `constructors.c` is
compiled at `-O0` to retain its explicit startup list: Clang legally folds the
optimized dispatch example's constructors into static initializers.
`aliases.rs` exercises Rust's `!callees` metadata at `-O1` and duplicate-function
merging into an alias at `-O2`. `aliases.ll` combines function/data aliases,
a constructor alias, and a constrained callback table.
`abi.c` and `abi.rs` add large struct returns, nested calls, and callbacks that
write result buffers. The x86-64 Clang variant also exercises implicit `byval`
copies; arm64 frontends often emit explicit caller storage instead.

## Semantics and execution bounds

Each scalar has data wires and a poison wire. Arithmetic without no-wrap flags
wraps modulo its width. `nsw`/`nuw`, oversized shifts and `exact` violations
produce poison. `select` uses poison only from its chosen arm and condition;
`phi` selects the incoming edge first. `freeze` chooses fixed zero for poison.
Explicit `undef` and unwritten stack bytes are refined to zero, a deterministic
choice permitted by LLVM. This does not model every nondeterministic outcome.
Overflow intrinsics return a wrapped integer and overflow bit; overflow alone
is not poison. Both fields propagate poison from their operands. `or disjoint`
produces poison when the operands share a set bit. Integer `range` attributes
produce poison outside their possibly wrapping interval; `noundef` turns such
poison into an immediate diagnostic. Load `!noundef` is also checked.
Saturating arithmetic clamps overflow to the appropriate signed or unsigned
bound instead of producing poison. Saturating shifts still produce poison if
their unsigned shift amount is greater than or equal to the integer width.

Active division/remainder by zero or signed MIN/-1, poison control conditions,
invalid/unaligned accesses, executed `unreachable`, and poison across supported
`noundef` contracts produce diagnostic flags. Returned poison reports
`trap.poison_result`. Poison stored to memory is preserved. An unchosen
branch's division or memory fault does not fault the run.

`--optimize` allows LLVM's legal refinements before lowering, including changes
on undefined executions. Diagnostics describe the normalized program; this is
not a full source UB sanitizer. Unsupported ABI/semantic attributes are rejected.
Optimization promises that do not change the implemented behavior are not
exploited by the circuit backend.

Memory uses disjoint finite allocation identities and signed 64-bit byte
offsets. Loads/stores compare addresses against candidate slots and multiplex
bytes; no host memory interpreter runs. Only little-endian layouts with 64-bit
default pointers/indices are supported. Non-default spaces are rejected when
used. One-past pointers cannot be dereferenced. Frames release their allocations
at return. Internal calls may return pointers to caller/global storage; returning
a pointer to an expired local does not keep that allocation alive. Dereferencing
it reports `trap.invalid_memory`. Object sizes remain available for permitted
pointer arithmetic/comparison after deallocation. Entry results must be integers.

Typed loads/stores use LLVM's store size, independently of allocation size and
GEP stride. For example, an `i32` still writes four bytes when its ABI allocation
spacing is eight bytes. Scalar and pointer accesses exclude alignment padding;
aggregate fields retain LLVM's offsets/strides, and padding does not contribute
poison to a loaded field. Global initializers preserve the complete allocation,
including padding outside the typed store span.

`byval(T)` makes a private byte copy at each call, preserving padding, poison
and pointer provenance. The callee's stores change that copy; pointers contained
inside it still refer to their original pointees. The hidden copy belongs to
the caller's frame and stays alive until that caller returns, including when a
callee returns its address. Such copies consume the shared memory budget;
bounded repeated calls can exhaust it even when the source object is small.
Entry `byval` storage is constructed directly from integer input fields and is
already private. Other pointer entry parameters remain unsupported.

`sret(T)` passes caller-owned result storage through ordinary bounded pointer
memory. Calls check that the result span is live, writable and properly aligned,
even if the callee never writes it. The ordinary direct/indirect signature checks
also compare `byval`/`sret` pointee types and declared `byval` alignment; mismatched
direct calls fail compilation and incompatible indirect targets cannot dispatch.

For an `sret` entry, the adapter allocates result storage before execution,
passes its hidden pointer, then reads its integer leaves after return. For a
`byval` entry, input fields flatten in structure/array element order. Manifests
record parameter paths and `entry_abi` storage types/sizes. This interface follows
the LLVM storage type: Rust often emits `sret([24 x i8])` for a three-word struct,
so that entry returns 24 byte outputs rather than three inferred 64-bit fields.
The Clang example emits a named three-`i64` struct and returns three fields.
Internal ABI storage can contain pointers; entry adapters accept integer leaves
only. Zero-sized and oversized ABI storage is rejected explicitly.

Globals occupy byte objects with LLVM ABI padding. Initial
data is parsed from LLVM-verified constants, never from program input/output
mappings. Loads and copies from globals use the same circuits as stack memory.
A guarded write to constant storage reports `trap.readonly_memory` only when
the write executes. Externally supplied storage remains unsupported. Relocations
to defined globals/functions and constant GEPs are supported, including forward
references and cyclic graphs. Function addresses use a separate finite identity
space from data allocations; they cannot be dereferenced as data memory.

Numbered globals/functions/aliases retain distinct canonical LLVM identities.
`@0`, named `@"0"`, and named `@"@0"` do not share lookup/cache entries. To select
a numbered entry, use `--function @0`; numbering follows LLVM's canonical printed
module. Quoted identifiers select numeric-looking named entries. Bare names keep
their usual behavior, including preferring an actual named function `0` over a
numbered slot when both exist.

**Each shaping run is a fresh module instance.** Mutable globals start at their
declared initializers, then all calls, branches and bounded loop iterations
share their guarded updates. A subsequent `NativeFont.invoke` starts over.
Global state is not persisted in the host between shapes. Manifests for these
programs record `global_state: fresh-per-shape` and their mutable globals.
Native differential tests either reset the reference globals before each
invocation or use entry functions that initialize their own state.

Constructors run after global storage initialization and before the entry call,
sharing the same guarded global memory. `llvm.global_ctors` entries must name
defined, nonvariadic `void()` functions using `ccc`. Unsigned 32-bit priorities
run in ascending order. Equal priorities preserve array/discovery order as one
legal choice; LLVM does not specify their relative order. A non-null associated
symbol must be a strongly defined global or function retained in this module.
External/link-time COMDAT selection is outside this closed-module model.

Rust-style initializer tables are also recognized in `.init_array`,
`.init_array.N` (numeric priority), `__DATA,__mod_init_func` and
`__DATA_CONST,__mod_init_func`. These must be immutable, default-space pointer
cells or pointer arrays naming defined `void()` functions. Unsuffixed sections
use priority 65535. Known unsupported families such as legacy `.ctors`,
`.preinit_array`, `.CRT$X*` and initializer-offset tables are rejected instead of
being silently ignored. Destructors/finalizer tables remain unsupported.
Mach-O startup/finalizer sections with extra type flags are explicitly rejected.
Section attributes are parsed outside quoted global names and initializer data.
LLVM linker metadata globals cannot be accessed as ordinary runtime storage.
Constructor faults, call limits and block limits invalidate the whole result.

Indirect calls use a fixed-point discovery of address-taken functions reachable
from the entry, constructors, globals and callback arguments. A call's candidate
set contains definitions with exactly matching LLVM result/argument types and
calling convention (`ccc` or `fastcc`). Every candidate is validated before
lowering. A `!callees` attachment further restricts the candidate set to its
listed, defined functions (aliases resolve to the underlying code identity).
An executed target outside that list is undefined in LLVM and reports
`trap.invalid_indirect_call` here. Empty lists allow no executed calls. The
metadata narrows dispatch without executing any host callback. Manifests record
both the declared target list and the compatible dispatch candidates.
Candidate sets are conservative across the compiled call graph and
bounded by `max_indirect_targets`; they are not inferred from runtime input
enumeration or host addresses.

Each candidate receives a runtime guard comparing function identity, zero code
offset and non-poison status. Only that guard enables its calls and memory
effects, and its result is selected into the caller's SSA value. Null, poison,
data addresses, nonzero code offsets and incompatible signature/convention
targets report `trap.invalid_indirect_call`. Unsupported external/intrinsic
function addresses and variadic calls are rejected at compile time. The ordinary
call-depth and block budgets also apply to indirect recursion. Manifests expose
the function identities, candidate sets and constructor order for inspection.

Strong aliases (`external`/default, `internal`, `private`) are alternate names
for existing code or storage. They allocate no new memory or function identity.
Chains and constant GEPs into data objects are supported, including relocations
back to an alias from its underlying global. Aliases can name an entry selected
with `--function`, a callback, or a constructor. Code entries and constructors
must resolve to a zero-offset function base; an entry alias's declared type must
match that function's type. Alias chains are limited to 64
links and use the same closed-module linkage model as ordinary definitions;
external interposition/linker selection is not simulated. Weak, linkonce,
available-externally, thread-local, partitioned and non-default-space aliases
remain rejected when used. LLVM may already replace `unnamed_addr` aliases
with their targets while parsing; other used alias names appear in manifests.

Pointer-valued memory uses opaque 8-byte cells plus glyph-encoded provenance:
allocation identity, byte offset, byte lane and validity. It does not encode
host memory addresses. Full typed loads/stores and bulk copies preserve these
fields through dynamic addressing and predication. Arrays/structures can mix
pointer and integer fields, and an eight-byte zero fill produces null. Pointer
poison survives stores/copies and can be frozen normally.

Pointer payload bytes cannot be observed as integers: such loads report
`trap.pointer_as_integer`. Partial pointer overwrites, mixed pointer fragments
and nonzero integer-to-pointer memory reinterpretation report
`trap.pointer_representation` on a typed pointer load. A full untagged zero
representation is accepted as null; a partially overwritten tagged pointer is
not silently converted to null. This preserves pointer identity for the
supported operations without claiming arbitrary pointer-byte/ABI compatibility.

Bulk copies support runtime lengths up to the finite allocation capacity.
`memmove` snapshots all source bytes before guarded writes. Ordinary `memcpy`
permits equal source/destination pointers and diagnoses other overlap as
`trap.memcpy_overlap`; `memcpy.inline` requires nonoverlap. Zero-length calls
do not dereference their pointers, while argument attributes still apply.
Misaligned/nonnull argument promises produce poison, `noundef` checks that
poison, and dereferenceability requires a valid live span. Invalid or overlong
copies report an error rather than returning a partially copied result.

Lifetime semantics follow **LLVM 20.1**, matching the pinned parser. A local
object with a `lifetime.start` marker begins dead. Starting a dead object makes
it live with uninitialized bytes (refined to zero); starting an already-live
object poisons its contents. Ending a lifetime makes the object inaccessible;
ending an already-dead object is a no-op. Lifetimes are predicated and work
across bounded loop iterations. Markers must refer directly to an entry-block
alloca or an all-zero GEP to it, and specify its full size or `-1`. Other marker
forms are rejected. Ending a lifetime does not reclaim the frame's byte budget.

| Resource | Default | Maximum |
| --- | ---: | ---: |
| Blocks executed per invocation | 16 | 128 |
| Call depth, including entry | 3 | 8 |
| Global and frame allocation bytes | 64 | 4,096 |
| Boolean gates, including output copies | 24,000 | 32,000 |
| Lowered instruction instances | 20,000 | 1,000,000 |
| Candidates per indirect call | 16 | 256 |
| Module initializer entries | 32 | 256 |

Also bounded: source 1 MiB (text counts UTF-8 bytes; file reads are capped before parsing),
256 blocks/function, 256 direct aggregate elements,
4,096 aggregate tree nodes, aggregate depth 32, global-initializer graph depth 64,
and OpenType glyph/layout capacity. Entry arguments have a 32,766-bit total limit,
including flattened `byval` fields, checked during argument lowering.
Outputs and gates further reduce the available glyph capacity.
A 32,000 gate budget does not guarantee fitting 65,535 glyphs.
Compilation resource exhaustion raises `ResourceLimit`.
`--max-indirect-targets` and `--max-initializers` configure the new bounds.
Constructor invocations each count as a root call at depth one and use their
own block budget; all startup and entry stages share the gate, memory and
lowered-instruction budgets.

One step is **one basic-block execution**, including entry/exit, not one source
loop iteration. Still-active paths at `max_steps` set `limit.block_steps`.
Calls past `max_call_depth` set `limit.call_depth`. Decode raises
`ExecutionBoundExceeded`; partially executed accumulators are never valid.

~~~sh
/tmp/llvmfont-env/bin/python languages/llvm/build.py \
  languages/llvm/examples/loop.ll -o /tmp/loop.ttf --max-steps 16
/tmp/llvmfont-env/bin/python languages/llvm/run.py /tmp/loop.ttf 6
# 15
/tmp/llvmfont-env/bin/python languages/llvm/run.py /tmp/loop.ttf 7
# ExecutionBoundExceeded: block_steps
~~~

Larger bounds expand fonts. HarfBuzz can also stop a very large shaping run;
`IncompleteShaping` rejects uninitialized/misplaced cells without computing
missing operations in the decoder.

## Architecture

LLVM parses/verifies, the frontend validates the call graph, optional LLVM
passes normalize IR, and bounded SSA lowering produces shared Boolean circuits.

Control is a finite predicated state machine expanded at compile time. Each
tick reads an SSA snapshot and incoming-edge predicates. Phi nodes read that
snapshot in parallel. Enabled blocks compute dataflow, guarded writes update
the next snapshot, and branches enable the next tick. Mutually exclusive
predicates guard memory effects and calls. Each call expands another bounded
invocation. No runtime input values are used for specialization.

The shared backend folds constants, shares gates and removes dead wires.
Local truth tables have at most four dynamic bits per gate. Ordered GSUB
lookups compute them on a glyph tape. Scratch/output cells start uninitialized;
even identity/constant outputs are materialized through GSUB. Existing PUA ABI,
table packing, digest checking and HarfBuzz bindings are reused unchanged.
Global constructors and checked dispatch lower to this same circuit graph;
the Python/JavaScript runtime does not execute callbacks or startup functions.

## Regenerate C and Rust examples

From the repository root, tested with Apple Clang 17 and Rust 1.90.0:

~~~sh
clang -S -emit-llvm -O0 languages/llvm/examples/programs.c \
  -o languages/llvm/examples/clang.ll
clang -c -emit-llvm -O0 languages/llvm/examples/programs.c \
  -o languages/llvm/examples/clang.bc
rustc --crate-type=lib --edition=2021 --emit=llvm-ir \
  -C opt-level=1 -C panic=abort languages/llvm/examples/programs.rs \
  -o languages/llvm/examples/rust.ll
rustc --crate-type=lib --edition=2021 --emit=llvm-bc \
  -C opt-level=1 -C panic=abort languages/llvm/examples/programs.rs \
  -o languages/llvm/examples/rust.bc
/tmp/llvmfont-env/bin/python languages/llvm/build_examples.py
~~~

Regenerate the optimized intrinsic examples with the same frontends:

~~~sh
clang -S -emit-llvm -O1 -fno-vectorize -fno-slp-vectorize \
  languages/llvm/examples/intrinsics.c -o languages/llvm/examples/clang-intrinsics.ll
clang -c -emit-llvm -O1 -fno-vectorize -fno-slp-vectorize \
  languages/llvm/examples/intrinsics.c -o languages/llvm/examples/clang-intrinsics.bc
rustc --crate-type=lib --edition=2021 --emit=llvm-ir \
  -C opt-level=1 -C panic=abort languages/llvm/examples/intrinsics.rs \
  -o languages/llvm/examples/rust-intrinsics.ll
rustc --crate-type=lib --edition=2021 --emit=llvm-bc \
  -C opt-level=1 -C panic=abort languages/llvm/examples/intrinsics.rs \
  -o languages/llvm/examples/rust-intrinsics.bc
~~~

Regenerate the saturation/state/pointer examples similarly:

~~~sh
clang -S -emit-llvm -O1 -fno-vectorize -fno-slp-vectorize \
  languages/llvm/examples/state.c -o languages/llvm/examples/clang-state.ll
clang -c -emit-llvm -O1 -fno-vectorize -fno-slp-vectorize \
  languages/llvm/examples/state.c -o languages/llvm/examples/clang-state.bc
rustc --crate-type=lib --edition=2021 --emit=llvm-ir \
  -C opt-level=1 -C panic=abort languages/llvm/examples/state.rs \
  -o languages/llvm/examples/rust-state.ll
rustc --crate-type=lib --edition=2021 --emit=llvm-bc \
  -C opt-level=1 -C panic=abort languages/llvm/examples/state.rs \
  -o languages/llvm/examples/rust-state.bc
~~~

Regenerate callback and constructor examples:

~~~sh
clang -S -emit-llvm -O1 -fno-vectorize -fno-slp-vectorize \
  languages/llvm/examples/dispatch.c -o languages/llvm/examples/clang-dispatch.ll
clang -c -emit-llvm -O1 -fno-vectorize -fno-slp-vectorize \
  languages/llvm/examples/dispatch.c -o languages/llvm/examples/clang-dispatch.bc
clang -S -emit-llvm -O0 languages/llvm/examples/constructors.c \
  -o languages/llvm/examples/clang-constructors.ll
clang -c -emit-llvm -O0 languages/llvm/examples/constructors.c \
  -o languages/llvm/examples/clang-constructors.bc
rustc --crate-type=lib --edition=2021 --emit=llvm-ir \
  -C opt-level=1 -C panic=abort languages/llvm/examples/dispatch.rs \
  -o languages/llvm/examples/rust-dispatch.ll
rustc --crate-type=lib --edition=2021 --emit=llvm-bc \
  -C opt-level=1 -C panic=abort languages/llvm/examples/dispatch.rs \
  -o languages/llvm/examples/rust-dispatch.bc
~~~

The alias examples additionally use Rust at two optimization levels:

~~~sh
rustc --crate-type=lib --edition=2021 --emit=llvm-ir \
  -C opt-level=1 -C panic=abort languages/llvm/examples/aliases.rs \
  -o languages/llvm/examples/rust-aliases.ll
rustc --crate-type=lib --edition=2021 --emit=llvm-bc \
  -C opt-level=1 -C panic=abort languages/llvm/examples/aliases.rs \
  -o languages/llvm/examples/rust-aliases.bc
rustc --crate-type=lib --edition=2021 --emit=llvm-ir \
  -C opt-level=2 -C panic=abort languages/llvm/examples/aliases.rs \
  -o languages/llvm/examples/rust-merged-aliases.ll
rustc --crate-type=lib --edition=2021 --emit=llvm-bc \
  -C opt-level=2 -C panic=abort languages/llvm/examples/aliases.rs \
  -o languages/llvm/examples/rust-merged-aliases.bc
~~~

Aggregate ABI examples use the host Clang ABI, an x86-64 Clang variant, and Rust:

~~~sh
clang -S -emit-llvm -O1 -fno-vectorize -fno-slp-vectorize \
  languages/llvm/examples/abi.c -o languages/llvm/examples/clang-abi.ll
clang -c -emit-llvm -O1 -fno-vectorize -fno-slp-vectorize \
  languages/llvm/examples/abi.c -o languages/llvm/examples/clang-abi.bc
clang -target x86_64-apple-macosx11.0.0 -S -emit-llvm -O1 \
  -fno-vectorize -fno-slp-vectorize languages/llvm/examples/abi.c \
  -o languages/llvm/examples/clang-byval.ll
clang -target x86_64-apple-macosx11.0.0 -c -emit-llvm -O1 \
  -fno-vectorize -fno-slp-vectorize languages/llvm/examples/abi.c \
  -o languages/llvm/examples/clang-byval.bc
rustc --crate-type=lib --edition=2021 --emit=llvm-ir \
  -C opt-level=1 -C panic=abort languages/llvm/examples/abi.rs \
  -o languages/llvm/examples/rust-abi.ll
rustc --crate-type=lib --edition=2021 --emit=llvm-bc \
  -C opt-level=1 -C panic=abort languages/llvm/examples/abi.rs \
  -o languages/llvm/examples/rust-abi.bc
~~~

Font rebuilding uses checked-in IR and needs neither frontend installed.
The example builder validates outputs, rebuilds forty-seven fonts/manifests, writes
`benchmarks/latest.json` and captures a full HarfBuzz before/after tape in
`benchmarks/max-trace.json`. Font bytes/manifests are deterministic with pinned
dependencies; timings are kept separately.
Independent-process tests also vary `PYTHONHASHSEED` to verify that overflow
flag handling cannot change font bytes or manifests through set iteration order.

## Validation

~~~sh
/tmp/llvmfont-env/bin/python -m pytest languages/llvm/tests -q
/tmp/llvmfont-env/bin/python -m pytest \
  languages/shared/tests languages/verilog/tests languages/wasm/tests -q
node --test languages/wasm/tests/test_playground.mjs \
  languages/verilog/tests/test_playground.mjs
node --test languages/llvm/tests/test_harfbuzzjs.mjs
~~~

The suite exhaustively checks all 65,536 input pairs for each 8-bit arithmetic,
bitwise, shift and division operation and all comparison predicates using the
test-only circuit evaluator. HarfBuzz tests cover random 1/8/16/32/64-bit
arithmetic. All integer operations at 32/64 bits are checked against LLVM MCJIT.
Clang native functions provide references for maximum, mixing, loops and dynamic
array memory. Tests cover Clang/Rust IR and bitcode, recursion, phi snapshots,
aggregate values, caller memory, poison/freeze/select, attributes, rejection
and bounds. Disabled GSUB cannot yield a decoded result. An optional test
regenerates Rust IR when `rustc` is installed. The intrinsic tests also compile
the optimized Rust examples as a native shared library using the standard
library (`--cfg native_reference`) and compare `.ll`/`.bc` font results against
it. Set `RUSTC` to an explicit compiler path if necessary. All six overflow
intrinsics receive exhaustive 8-bit tests and native LLVM differential checks
at 1/16/32/64 bits. Dynamic bulk-memory lengths are checked against native LLVM,
alongside lifetime restarts, overlap, zero-length copies, argument contracts,
poison propagation and rejected global storage forms.
All six saturating add/sub/shift intrinsics receive exhaustive 8-bit checks and
native LLVM comparisons at 1/8/16/32/64 bits. Optimized C/Rust state programs
are tested through both `.ll` and `.bc` against native shared libraries. Further
checks cover fresh global initialization, cross-call effects, cyclic pointer
initializers, aggregate pointer copies, zeroing, unaligned memmove, dangling
pointer access and explicit representation limits.
Callback tests compare optimized Clang/Rust `.ll` and `.bc` against native shared
libraries, including copied tables and guarded global side effects. Constructor
priority ordering is compared with a native Clang-linked library and its loader;
MCJIT's constructor helper runs raw array order and is not used as a priority
oracle. Tests also cover function-pointer parameters/returns, `select`/`phi`,
void/aggregate callbacks, `fastcc`, null/poison/incompatible callees, fixed-point
target discovery, indirect recursion, section-based startup, constructor-installed
callbacks and startup fault/resource diagnostics.
Alias tests compare native LLVM with shared data/code identity, alias chains,
interior data offsets and cyclic relocations. Rust `-O1` and `-O2` builds are
tested as both `.ll` and `.bc` against native shared libraries, including alias
entry selection and `!callees`. Rejection tests cover unsupported alias forms,
metadata violations and alias depth bounds.
Aggregate ABI tests compare Clang/Rust struct results and callback results against
native shared libraries through `.ll` and `.bc`. The Clang x86-64 variant adds
`byval` entry and internal-call tests, compared with the same C values under the
native host ABI. Native LLVM checks hidden-copy identity/lifetime; other checks
cover pointer fields, padding, poison, guarded invalid buffers, ABI mismatches,
memory bounds and deterministic named types across repeated builds and failures.
Validation regressions cover 64-bit array lengths and aggregate limits before
expansion, quoted types and keyword-like string data, long zero-GEP lifetime
chains, and safe collection of failed parsing/verification tracebacks.
Symbol/layout regressions compare numbered globals, direct/indirect calls and
relocations with native LLVM through `.ll`/`.bc`, plus aliased constructors with a
native linked loader. Custom-layout tests cover scalar/pointer store spans,
aggregate alignment/stride, padding poison and global allocation padding. For
native comparison of custom layouts, LLVM first eliminates all memory accesses
under the original layout; host JIT code generation runs only after those
layout-dependent instructions and calls are gone.
Startup parsing regressions compare quoted global names and ELF/Mach-O initializer
tables against a native linked loader. Resource tests check source byte limits
at the exact boundary and reject oversized scalar/`byval` input interfaces early.
The forty-seven bundled fonts also execute in the independent browser HarfBuzz build
through the unchanged shared JavaScript register runtime.

[Benchmark results](benchmarks/latest.json) record build/shaping time, bytes,
glyphs, gates and lookups. The initial 32-bit maximum uses 98 gates, 426 glyphs,
99 lookups and 18,024 font bytes. Its 64 input bits represent 2^64 possible
argument pairs without enumeration. Timing varies with CPU, concurrent work
and HarfBuzz version.

## Further coverage investigations

Floating point still needs IEEE rounding, exceptional values and LLVM fast-math/
constrained-FP semantics implemented as circuits. Indirect calls now use closed
target sets and predicated dispatch; dynamically linked targets, weak aliases
and richer ABI variants remain outside the supported subset.
Next frontend extensions include additional widths, pointer-byte reinterpretation,
ifunc resolvers, destructors, external/library calls and broader ABI handling.

References: [LLVM 20.1 language reference](https://releases.llvm.org/20.1.0/docs/LangRef.html),
[LLVM UB manual](https://llvm.org/docs/UndefinedBehavior.html),
[llvmlite parsing](https://llvmlite.readthedocs.io/en/v0.46.0/user-guide/binding/modules.html).
