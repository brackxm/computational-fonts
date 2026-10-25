# Poem Oracle

Type a word or multiple paragraphs. The playground displays **one poem per
nonempty paragraph**, chosen from **2876 short poems by 16 authors**, including
each poem’s title, stanza breaks and author. The same paragraph selects the same poem. There is no semantic interpretation or fresh randomness.

**[Try the playground](playground.html)** · **[Download TTF](poem-oracle.ttf)** ·
**[WOFF2](poem-oracle.woff2)** · **[Poem corpus](poems.json)**

## Try it

From the repository root:

```sh
python3 -m http.server 8000
```

Open <http://localhost:8000/literature/poem-oracle/playground.html>. Type your
own input or choose a word, phrase, paragraph or two-paragraph example. Results update as you
edit. Each poem has a source link and copy button. Selectable text, a copy-all button
and a font-computation toggle are also available. Turning computation off leaves the original input
and produces no poem glyph.

The playground supports **up to 16 nonempty paragraphs and 1–4,096 characters total** of printable Latin text
through Latin Extended-A, plus common punctuation. **Blank lines separate
paragraphs**, including blank lines containing spaces/tabs. Extra empty
paragraphs are ignored. Within each paragraph, NFC normalization is applied
and tabs/single line breaks become spaces; other spaces, case and punctuation
contribute to selection. Repeated paragraphs each produce their own copy of
the same poem. Changing one paragraph does not affect the others. Empty/whitespace-only input, unsupported characters (including
emoji), longer input and batches over 16 paragraphs show an explicit message and clear the previous result.
The paragraph limit is checked before shaping, bounding the number of SVG
outlines sent to the page and rendered on each edit.
The complete repertoire is recorded in `poem-oracle.json` and `model.py`.

Everything runs in the browser using the repository's bundled HarfBuzz
WebAssembly runtime. No input is sent to a service. JavaScript prepares and
validates text, splits it on blank lines, submits each paragraph as a separate
shaping run, and draws the returned glyph outlines as SVG. It looks up the selected glyph's metadata for accessibility,
copying and source attribution; **it does not calculate the poem index**.
Font/corpus SHA-256 checks reject mismatched build artifacts.

## Font construction

The font's default `rlig` feature executes four steps:

1. Map each supported character to its numeric seed (its alphabet index + 1).
2. A single reverse chaining GSUB lookup (type 8, wrapped in extension type 7)
   scans right to left. At each character it computes
   `h = (character_seed + 257 * suffix_hash) mod 2876` through substitutions.
3. Replace the first hash glyph with the corresponding poem glyph.
4. Replace all remaining hash glyphs with zero-width empty glyphs.

The rightmost character initializes the recurrence. The reverse lookup's
input coverage contains only the original character seeds; its lookahead
matches the already-computed suffix state. This needs one subtable per suffix
state rather than enumerating possible input strings. The work is a single
reverse scan, with no build-time limit on word length encoded as repeated
passes. The playground enforces the tested 4,096-character bound; ordinary
font hosts do not enforce that bound.

Each poem is a composite glyph built from shared letter outlines from the
repository's pinned Roboto 2 Regular and Bold fonts. Original line and stanza
breaks are baked into its geometry. A title, poem and author are included in
the glyph itself. The TTF shares repeated pairs of exactly positioned letters
and author attributions, with all original glyph IDs and outlines retained.
The WOFF2 uses the original flat letter sequences for better Brotli compression.
The TTF is approximately 7.3 MiB; the WOFF2 is approximately
1.5 MiB. The default build bundles **all 2876 selected poems**.

`model.py` is an independent Python reference for differential tests. The
browser does not import or port that hash calculation. Changing the corpus
size or order changes the mapping, so regenerate the font and its manifest
together whenever the corpus changes.

## Using the font outside the playground

Install the TTF, apply **Poem Oracle**, and keep the input in one consistently
formatted shaping run with `rlig` enabled. Start around 100 pt: poem lettering
has a cap height of 160 units in a 1,000-unit em. Whole poems occupy a large
advance and vertical extent. A single word is the most portable first test.

Native applications may divide paragraphs at spaces, wrapping, script changes,
formatting or fallback characters. The font cannot combine text across those
boundaries. The playground avoids host itemization by supplying a Latin LTR
buffer directly to HarfBuzz. Native browser/Writer paragraph behavior is not
claimed to match this explicit-buffer path. The built-in multiline poem is an
atomic glyph and does not reflow to a column width.

Copying ordinary shaped font text preserves the typed seed, not the poem.
The playground's **Copy poem text** button explicitly copies the readable text.
Selection is deterministic and collisions are expected. Each complete paragraph
is its own seed; words inside a paragraph jointly select one poem. Paragraph
splitting happens in the playground. The downloadable font continues to select
one poem for each shaping run supplied by its host application.

## Corpus and provenance

The corpus contains **2876** complete poems from **25 collections**. Every selected poem has
**2–16 nonblank lines** and **at most 120 whitespace-separated words**. Longer
poems are excluded, not excerpted. Whitespace indentation is normalized while
explicit stanza breaks are preserved. The collection includes nursery verse
and historical dialect spelling. Herrick contributes 1248 short lyrics and
epigrams, so the collection is weighted toward his work. It is a broad source
pool rather than a balanced anthology.

