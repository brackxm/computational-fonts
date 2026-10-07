# Mini BASIC

A small BASIC interpreter implemented in OpenType substitutions. The font
parses numbered statements, executes assignments, jumps and subroutines, and draws printed
output, final variables and a status message. JavaScript in the playground
joins source lines and loads the font; it does not parse or execute BASIC.

Open [the playground](playground.html) through a web server, or open the
[editable ODT specimen](mini-basic.odt) in LibreOffice Writer. The document
embeds the interpreter font and Roboto and needs no macros or installation.

```bash
python3 -m http.server 8000
```

Visit <http://localhost:8000/languages/mini-basic/playground.html>.

## Language

Variables `A`, `B`, `C` and `D` start at zero and hold integers from 0 to 99.
Statements have line numbers from 1 to 99 in strictly increasing order.
Execution begins at the first line. Keywords and variables are case-insensitive;
printed strings preserve their spelling and spaces. Spaces outside strings are
ignored. Constants contain one or two digits, including leading zeros.

| Statement | Example | Meaning |
| --- | --- | --- |
| `LET variable=operand` | `10 LET A=3` | Assign a constant or variable. |
| `LET variable=operand+operand` | `20 LET B=A+7` | Add; `-` subtracts. One operator per expression. |
| `variable=expression` | `20 B=A*3` | Assign without the optional `LET` keyword. |
| `LET variable=operand*operand` | `20 LET B=A*3` | Multiply; an out-of-range result stops execution. |
| `LET variable=operand/operand` | `20 LET B=A/2` | Integer division, discarding the remainder. |
| `LET variable=operand MOD operand` | `20 LET B=A MOD 2` | Remainder after integer division. |
| `PRINT expression` | `30 PRINT B/2` | Print a number on a new output row. |
| `PRINT "text"` | `40 PRINT "Hello!"` | Print an ASCII string, including an empty string. |
| `PRINT item;item` | `40 PRINT "A=";A;", B=";B` | Join up to four strings or numeric expressions into one row. |
| `IF operand comparison operand THEN GOTO line` | `50 IF A<5 THEN GOTO 20` | Jump when the comparison is true. |
| `IF operand comparison operand THEN line` | `50 IF A<5 THEN 20` | Short form of the same conditional jump. |
| `IF NOT comparison THEN line` | `50 IF NOT A=0 THEN 20` | Jump when the comparison is false. |
| `IF comparison AND comparison THEN line` | `50 IF A>0 AND B<5 THEN 20` | Jump when both comparisons are true. |
| `IF comparison OR comparison THEN line` | `50 IF A=0 OR B=0 THEN 20` | Jump when either comparison is true. |
| `IF condition THEN line ELSE line` | `50 IF A<3 THEN 20 ELSE 70` | Choose a jump for either result; `GOTO` is optional before each line. |
| `GOTO line` | `60 GOTO 10` | Jump to a constant line number. |
| `GOSUB line` | `20 GOSUB 70` | Call a subroutine, saving the next statement as a return address. |
| `RETURN` | `80 RETURN` | Resume after the most recent unfinished `GOSUB`. |
| `FOR variable=constant TO constant` | `10 FOR A=1 TO 5` | Start an inclusive counted loop with a step of one. |
| `FOR variable=constant TO constant STEP constant` | `10 FOR A=9 TO 2 STEP -2` | Count using a nonzero literal step from −99 to 99. |
| `NEXT variable` | `30 NEXT A` | Add the loop's step to its counter, then repeat or finish the loop. |
| `WHILE condition` | `20 WHILE A<3 AND NOT B=1` | Test before each iteration; skip the body when false. |
| `WEND` | `50 WEND` | Return to the matching `WHILE` and retest its condition. |
| `END` | `70 END` | Finish. Falling past the last statement also finishes. |
| `REM text` | `80 REM A comment` | Ignore the remainder of the statement. |

An operand is a variable or constant. Comparisons are `=`, `<>`, `<`, `<=`, `>`
and `>=`. A jump target must exist when the jump is taken; an untaken conditional
jump does not require a matching line. Arithmetic outside 0–99 stops before
changing the destination variable. Division and `MOD` by zero stop with
`DIVISION BY ZERO`. Assignments and numeric `PRINT` items accept a single operand
or exactly one binary operator: `+`, `-`, `*`, `/` or `MOD`. Comparisons in
`IF` and `WHILE` still take simple operands.

`PRINT` accepts up to four items separated by semicolons. Each item is a quoted
string or numeric expression; numbers use ordinary decimal digits, without
leading zeros or automatic spacing. Include spaces in strings where needed:

