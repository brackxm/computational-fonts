# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build editable ODF specimens from the bundled fonts. Requires FontTools."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "decoders/shared/fonts/roboto-2/Roboto-Regular.ttf"
MIMETYPE = "application/vnd.oasis.opendocument.text"
NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
    "dc": "http://purl.org/dc/elements/1.1/",
    "config": "urn:oasis:names:tc:opendocument:xmlns:config:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


@dataclass(frozen=True)
class Example:
    label: str
    source: str
    expected: str


@dataclass(frozen=True)
class Specimen:
    folder: str
    font: str
    title: str
    description: str
    examples: tuple[Example, ...]
    exercise: str
    note: str
    size: int = 20
    line_height: int | str | None = None
    compact: bool = False
    unbroken_run: bool = False


SPECS = (
    Specimen(
        "graphics/ppm", "ppm-font.ttf", "PPM / color in text",
        "The font reads this plain PPM image and draws its RGB pixels.",
        (Example("Color bars", "P3 16 8 3 " + " ".join(
            str(channel) for row in range(8)
            for rgb in ((3, 0, 0), (3, 3, 0), (0, 3, 0), (0, 3, 3),
                        (0, 0, 3), (3, 0, 3), (3, 3, 3), (0, 0, 0))
            for repeat in range(2) for channel in rgb),
            "Eight bars: red, yellow, green, cyan, blue, magenta, white and black."),),
        "Change an RGB triple in the blue block: 3 0 0 is red, 0 3 0 is green, "
        "and 0 0 3 is blue. Keep spaces between samples and the image in one paragraph.",
        "Plain P3 only; dimensions 1–32, maxval 3, exactly three samples (0–3) per pixel in RGB order. "
        "Use prepared single-line source without comments; one space between header fields. "
        "Colors use sRGB channel values. Color-font support is needed for RGB output.",
        size=160, line_height="100%", compact=True, unbroken_run=True,
    ),
    Specimen(
        "graphics/pgm", "pgm-font.ttf", "PGM / shades in text",
        "The font reads this plain PGM image and draws sixteen shades of gray.",
        (Example("Sixteen shades", "P2 16 8 15 " + " ".join(
            str(value) for row in range(8) for value in range(16)),
            "A sixteen-by-eight gradient from black to white."),),
        "Change a sample in the blue block to a number from 0 to 15. "
        "Try P2 2 2 15 0 5 10 15 for four shades. "
        "Keep spaces between samples and the image in one paragraph.",
        "Plain P2 only; dimensions 1–32, maxval 15, exactly width × height samples (0 black, 15 white). "
        "Use prepared single-line source without comments; one space between header fields. "
        "Gray levels are evenly spaced display values. Color-font support is needed for solid grays.",
        size=160, line_height="100%", compact=True, unbroken_run=True,
    ),
    Specimen(
        "graphics/pbm", "pbm-font.ttf", "PBM / an image in text",
        "The font reads this plain PBM image and draws its black-and-white pixels.",
        (Example("A heart", "P1 32 32 " + "".join((
            "00000000000000000000000000000000", "00000000000000000000000000000000",
            "00000011111100000000111111000000", "00000011111100000000111111000000",
            "00001111111111000011111111110000", "00001111111111000011111111110000",
            "00111111111111111111111111111100", "00111111111111111111111111111100",
            "00111111111111111111111111111100", "00111111111111111111111111111100",
            "00111111111111111111111111111100", "00111111111111111111111111111100",
            "00001111111111111111111111110000", "00001111111111111111111111110000",
            "00000011111111111111111111000000", "00000011111111111111111111000000",
            "00000000111111111111111100000000", "00000000111111111111111100000000",
            "00000000001111111111110000000000", "00000000001111111111110000000000",
            "00000000000011111111000000000000", "00000000000011111111000000000000",
            "00000000000000111100000000000000", "00000000000000111100000000000000",
            "00000000000000000000000000000000", "00000000000000000000000000000000",
            "00000000000000000000000000000000", "00000000000000000000000000000000",
            "00000000000000000000000000000000", "00000000000000000000000000000000",
            "00000000000000000000000000000000", "00000000000000000000000000000000",
        )), "A thirty-two-by-thirty-two image with a black heart on white."),),
        "Change a 0 to 1 in the blue block to turn a white pixel black. "
        "Try P1 2 2 0110 for a two-by-two checkerboard. "
        "Keep the full image in one paragraph with the same formatting.",
        "Plain P1 only; dimensions 1–32, with exactly width × height bits (0 white, 1 black). "
        "Use one space between the header fields and raster; raster spaces are optional. "
        "Use prepared single-line source without comments.",
        size=110, line_height="100%", compact=True, unbroken_run=True,
    ),
    Specimen(
        "languages/mini-basic", "mini-basic-font.ttf", "Mini BASIC / a language in a font",
        "The font parses and executes this BASIC program, drawing its output and final variables.",
        (Example("Descending with labelled output",
                 'RUN:10 FOR A=9 TO 2 STEP -2:20 PRINT "A=";A;", square=";A*A:30 NEXT A:40 END:!',
                 "Four output rows: A=9, square=81; A=7, square=49; A=5, square=25; A=3, square=9. A=01 and DONE."),),
        "In the blue block, change STEP -2 to STEP -3 to print 9, 6 and 3. "
        "Edit the quoted labels to change their wording. "
        "Use colons between statements, semicolons between PRINT items, and keep the final !.",
        "Variables A-D and integers 0-99; optional LET, PRINT expressions, +, -, *, /, MOD, "
        "IF ... THEN [GOTO] line [ELSE [GOTO] line], GOTO, GOSUB/RETURN, FOR/NEXT, WHILE/WEND, END and REM. "
        "IF and WHILE accept two comparisons joined by AND or OR, with NOT on either comparison. "
        "PRINT joins up to four strings or expressions into a row of at most 24 characters. "
        "Up to four call levels share variables A-D. Counted loops use constant bounds "
        "and optional nonzero STEP values from -99 to 99. WHILE retests before each iteration. "
        "One loop may be active; nesting is unsupported. "
        "At most 16 ordered lines, 128 executed instructions and eight output rows. "
        "Use printable ASCII. Arithmetic outside 0-99 stops execution. "
        "The font restarts from zero whenever the source changes.",
        size=70, line_height="100%", compact=True, unbroken_run=True,
    ),
    Specimen(
        "formatters/json", "json-font.ttf", "JSON / formatting in a font",
        "The font highlights JSON tokens and normalizes spaces around punctuation.",
        (
            Example("A small object", '{  "name" : "Ada  Lovelace" , "n":3 }',
                    "Colored keys and values; the two spaces inside the name remain."),
            Example("Numbers and keywords", '[0,-12.5,1e+3,true,false,null]',
                    "Numbers are blue; keywords are purple; commas add one space."),
        ),
        "Edit a blue block. Put a colon or comma inside a quoted string to see it "
        "stay literal. Add spaces outside the strings to see them normalize.",
        "Inline formatting only, in one text run. Highlighting does not validate JSON. "
        "Use printable ASCII and JSON Unicode escapes for other characters. "
        "Copying preserves the original source.",
        size=20, line_height=28,
    ),
    Specimen(
        "formatters/markdown", "markdown-font.ttf", "Markdown / formatting in a font",
        "The font draws headings, emphasis, code and strikethrough from plain-text markers.",
        (
            Example("A heading", "# A page inside the font", "The prefix disappears; the text becomes a large bold heading."),
            Example("Inline styles", "**Bold** *italic* ~~removed~~", "Bold, italic and strikethrough, without visible delimiters."),
            Example("Code and combined emphasis", "Use `x = 3` or ***both***.", "Fixed-width code and combined bold italic."),
        ),
        "Edit a blue block: try **hello** or *hello*, then delete the closing marker.",
        "Flat styles only; no nesting, lists or links. Use a new paragraph for each heading.",
        size=20, line_height=34,
    ),
    Specimen(
        "decoders/morse", "morse-font.ttf", "Morse / a decoding font",
        "The font decodes International Morse code as it draws your text. "
        "Spaces separate letters; / separates words.",
        (
            Example("A greeting", ".... . .-.. .-.. --- / .-- --- .-. .-.. -..", "HELLO WORLD"),
            Example("Digits and punctuation", "..--- ----- ..--- -.... / ..-.. .-.-.-", "2026 É."),
        ),
        "In the greeting's blue block, type ... --- ... / .... . .-.. .--. "
        "to display SOS HELP. Use a dot or hyphen for each signal, "
        "spaces between letters and / between words.",
        "Supports A-Z, É, 0-9 and 13 punctuation marks. "
        "Unknown groups stay visible. Copying a blue block keeps the Morse source, "
        "and each Roboto copy is independent.",
        size=28,
    ),
    Specimen(
        "validators/multi-format", "validator-font.ttf", "A font that checks your text",
        "Identifiers and dates are checked as the font draws the text. "
        "The value stays visible; a final ? becomes a check mark or a cross.",
        (
            Example("In a sentence", "Invoice: iban:BE68539007547034? Due: date:2025-02-29?",
                    "The IBAN passes; the impossible date fails."),
            Example("Change one digit", "iban:BE68539007547034? + iban:BE69539007547034?",
                    "The first IBAN passes; the second fails its checksum."),
            Example("Leap years", "Calendar: date:2024-02-29? + date:2025-02-29?",
                    "2024 has a February 29; 2025 does not."),
        ),
        "Edit a digit in a blue block and watch the result change. "
        "Delete its final ? to remove the result, then type ? to evaluate it again.",
        "A check mark means the implemented structure and checksum rules pass. "
        "It does not confirm registration, ownership, or account existence.",
        size=16,
    ),
    Specimen(
        "decoders/vigenere-static", "vigenere-static-font.ttf", "Vigenere / a key in the font",
        "The repeating key LEMON is built into this font. "
        "The same ciphertext appears as plaintext when drawn with it.",
        (Example("Bundled message", "LXFOPVEFRNHR", "ATTACKATDAWN"),),
        "Replace the blue block with another ciphertext encrypted with LEMON. "
        "Use continuous A-Z letters to keep the message in one run.",
        "The key is fixed at font build time.",
    ),
    Specimen(
        "decoders/vigenere-dynamic", "vigenere-dynamic-font.ttf", "Vigenere / a key in the text",
        "The font reads KEY~CIPHERTEXT, hides the key and delimiter, "
        "and draws the decoded message.",
        (Example("Bundled message", "LEMON~LXFOPVEFRNHR", "ATTACKATDAWN"),),
        "In the blue block, change LEMON to AAAAA. The rendered message becomes "
        "LXFOPVEFRNHR because an all-A key applies no shift. Restore LEMON to decode it.",
        "This bundled font supports keys up to 6 letters and messages up to 24 letters. "
        "Use continuous ASCII letters after ~.",
    ),
    Specimen(
        "decoders/playfair-static", "playfair-static-font.ttf", "Playfair / decoding letter pairs",
        "This font decodes Playfair letter pairs using the built-in key PLAYFAIR EXAMPLE.",
        (Example("Bundled message", "BMODZBXDNABEKUDMUIXMMOUVIF", "HIDETHEGOLDINTHETREXESTUMP"),),
        "Change a letter in the blue block to see the decoded pair change. "
        "Keep an even number of continuous A-Z letters.",
        "The X in TREXESTUMP is a Playfair filler between repeated letters. "
        "The font preserves it.",
    ),
    Specimen(
        "decoders/enigma-static", "enigma-static-font.ttf", "Enigma I / a machine in the font",
        "Rotor stepping and decoding happen while the font draws the message. "
        "The initial ~ starts the machine and disappears visually.",
        (Example("Bundled message", "~BDZGO", "AAAAA"),),
        "Replace the blue block with ~AAAAA. This reciprocal machine now displays BDZGO.",
        "Bundled configuration: rotors I-II-III, starting positions AAA, rings AAA, "
        "reflector B, and no plugboard.",
    ),
    Specimen(
        "decoders/enigma-dynamic", "enigma-dynamic-font.ttf", "Enigma I / settings in the text",
        "The font reads ROTORS/POSITIONS/RINGS~CIPHERTEXT. "
        "The settings disappear visually while the ciphertext becomes plaintext.",
        (Example("Bundled message", "V-II-IV/QWE/BDF~SXWQHHBR", "ENIGMART"),),
        "Keep the settings and replace SXWQHHBR with ENIGMART in the blue block. "
        "The reciprocal machine displays SXWQHHBR.",
        "The font supports up to 8 ciphertext letters. Reflector B and plugboard "
        "AV BS CG DL FU HZ IN KM OW RX are built into it.",
    ),
    Specimen(
        "decoders/lorenz-static", "lorenz-static-font.ttf", "Lorenz / a teleprinter in the font",
        "A Lorenz SZ42a wheel machine decodes raw ITA2 symbols as the font draws them. "
        "The ~ initializer and teleprinter shift controls disappear visually.",
        (Example("Beginning of the bundled message", "~CH58USOQWRTRIMW/OGXR3Q5P", "HELLO CYBERCHEF USER,"),),
        "Change a symbol after ~ in the blue block to see the decoded character change. "
        "Select the block and switch it to Roboto to reveal the original symbols.",
        "The BREAM wheel pattern and starting positions are built into this font. "
        "Keep each message on one line; up to 128 raw ITA2 symbols are supported.",
    ),
    Specimen(
        "games/snake-fixed", "snake-fixed-font.ttf", "Snake / a board in the font",
        "A fixed 20 by 11 board is drawn and updated by the font. "
        "The text records the moves; shaping computes the current position.",
        (
            Example("After five moves", "bddwwa", "Right twice, up twice, then left once."),
        ),
        "Place the caret at the end of the blue block and append w, a, s, or d "
        "to move up, left, down, or right. Backspace undoes a move. "
        "Replace the block with b to start again. The diamond marks the food.",
        "Up to 128 moves and eight food pickups. Walls, reversals, and body collisions "
        "end the game with an X. A crown marks a win.",
        size=130,
    ),
    Specimen(
        "games/snake-dynamic", "snake-dynamic-font.ttf", "Snake / a board in the text",
        "The font reads the board dimensions and a move history. "
        "It draws every cell and computes the current game state.",
        (
            Example("Starting board", "10x5b", "A 10 by 5 board with a three-cell snake."),
        ),
        "Append w, a, s, or d to move up, left, down, or right. Backspace undoes a move. "
        "Replace the blue block with 10x5bdddddddw to win: seven moves right, then one up. "
        "A crown marks the win. Try 6x4b for another board size.",
        "Board dimensions range from 4 to 10 cells in each direction. "
        "This prototype evaluates up to 8 moves and has one food target.",
        size=145, line_height=140,
    ),
    Specimen(
        "graphics/turtle", "turtle-font.ttf", "Turtle / a drawing in the font",
        "The font executes movement, turn, and pen commands to draw a path in color.",
        (
            Example("A square in four colors", "b1ffffl2ffffl3ffffl5ffffl",
                    "A four-cell square with red, blue, green, and purple sides."),
        ),
        "Append f to extend the path. Use l / r to turn left / right, "
        "u / d to lift / lower the pen, and 0-5 to select a color. "
        "Backspace undoes a command; replace the block with b to reset.",
        "Colors: 0 ink, 1 red, 2 blue, 3 green, 4 orange, 5 purple. "
        "Filled / hollow triangles mean pen down / up; X marks a boundary. "
        "Font limit: 128 commands; application shaping limits can be lower.",
        size=85, line_height=230,
    ),
    Specimen(
        "games/text-adventure", "text-adventure-font.ttf", "The Last Light / a font adventure",
        "Explore a locked house and solve its puzzles to escape. "
        "The font draws the current room, inventory and reply from your commands.",
        (Example("Your journey begins", "start;", "The atrium, an empty inventory and a prompt to find a way out."),),
        "Click the blue scene and press End. Append east;take key; to enter the study "
        "and collect its key, then west; to return. Type help; for commands. "
        "End each command with a semicolon. Delete a command to undo; replace the "
        "history with start; to begin again.",
        "Up to 128 commands of at most 24 ASCII characters each. "
        "Keep the history in one paragraph and one font; do not press Enter inside it. "
        "Copy the scene to save its underlying history. The Roboto copy is independent.",
        size=64, line_height="100%", compact=True, unbroken_run=True,
    ),
)


