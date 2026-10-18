# Wasm-to-OpenType: local experimental prototype

This is a **working font generator**, not a general-purpose Wasm compiler.

## Scope

* Accepts one restricted WAT function with two i32 parameters, i32 result, and `local.get 0; local.get 1; i32.add` (named parameters accepted).
* Accepts one restricted binary Wasm code body with the same instructions.
* Generates a real OpenType GSUB font with 32 sequential carry propagation rounds (64 lookups), using ligature and multiple substitutions.
* Uses 18 glyphs, with input **glyph IDs**, not ordinary Unicode text. The API `encode(a,b)` returns the glyph-name stream to feed to HarfBuzz with an appropriate glyph-buffer interface. The generated font is deliberately not a direct text-input calculator.
* The resulting glyph sequence should be `s0`/`s1` least-significant-bit first, followed by a final `c0`/`c1` overflow glyph. Ignore the final carry for i32 wrapping.

## Build

`python compiler.py add.wat -o add32.ttf`

`python -m unittest discover -v`

## Execution model

Input: `c0 p[a0][b0] ... p[a31][b31]` (least-significant bit first).

For each of 32 ordered rounds:
1. Ligature GSUB combines `cX pAB` into `qABX`.
2. Multiple GSUB expands `qABX` into `s(A xor B xor X) c(majority(A,B,X))`.

This is a full-adder circuit implemented by actual shaping operations, not a precomputed table of 32-bit input/output combinations. Each small full-adder truth table is a reusable logic gate.

## Important limitations

* HarfBuzz runtime shaping was **not tested** here: neither `uharfbuzz` nor `hb-shape` is installed. FontTools parses and validates generated GSUB structure, but end-to-end runtime correctness is not yet established.
* Standard HarfBuzz APIs commonly take Unicode code points rather than arbitrary glyph names; a reliable glyph-input harness and a suitable textual encoding need implementation.
* No general Wasm stack-machine interpreter, function calls, branches, memory, traps, i64 or floating point.
* The binary reader validates only the code body pattern, not the full Wasm module type/export sections. It is not a general Wasm validator.
* WAT parsing is pattern-based, not a complete grammar.
* Real repository integration was blocked by GitHub DNS/network access.

This prototype is an initial isolated implementation, not completion of the requested deliverables.

## Continuation: integer frontend

`wasm_ir.py` adds a separate flat-instruction Wasm binary/WAT frontend and
Python stack-machine reference interpreter. It supports i32/i64 constants,
locals (get/set/tee), add/sub/mul/and/or/xor/shl/shr_s/shr_u/eqz and return.
The WAT reader accepts flat instructions, not folded WAT expressions.
The binary reader supports simple function type/function/code sections and
rejects unsupported opcodes. It is **not** a complete WebAssembly validator.

The **font backend remains limited to the canonical two-parameter i32.add**;
other frontend instructions are not compiled to GSUB yet. HarfBuzz runtime
execution remains unverified. No claim of general Wasm-to-font execution is made.

Run tests: `python -m unittest discover -v`.

## Language feature extension (experimental)

`wasm_features.py` adds a **reference-side**, fuel-bounded interpreter for
structured `block`, `loop`, `if`/`else`, `br`, `br_if`, `br_table`, direct
`call`, `drop`, `select`, comparisons, unsigned/signed division and remainder,
and rotates. `extend_frontend.py` registers binary opcodes; flat WAT accepts
most of these operations. Block result types, imported functions, memory,
globals, tables, and folded WAT remain unsupported. The interpreter does not
perform full Wasm static type validation. No new operations have been lowered
to GSUB; the font backend remains addition-only. Run `python -m unittest discover -v`.

## Bounded memory and globals (reference-side)

`wasm_state.py` adds a bounded, little-endian linear memory and typed mutable
integer globals. `wasm_features.run(..., state=MachineState(...))` supports
`i32/i64.load`, `store`, narrow signed/unsigned loads and stores, `memory.size`,
`memory.grow`, `global.get`, and `global.set`. Binary instruction decoding
supports their immediates; **module memory/global declarations and data
segments are not yet parsed or instantiated**. Supply state explicitly.
Memory defaults to one 64-KiB page, capped at 16 pages; bounds failures trap.
This is a Python reference implementation, **not GSUB font execution**.

### Module-level binary support (next iteration)

`wasm_module.load_binary(path)` loads core Wasm binary modules with one bounded
linear memory declaration, constant-initialized i32/i64 globals, active data
segments, and export metadata. `module.instantiate()` creates a fresh
`MachineState` with initialized data and globals. Invoke the existing reference
VM with `run(module.functions, function_index, args, state=module.instantiate())`.

