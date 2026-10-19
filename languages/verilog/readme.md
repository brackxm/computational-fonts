# Verilog → OpenType GSUB

Compile a two-state combinational Verilog design into an OpenType
font. Change input ports at runtime; the font computes the output ports during
**one HarfBuzz shaping call**. This is a bounded subset, not a full Verilog
simulator or synthesis tool. There is no clock, event loop or persistent state.

The frontend uses the [shared bit-circuit backend and register
runtime](../shared/) alongside WebAssembly. JavaScript and Python only serialize
inputs and decode shaped registers. They do not evaluate the source circuit at
invocation time.

## Browser playground

From the repository root:

```sh
python3 -m http.server 8000
```

Open <http://localhost:8000/languages/verilog/playground.html>. Thirteen bundled
examples include an eight-bit adder with carry, an ALU, a four-by-four-bit
multiplier, bit routing with reductions, signed arithmetic/shifts, and a
parameterized adder/mask circuit. New examples demonstrate procedural ALU logic,
a hierarchical carry-chain adder, dynamic selects/slice updates, and signed versus
unsigned division/remainder. Population count, generated XOR lanes, and a
function with a small array demonstrate compilation-time expansion. Edit decimal, `0x` hexadecimal or
`0b` binary input values. Inputs wrap to their declared port widths; negative
integers supply their low two's-complement bits. Decimal outputs follow the port's
signedness; hexadecimal and binary always show the raw bits.

Source is shown for reference. To change a circuit, compile it locally and load
its matching `.ttf` and `.json` together under **Load your own compiled circuit**.
The browser verifies the font hash and glyph layout. Files stay local. Use
localhost or HTTPS, with a browser supporting module workers, BigInt and
WebAssembly. The bundled [HarfBuzz engine and licenses](../shared/vendor/harfbuzzjs/)
are shared with the Wasm playground; no CDN or server compiler is used.

## Build and run

Use Python 3.10+ and FontTools. Running fonts from Python additionally requires
the system HarfBuzz shared library (`brew install harfbuzz` on macOS or
`sudo apt install libharfbuzz0b` on Debian/Ubuntu).

```sh
python3 -m venv /tmp/verilog-font-venv
. /tmp/verilog-font-venv/bin/activate
python -m pip install -r languages/verilog/requirements.txt
python languages/verilog/build.py languages/verilog/examples/adder.v -o /tmp/adder.ttf
python languages/verilog/run.py /tmp/adder.ttf 255 1
# sum=256 (0x100, 9'b100000000)
```

Inputs are supplied in their declaration order. Keep the generated JSON manifest
beside the TTF; it contains port names, widths, source, register layout and the
font's SHA-256. The CLI accepts one or more source files, compiled together.
Omitting `-o` writes beside the first source. `--max-gates` changes the
default 12,000-gate compilation budget (maximum 32,000, subject to font capacity).

Rebuild all bundled fonts and the catalog:

```sh
python languages/verilog/build_examples.py
```

## Parameters and elaboration

Module `parameter` declarations work in a `#(...)` header or in the module body.
`localparam` declares a derived constant in the body. Constant expressions can
refer to earlier parameters; references before declaration, cycles, duplicate
names and references to runtime signals are rejected. Every parameter is
validated, including unused declarations.

```verilog
module parameter_adder #(
  parameter WIDTH = 8,
  parameter [WIDTH-1:0] MASK = 8'hA5
)(input [WIDTH-1:0] a, b,
  output [WIDTH:0] sum,
  output [WIDTH-1:0] masked);
  wire [WIDTH-1:0] mixed = a ^ b;
  assign sum = a + b;
  assign masked = mixed & MASK;
endmodule
```

Specialize a module at build time with repeatable `-P NAME=VALUE` options:

```sh
python languages/verilog/build.py languages/verilog/examples/parameter_adder.v \
  -P WIDTH=16 -P "MASK=16'h0ff0" -o /tmp/parameter-adder.ttf
python languages/verilog/run.py /tmp/parameter-adder.ttf 65535 1
```

