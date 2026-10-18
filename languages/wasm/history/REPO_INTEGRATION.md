# Repository inspection and local integration

Read-only GitHub access succeeded during this continuation. No git checkout,
commit, push, pull request, or other remote mutation was performed.

Inspected upstream files:

- `readme.md`, SHA `1de240c043f68c24e4c06ba8871b040f0038a678`.
- `languages/mini-basic/build.py`, SHA `1db140420aa3b9c3603bc364a2a66189fcbe9e85`, especially its font setup and mark-filtered lookup builder.

Upstream source locations:
https://github.com/brackxm/computational-fonts/blob/master/readme.md
https://github.com/brackxm/computational-fonts/blob/master/languages/mini-basic/build.py

The repository organizes projects into independent directories with `build.py`,
usage/limits documentation and tests. Its generators use FontTools. The Mini
BASIC builder classifies machine glyphs as GDEF marks and uses
`UseMarkFilteringSet` to address distant components. The new backend uses the
same addressing convention and retains the uploaded implementation's
FontBuilder/TTGlyphPen generation infrastructure. It does not need a Roboto base
font because its machine glyphs have no display outlines.

Suggested destination: `languages/wasm/`. The new `build.py` and the existing
`compiler.py` both launch native compilation. Building a demonstration writes
its font and ABI manifest locally; no binary font assets are needed in this
source bundle.

Still outstanding for full repository integration: add the project to the root
project list, decide whether to provide a visible glyph/document specimen and a
browser controller for the token ABI, and run the upstream repository's other
font/browser tests in a complete checkout. None of those changes are claimed in
this handoff. All regression tests from the uploaded Wasm implementation are
included and run locally.

Implementation references (not copied program code):
https://learn.microsoft.com/en-us/typography/opentype/spec/gsub
https://learn.microsoft.com/en-us/typography/opentype/spec/chapter2
https://adobe-type-tools.github.io/afdko/OpenTypeFeatureFileSpecification.html