def element(parent, tag, attrs=None, text=None):
    def expanded(name):
        prefix, local = name.split(":", 1)
        return f"{{{NS[prefix]}}}{local}"
    node = ET.SubElement(parent, expanded(tag), {
        expanded(k): str(v) for k, v in (attrs or {}).items()
    })
    node.text = text
    return node


def literal_text(node, value):
    """Keep source spaces editable: ODF collapses ordinary XML whitespace."""
    previous = None
    for part in re.findall(r" +|[^ ]+", value):
        if part.startswith(" "):
            previous = element(node, "text:s", {"text:c": len(part)})
        elif previous is None:
            node.text = part
        else:
            previous.tail = part


def document(kind):
    return ET.Element(f"{{{NS['office']}}}document-{kind}", {
        f"{{{NS['office']}}}version": "1.3",
    })


def xml_bytes(root):
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def font_family(path):
    with TTFont(path) as font:
        # Editable specimens must allow editable or installable embedding.
        if (font["OS/2"].fsType & 0x000F) not in (0, 8):
            raise ValueError(f"Font does not permit editable embedding: {path}")
        return font["name"].getBestFamilyName()


def declare_fonts(root, family):
    decls = element(root, "office:font-face-decls")
    for name, actual, filename in (
        ("BodyFont", font_family(BASE), "Roboto-Regular.ttf"),
        ("ComputeFont", family, "computational.ttf"),
    ):
        face = element(decls, "style:font-face", {
            "style:name": name, "svg:font-family": f"'{actual}'",
        })
        src = element(face, "svg:font-face-src")
        uri = element(src, "svg:font-face-uri", {"xlink:href": f"Fonts/{filename}"})
        element(uri, "svg:font-face-format", {"svg:string": "truetype"})