This builds 16-bit input ports and a 17-bit sum. The example also returns the
masked XOR and a copy of `a` with its top bit toggled. Overrides accept a decimal
integer or sized literal (including signed forms such as `8'shff`), with optional
unary `+`/`-`. Unknown names,
repeated CLI overrides and attempts to override a `localparam` are errors.
Python callers can pass the same values in a `parameters` mapping to `build()`
or `compile_source()`. Parameters are fixed in the generated font; changing them
requires rebuilding. The manifest records effective values as decimal strings
to preserve all 64 bits, and the playground displays them under font details.

Ranges, select indices and replication counts accept constant expressions such
as `[WIDTH-1:0]`, `data[(WIDTH/2)-1:0]`, `{(WIDTH/2){data[1:0]}}` and
`[$clog2(DEPTH)-1:0]`. Alongside the existing expression operators, compile-time
expressions support `/`, `%` and `$clog2`. Division truncates toward zero; an
evaluated zero divisor is rejected. Constant ternaries evaluate only the chosen
branch, allowing guarded divisions. `$clog2(0)` and `$clog2(1)` return zero;
negative arguments are unsupported.

Constant and runtime arithmetic use fixed-width Verilog sizing and signedness.
Unsized decimal literals are signed 32-bit values, with each literal limited to
0–2,147,483,647; unary minus produces negative values. An untyped parameter
inherits its expression's width and signedness; a ranged parameter is unsigned
unless declared `signed`. A `parameter signed` without a range infers its width
from the expression. Overrides determine the inferred width/type before the
explicit declaration is applied. `/` and `%` also work in runtime expressions;
`$clog2` remains restricted to elaboration.

Fonts contain original empty machine-glyph outlines, named **Verilog GSUB
Registers**. They use the shared `wasm-gsub-registers-v1` tape ABI with arbitrary
integer widths, plus `language: verilog` and `combinational-v2` metadata. Each
input/output has a Boolean `signed` flag. The runners also accept existing
`unsigned-combinational-v1` manifests with unsigned ports. Python `NativeFont`
returns raw unsigned bit patterns; the Verilog CLI and playground interpret the
port flags for decimal display.
They are not display fonts: ordinary text rendering and ODT specimens do not
display their results. Use the provided runtime or browser playground.

## Supported subset

```verilog
module adder(input [7:0] a, b, output [8:0] sum);
  assign sum = a + b;
endmodule
```

ANSI-style `input`/`output` ports with optional `wire`, `reg` (outputs only)
and `signed` qualifiers, scalar or descending `[N:0]` ranges, internal `wire`/`reg`
declarations, continuous `assign`, and combinational `always @*` blocks are
supported. Multiple names per declaration, comma-separated assignments and wire
initializers (`wire [7:0] mixed=a^b;`) work. Identifiers are case-sensitive; both
`//` and `/* ... */` comments are accepted. Declarations and drivers resolve by
dependencies rather than source order.

Each output and internal signal bit must have exactly one driver. Static
assignments to disjoint slices may come from different continuous assignments
or different procedural blocks. Overlaps, undriven bits, driven inputs,
undeclared nets and combinational cycles are errors, including unused logic.
Bit dependencies are checked individually, so `y[1]=y[0]` is accepted when
`y[0]` has an independent source. Structural wiring resolves only the selected
bits; arithmetic operands, function arguments and captured procedural values
conservatively depend on whole operands during feedback checks.

| Expressions | Supported syntax |
| --- | --- |
| Sized constants | `1'b1`, `8'o17`, `8'd42`, `16'hbeef`, `8'shff`, `8'sd127`, with underscores |
| Decimal/parameter constants | `1`, `-1`, `MASK`, `WIDTH[7:0]` |
| Arithmetic | `+`, `-`, `*`, `/`, `%`; unary `+` and `-` |
| Bitwise | `~`, `&`, `|`, `^`, `~^`, `^~` |
| Logical | `!`, `&&`, `||` |
| Comparisons | `==`, `!=`, `<`, `<=`, `>`, `>=` |
| Shifts | `<<`, `>>`, `<<<`, `>>>`; dynamic counts are not masked |
| Signedness casts | `$signed(expr)`, `$unsigned(expr)`; retain the operand's width |
| Selection | `condition ? yes : no`, including nested ternaries |
| Reductions | unary `&`, `~&`, `|`, `~|`, `^`, `~^`, `^~` |
| Bit/part selects | `data[i]`, `data[WIDTH-1:0]`, `data[i +: 4]`, `data[i -: 4]`; indexed widths are constant |
| Concatenation/replication | `{a,b}`, `{4{a}}`, `{COUNT{a,b}}`; constant counts |
| Grouping | Parentheses with Verilog operator precedence |

