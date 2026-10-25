# SKI evaluator

A bounded normal-order SKI evaluator implemented in OpenType GSUB. The visible
font parses explicit prefix input, selects and contracts I/K/S redexes, copies
subtrees, accounts for fuel, and draws the result. All of that runs in one
shaping invocation. The independent Python reducer is used only by tests.

Open [the playground](playground.html) through a web server, or open the
[editable ODT specimen](ski.odt) in LibreOffice Writer. The playground accepts
ordinary parenthesized notation and converts it to prefix syntax; JavaScript
does not evaluate the expression. The document embeds the font and Roboto and
needs no Python, macros, installation or web server.

From the repository root:

```bash
python3 -m http.server 8000
```

Visit <http://localhost:8000/languages/ski/playground.html>.

The bundled visible `ski-font.ttf` supports depth **5 edges**, up to
**63 AST nodes**, and **32 reductions**. Operands can be arbitrary compound
trees within these bounds. The alphabet is `S`, `K`, `I` and all 26 lowercase
atoms. The reduction rules are:

```text
I x     → x
K x y   → x
S x y z → x z (y z)
```

Application associates to the left. Both ordinary syntax (`S K K a`) and
explicit prefix syntax (`@@@SKKa`) are accepted by the playground and CLI.
The raw font consumes explicit prefix syntax in the envelope described below. Partial applications are
preserved; reducible arguments inside them are still normalized.

## CLI

The separate `ski.ttf` / `ski.json` machine font exposes the same evaluator's
internal tree tape for programmatic inspection. Python parses and encodes
input, calls HarfBuzz once, then validates and decodes output glyphs. This path
preserves the original PUA protocol; its glyph outlines are invisible.

Use Python 3.11 or later and install this project's reproducible dependency:

```bash
python3 -m pip install -r languages/ski/requirements.txt
```

A system HarfBuzz shared library is also required: for example,
`brew install harfbuzz` on macOS or `apt install libharfbuzz0b` on Debian/Ubuntu.
The runner uses its C API through `ctypes`; `uharfbuzz` and the `hb-shape`
executable are not required.

From the repository root:

```bash
python3 languages/ski/run.py 'S (I a) b (I c)'
python3 languages/ski/run.py 'S a b (K c d)' --fuel 1
python3 languages/ski/run.py 'K a (S I I (S I I))'
```

The first expression returns `a c (b c)` in four reductions. The second
returns `a (K c d) (b (K c d))` after one reduction with status `budget`.
With the default fuel it normalizes to `a c (b c)` in three reductions.
The third returns `a` in one step without evaluating the discarded argument.

Output is JSON with `status`, readable `expression`, `prefix`, `steps`,
`shaping_calls`, HarfBuzz version and font digest. `--glyphs` includes the actual
output glyph names. Invalid input, an oversized initial tree, missing files or
an incomplete/corrupt machine result produces an error on stderr and exit code 2.
A valid `budget` or `overflow` result has exit code 0.

The default font path is relative to the script, so the runner works from any
directory. An explicit `--font path.ttf` is relative to your current directory;
keep its matching `.json` beside it. The runtime checks the font digest, cmap,
tree capacity and output tape before accepting a result.

## Bounds and statuses

| Status | Meaning |
| --- | --- |
| `normal` | No redex remains, including when fuel was initially zero. |
| `budget` | A redex remains and the supplied fuel has been consumed. This does not prove nontermination. |
| `overflow` | The next S expansion would exceed the tree depth. The previous expression and fuel are retained. |
| `input_overflow` | The encoder rejects an initial tree that is too deep, before shaping. |

The default physical tape always contains 191 glyphs, even for an atom.
Depth is a storage constraint: a small but deep tree can overflow. An oversized
argument is rejected even if a later K would discard it.