def styles_xml(spec, family):
    compact = spec.compact or len(spec.examples) > 1
    root = document("styles")
    declare_fonts(root, family)
    styles = element(root, "office:styles")
    default = element(styles, "style:default-style", {"style:family": "paragraph"})
    element(default, "style:paragraph-properties", {
        "fo:margin-bottom": "0.18cm" if compact else "0.25cm",
        "fo:line-height": "115%" if compact else "125%",
        "fo:orphans": "2", "fo:widows": "2",
    })
    element(default, "style:text-properties", {
        "style:font-name": "BodyFont", "style:font-name-asian": "BodyFont",
        "style:font-name-complex": "BodyFont", "fo:font-size": "11pt",
        "fo:color": "#24333F", "fo:language": "en", "fo:country": "GB",
    })
    definitions = {
        "Body": ({}, {}),
        "Eyebrow": ({"fo:margin-bottom": "0.35cm"},
                    {"fo:font-size": "9pt", "fo:color": "#356C80"}),
        "Title": ({"fo:margin-bottom": "0.4cm", "fo:keep-with-next": "always"},
                  {"fo:font-size": "27pt"}),
        "Section": ({"fo:margin-top": "0.15cm" if compact else "0.25cm",
                     "fo:margin-bottom": "0.1cm" if compact else "0.15cm",
                     "fo:keep-with-next": "always"}, {"fo:font-size": "13pt"}),
        "Label": ({"fo:margin-bottom": "0.08cm", "fo:keep-with-next": "always"},
                  {"fo:font-size": "8pt", "fo:color": "#5E707C"}),
        "Source": ({"fo:background-color": "#F1F3F5",
                    "fo:padding": "0.14cm" if compact else "0.2cm",
                    "fo:margin-bottom": "0.15cm", "fo:keep-with-next": "always"},
                   {"fo:font-size": "10pt"}),
        "Rendered": ({"fo:background-color": "#EAF3F8",
                      "fo:padding": "0.14cm" if compact else "0.2cm",
                      "fo:margin-bottom": "0.12cm", "fo:keep-with-next": "always",
                      **({"fo:line-height": spec.line_height if isinstance(spec.line_height, str)
                          else f"{spec.line_height}pt"} if spec.line_height else {}),
                      **({"fo:margin-right": "-2000cm", "fo:padding": "0cm",
                          "fo:background-color": "transparent"} if spec.unbroken_run else {})},
                     {"style:font-name": "ComputeFont", "fo:font-size": f"{spec.size}pt",
                      "style:letter-kerning": "false"}),
        "Caption": ({"fo:margin-bottom": "0.2cm"},
                    {"fo:font-size": "9pt", "fo:color": "#5E707C"}),
        "Note": ({"fo:margin-top": "0.25cm"},
                 {"fo:font-size": "9pt", "fo:color": "#5E707C"}),
        "Footer": ({"fo:margin-top": "0.2cm", "fo:border-top": "0.5pt solid #C8D5DC",
                    "fo:padding-top": "0.15cm"},
                   {"fo:font-size": "8pt", "fo:color": "#5E707C"}),
    }
    for name, (para, text) in definitions.items():
        style = element(styles, "style:style", {
            "style:name": name, "style:family": "paragraph",
            **({"style:master-page-name": "Standard"} if name == "Eyebrow" else {}),
        })
        element(style, "style:paragraph-properties", para)
        element(style, "style:text-properties", text)
    auto = element(root, "office:automatic-styles")
    page = element(auto, "style:page-layout", {"style:name": "A4"})
    element(page, "style:page-layout-properties", {
        "fo:page-width": "21cm", "fo:page-height": "29.7cm", "fo:margin": "2cm",
        "style:print-orientation": "portrait",
    })
    footer = element(page, "style:footer-style")
    element(footer, "style:header-footer-properties", {"fo:min-height": "0.6cm"})
    masters = element(root, "office:master-styles")
    master = element(masters, "style:master-page", {
        "style:name": "Standard", "style:page-layout-name": "A4",
    })
    footer = element(master, "style:footer")
    element(footer, "text:p", {"text:style-name": "Footer"},
            "COMPUTATIONAL FONTS  /  Editable specimen  /  Apache License 2.0")
    return xml_bytes(root)


