# SKI: a bounded tree machine in GSUB

This is the V36 design imported from the V44 source archive. The integrated
generator supports depth 3–5 with 0–32 rounds, and depth 6 with 0–16 rounds.
See [the project README](readme.md) for current commands, limits and tests.

## Visible font frontend

`bounded/visible.py` wraps the original machine with a font-side ASCII prefix
parser and renderer. It compiles the machine's generated feature source with
these additional stages, then allocates distinct lookup indices for the entire
initialization, evaluation and rendering schedule under required ligatures
(`rlig`). The standalone machine font and its PUA protocol remain unchanged.

Input is `SKI[fuel];PREFIX!` followed by a fixed workspace of `3N+2` dots.
Spaces and dots are removed inside GSUB. The workspace gives shaping engines
an initial buffer comparable to the machine tape before expansion; HarfBuzz's
work budget is based on initial input length. It is fixed framing, independent
of the expression's value and of which redexes will be selected.

A header sets the requested fuel. The terminator allocates an empty main bank,
scratch bank and fuel register. A path cursor consumes prefix symbols: `@`
writes application and descends left, while a leaf advances to the nearest
unvisited right sibling. Slot/value markers record each assignment, and
mark-filtered writes populate the main bank. This visits each input node once;
there is no enumeration of complete expressions. Overdeep input, unfinished
applications, extra symbols and malformed framing prevent evaluation.

Depth-six builds share one write helper per node value across all tree slots.
This keeps lookup headers within OpenType's 16-bit offset limit when compiling
with FontTools alone. Smaller builds retain their existing binary layout.

After validation, all parser cursors and assignment markers are deleted,
leaving the bounded machine tape. The original finite reduction schedule
executes unchanged. A final renderer replaces node glyphs with outlined output.
An application emits `(`; a node in a right-child position gets a leading
space; a leaf emits closing parentheses for its trailing right-path edges.
Thus the preorder bank draws fully parenthesized syntax without host-side
decoding. Empty slots and scratch storage stay invisible. Halt states and
remaining fuel have their own outlined glyphs. Error states suppress partial
tree output. Roboto outlines are decomposed into the output glyphs, with their
license and attribution retained.

The browser converts ordinary notation into prefix syntax and appends the
workspace. The ODT stores the same editable ASCII directly. Neither uses a
host-language reducer. Automated tests disable the reference reducer while
performing each actual shaping call, then compare the drawn glyph sequence
with the independent result. Browser and LibreOffice rendering are checked
visually in addition to the machine-font protocol tests below.

## What changed

V2 enumerated 1,884 complete redex patterns. Later prototypes demonstrated opaque copying and hybrid Python-scheduled contractions, but did not solve general font-side selection. V36 changes representation: it materializes a complete binary tree as fixed positions, then performs synchronous read/write rounds through GSUB. The generator never enumerates operand trees or computes answers to example programs.

The existing FontTools construction pattern, prefix-AST convention, real HarfBuzz testing method, and independent-reference approach were reusable. The old adjacent-swap copier was not required for the new machine; it and the earlier work were not used to disguise preprocessing as font computation.

## Architectural choices

| Representation | Assessment |
| --- | --- |
| Variable-length bracketed prefix strings | Compact, but generic capture, relocation, and boundary discovery require additional machinery; not needed for this implementation. |
| Complete binary tree / fixed-capacity slots | Chosen. Bounded paths make redex shapes and every copy destination explicit without restricting operand values. |
| Heap nodes with pointers and allocation | Potentially more space-efficient, but would need allocation, reachability/garbage collection, and pointer bookkeeping. Not implemented. |
| Fixed-width subtree blocks | Equivalent positional reasoning, but wasteful if each subtree reserves a separate maximum-size block. |
| Cursor/state glyphs | Used: one sentinel identifies the selected combinator and root position. |
| Multiple substitutions/insertion | Supported by OpenType in general, but deliberately unnecessary here. The entire tape is preallocated and never changes length. |

These are engineering assessments, not impossibility claims about alternative encodings.

## Representation

For maximum depth `D`, reserve `N = 2^(D+1)-1` node positions. Depth counts edges, so the root is at zero. Paths are binary strings: `0` is the left child, `1` the right child. Complete-tree positions are serialized in preorder.