```basic
10 A=7
20 B=3
30 PRINT "A=";A;", B=";B
40 PRINT "sum=";A+B
```

This prints `A=7, B=3` and `sum=10`. Each list uses one output row and counts
as one instruction. Empty strings are allowed, including a list that prints an
empty row. The combined row must fit within 24 characters; exceeding that
limit reports `PRINT WIDTH ERROR`. All numeric expressions are checked before
layout. Arithmetic, width or output-row errors retain prior rows and leave the
current row unprinted. A trailing semicolon or missing item is a syntax error;
rows always end after the statement.

An `IF` or `WHILE` condition contains one comparison, or two joined by `AND` or `OR`.
Each comparison may have one `NOT` prefix, which inverts that comparison's
result. `NOT` applies to the entire comparison, so `NOT A=0` means `A<>0`.
Both the short `THEN line` and long `THEN GOTO line` forms accept these
conditions. Both comparisons use the current variables; each `IF` or `WHILE`
evaluation counts as one instruction. Boolean operators are available only in conditions;
parentheses and chains of three or more comparisons are unsupported.

```basic
10 A=3
20 B=0
30 IF A>0 AND NOT B=1 THEN 50
40 END
50 PRINT "MATCH"
```

This prints `MATCH`. Change `B=0` to `B=1` to skip the print; then change
`AND` to `OR` to print it again.

Add `ELSE` to choose the destination when the condition is false:

```basic
10 A=3
20 IF A<3 THEN 50 ELSE 30
30 PRINT "HIGH"
40 END
50 PRINT "LOW"
```

It prints `HIGH`. Change `A=3` to `A=2` to print `LOW`. Each branch names a
literal line number, optionally preceded by `GOTO`; short and long forms can
be mixed. `AND`, `OR` and `NOT` work with `ELSE` too. Only the selected
destination must exist. Without `ELSE`, a false condition continues to the next
statement. The condition and branch selection together count as one instruction.
Branches contain line numbers; assignments, `PRINT`, `GOSUB` and nested `IF`
statements cannot be written after `THEN` or `ELSE`.

Try a counted loop:

```basic
10 FOR A=1 TO 5
20 PRINT A
30 NEXT A
40 END
```

It prints 1, 2, 3, 4, 5 and ends with `A=06`. Every edit reruns the entire
program from zero. The other playground examples demonstrate arithmetic,
conditional jumps and an endless loop that reaches the instruction limit.
Change `PRINT A` to `PRINT A*A` to print squares.

Add `STEP 2` and use `TO 9` to print 1, 3, 5, 7, 9, ending with `A=11`:

```basic
10 FOR A=1 TO 9 STEP 2
20 PRINT A
30 NEXT A
40 END
```

Use a negative step to count down:

```basic
10 FOR A=9 TO 2 STEP -2
20 PRINT "A=";A;", square=";A*A
30 NEXT A
40 END
```

It prints labelled rows for 9, 7, 5 and 3, ending with `A=01`.

`FOR` requires two literal bounds in 0–99 and a matching `NEXT` naming the
same variable. `STEP` is optional and defaults to one. An explicit step must be
a nonzero literal integer from −99 to 99; zero, variables and expressions are
syntax errors. Only one loop can be active, but sequential loops are supported.
Nested, mismatched or unclosed pairs are syntax errors. A positive step skips
the body when the start exceeds the limit; a negative step skips it when the
start is below the limit. In either case the counter is initialized.
`NEXT` adds the signed step before testing the bound, repeating while the
counter is at most the limit for a positive step, or at least the limit for a
negative step. Successful completion leaves the counter at the first value
beyond the bound in that direction.

Variables still hold only 0–99. An increment outside that range reports an
arithmetic range error before changing the counter, even if it would also end
the loop. `FOR A=90 TO 90 STEP 20` stops with `A=90` at `NEXT` after one
iteration. Similarly, `FOR A=3 TO 0 STEP -1` prints 3, 2, 1 and 0, then
reports an arithmetic range error with `A=00`. Use a positive lower bound
when a countdown should finish without going below zero.

Try a condition-controlled loop:

```basic
10 A=0
20 WHILE A<3 AND NOT B=1
30 PRINT A
40 A=A+1
50 WEND
60 PRINT "DONE"
```

It prints 0, 1, 2 and `DONE`, ending with `A=03`. `WHILE` tests before the
first iteration and again whenever `WEND` returns to its header. If the
condition is false, execution continues after the matching `WEND`; an initially
false condition skips the body entirely. `WEND` counts as an instruction in
addition to the condition evaluation. A loop that never finishes reaches the
128-instruction limit.