def content_xml(spec, family):
    root = document("content")
    declare_fonts(root, family)
    if spec.unbroken_run:
        # Writer can estimate line breaks before applying GSUB. Give long
        # histories a wide shaping paragraph, inside a page-width blue cell.
        # The scene's final advance still fits the page; the input stays intact.
        auto = element(root, "office:automatic-styles")
        for name, style_family, properties, attrs in (
            ("SceneTable", "table", "table-properties",
             {"style:width": "17cm", "table:align": "left", "fo:keep-with-next": "always"}),
            ("SceneColumn", "table-column", "table-column-properties",
             {"style:column-width": "17cm"}),
            ("SceneCell", "table-cell", "table-cell-properties",
             {"fo:padding": "0.2cm", "fo:background-color": "#EAF3F8"}),
        ):
            style = element(auto, "style:style", {"style:name": name, "style:family": style_family})
            element(style, "style:" + properties, attrs)
    body = element(root, "office:body")
    text = element(body, "office:text")
    def paragraph(style, value):
        node = element(text, "text:p", {"text:style-name": style})
        if style in ("Source", "Rendered"):
            literal_text(node, value)
        else:
            node.text = value
    paragraph("Eyebrow", "COMPUTATIONAL FONTS  /  " + spec.folder.split("/")[0].upper())
    paragraph("Title", spec.title)
    paragraph("Body", spec.description)
    paragraph("Body", "Each pair is identical text in two embedded fonts. Edit the blue block directly.")
    for index, example in enumerate(spec.examples, 1):
        paragraph("Section", example.label)
        paragraph("Label", "UNDERLYING TEXT / ROBOTO")
        paragraph("Source", example.source)
        paragraph("Label", "SAME TEXT / COMPUTATIONAL FONT")
        if spec.unbroken_run:
            table = element(text, "table:table", {
                "table:name": f"Scene{index}", "table:style-name": "SceneTable",
            })
            element(table, "table:table-column", {"table:style-name": "SceneColumn"})
            row = element(table, "table:table-row")
            cell = element(row, "table:table-cell", {"table:style-name": "SceneCell"})
            literal_text(element(cell, "text:p", {"text:style-name": "Rendered"}), example.source)
        else:
            paragraph("Rendered", example.source)
        paragraph("Caption", "Expected: " + example.expected)
    paragraph("Section", "Try it")
    paragraph("Body", spec.exercise)
    paragraph("Note", spec.note)
    paragraph("Note", "Open in LibreOffice Writer. Keep each blue block on one line "
              "with consistent formatting and standard ligatures enabled. "
              "Copying it preserves the underlying text.")
    return xml_bytes(root)