Each main node is one glyph `n{index}_{value}`. Values are `A` (application), `E` (empty), `S`, `K`, `I`, or a lowercase atom. Descendants of every leaf are `E`. The whole tape is:

```text
MODE  n0 ... n(N-1)  t0 q0 t1 q1 ... t(N-1) q(N-1)  FUEL
```

The `t` glyphs are immutable scratch-slot labels. `q` glyphs are empty scratch slots. `MODE` starts as `seek`; the fuel register starts as `f0` through `fB`. The tape length is exactly `3N+2`: 191 for D=5. The maximum logical AST is 63 nodes; unused slots still occupy glyph positions.

The encoder parses ordinary left-associative SKI or fully explicit `@` prefix syntax, checks input depth, populates all main slots, and inserts the fixed scratch/fuel registers. It does not inspect redexes, prepare selected S operands, or perform any SKI substitution. Encoding is accepted preprocessing, not evaluation.

Main nodes, scratch labels, scratch values, and pointers are classified as GDEF marks. Mode and fuel are base glyphs. These classifications are used as computational filters, not for visible text layout.

## One reduction round

### 1. Find the first redex

An ordered contextual lookup targets `seek`. Each rule tests the fixed main-node positions needed for exactly one redex:

```text
I: r=A, r0=I
K: r=A, r0=A, r00=K
S: r=A, r0=A, r00=A, r000=S
```

Candidate roots are ordered by preorder. The first match changes the mode to `runI{r}`, `runK{r}`, or `runS{r}`. Later candidates cannot replace an already selected mode. A final fallback changes unmatched `seek` to `normal`.

Insufficiently applied combinators cannot match: the necessary application nodes are absent. In oversaturated applications the innermost saturated portion of the left spine is contracted before the extra arguments. Traversal continues into both children of non-redex applications, so this computes full normal forms, not merely weak-head normal forms. In particular, a saturated K is selected before its discarded argument.

### 2. Check fuel and expansion

If a redex is selected and fuel is zero, set `budget` before any write. Normal-form detection precedes this guard, so a normal form with zero fuel is still `normal`.

I and K cannot increase depth. S moves `z` down one edge. A finite set of contextual guards checks for any occupied deepest-level node in the selected original `z` subtree. If found, mode becomes `overflow` before scratch writes. This is an exact depth-overflow test for canonical inputs. The input/main bank and fuel stay unchanged.

No separate node-count-overflow circuit is necessary for the chosen capacity: any valid binary tree of depth at most D has at most N nodes. A future independent node-capacity parameter would require a separate check and is not implemented.

### 3. Route destinations to sources

For each operation/root pair, a generated single-substitution map changes scratch `q_j` into a pointer `p_s` to an original main slot, or a constant raw value. The map depends only on bounded paths and the SKI rule.

For I, copy subtree `r1` to `r`. For K, copy `r01` to `r`. Everything outside `r` is copied unchanged, and absent source positions produce `E`.

For S, write application nodes at `r`, `r0`, and `r1`, and map:

| Destination subtree | Original source subtree |
| --- | --- |
| `r00` | `r001` (x) |
| `r01` | `r1` (z) |
| `r10` | `r01` (y) |
| `r11` | `r1` (z) |

Every node and every empty descendant is handled by the same positional mapping. Both copies of z point into the unchanged original bank. Neither copy depends on the shape or values of the other operands.

### 4. Copy values with mark-filtered contexts

This is the central copying mechanism. For each source slot s, one lookup has a mark-filtering set containing only main glyphs `n_s_value` and pending pointers `p_s`. Everything else marked is skipped. Since all main slots precede scratch storage, rules of this form read the source value:

```text
n_s_a  p_s'  -> raw_a
n_s_A  p_s'  -> raw_A
... one rule per node value ...
```

After a pointer becomes a raw value, it is no longer in that filtering set. A later pointer to the same source sees the same original node across all skipped glyphs. Thus one source can populate both S-copy destinations. There are no substring captures, whole-operand patterns, or Python-supplied redex boundaries.

A dispatch lookup uses the same idea: only the mode and unfilled q slots are visible; filled pointer slots disappear from that lookup's filtered view. Already substituted glyphs can therefore enable subsequent contextual matches during the same left-to-right lookup.

### 5. Commit and reset