Limits: imported memories/functions/globals, passive data, multiple memories,
non-constant initializers, and memory64 are rejected. Memory is bounded to 256
pages. This is **reference VM support**, not native GSUB execution. The font
backend remains limited to its existing addition demonstration.

## October 2026 continuation

The font backend now accepts canonical two-parameter `i32.and`, `i32.or`, and
`i32.xor` functions in addition to `i32.add`. Each uses 32 independent
bit stages with GSUB ligature + multiple substitutions (64 lookups), not a
whole-word truth table. `build(path, operation)` selects the circuit.

`Module.invoke(export_name, args, state=..., fuel=...)` connects parsed
binary exports to the reference interpreter. Supply a shared `state` from
`instantiate()` to preserve mutable globals and memory across invocations.

**Verification boundary:** Tests verify font compilation and GSUB table
structure; HarfBuzz shaping correctness is not established by these tests.
The GSUB encoding currently uses glyph names and requires an external
encoding/shaping harness. Control flow, memory, calls, and other arithmetic
still run only in the reference VM. This is not yet a general Wasm-to-font
compiler. No repository writes or commits are performed.

## Verified HarfBuzz GSUB execution (October 2026)

`hb_runtime.py` invokes the system `libharfbuzz.so.0` through ctypes and shapes
Private Use Area Unicode characters mapped to the internal operand glyphs.
`test_harfbuzz.py` executes actual GSUB for `i32.add`, `i32.sub`, `i32.and`,
`i32.or`, and `i32.xor`. Subtraction uses two's-complement addition with
inverted second operand and initial carry one. The backend has 64 lookups,
18 glyphs, and a 32-stage carry/bit propagation network per font.

Run `python -m unittest discover -v` in this directory. The HarfBuzz test
requires a system `libharfbuzz.so.0` shared library. 24 tests pass locally,
including 140 end-to-end arithmetic cases. For input use `encode(a,b,op)`;
`hb_runtime.run(font_path, glyph_tokens)` returns output glyph names, 32
least-significant-bit-first `s0`/`s1` plus final carry.

**Not yet complete:** GSUB currently supports only canonical two-argument
single-operation functions. Arbitrary stack-machine programs, control flow,
function calls, memory, globals, 64-bit arithmetic and trap representation
remain reference-runtime-only or unsupported. Binary/WAT parsing remains
restricted. No whole-program enumeration is used by the five GSUB circuits.

### October 2026: native i64 circuits

The GSUB backend now accepts canonical two-parameter `i64` functions for `add`, `sub`, `and`, `or`, and `xor` in addition to `i32`. Each 64-bit font uses 128 ordered lookups (two per bit). `build(path, op, width=64)` generates the font and `encode(a,b,op,width=64)` produces its bit-encoded input. HarfBuzz differential tests cover wraparound and randomized values. The backend still **does not** lower arbitrary instruction sequences, locals, branches, memory, or calls into GSUB. Other Wasm operations remain interpreter-only.

### October 2026: native GSUB zero tests

The compiler additionally recognizes canonical `i32.eqz` and `i64.eqz`
functions containing `local.get 0` followed by the matching `eqz` opcode.
`build(path, 'eqz', width)` generates a genuine ordered GSUB reduction:
its carry token accumulates the OR of all operand bits, and the final
`c0` means the operand was zero. `decode_eqz` converts the final carry to
the WebAssembly Boolean result (an i32). The intermediate `s0` glyphs are
internal tokens, **not** a standard Wasm i32 result encoding. Input encoding
still takes place outside the font, and full Wasm stack lowering is pending.

Run `python -m unittest discover -q` to exercise the native shaping tests.

### Native equality comparisons (October 2026)

`i32.eq`, `i32.ne`, `i64.eq`, and `i64.ne` now have actual HarfBuzz-executed GSUB reduction circuits, in addition to `eqz`. Each bit compares its two input bits via XOR, and a running accumulator tracks whether any bit differs. `decode_comparison(shaped_tokens, width, operation)` reads the final accumulator as a 0/1 result. Input encoding is provided by `encode(a,b,operation,width)`. These circuits use 2×width lookups and do **not** enumerate full input combinations.

The compiler's accepted source pattern is still a single canonical operation over direct parameters; these improvements do not implement general composable Wasm stack execution. The result of Wasm `eq`/`ne` is `i32`, even for `i64` operands. Test with `python -m unittest discover -q`.

### Native GSUB relational comparisons (October 2026)

The single-operation GSUB backend now also implements `i32` and `i64`
`lt_u`, `le_u`, `gt_u`, `ge_u`, `lt_s`, `le_s`, `gt_s`, `ge_s`.
Each uses width-dependent borrow propagation with a sign-bit adjustment
in the final stage for signed ordering. The resulting boolean is decoded
from the final accumulator glyph, as for equality. This remains a restricted
single-operation backend, not general Wasm program lowering.
Run `python -m unittest discover -q` for HarfBuzz differential tests.