Sized constants truncate to their specified size. Assignment width propagates
through arithmetic, bitwise operators, shifts and ternary branches before final
truncation. This preserves the carry in the adder above and the full product in
the multiplier example. All arithmetic wraps at the applicable width.

When all operands of an arithmetic/bitwise/comparison operation are signed,
shorter operands sign-extend. Mixing signed and unsigned operands makes the
operation unsigned and zero-extends operands before evaluating it. The two
ternary result branches follow the same rule. A signed destination does not
change the signedness of its right-hand expression. Bit/part selects and
concatenations are unsigned, even when they contain signed signals.

`>>>` fills from the sign bit when the left expression is signed, including any
outer expression context; otherwise it fills with zero. `>>` always fills with
zero. `<<<` behaves like `<<`. Counts at least as large as the expression width
produce all fill bits; negative signed counts have their unsigned bit-pattern
value and are not masked.

Comparisons, logical operators and reductions produce an unsigned bit.
Concatenation operands, shift counts, ternary conditions and cast operands use
their own widths. Raw unsized literals cannot supply an indefinite-width
concatenation operand; use a sized literal or an explicit cast. A declared wire
is a width and signedness boundary: an eight-bit wire discards carry before a
later nine-bit output reads it. `$signed(a+b)` also evaluates `a+b` at its own
width before extending the result.

For example, the bundled signed circuit preserves the complete signed product:

```sh
python languages/verilog/build.py languages/verilog/examples/signed_math.v -o /tmp/signed.ttf
python languages/verilog/run.py /tmp/signed.ttf -128 3 2
# sum=-125, product=-384, shifted=-32, less=1 (plus hexadecimal/binary bits)
```

## Runtime division and remainder

`/` and `%` accept signed and unsigned runtime operands at widths 1–64. They use
the same expression/assignment sizing rules as other arithmetic: operands extend
before evaluation, mixed signedness selects unsigned arithmetic, and final
results truncate to their destination. Quotients truncate toward zero. A signed
remainder has the dividend's sign, or is zero; changing the divisor's sign does
not change the remainder.

Signed overflow wraps at the expression width. For example, eight-bit signed
`-128 / -1` produces the bit pattern for `-128`, and `-128 % -1` produces zero.
A nine-bit assignment context first extends both operands and produces positive
`128` instead. The frontend does not apply WebAssembly's signed-overflow trap.

```sh
python languages/verilog/build.py languages/verilog/examples/division.v -o /tmp/division.ttf
python languages/verilog/run.py /tmp/division.ttf -23 5
# quotient=-4, remainder=-3, unsigned_q=46, unsigned_r=3 (plus raw bits)
```

The font computes an `integer_divide_by_zero` trap flag. An evaluated `/` or `%`
with a zero divisor fails the invocation instead of returning bits for X. The
flag remains active for identities such as `a/a` or `0/a` when `a` is zero.
Ternary/procedural branches and short-circuited logical operands guard the check:

```verilog
assign quotient = divisor ? dividend / divisor : 8'sd0;
```

A runtime expression with a known zero divisor can appear in a guarded branch;
it reports an error only if that branch is evaluated. Compile-time parameter,
range and other elaboration expressions still reject an evaluated zero divisor
at build time. As with dynamic selects, this is strict two-state checking;
continuous wires are evaluated independently even if an output branch does not
use them.

Division reuses the shared unsigned divider with frontend-specific sign
handling. `/` and `%` with identical effective operands, width and signedness
share one circuit. Constant powers of two use shifts/bias and bit routing;
non-power-of-two constants use the shared bounded-remainder divider. Structural
zero/sign extension can narrow a divider while preserving the extra positive
`MIN / -1` result bit in a wider context. These decisions depend on source/wire
structure, never runtime input values.