Adjacent immutable scratch labels convert anonymous raw values into addressed scratch glyphs. Per-slot write lookups copy each addressed scratch value to its main slot. The original bank is not modified until every read has finished, eliminating read-after-write corruption.

A successful running mode authorizes exactly one fuel decrement. Scratch values are reset to q glyphs and the mode returns to `seek`. Halted modes do not create pointers or write scratch data, so later unrolled rounds are no-ops.

## Finite scheduling, not implicit iteration

The compiler explicitly allocates distinct GSUB LookupList indices for every round. The default has 133 scheduled lookup entries per round, repeated 32 times, followed by selection and zero-fuel classification: 4,258 active entries. FontTools' GSUB lookup closure then removes unreachable template entries and remaps contextual helper references. The default total is 4,493, including the reachable shared helpers (4,626 before pruning). The visible frontend performs the same pruning after installing its combined `rlig` schedule.

This pass changes only GSUB: input cmap, glyph IDs, GDEF mark-filter sets, and outlines retain their meaning and bytes. It does not merge scheduled occurrences or reduce the finite execution budget. `--no-optimize` retains the pre-pruning layout for comparative profiling. Differential tests compare actual shaped outputs from both layouts against each other and the independent reference.

Repeated references to the same lookup index are not used as an iteration mechanism. Helper subtables are shared in the compiled font, but each scheduled occurrence has its own index. There is no fixed-point loop in HarfBuzz, no unbounded recursion, and no arbitrary random-access RAM. All paths, filters, and rounds are compiled finite circuits.

An early prototype ran out of 16-bit lookup-header offset space when it emitted a separate helper for each contextual value rule. Sharing value-setting helpers and using extension lookup wrappers solved that demonstrated compiler obstacle. The supported depth/budget range is deliberately bounded to D=3..5 and B=0..32, plus D=6 and B=0..16. The earlier D=6/B=32 experiment produced unfinished machine states; compilation alone does not establish successful evaluation.

## Correctness argument within the contract

Assume a well-formed canonical input tape and conforming OpenType lookup execution. The selection rules match exactly saturated I/K/S subtrees; preorder priority gives the leftmost-outermost redex. If no rule matches, no SKI redex exists anywhere in the tree.

For a selected redex, the route map is exactly the corresponding SKI replacement expressed as a mapping from destination paths to source paths and application constants. Reading from an immutable bank and applying that map to every slot constructs the complete replacement, including both copies of arbitrary compound z. Clearing unreachable positions preserves the canonical-empty-descendant invariant. The source/destination layout and mark filters ensure that each pending copy sees its original source rather than another pending/finished destination.

The overflow predicate is exact because the only downward-moving operand is z, by one edge. Commit occurs only after a successful preflight; fuel decreases only after commit. Induction on the number of successful rounds yields agreement with bounded normal-order SKI evaluation. This is a structural argument over arbitrary node values, not a claim that the enormous finite expression space was exhaustively tested.

## Failure and portability boundaries

The runtime verifies the font/configuration SHA-256 and cmap. It rejects unexpected output length, nonterminal mode, dirty scratch slots, wrong addresses, missing/orphaned nodes, and invalid fuel values. It does not repair an incomplete result or consult the reference evaluator. Disabling `calt` leaves `seek` and is rejected rather than silently producing a Python-computed answer.

Arbitrary malformed tapes bypassing the encoder are outside the font's contract. Visible typesetting, browser text itemization, other engines, and other HarfBuzz versions remain unverified. No claim of unrestricted Turing completeness is made.

## Primary technical references

OpenType GSUB substitution types, contextual lookup sequencing, and lookup application order:
https://learn.microsoft.com/en-us/typography/opentype/spec/gsub

OpenType LookupFlag semantics (`USE_MARK_FILTERING_SET`, `IGNORE_MARKS`) and LookupList ordering:
https://learn.microsoft.com/en-us/typography/opentype/spec/chapter2

GDEF glyph classes and mark glyph sets:
https://learn.microsoft.com/en-us/typography/opentype/spec/gdef

HarfBuzz feature application:
https://harfbuzz.github.io/shaping-opentype-features.html

The mechanism and measurements above are demonstrated by this implementation's actual generated fonts and local HarfBuzz tests, not established merely by citing these specifications.