### Latest extension: native counting instructions

`i32.clz`, `i32.ctz`, `i32.popcnt`, `i64.clz`, `i64.ctz`, and
`i64.popcnt` are now accepted by the restricted frontend and generated
as real GSUB circuits. Their output is a unary `s0`/`s1` stream,
converted to an integer by `compiler.decode_count`; the conversion
counts result glyphs and does not inspect original operand values.
`clz` reverses bit order in the input encoder to process the MSB first.
These instructions are still limited to canonical single-operation
functions; general stack-machine composition remains unsupported.

Run `python -m unittest discover -q` to verify the new HarfBuzz tests.

### October 2026 continuation

The bounded Wasm reference frontend now supports `i32.rotl`, `i32.rotr`,
`i64.rotl`, and `i64.rotr` in both flat WAT and binary Wasm. Rotation counts
are reduced modulo the operand width, including counts >= width. Binary
section parsing rejects duplicate, out-of-order and unknown standard section
IDs, and invalid function type indices. These are **reference-interpreter
features only**: the OpenType backend still does not compile rotations or
arbitrary multi-instruction programs. The binary parser is not yet a complete
WebAssembly validator.

### Integer conversion extension (October 2026)

The WAT and binary parsers and both Python reference execution paths support
`i32.wrap_i64`, `i64.extend_i32_s`, `i64.extend_i32_u`,
`i32.extend8_s`, `i32.extend16_s`, `i64.extend8_s`,
`i64.extend16_s`, and `i64.extend32_s`.
These operations **are not yet lowered to GSUB**. The font backend remains
restricted to its explicitly supported canonical arithmetic/comparison/counting
circuits. Run `python -m pytest -q` for the full regression suite.

### Composable GSUB stage (experimental)
`wasm_pipeline.build_not_pipeline(path, operation, width)` now composes an
existing native binary circuit (`add`, `sub`, `and`, `or`, `xor`) with a **second
native GSUB lookup** implementing bitwise NOT on the first stage's output.
`decode_not` reads the final `t0`/`t1` glyphs. Both 32- and 64-bit widths
are tested against a Python arithmetic oracle via actual HarfBuzz shaping.
This is a limited two-stage pipeline, **not** arbitrary Wasm stack lowering.

### Repeated native GSUB stages

`wasm_pipeline.build_not_pipeline(path, operation, width, not_stages=N)`
now supports N >= 0, rather than exactly one bitwise inversion. Every
inversion is a separate ordered GSUB lookup that reads glyphs from the
preceding stage. `decode_not(tokens, width, not_stages=N)` validates the
final stage's glyph alphabet. Supported initial binary operations remain
add/sub/and/or/xor, with widths 32 and 64. This is **not** yet general
WebAssembly instruction lowering or arbitrary multi-operand composition.

Run `python -m unittest discover -q` to validate the backend using HarfBuzz.

### Symbolic Wasm stack lowering (new)
`wasm_lowering.compile_module(source, font_path)` compiles a restricted WAT or
binary Wasm function with two same-width integer parameters, one result,
local.get/set/tee, a supported binary operation, and repeated XOR-with-all-ones
stages. The intermediate value stays in the GSUB pipeline and is not computed
by Python. Unsupported expression trees fail closed with NotImplementedError.
See `test_wasm_lowering.py` for executable examples and HarfBuzz verification.
This is not yet general composition of arbitrary Wasm operators.

### Symbolic identity lowering (October 2026)

The restricted native stack lowering now simplifies fixed-width identity operations
(`x + 0`, `0 + x`, `x ^ 0`, `x | 0`, `x & -1`, `x - 0`) and
annihilators (`x & 0`, `x | -1`) without evaluating runtime inputs.
This permits additional Wasm instructions around a supported binary GSUB
operation while retaining native HarfBuzz execution. General binary-to-binary
composition, arbitrary constants, branches, and memory are not yet supported
by this lowering. Run `python -m unittest discover -q` to verify.

### Operand-order lowering (October 2026)
The symbolic lowering pass now recognizes reversed parameter order for native
`i32`/`i64` add, sub, and, or, xor circuits. The compiled entrypoint encodes
operands in the order required by the GSUB circuit; notably `b - a` remains
noncommutative and is tested through HarfBuzz. The inversion pipeline preserves
operand-order metadata. This is a restricted lowering optimization, not general
register-based GSUB execution.

### Native symbolic outputs (October 2026)

The restricted GSUB lowerer now accepts final symbolic outputs that are
`local.get 0`, `local.get 1`, zero, or all-ones (for both i32 and i64).
These are realized with actual GSUB XOR circuits: parameter passthrough
uses XOR with zero; zero uses XOR of equal runtime operands; all-ones adds
an inversion lookup. The input encoder selects the appropriate operands;
it does not calculate the output value. Other constant results remain
unsupported. This is not general register-based execution.