The existing **12,000-gate default budget** covers a single full 64-bit dynamic
quotient/remainder pair, including signed operation. Independent dividers add
to the design's cost. Set `--max-gates N` (or `max_gates=N` in Python) to choose
a budget up to 32,000; OpenType capacity also applies. Exceeding the budget fails
compilation. Neither runtime uses a host-language arithmetic fallback.

## Combinational procedural blocks

`always @*` and `always @(*)` support blocking `=`, `begin`/`end`, `if`/`else`,
and plain `case` with comma-separated labels and one optional `default`.
Procedural targets must be `reg`; continuous and instance output targets must
be `wire`. A `reg` in this subset describes a combinational variable with no
persistent state.

```verilog
module choose(input [7:0] a, b, input select, output reg [8:0] y);
  always @* begin
    y = a + b;
    if (select) begin
      y = y + 1;
      y[0] = 1'b0;
    end
  end
endmodule
```

Blocking assignments capture the current values immediately, including at
width/signedness boundaries. Every bit owned by a block must be assigned on
every control-flow path before exit or a read. Defaults followed by conditional
updates work. Reads before definite assignment and incomplete assignments are
rejected as feedback/latch inference. The analysis is conservative: it does not
prove correlations between separate conditions. A `case` needs a default or
constant labels that cover every selector value. All labels participate in
Verilog case sizing; the first matching item wins.

Assignments can target whole variables, static slices, dynamic bits/indexed
slices, or concatenations of these. RHS values and dynamic target indices are
captured before any target bits change. Static overlapping elements in an
assignment concatenation are rejected.

## Bounded loops and generate

Procedural `for` loops use a declared `integer` iterator and blocking assignments
in the header. Initial values, conditions and steps must depend only on
parameters and enclosing loop iterators. The compiler simulates the fixed-width
32-bit iterator and unrolls the body, with at most **64 iterations per loop**.
Runtime-dependent bounds, repeated iterator values and assignments to an
iterator inside its body are rejected. Nested loops may use different iterators.
The iterator's final value is visible after the loop, including a zero-iteration
loop. Every output still needs complete assignment on every path.

```verilog
integer i;
always @* begin
  count = 0;
  for (i = 0; i < 8; i = i + 1)
    count = count + data[i];
end
```

`generate`/`endgenerate` accepts constant `if`/`else` and `for` loops using
separately declared `genvar` variables. These constructs also work directly at
module scope. Blocks may contain local wires, variables, parameters, functions,
instances and further generate constructs. Named blocks give readable instance
paths such as `lanes[3].u`; unnamed blocks receive `genblkN` names. Each iteration
has its own constant genvar value and declarations. Only the selected branch is
elaborated; all branches must have supported syntax. Generated declarations can
refer to enclosing signals and constants. Hierarchical references in source
remain unsupported.

```verilog
genvar g;
generate
  for (g = 0; g < WIDTH; g = g + 1) begin: lanes
    xor_cell u(.a(a[g]), .b(b[g]), .y(y[g]));
  end
endgenerate
```

There are no runtime loop counters or generate dispatchers. Expansion is limited
to 4,096 statements/scopes, 128 generated scopes and 16 generate nesting levels,
in addition to the existing signal, instance and gate budgets.

## Combinational functions and small arrays

Functions inline into the circuit. Both Verilog-2005 ANSI input declarations and
classic `input ...;` declarations are accepted, with optional `automatic`.
Return types may be scalar, packed `[N:0]`, signed, or `integer`. Function inputs
use their own expression widths before conversion to their declared widths;
return declarations form another width/signedness boundary. Local `reg`,
`integer` and small array variables support the same blocking control flow and
bounded loops as combinational blocks. Arguments and intermediate assignments
capture their current values before later updates.

```verilog
function [7:0] lookup(input [7:0] x, z, input [2:0] address);
  reg [7:0] words[0:3];
  begin
    words[0] = x;
    words[1] = z;
    words[2] = x ^ z;
    words[3] = ~x;
    lookup = words[address];
  end
endfunction
assign y = lookup(a, b, index);
```