`WHILE` needs a matching `WEND`. Both loop types share one active loop, so
sequential `FOR` and `WHILE` loops are supported; nesting either type inside
the other is a syntax error, even in unreachable code.

Jumping into an inactive loop's `NEXT` or `WEND`, restarting an active `FOR`, or starting
a second loop while another remains active reports `LOOP ERROR`. Editing the
counter inside the body changes what the following `NEXT` increments. Jumping
back to the same active `WHILE` retests its condition. Jumping out of a loop
leaves it active; retesting its `WHILE` with a false condition releases it.

Subroutines share the four variables and one active loop. Calls may
nest or recurse up to four levels; a fifth unfinished call reports
`CALL STACK FULL`. `RETURN` without a saved address reports
`RETURN WITHOUT GOSUB`. Returning from a call on the final statement finishes
the program. `END` finishes immediately, even inside a subroutine. There are
no arguments or local variables. Use `END` or `GOTO` to keep normal execution
from falling into subroutine definitions.

For example, call one routine twice:

```basic
10 A=3
20 GOSUB 70
30 PRINT A
40 GOSUB 70
50 PRINT A
60 END
70 A=A*2
80 RETURN
```

It prints 6 and 12 and ends with `A=12`. `IF A>0 THEN 20` is equivalent to
`IF A>0 THEN GOTO 20`; both forms jump rather than save a return address.

## Raw font input

The font consumes one printable-ASCII text run, with this envelope:

```text
RUN:10 FOR A=3 TO 1 STEP -1:20 PRINT "A=";A:30 NEXT A:40 END:!
```

Use the exact uppercase `RUN:` prefix, terminate each statement with a colon,
and end the program with `!`. The empty program is `RUN:!`. Semicolons join
`PRINT` items. Colons and semicolons inside quoted strings are literal; a colon
ends a `REM` comment. Quotes cannot appear inside strings. Use straight ASCII
quotes and spaces.

Legacy input uses the exact uppercase `RUN;` prefix and semicolons to terminate
statements. Its empty program is `RUN;!`. In that mode, a semicolon ends a `REM`
comment, colons in comments remain literal, and `PRINT` takes one item. Use
`RUN:` for `PRINT` lists; the playground serializes this format automatically.

Apply **Mini BASIC Regular**, keep the run on one line with consistent
formatting, and enable required ligatures (`rlig`). Use the playground's
"Underlying font input" to copy a program for use with the font in another
application. The ODT contains this serialized text directly; edit its blue
block, including the separators and final sentinel.

Output is drawn from glyph outlines. Copy, search and accessibility tools
receive the source program, rather than a transcript of the computed output.

## Bounds and errors

- At most 16 statements and 128 executed instructions.
- At most eight `PRINT` rows, each containing at most 24 printable ASCII characters.
- Up to four strings or numeric expressions per `PRINT` list, joined by semicolons.
- Four variables, integer arithmetic, one arithmetic operator per assignment or numeric `PRINT` item.
- One or two comparisons per `IF` or `WHILE`, joined by one `AND` or `OR`, with optional `NOT` on each comparison.
- One active `FOR` or `WHILE` loop, with matching closers and no nesting.
- Up to four unfinished subroutine calls, with shared variables and no arguments.
- No negative variable values, floats, parentheses, multiple-operator expressions, arrays,
  `INPUT`, variable loop bounds or steps, nested loops, local variables or interactive
  session state.
- Source must stay in a single shaping run. Other scripts, Unicode characters,
  mixed formatting, or application run splitting can interrupt execution.
- The browser rejects non-ASCII source, more than 16 nonempty editor lines, and
  editor lines longer than 128 characters before passing input to the font.

The font validates the whole program before execution. Bad syntax, duplicate or
out-of-order line numbers, and excess statements show `SYNTAX ERROR` with zeroed
variables. During execution, errors retain output and assignments already made:
`ARITHMETIC RANGE ERROR`, `DIVISION BY ZERO`, `LOOP ERROR`, `MISSING LINE`,
`CALL STACK FULL`, `RETURN WITHOUT GOSUB`, `OUTPUT LIMIT`, `PRINT WIDTH ERROR` or `STEP LIMIT`.
Successful completion shows `DONE`. These are deliberate bounds, not a complete
implementation of a historical BASIC dialect.

## Build

Python 3.10 or later and FontTools are required. Run from the repository root:

```bash
python3 -m pip install fonttools
python3 languages/mini-basic/build.py
python3 specimens/build.py --project languages/mini-basic
```

`--output /path/to/font.ttf` selects a different output location. The builder
protects the source font from overwrite. Generated fonts retain the original
Roboto attribution and add interpreter modification metadata.

