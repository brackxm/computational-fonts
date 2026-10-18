# Verilog → OpenType GSUB

Compile an unsigned, two-state combinational Verilog module into an OpenType
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

Open <http://localhost:8000/languages/verilog/playground.html>. Four bundled
examples include an eight-bit adder with carry, an ALU, a four-by-four-bit
multiplier and bit routing with reductions. Edit decimal, `0x` hexadecimal or
`0b` binary input values. Inputs wrap to their declared port widths; negative
integers supply their low two's-complement bits. Outputs are unsigned.

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
font's SHA-256. Omitting `-o` writes beside the source. `--max-gates` changes the
default 12,000-gate compilation budget (maximum 32,000, subject to font capacity).

Rebuild all bundled fonts and the catalog:

```sh
python languages/verilog/build_examples.py
```

Fonts contain original empty machine-glyph outlines, named **Verilog GSUB
Registers**. They use the shared `wasm-gsub-registers-v1` tape ABI with arbitrary
integer widths, plus `language: verilog` and `unsigned-combinational-v1` metadata.
They are not display fonts: ordinary text rendering and ODT specimens do not
display their results. Use the provided runtime or browser playground.

## Supported subset

```verilog
module adder(input [7:0] a, b, output [8:0] sum);
  assign sum = a + b;
endmodule
```

Exactly one module with ANSI-style `input`/`output` ports, optional `wire`, scalar
or descending `[N:0]` ranges, internal `wire` declarations and continuous `assign`
statements. Multiple names per declaration and comma-separated assignments work.
Identifiers are case-sensitive. Both `//` and `/* ... */` comments are accepted.
Declarations may follow assignments; drivers are resolved by dependencies rather
than source order. Each output and internal wire must have exactly one whole-net
driver. Inputs cannot be driven. Undeclared nets and combinational cycles are
errors, including in unused logic.

| Expressions | Supported syntax |
| --- | --- |
| Unsigned sized constants | `1'b1`, `8'o17`, `8'd42`, `16'hbeef`, with underscores |
| Arithmetic | `+`, `-`, `*`; unary `+` and `-` |
| Bitwise | `~`, `&`, `|`, `^`, `~^`, `^~` |
| Logical | `!`, `&&`, `||` |
| Comparisons | `==`, `!=`, `<`, `<=`, `>`, `>=` |
| Logical shifts | `<<`, `>>`; dynamic counts are not masked, and counts ≥ width yield zero |
| Selection | `condition ? yes : no`, including nested ternaries |
| Reductions | unary `&`, `~&`, `|`, `~|`, `^`, `~^`, `^~` |
| Bit/part selects | `data[3]`, `data[7:4]`; literal indices on declared signals |
| Concatenation/replication | `{a,b}`, `{4{a}}`, `{2{a,b}}` |
| Grouping | Parentheses with Verilog operator precedence |

Only **unsigned sized constants** are accepted in expressions. Write `8'd1`,
rather than unsized `1`, to make width and signedness explicit. Plain decimal
literals are accepted for range bounds, select indices and repeat counts.
Constants truncate to their specified size. The accepted datapath has unsigned
Verilog width rules: assignment width propagates through arithmetic, bitwise
operators, shifts and ternary branches before final truncation. This preserves
the carry in the adder above and the full product in the multiplier example.
Comparisons/logical operators/reductions produce one bit. Concatenation operands,
shift counts and ternary conditions use their own widths. A declared wire is a
width boundary: assigning an eight-bit sum to an eight-bit wire discards carry
before a later nine-bit output reads that wire. All arithmetic wraps at the
applicable expression/assignment width.

Not supported: non-ANSI ports, signed declarations/literals, unsized expression
constants, four-state `X`/`Z`/`?`, case equality, division/remainder, exponentiation,
arithmetic shifts, dynamic selects, partial-net assignments, multiple drivers,
wire initializers, arrays/memories, parameters, preprocessor directives, module
instances, primitives, functions/tasks, procedural blocks, clocks, delays,
sequential logic, `generate`, or SystemVerilog extensions. Unsupported syntax
fails compilation rather than being treated as zero or ignored.

## Bounds and execution

- Signal and expression widths: 1–64 bits. Wide intermediates, including a
  concatenation wider than 64 bits, are rejected even if later truncated.
- At most 128 declared signals, 65,536 source characters and 8,192 tokens.
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
precedence, assignment sizing, 64-bit ports, shifts beyond the operand width,
constant/identity outputs, error/resource boundaries, CLI execution, manifest
verification and reproducible bundled assets. Node uses the actual bundled
browser HarfBuzz engine with independent arithmetic expectations. Both suites
check disabled-shaping failure. No Verilog simulator is required for these tests.

Optional differential tests compare shaped outputs against Icarus Verilog for
all examples, mixed-width operator compositions and 64-bit arithmetic/shifts.
Install `iverilog` and `vvp` on `PATH` (or set `IVERILOG` and `VVP` to their
executables). These tests skip when the simulator is unavailable.

The shared backend/runtime regression checks are documented in the
[WebAssembly readme](../wasm/readme.md#validation).