Functions must assign every return bit on every path and initialize locals
before reading them. They can read enclosing parameters and call other pure
functions. Pass runtime signals explicitly as inputs; reading or modifying
module signals inside a function is rejected. Recursion, output/inout arguments,
timing, persistent state and tasks are unsupported. User functions are currently
supported in runtime expressions; parameter/range constants use the existing
constant-expression operators. At most 128 calls expand per design, with a
maximum call depth of eight. Unused function declarations are also validated.

One-dimensional unpacked internal `wire`/`reg` arrays have constant ascending or
descending ranges, including nonzero or negative bounds. Each array has at most
**16 words**, each 1–64 bits, with **1,024 array storage bits** across the flattened
design and active function locals. Each word counts toward the 128-signal limit.
Array ports, whole-array operations, multiple dimensions and memory state are
unsupported. An array word preserves its declared signedness; selecting packed
bits within a word produces an unsigned value.

Use `words[i]`, `words[i][bit]` or `words[i][offset +: WIDTH]`. A static index must
be in range. An evaluated dynamic read outside the array raises
`invalid_array_index`, guarded by the same branch rules as vector selects and
division. All 64 index bits participate in the bounds check. Out-of-range dynamic
writes are ignored; initialize every possibly written word before conditional
updates. Continuous array assignments require static word indices and complete,
nonoverlapping coverage of every declared word.

Procedural/function expansion stores at most 4,096 intermediate values or 65,536
intermediate bits. These are compile-time boundaries that preserve blocking
assignment order and bound compiler work. The generated font still executes a
fixed circuit in one shaping call.

## Module hierarchy

Source files may contain multiple module definitions. Named port connections
and named parameter overrides specialize each instance and flatten the complete
design into one font. Definitions may appear before or after their instances.

```sh
python languages/verilog/build.py top.v adder_cell.v --top top -o /tmp/top.ttf
```

`--top` (or `top=` in Python `build()`/`compile_source()`) selects the root module.
Without it, the unique module not instantiated by another definition is chosen;
ambiguous roots, unknown modules and recursive hierarchy are rejected. Connect
every port explicitly. `.unused()` is allowed for an output; inputs must have an
expression. Positional connections/overrides and hierarchical source references
are outside the subset. Each instance gets its own parameter/localparam scope;
parent constant expressions may supply its overrides. The manifest records
instance paths, module names and effective constants under `hierarchy`.

Input connection expressions evaluate at their own widths, then extend or
truncate to the receiving port. The source expression determines extension; the
receiving declaration determines how the resulting bits are interpreted inside
the module. Output ports likewise preserve their own width and signedness
before assigning to a parent wire or static slice. The bundled hierarchical
adder connects two four-bit cells through a carry wire and output slices.

## Dynamic selection and slice assignments

`data[i]`, `data[i +: WIDTH]` and `data[i -: WIDTH]` read signals or parameters.
The index may vary at runtime; an indexed part width must be a positive constant.
Ordinary `[high:low]` endpoints remain constant. Select results are unsigned.
All 64 index bits are checked, including the sign of signed indices.

The font computes an `invalid_select` trap flag when an evaluated dynamic read
would address any bit outside the vector. The runner reports an error instead
of returning bits for an X value. This is a strict two-state check, without
four-state propagation through later expressions. Ternary branches, procedural
branches and the right operand of `&&`/`||` guard reads that are not selected.
Continuous wires are independently evaluated even when an output does not use
them. A compile-time out-of-range select is rejected during compilation.

```verilog
always @* begin
  window = 0;
  if (index <= 5) window = data[index +: 3];
  patched = data;
  patched[index +: 3] = value;
end
```

Procedural dynamic writes require defaults for every potentially affected bit.
Out-of-range write bits are ignored; in-range bits of a partly overlapping
indexed write still update. Continuous assignments and instance output
connections support static slices/concatenations, with complete nonoverlapping
coverage; dynamic continuous targets are rejected because they leave bits
undriven.

