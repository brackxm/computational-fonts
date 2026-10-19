# SMILES diagrams

An OpenType font that turns a bounded subset of SMILES into skeletal molecular
structure diagrams. Atom placement, bond drawing, branches and ring closures
run inside the font’s GSUB substitutions; GPOS attaches bracket labels to atom anchors. No molecule catalog, RDKit,
smiles2svg, SVG molecule renderer or host-side coordinate calculation is used.
The linked [smiles2svg project](https://github.com/iribirii/smiles2svg) was a
visual reference only; no code or assets are incorporated from it.

## Try it

Serve the repository root with `python3 -m http.server 8000` and open
<http://localhost:8000/graphics/smiles/playground.html>.
The browser checks supported syntax and wraps your input in braces; the font
draws the diagram. Edit a chain, add a branch or close a ring:

```text
CCO
CC(=O)O
CC(C(O)N)O
C1CCCCC1
c1ccccc1
c1ccncc1
c1ccsc1
[nH]1cccc1
[NH4+]
CC(=O)[O-]
[NH4+].[Cl-]
C1=CC=CC=C1
ClCCBr
CC#N
```

In another application, use **SMILES Diagrams**, enable standard ligatures and contextual alternates,
and include the braces: `{CC(=O)O}`. Keep the complete expression in one
left-to-right text run. Copying the picture preserves its SMILES source,
including braces. Open [smiles.odt](smiles.odt) in LibreOffice Writer for an
editable specimen with the font embedded.

## Supported syntax and limits

- At most **10 atoms across all fragments**, with at most **two nested branch levels**.
- Aliphatic atoms: `B C N O P S F Cl Br I H`; aromatic atoms: `b c n o p s`.
  Case matters; `Cl` and `Br` each count as
  one atom. Hydrogen is explicit when supplied as `H`.
- Bracket atoms use the same elements, with optional `H` or `H0`–`H4` and
  formal charges from −3 to +3: `[nH]`, `[NH4+]`, `[O-]`, `[N+2]`.
  Repeated signs such as `[N++]` are also accepted. Bracket hydrogens belong
  to that atom and do not count as additional vertices. Bracketed carbon is
  explicitly labeled. Hydrogen counts are subscripts and charges superscripts.
- Bonds: `-`, `=`, `#`. An omitted bond between two lowercase aromatic atoms
  is aromatic; other omitted bonds are single. An explicit `-` always stays
  single, including between two aromatic atoms. Explicit `=` and `#` retain
  their bond orders.
- Non-empty branches in `(...)`, including a bond at the start: `C(=O)O`.
- Ring digits `1`, `2`, `3`. Each digit joins its two neighboring atoms;
  a digit can be reused after closing. A ring bond order must be specified
  at the closing occurrence, as in `C1CCC=1`.
- Disconnected fragments separated by `.`, as in `[NH4+].[Cl-]` or `CCO.C1CC1`.
  Each fragment has its own layout, with space between fragments and no connecting
  bond. Close branches and ring digits before each dot; ring labels can be reused
  in the next fragment. Leading, trailing and consecutive dots are rejected.
- One complete expression per brace pair; no whitespace inside it.

The drawing uses skeletal notation: unlabeled carbon vertices, zigzag chains,
regular three- to ten-member ring polygons, and inward double bonds. Simple
unlabeled carbon rings use a single hollow outline with mitered corners, avoiding
seams between separately drawn bonds. Aromatic
rings have a circle inside their solid polygon outline, so lowercase benzene
keeps its aromatic annotation without assigning a Kekulé pattern. Each fully
aromatic face gets one circle, including the faces of linked and fused systems.
A circle is omitted if a ring contains an explicit non-aromatic bond override. Heteroatom
labels keep their element colors and bonds stop before their labels. Clearance
uses an envelope of the source font’s element-label bounds, the bond direction
and its painted stroke width, including two-letter labels such as Cl and Br. A standalone
carbon keeps an explicit C label. Fused rings share an edge; spiro rings share a
vertex. Linked ring pairs have separate polygons and a connecting bond.

The font includes 363 geometric connectivity scaffolds. These are independent
of element identity, bond order and ring-digit spelling; no complete molecule
images or per-molecule SMILES ligatures are stored. Ring layouts cover:

- Simple 3–10 member rings, optionally preceded or followed by linear chains.
- A simple ring with one linear side chain attached at any ring vertex.
- Two directly linked rings, and the supplied fused and spiro traversals.

More complicated ring substitutions, arbitrary bridged systems and other
traversals are outside the current geometry library. The playground rejects
unmatched ring arrangements; raw font input shows an X for unsupported ring
layouts. Common single branches and the nested playground example also use uniform
bond lengths and 120-degree junctions. Other acyclic inputs retain the general
bounded branch interpreter; long branches can still have nonideal spacing. This is not a general-purpose chemical
layout optimizer. Valence, implicit hydrogen labels and stereochemistry are not
computed. Color is optional; ordinary TrueType outlines draw the same structures.

Isotopes, other elements, atom mapping, bracket stereochemistry, the explicit
aromatic `:` bond, `/` and `\` stereochemistry and `%` ring numbers
are unsupported. Ring closures across a dot and dots inside branches are outside
this prototype’s disconnected-fragment syntax. Benzene accepts both aromatic `c1ccccc1` and the explicit
Kekulé form `C1=CC=CC=C1`. Aromatic heteroatoms use uppercase element labels in
the drawing, such as N in `c1ccncc1`. Aromaticity is taken from the input;
the font does not validate electron counts or infer aromaticity. Hydrogen
labels are drawn only when explicitly supplied in brackets. Aromatic atom/bond syntax follows the
[OpenSMILES aromatic notation](https://opensmiles.org/opensmiles.html).
The playground rejects unsupported or structurally incomplete input, including
ring topologies without a geometric scaffold. It does
not check chemical validity. In documents, incomplete states or unmatched ring
and branch marks show an X; unsupported text may remain visible. The font is
not a complete SMILES validator. Inputs beyond its bounds can leave visible
unevaluated text. Application shaping limits can be lower than font limits.

## Build

Requires Python 3.10+, FontTools and uharfbuzz (for packing the large GSUB table).
The pinned versions below were used for the bundled font:

```bash
python3 -m pip install -r graphics/smiles/requirements.txt
python3 graphics/smiles/build.py
python3 graphics/smiles/build.py --output /tmp/smiles.ttf
python3 specimens/build.py --project graphics/smiles
```

Default output is `smiles-font.ttf` beside the builder. A relative `--output`
is relative to the working directory. The builder also writes a matching `.topologies.json` file containing only
connectivity signatures for playground validation. Importing it writes no files.
The font uses the bundled Roboto Regular source for input and element labels;
it retains the source's Apache-2.0 notices and identifies its modifications.
Graph outlines and interpreter code are original Apache-2.0 work.

## How shaping draws the graph

The opening brace starts a state containing the next atom column, previous
atom position, branch depth and pending bond order. Each atom consumes that
state, emits a zero-advance element label and connecting bond, and advances
the state. Branch opening emits a saved origin mark; branch closing restores
that origin while preserving the next unused column. Ring digits emit origin
marks, and a later matching digit replaces its mark with a closure bond.
The closing brace consumes a completed outer state and supplies the canvas
advance. All earlier outlines remain positioned relative to the same origin.

Distinct contextual wrappers run `2 × MAX_ATOMS` passes over shared transition
lookups. Branch pushes and returns run before bond parsing, so explicit bonds
at branch starts or after returns do not require extra clock ticks. Each return
consumes exactly one closing parenthesis before the next clock pass.
Mark filtering lets ordinary steps skip drawings, branch operations see the
nearest saved origin, and ring operations find their matching ring marker.
The parser uses `liga` with default and Latin script support.
A dot after a completed outer atom inserts an internal closing brace, a fragment
separator and a new opening brace. This restarts atom indices and ring state;
non-mark boundaries keep operations inside their component. The complete source
is still one text run, including its original dots. GPOS in `calt` reduces unused
canvas space after each fragment, using its selected scaffold or generic chain
extent. Bracket mark attachment finishes within each component before the separator.
Lowercase input tokens carry a mark into the next atom emission, preserving
aromatic identity in the font without adding a host-side normalizer. The final
`calt` stage recognizes pairs of aromatic endpoints on omitted bonds; a separate
explicit-single token prevents `-` from being converted to an aromatic bond.
Fully aromatic chordless cycles emit one inset circle each, with opposing
outline winding to keep the center hollow in monochrome renderers.
It then recognizes the completed edge graph, clips bonds at
heteroatoms, and selects regular ring, linked, fused or spiro geometry. Element
labels move with their scaffold vertices. After placement, simple carbon rings
combine their outer strokes into one closed polygon band with opposite contour
winding. Double bonds keep their separate inner strokes; labeled vertices keep
their clipped bonds. Bracket atom tokens retain a hydrogen
count and charge in a shared label mark; GPOS mark-to-mark attachment places it
at the final vertex. GSUB selects an open side using the bounds of the complete
hydrogen, count and charge decorations against the scaffold's incident bonds.
The bracket lexer recognizes the supported grammar
rather than particular molecule strings. Shape selection and drawing run in
OpenType; JavaScript never computes positions or creates molecule paths. The browser
fits the resulting font ink bounds to the viewport. COLR v0 / CPAL
color the labels while retaining ordinary TrueType fallback outlines.

## Tests

```bash
python3 -m unittest discover -s graphics/smiles -p 'test_*.py' -v
node graphics/smiles/test_controls.cjs
```

Font tests require FontTools and `hb-shape`. They rebuild the font, check
reproducibility and metadata, and compare both generated and bundled font
output against an independent graph parser for chains, nested branches,
multiple bond orders, ring reuse and random inputs. Geometry tests check
regular polygon area, consistent bond lengths, full shaped ring outlines, fused
and spiro scaffolds, heteroatom label placement, aromatic rings and explicit
bond overrides, bracket-atom graph identity, charge aliases, GPOS label attachment
and disconnected components. Fragment tests compare each component to its standalone
rendering and check that their ink bounds stay separated. Browser checks cover
supported examples, syntax errors, unsupported SMILES features and bounds.