def build(spec):
    folder = ROOT / spec.folder
    font_path = folder / spec.font
    family = font_family(font_path)
    meta = document("meta")
    metadata = element(meta, "office:meta")
    element(metadata, "dc:title", text=spec.title)
    element(metadata, "meta:initial-creator", text="Michael Brackx")
    element(metadata, "meta:generator", text="computational-fonts/specimens/build.py")
    settings = document("settings")
    # config:name is a QName; its prefix must be declared for Writer to apply it.
    settings.set("xmlns:ooo", "http://openoffice.org/2004/office")
    setting_set = element(element(settings, "office:settings"), "config:config-item-set", {
        "config:name": "ooo:configuration-settings",
    })
    for name in ("EmbedFonts", "EmbedOnlyUsedFonts", "EmbedLatinScriptFonts"):
        element(setting_set, "config:config-item", {
            "config:name": name, "config:type": "boolean",
        }, "true")
    for name in ("EmbedAsianScriptFonts", "EmbedComplexScriptFonts", "EmbedSystemFonts"):
        element(setting_set, "config:config-item", {
            "config:name": name, "config:type": "boolean",
        }, "false")
    entries = {
        "content.xml": ("text/xml", content_xml(spec, family)),
        "styles.xml": ("text/xml", styles_xml(spec, family)),
        "meta.xml": ("text/xml", xml_bytes(meta)),
        "settings.xml": ("text/xml", xml_bytes(settings)),
        "Fonts/computational.ttf": ("application/x-font-ttf", font_path.read_bytes()),
        "Fonts/Roboto-Regular.ttf": ("application/x-font-ttf", BASE.read_bytes()),
        "LICENSE.txt": ("text/plain", (ROOT / "LICENSE").read_bytes()),
        "THIRD_PARTY_NOTICES.txt": ("text/plain", (ROOT / "THIRD_PARTY_NOTICES.md").read_bytes()),
    }
    manifest = ET.Element(f"{{{NS['manifest']}}}manifest", {
        f"{{{NS['manifest']}}}version": "1.3",
    })
    element(manifest, "manifest:file-entry", {
        "manifest:full-path": "/", "manifest:media-type": MIMETYPE,
        "manifest:version": "1.3",
    })
    for path, (mime, _) in entries.items():
        element(manifest, "manifest:file-entry", {
            "manifest:full-path": path, "manifest:media-type": mime,
        })
    entries["META-INF/manifest.xml"] = ("text/xml", xml_bytes(manifest))
    output = font_path.with_name(font_path.stem.removesuffix("-font") + ".odt")
    # Fixed archive timestamps make unchanged specimens reproducible.
    with ZipFile(output, "w") as package:
        for path, data in [("mimetype", MIMETYPE.encode()),
                           *((p, d) for p, (_, d) in entries.items())]:
            info = ZipInfo(path, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_STORED if path == "mimetype" else ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            package.writestr(info, data)
    print(output.relative_to(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", choices=[s.folder for s in SPECS],
                        help=f"Build one project instead of all {len(SPECS)} specimens")
    args = parser.parse_args()
    for spec in SPECS:
        if args.project is None or spec.folder == args.project:
            build(spec)


if __name__ == "__main__":
    main()