Not supported: non-ANSI ports, four-state literals, `casex`/`casez`, case equality,
exponentiation, variable-width part selects,
nonblocking assignments, explicit event lists, `while`/`repeat`/`forever` loops,
block-local declarations, multidimensional arrays/array ports, persistent memories,
typed `integer` parameters, user constant functions, preprocessor directives,
primitives, tasks, clocks, delays, sequential logic, generate `case`, or
SystemVerilog extensions.
Unsupported syntax fails compilation rather than being treated as zero or
ignored.

## Diagnostics

Build errors report `filename:line:column`, the source line and a caret. Each
input file keeps its own location when several files are compiled together.
Parameter, width, driver and expansion errors retain the relevant source
location through elaboration. Gate-limit diagnostics identify `--max-gates` and
its maximum; loop, function, array and intermediate-value limits state the
specific budget to reduce. Font output copies and OpenType capacity can also
exceed a budget after expression compilation.

Python `build()` and `compile_source()` accept `source_name="circuit.v"`.
`SourceText.combine([(filename, text), ...])` retains multiple file locations.
Errors remain `ValueError` subclasses; resource failures also retain
`fontcircuit.gsub.circuit.ResourceLimit` compatibility.

## Bounds and execution

- Signal and expression widths: 1–64 bits. Wide intermediates, including a
  concatenation wider than 64 bits, are rejected even if later truncated.
- At most 128 signals across the flattened design, 128 parameters/localparams
  per module, 32 module definitions, 128 elaborated instances including the root,
  and 16 hierarchy levels. Combined source is limited to 65,536 characters and
  8,192 tokens.
- At most 64 iterations per loop, 4,096 expanded statements/scopes, 128 generated
  scopes, 16 generate nesting levels, 128 function calls, and eight call levels.
- Arrays: 16 words each, 1,024 storage bits across the design/active locals.
  Procedural captures: 4,096 values or 65,536 bits.
- Expression nesting/tree depth at most 64; excessive dependency nesting is
  rejected when it exceeds compiler capacity.
- Default gate budget 12,000, including canonical output copies. Even unused
  drivers are validated/lowered and count against compilation bounds.
- OpenType's glyph/lookup limits can reject a circuit below its gate budget.

Input bits initialize argument glyph cells; scratch cells begin uninitialized.
The compiler emits Boolean gates as GSUB contextual substitutions, with at most
16 local truth-table entries per gate. It never enumerates all input/output
pairs. Output bits are copied to fresh cells by the font, including constant and
identity outputs. The runtime verifies every scratch cell before decoding any
result. Disable font computation in the playground to see incomplete shaping
rejected instead of a plausible zero. There is no host-language fallback.

## Tests

From the repository root, after installing the requirements:

```sh
python -m pip install pytest
python -m pytest languages/verilog/tests -q
node --test languages/verilog/tests/test_playground.mjs
```

The Python suite builds fresh fonts and shapes them using the system HarfBuzz
library. It covers exhaustive small multiplication, bit routing, ALU behavior,
precedence, signed/mixed arithmetic and casts, assignment sizing, 64-bit ports,
shifts beyond the operand width,
constant/identity outputs, blocking assignment order, latch detection, hierarchy,
port sizing, dynamic select traps, partial writes, error/resource boundaries,
CLI execution, dynamic division/remainder, zero-divisor guards, gate budgets,
unrolled loops, generate scopes, pure functions, arrays and source diagnostics,
manifest verification and reproducible bundled assets. Node uses the actual bundled
browser HarfBuzz engine with independent arithmetic expectations. Both suites
check disabled-shaping failure. No Verilog simulator is required for these tests.

Optional differential tests compare shaped outputs against Icarus Verilog for
all examples, parameter overrides, constant sizing/signedness, mixed-width
operator compositions, procedural control flow, hierarchical port boundaries,
dynamic reads/writes, loops/generate, functions and arrays,
division/remainder and zero divisors, signed
declarations/literals/casts and 64-bit arithmetic/shifts. They use Icarus's
`-gstrict-expr-width` mode for standard 32-bit unsized constant sizing.
Install `iverilog` and `vvp` on `PATH` (or set `IVERILOG` and `VVP` to their
executables). These tests skip when the simulator is unavailable.

The shared backend/runtime regression checks are documented in the
[WebAssembly readme](../wasm/readme.md#validation).