The compiler supports depth 3–5 with 0–32 rounds, and depth 6 (127 nodes,
383 tape glyphs) with 0–16 rounds. Depth 6 with more than 16 rounds is rejected:
an earlier 32-round experiment returned an unfinished `seek` state. V44 extends
the tested machine-font range to 16 rounds without claiming to fix that failure.
The bundled browser/document font uses depth 5 and 32 rounds. Neither font is
an unbounded evaluator.

## Build

```bash
python3 languages/ski/build.py
python3 languages/ski/build.py --depth 4 --rounds 8 --output /tmp/ski-compact.ttf
python3 languages/ski/run.py 'S K K a' --font /tmp/ski-compact.ttf
python3 languages/ski/build.py --depth 6 --rounds 16 --output /tmp/ski-depth6.ttf
python3 languages/ski/build.py --visible --output /tmp/ski-visible.ttf
python3 specimens/build.py --project languages/ski
```

With no output option the builder regenerates both bundled fonts: `ski.ttf`
and `ski-font.ttf`. An explicit `--output` builds a machine font at that path;
add `--visible` to select a visible font. Paths are relative to your current
directory (`--out` is an alias). Machine builds write a `.json` configuration,
generated `.fea` source and separate `.build.json` timing record. Visible
builds write their own `.json` display metadata and `.fea` source. Both fonts
and JSON files are bundled; generated feature sources and timings are ignored.
Identical source and the pinned FontTools version produce identical bytes.
Rebuild the specimen after changing the visible font.

Both builders prune unreachable GSUB template lookups after allocating the
complete execution schedule. Contextual helpers remain reachable, and each
scheduled occurrence retains its own index. Glyph order, input characters,
GDEF mark sets, outlines and evaluation bounds are preserved. The bundled
machine font contains 4,493 lookups and occupies 267,012 bytes; the visible
font contains 6,749 lookups and occupies 612,580 bytes. In addition to lookup
pruning, the visible font shares identical unhinted outlines and exact contour
runs, preserving every original point and glyph ID. Both fonts
use the pinned HarfBuzz layout repacker. These are storage improvements; no
shaping speedup is assumed. Pruning adds a GSUB serialization/remapping pass
to build time. See the [font storage audit](../../font-size-audit.md).

For an unpruned comparison build, use `--no-optimize` with a separate output:

```bash
python3 languages/ski/build.py --no-optimize --output /tmp/ski-unpruned.ttf
```

Non-default visible configurations require a separate `--output` path. The
bundled visible font stays at depth 5 / 32 rounds to match the playground
controls and specimen. The builder rejects incompatible bundled builds before
writing either font.
Machine builds cannot target any bundled visible-font artifact, and visible
builds cannot target any bundled machine artifact. All builds
check every output path before writing, including sidecars and hardlink or
symlink aliases; visible builds also protect all input artifacts.

The visible font uses decomposed outlines from the repository's pinned Roboto
Regular source. It retains Google's attribution and Apache-2.0 license and adds
Michael Brackx's interpreter modification metadata. Source protection prevents
overwriting Roboto. The machine font uses original empty outlines and contains
no Roboto. See [the provenance notes](../../decoders/shared/fonts/roboto-2/),
[third-party notices](../../THIRD_PARTY_NOTICES.md) and
[architecture](architecture.md).

## Visible font input

The visible font is **SKI Evaluator Regular**. Its input consists of `SKI;`, an
explicit prefix expression, `!`, then **191 trailing dots** for workspace.
`SKI0;` through `SKI32;` select fuel; `SKI;` defaults to 32. A space or dot is
ignored by the parser. Keep the complete input in one left-to-right text run
with required ligatures (`rlig`) enabled.

For example, the meaningful part of the identity input is `SKI;@Ia!`; its
workspace dots follow `!`. `@` applies the next two expressions: `@Ia` is
`I a`, and `@@@SKKa` is `S K K a`. Edit these prefixes directly in the ODT.
Copy the complete line from the playground's "Underlying font input" when
moving an expression into a document. Preserve the dots when editing.