| Author | Poems | Collections |
| --- | ---: | --- |
| Emily Dickinson | 360 | Poems, Three Series, Complete |
| Christina Rossetti | 191 | Sing-Song: A Nursery Rhyme Book; Poems |
| Robert Louis Stevenson | 49 | A Child’s Garden of Verses; Underwoods |
| William Blake | 23 | Songs of Innocence and of Experience |
| Sara Teasdale | 252 | Flame and Shadow; Love Songs; Rivers to the Sea; Dark of the Moon |
| A. E. Housman | 52 | A Shropshire Lad; Last Poems |
| Edna St. Vincent Millay | 64 | A Few Figs from Thistles; Second April; Renascence and Other Poems |
| Paul Laurence Dunbar | 121 | The Complete Poems of Paul Laurence Dunbar |
| William Shakespeare | 136 | Shakespeare’s Sonnets |
| Claude McKay | 50 | Harlem Shadows |
| Adelaide Crapsey | 57 | Verse |
| W. B. Yeats | 42 | The Wind Among the Reeds; The Wild Swans at Coole |
| Robert Herrick | 1248 | The Hesperides & Noble Numbers, Volumes I and II |
| Edward Lear | 112 | A Book of Nonsense |
| Elizabeth Barrett Browning | 35 | Sonnets from the Portuguese |
| Edgar Lee Masters | 84 | Spoon River Anthology |

`poems.json` records stable IDs, titles, authors, full text, lengths and source
references. For untitled poems, the first line is the title. Repeated editorial
titles have disambiguated IDs. `sources.json` records the exact edition,
author death year, download URL, source SHA-256 and retrieval date. Source
anchors are HTML IDs when `anchor_kind` is `id`; other sources use title slugs
or printed Roman numerals, so their links point to the collection. Unchanged
compressed HTML snapshots retain the original source credits and notices.
Illustrations, introductions and modern appended notes are excluded.

All 25 source editions are from Project Gutenberg. The [source manifest](sources.json)
links each exact catalog entry and full-text edition, including the retained
compressed snapshots used for offline rebuilding.

The historical poem texts are public domain in the USA according to their
source catalog. Every author also died over 70 years ago, meeting the ordinary
[Belgian copyright duration rule](https://economie.fgov.be/en/themes/intellectual-property/intellectual-property-rights/copyright-and-related-rights/copyright/copyright-protection-works/copyright-duration).
This concerns the historical texts rather than every modern edition. Dickinson
follows early Todd/Higginson editions with editorial punctuation and titles,
which differ from manuscript-based modern editions. The poem texts are separate
from the repository's Apache-2.0 code license. Source snapshots retain their
own embedded distribution notices. Font outline attribution is retained in the
font metadata and [third-party notices](../../THIRD_PARTY_NOTICES.md).

## Rebuild and verify

Use Python 3.10 or later and the pinned build dependencies:

```sh
python3 -m venv /tmp/poem-font-venv
/tmp/poem-font-venv/bin/pip install -r literature/poem-oracle/requirements.txt
python3 literature/poem-oracle/collect.py
/tmp/poem-font-venv/bin/python literature/poem-oracle/build.py
```

Collection is offline and requires only the Python standard library. It checks
snapshot hashes, extracts complete poems, deduplicates normalized texts and
writes `poems.json` and `summary.json`. Parsers target the pinned snapshots;
counts describe extracted candidates, not a guarantee of capturing every poem
in a book. The build writes TTF, WOFF2 and the glyph/geometry manifest. `--output`
can select another TTF path; the companion files follow it. Rebuilds are byte
reproducible with the pinned dependencies.

```sh
/tmp/poem-font-venv/bin/python literature/poem-oracle/test_font.py
node --test literature/poem-oracle/test_runtime.mjs
```

Native shaping tests require `hb-shape` on PATH. The suites check corpus
reproducibility, known complete poems (including nested stanza extraction, div-based verse
lines, omitted editorial footnote references and a verse line misencoded as
a heading in Rivers to the Sea),
unique IDs, fresh font builds, font geometry and attribution, every poem's
reachability against the independent Python oracle, accent/paragraph inputs,
blank-line paragraph boundaries, independent/repeated paragraph selections,
the 4,096-character total limit, the 16-paragraph limit before shaping, disabled computation and artifact mismatch
rejection. The JavaScript suite uses the actual bundled browser HarfBuzz engine
and checks real returned outlines for all 2876 poem outputs. The web UI was
also checked interactively for word/paragraph examples, errors and recovery.
A full editorial proofread of every historical transcription remains outside
this prototype's validation.

Technical references:
[OpenType GSUB](https://learn.microsoft.com/en-us/typography/opentype/spec/gsub),
[pinned Roboto provenance](../../decoders/shared/fonts/roboto-2/readme.md), and
[HarfBuzz runtime provenance](../../languages/shared/vendor/harfbuzzjs/readme.md).
