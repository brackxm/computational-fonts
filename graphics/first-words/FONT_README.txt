FIRST WORDS PICTURES — 200 drawings in a font

Install first-words-font.ttf using your operating system's normal font installer.
In your application, select the family "First Words Pictures", Regular, and
enable standard ligatures. Try a display size of 48 to 96 pt.

Type:
apple banana cat dog house ball

Each recognized whole word becomes its picture. Matching is case-insensitive.
Unknown words and punctuation stay as ordinary text. Copying preserves the input.
The 200 primary labels are in words.txt. All 977 accepted spellings and their
drawing IDs are in aliases.tsv. No JavaScript or external image is needed.

Compound labels:
ice cream / ice-cream / icecream
teddy bear / teddy-bear / teddybear

Spaced compounds need a single ordinary or non-breaking space, consistent
formatting, and an application that shapes the phrase as one run. Joined or
hyphenated spellings are useful if a host splits shaping at spaces.

The drawings accept 622 curated labels, including synonyms and explicit plurals:
sofa / couch, bicycle / bike, airplane / aeroplane / plane,
fridge / refrigerator, cookie / biscuit, mouse / mice, foot / feet, tooth / teeth.
Every spaced label also accepts hyphenated, joined and non-breaking-space forms.
Use the listed forms; additional plurals and synonyms are not inferred.
Adjacent letters, digits, combining marks, underscores, apostrophes and hyphens
prevent partial substitutions within one shaping run. For example, "cat" becomes
a picture, while "caterpillar", "cat's" and "hot-dog" remain text.

Countable plurals show two diagonally stacked copies at the same glyph width:
apple / apples, cat / cats, chair / chairs, mouse / mice, foot / feet, tooth / teeth.
The font contains 200 original pictures and 191 stacked plural variants.
Plural synonyms select the same stacked variant. Number selection is explicit.
Grouped pictures (grapes, peas, blueberries, pancakes), uncountable words,
fish, sheep and plural-only names for one item (trousers, pants, scissors) keep
their existing image. Countable units such as loaves and bars of soap use stacks.

The drawings are vector COLRv0/CPAL glyphs and remain sharp when enlarged.
Colour needs application support for COLRv0. Monochrome outline drawings are
provided in the same font for renderers without colour support. Text shaping,
font embedding and PDF export depend on the application. Avoid synthetic bold
or italic formatting of the picture glyphs.

For websites, use first-words-font.woff2 with font-family "FirstWordsPictures"
and font-feature-settings: "liga" 1. Do not add letter spacing between letters.

Licensing: original artwork, build code, compiled font and Roboto text outlines
Apache-2.0. Retain FONT_NOTICE.txt and FONT_LICENSE.txt when redistributing.