The workspace is part of the framing protocol, not an expression vocabulary
or a reduction computed by JavaScript. HarfBuzz derives its operation budget
from the initial input length, before the font expands its internal tape.
The fixed dots provide room for that expansion and are deleted inside GSUB.
See [HarfBuzz's buffer initialization](https://github.com/harfbuzz/harfbuzz/blob/main/src/hb-buffer.cc).
Very short unpadded inputs may stop partway through shaping; use complete
serialized inputs for the supported bounds.

The font draws a fully parenthesized expression preceded by `NORMAL`,
`STEP LIMIT` or `DEPTH LIMIT`, followed by remaining fuel. Bad prefix syntax
draws `SYNTAX ERROR`; an oversized initial tree draws `INPUT TOO DEEP`.
Copying, search and accessibility receive the original input rather than the
computed output. The CLI provides decoded text when that is needed.

Font-side parsing uses a path cursor to assign prefix nodes to tree slots.
After validation it deletes parser state and executes the original bounded
machine schedule, then converts node values to visible outlines. Output
parentheses and spaces are determined by tree positions. No complete operand
trees are enumerated and no host-language reducer is involved.

## Machine shaping protocol

The separate machine font is **SKI Bounded Tree Regular**. The CLI encodes its
PUA tape and reads shaped glyph names to display a result. It is useful for
traces, exact step counts and machine-output validation.

To inspect that protocol with an optional HarfBuzz command-line installation:

```bash
python3 languages/ski/run.py 'S K K a' --encode > /tmp/ski-program.txt
hb-shape languages/ski/ski.ttf --text-file=/tmp/ski-program.txt --direction=ltr --script=Latn --features=calt
```

Keep the entire tape in one left-to-right shaping run with `calt` enabled.
`--encode` does not perform reductions. Disabling `calt` leaves an unfinished
machine state that the decoder rejects. Manually fabricated malformed machine
tapes are outside the font's contract. The visible font is checked separately
in the browser and LibreOffice; compatibility with other engines is unverified.

## Tests

Run from the repository root with the requirements and HarfBuzz installed:

```bash
python3 languages/ski/test_font.py --quick
python3 languages/ski/test_font.py
python3 languages/ski/test_font.py --full
node languages/ski/test_controls.cjs
```

The gate also runs the imported V42 pruning regression: 1,030 comparisons
between unpruned and pruned machine fonts and the independent reference.
Additional checks preserve protocol tables and unique schedule indices,
compare visible-font output before and after pruning, and exercise the
profiling commands from another working directory.

The quick gate runs protocol, integration and visible-font tests, rebuild
reproducibility, and 6,603 compact-machine differential checks. It verifies one-call execution with
the reference disabled, feature-off detection, corrupt tape rejection, digest
checks, configuration boundaries, font metadata, a full 63-node input, and
build/run commands from an unrelated working directory.

Visible-font tests compare actual shaped output with the independent reducer
for 1,600 compact cases, plus default-font compound operands, discarded loops,
partial applications, every atom, full-capacity input and the 32-step cutoff.
They check font-side syntax/overflow errors, disabled-feature behavior,
attribution, editable embedding, source protection, exact rebuilds and embedded
specimen fonts. Controller tests cover notation conversion, workspace,
examples, invalid input, font-loading failures and error recovery.

The standard gate also builds a depth-six/16-round font and runs the V44
1,006-case differential regression plus a full 127-node tree at every fuel
value from 0 through 16. It builds the corresponding visible font using the
pure-Python serializer and checks 185 cases, including full-capacity inputs,
compound copying, every atom and malformed input. Test build products are
temporary. The V44 capacity boundary is part of the standard gate.

`--full` additionally runs the original 11,869-case default-font corpus,
covering exhaustive small trees, random trees, forced S copying, the full
alphabet, overflow, exact fuel and a 37-step program stopped at 32 steps.
It writes results to the ignored `languages/ski/build/` directory. Runtime is
engine-dependent; the standard gate can take several minutes and the full
corpus substantially longer on newer HarfBuzz versions.

Verified on Python 3.13, FontTools 4.60.2 and HarfBuzz 14.2.1: all 11,869
default-machine cases matched the independent reference (10,558 normal,
288 budget, 1,022 intermediate overflow and one encoder rejection). The
6,603 compact-machine cases, 1,600 compact-visible cases and all 20 protocol,
integration and visible-font test methods also pass. The original V44
depth-six regression passed its 1,006 cases plus 17 capacity/fuel checks.

The visible font is visually checked in the in-app browser and LibreOffice
Writer. Browser checks include full 63-node input reducing in 31 steps,
compound S copying, input errors and depth exhaustion. The embedded specimen
renders as one page. These checks establish bounded behavior on those engines,
not unbounded evaluation or portability to every OpenType implementation.

## Profiling and benchmarks

Profile an existing machine font without rebuilding it:

```bash
python3 languages/ski/profile_font.py --samples 30 --warmups 5 > /tmp/ski-profile.json
python3 languages/ski/profile_font.py --font /tmp/ski-unpruned.ttf --samples 30
```

Compare temporary unpruned and pruned builds at depth 4 / 8 rounds and
depth 5 / 32 rounds, or select a single supported configuration:

```bash
python3 languages/ski/benchmark.py --samples 30 > /tmp/ski-benchmark.json
python3 languages/ski/benchmark.py --depth 6 --rounds 16 --samples 15
```

The tools write JSON to stdout; benchmark build diagnostics go to stderr.
Default font paths resolve relative to the scripts, and explicit paths resolve
relative to the working directory. Benchmark fonts and sidecars are temporary.
Reports include Python, FontTools, HarfBuzz and platform versions, font digest,
size, glyph/lookup counts, statuses, reduction counts, median and nearest-rank
p95 latency. The benchmark also measures total build time.

Six fixed programs are encoded before timing. Only calls to the HarfBuzz
binding are timed, including its buffer setup and glyph-name extraction;
tree encoding, result decoding and deterministic-output checks are outside
the timed region. Warmups precede samples. Overdeep inputs are reported as
`input_overflow`; unexpected errors fail the command. These tools profile the
PUA machine font, rather than the visible `rlig` frontend.

Timings depend on hardware, load, engine and serializer versions. Compare
runs in a quiet environment using the same versions; size reductions alone
do not establish faster execution.

## Source and integration

Imported the bounded evaluator, independent reference, architecture and
regressions from the user-supplied `font-ski-v44-source.zip` (SHA-256
`3309d6dede02028a37e5437b3ec2f5683d8dd35119f0f0b04d7e99436a6f5032`).
The V2–V35 prototype runners, old build logs and historical result files are
not part of the integrated runtime.

The profiler, comparative benchmark and lookup-pruning regression are adapted
from [`brackxm/agent-work-2`, `font-ski/main` at `abb34b8`](https://github.com/brackxm/agent-work-2/tree/abb34b8659d1ee98fd38187c9ee00c2105366f75/font-ski).
Pruning uses FontTools' GSUB reachability/remapping operation directly,
limiting optimization to GSUB instead of running a whole-font subset.
GSUB is serialized and reloaded first so shared in-memory contextual subtables
receive exactly one index remapping, matching the original file-based tool.

Integration replaces the unavailable FontTools 4.63.0 pin with tested 4.60.2,
fixes the stale protocol assertion rejecting valid depth-six configurations,
adds explicit supported/rejected boundaries, and supplies repository-relative
entry points and current documentation. Configuration type validation occurs
before comparisons so invalid depth-six budgets consistently raise ValueError.

The project is distributed under [Apache License 2.0](../../LICENSE).