The rebuilt font measures 3,594,292 bytes (3.43 MiB), including a
1,141,784-byte GSUB table, with FontTools 4.66.1. Its serialized size checks are:

| Measure | Current | Limit |
| --- | ---: | ---: |
| Glyphs | 53,442 | 65,535 (format) |
| Stored lookup headers | 964 | 1,000 (regression budget) |
| Largest LookupList-to-Lookup offset | 37,442 bytes | 38,000 bytes (regression budget) |

The 7,368 lookup indices share stored headers. The current regression budgets
leave room for 36 more headers and 558 more offset bytes; larger additions need
further table sharing or a deliberate budget review. File and GSUB byte counts
are measurements, rather than enforced budgets, and may vary with FontTools
serialization. The offset's format limit is 65,535 bytes.

The VM uses hidden glyphs for the program counter, variables, operands and
output-row allocation. Each clock tick activates one numbered statement,
synchronizes variable references, executes it and advances or jumps. A fixed
sequence of 128 clock ticks permits backward branches while bounding shaping
work. Register updates share helpers across variables and operand roles. Each
update resets its selected glyph before setting the new value, so setters do
not need a mapping for every possible previous value. Jumps use the same
approach for the program counter.
Assignments and jumps preserve the stored operands and emit temporary state
beside them. PRINT evaluates its numeric items and copies string characters
into one temporary character stream. Shared column setters place that stream
into the existing row glyphs, so mixed output needs no separate numeric glyph
for every row and column. The complete row is validated before it is drawn.
Return addresses are hidden glyphs indexed by call depth beside source labels.
Calling stores the next label (or program end); returning consumes the address
at the top depth and emits its jump.
`NEXT` adds or subtracts its stored step magnitude and checks the limit in two internal passes that
share the arithmetic/comparison lookup table. Both passes count as one executed
instruction. Direction markers retain the appropriate bound comparison when
the loop repeats or restarts.
Logical conditions load both comparisons during the active `IF` or `WHILE` tick, negate
their results as needed, then combine them before branching. Labels isolate
these temporary results from neighboring instructions. Loop bounds and steps
share setters for their parse-time copies. `WHILE` keeps its condition in the
stored program and activates its header only while the loop is running. Its
`WEND` stores a jump back to that header; a false condition uses the same exit
address helper as a skipped `FOR`. An optional `ELSE` destination has a distinct
operand glyph, so the condition selects either target through the shared jump
helper. An unselected target emits no jump and is not checked for existence.

Repeated clock passes retain distinct lookup indices, so shaping clients execute
every tick, while sharing the wrapper tables behind those indices. The generator
counts shared headers once when reporting its conservative header-size bound.
Extension lookup tables keep larger substitution payloads within the format's
offset limits; successful serialization checks the actual layout.

## Tests

With FontTools and HarfBuzz's `hb-shape` installed:

```bash
python3 languages/mini-basic/test_font.py
node languages/mini-basic/test_controls.js
```

Font tests rebuild a fresh font and compare actual HarfBuzz shaping of both
fonts with an independent reference interpreter. Cases cover backward jumps,
variable synchronization, all comparisons, arithmetic boundaries, output order,
repeated strings, mixed PRINT lists, generated item-boundary cases, column
placement, complete-row errors, legacy and colon input envelopes, quoted
separators, comment boundaries and spaces outside strings,
counted loops, every positive and negative step for each variable,
skipped and sequential loops, `WHILE` condition retesting, mixed loop state,
malformed and nested loop pairs, invalid loop
entry, subroutine reuse, nested and recursive calls, stack overflow, unmatched
returns, short conditional jumps, both `ELSE` branches and every destination,
optional `GOTO` forms, missing selected and unselected targets,
logical combinations and negation, repeated
logical conditions, division by zero, malformed programs and
execution limits. They also check
font metrics, metadata, source protection and embedded specimen fonts.
Every value from 0 to 99 is exercised for all four variables. Table checks cap
stored lookup headers at 1,000 and the largest LookupList-to-Lookup offset at
38,000 bytes, allowing PRINT's additional layout stages while leaving room
below the format limit and detecting regressions in helper sharing.
A separate serialization check disables HarfBuzz repacking and
shapes the resulting FontTools-only font.
Controller tests check source serialization, input bounds, examples and font
loading states. Browser and LibreOffice rendering need visual verification
when changing outlines, metrics, examples or document styles.

## License

The interpreter is original project code under Apache-2.0. Output outlines come
from the repository's pinned Apache-2.0 Roboto Regular source. See the
[Roboto provenance notes](../../decoders/shared/fonts/roboto-2/) and
[third-party notices](../../THIRD_PARTY_NOTICES.md).