### Native parameter complement (latest local iteration)

The restricted symbolic lowering now recognizes `local.get N; i32.const -1;
i32.xor` (and its i64 counterpart), including reversed XOR operands.
The font executes an identity XOR circuit and a real GSUB inversion stage.
This is not general multi-register arithmetic. `test_param_complement.py` runs
both widths and parameter orders through HarfBuzz.

## 2026-10-09 native literal circuits

Native GSUB XOR circuits now accept arbitrary fixed-width literal outputs and XOR of either parameter with a literal. Constants are encoded as input glyph bits; the XOR gates are evaluated by HarfBuzz. This is not a general multi-register backend.

### Literal binary operations (2026-10-09)
The restricted symbolic GSUB lowering now supports `i32`/`i64` parameter-with-literal `add`, `sub`, `and`, and `or`, including reversed subtraction (`constant - parameter`). Literal bits are encoded as glyph inputs; the operation itself is performed in HarfBuzz by the native circuit. This does not yet permit arbitrary intermediate-to-intermediate binary operations.

### Chained literal XOR fusion (October 2026)

The restricted native lowering now combines `param ^ C1 ^ C2` into a single
parameter/literal XOR GSUB circuit, including reversed operand order and both
integer widths. It also simplifies `(param ^ C) ^ param` to the literal C.
The parameter-dependent XOR is performed by HarfBuzz; constant combination is
performed by the compiler. Arbitrary binary intermediate composition remains
unsupported and fails closed.

### Affine arithmetic fusion (October 2026)

The restricted native lowering recognizes wrapping addition/subtraction chains
containing one dynamic parameter and any number of integer constants. It
normalizes them to `parameter + C` or `C - parameter` modulo 2^32 or 2^64,
then emits the existing real GSUB arithmetic circuit. Intermediate operations
are algebraically specialized by the compiler; they are **not** independently
executed in the font. Arbitrary combinations of two dynamic intermediates,
branches and memory are still not supported by native GSUB lowering.

Run `pytest -q test_affine_fusion.py` for direct HarfBuzz differential tests.

### Native repeated operands and shift-left (October 2026)

The restricted native lowering accepts `local.get N; local.get N; i32.add`
(and the i64 equivalent), executing both input lanes of the GSUB adder with
one runtime parameter. It also accepts `local.get N; i32.const 1; i32.shl`
(and i64), lowering shift-left-by-one to wrapping addition `x+x`. A zero
shift is an identity. These are genuine font computations, not host-side
input/output enumeration. Arbitrary dynamic shifts and general multi-register
arithmetic composition remain unsupported and are rejected explicitly.

### Affine cancellation (latest local iteration)

The symbolic lowering pass recognizes cancellation of two affine expressions
of the same dynamic parameter, including `(a + 13) - (a + 6)` and
`(a + 13) + (6 - a)`, for i32 and i64 with wrapping arithmetic. These
expressions reduce to constants at compile time; the resulting constant output
is still emitted by the native GSUB XOR circuit. This does **not** implement
general dynamic multi-register arithmetic. New HarfBuzz tests cover both widths.

### Paired affine lowering (latest)

The native lowering pass now combines two affine expressions referring to the
same parameter, including cancellation to constants and coefficients +/-1.
A coefficient of +2 is supported only when the constant offset is zero, using
the native GSUB addition circuit. Unsupported coefficients or offsets fail
closed with `NotImplementedError`; there is no host-side runtime evaluation.
`test_affine_pairs.py` exercises both integer widths through HarfBuzz.

### Native constant multiplication specialization (October 2026)

The restricted symbolic GSUB lowering supports `i32.mul` and `i64.mul` with
constant factors `0`, `1`, `2`, and `-1`, in either operand order. Factors are
specialized algebraically at compile time: `2*x` executes the existing GSUB
adder with duplicated input lanes; `-x` executes the GSUB subtraction circuit
with a zero left operand. Factors 0 and 1 use existing constant/passthrough
circuits. Arbitrary dynamic multiplication and other constant factors remain
unsupported and fail closed. Tests: `test_native_mul_specialization.py`.

### Constant bit-operation lowering (October 2026)

`wasm_lowering` now folds constant `shr_u`, `shr_s`, `rotl`, `rotr`,
`clz`, `ctz`, `popcnt`, and `eqz` expressions (for same-width integer
results). It also recognizes zero-distance shifts/rotations of dynamic
parameters. Constant results are emitted using the native GSUB constant-output
circuit; **the bit operation itself is performed at compile time**, not in
HarfBuzz. Dynamic nonzero shifts and dynamic counting remain unsupported by
this particular lowering path and fail closed.
