# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""Shared bounded Netpbm renderer; project wrappers choose a format."""

from dataclasses import dataclass
from itertools import product
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildAnchor, buildLookup, buildMarkBasePosSubtable
from fontTools.pens.ttGlyphPen import TTGlyphPen

MAX_SIZE, CELL, UPM = 32, 64, 2048
MAX_PIXELS = MAX_SIZE * MAX_SIZE
TOP = MAX_SIZE * CELL
ERROR_ADVANCE = TOP + 1


def rectangle(pen, x, y, width, height):
    pen.moveTo((x, y))
    pen.lineTo((x + width, y))
    pen.lineTo((x + width, y + height))
    pen.lineTo((x, y + height))
    pen.closePath()


@dataclass(frozen=True)
class ImageFormat:
    name: str
    magic: int
    colors: tuple
    cells: tuple[str, ...]
    maxval: int | None = None
    channels: int = 1


PBM = ImageFormat("PBM", 1, ((1, 1, 1, 1), (0, 0, 0, 1)), ("white_cell", "black_cell"))
PGM = ImageFormat("PGM", 2, tuple((i / 15, i / 15, i / 15, 1) for i in range(16)),
                  tuple(f"gray_{i}_cell" for i in range(16)), 15)

PPM = ImageFormat("PPM", 3,
                  tuple((r / 3, g / 3, b / 3, 1) for r, g, b in product(range(4), repeat=3)),
                  tuple(f"rgb_{r}_{g}_{b}_cell" for r, g, b in product(range(4), repeat=3)), 3, 3)


def error_glyph(format):
    # Original five-by-seven lettering; no external font source is needed.
    letters = {
        "I": (31, 4, 4, 4, 4, 4, 31), "N": (17, 25, 25, 21, 19, 19, 17),
        "V": (17, 17, 17, 17, 17, 10, 4), "A": (14, 17, 17, 31, 17, 17, 17),
        "L": (16, 16, 16, 16, 16, 16, 31), "D": (30, 17, 17, 17, 17, 17, 30),
        "P": (30, 17, 17, 30, 16, 16, 16), "B": (30, 17, 17, 30, 17, 17, 30),
        "M": (17, 27, 21, 21, 17, 17, 17),
        "G": (14, 17, 16, 23, 17, 17, 14),
    }
    pen = TTGlyphPen(None)
    for column, letter in enumerate(f"INVALID {format.name}"):
        for row, bits in enumerate(letters.get(letter, ())):
            for bit in range(5):
                if bits & (1 << (4 - bit)):
                    rectangle(pen, (column * 6 + bit) * 30, TOP - (row + 1) * 30, 30, 30)
    return pen.glyph()


def sample_features(format):
    """Recognize bounded samples; group P3 channels into one token per pixel."""
    if format.maxval is None:
        return ["lookup SAMPLES { sub digit_0 by sample_0; sub digit_1 by sample_1; } SAMPLES;"]
    if format.channels == 3:
        # Channel recognition preserves whitespace boundaries. Triple grouping
        # skips spaces, but never skips invalid raw digits or leftover channels.
        rules = ["lookup SAMPLES useExtension {"]
        rules.extend(f"sub [@HEADER space] digit_{v}' [space eof] by channel_{v};"
                     for v in range(format.maxval + 1))
        rules.extend(["} SAMPLES;", "lookup RGB_TRIPLES useExtension {",
                      "lookupflag UseMarkFilteringSet [@ACTIVE_RAW eof];"])
        for index, (r, g, b) in enumerate(product(range(format.maxval + 1), repeat=3)):
            rules.append(f"sub channel_{r} channel_{g} channel_{b} by sample_{index};")
        rules.append("} RGB_TRIPLES;")
        return rules
    rules = []
    for value in range(format.maxval + 1):
        digits = " ".join(f"digit_{d}" for d in str(value))
        rules.append(f"lookup SAMPLE_{value} {{ sub {digits} by sample_{value}; }} SAMPLE_{value};")
    rules.append("lookup SAMPLES useExtension {")
    for value in range(format.maxval + 1):
        digits = " ".join(f"digit_{d}'" + (f" lookup SAMPLE_{value}" if j == 0 else "")
                          for j, d in enumerate(str(value)))
        rules.append(f"sub [@HEADER space] {digits} [space eof];")
    rules.append("} SAMPLES;")
    return rules


def build_font(output, format=PBM):
    glyphs, metrics, layers = {}, {}, {}

    def add(name, glyph=None, advance=0):
        if glyph is None:
            glyph = TTGlyphPen(glyphs).glyph()
        glyph.recalcBounds(glyphs)
        glyphs[name] = glyph
        metrics[name] = (advance, getattr(glyph, "xMin", 0))

    raw = [".notdef", "raw_invalid", "raw_P", "space", *(f"digit_{i}" for i in range(10))]
    for name in [*raw, "hidden", "eof"]:
        add(name)
    add("error", error_glyph(format), ERROR_ADVANCE)
    pen = TTGlyphPen(None)
    rectangle(pen, 0, 0, CELL, CELL)
    add("ink_cell", pen.glyph())
    # Solid COLR cells share one outline. Monochrome fallback uses ordered
    # dithering of display brightness; the palette stores sRGB display values.
    bayer = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
    palette = [(1, 1, 1, 1), *format.colors]
    for value, (cell, color) in enumerate(zip(format.cells, format.colors)):
        pen = TTGlyphPen(glyphs)
        darkness = 1 - (color[0] if format.channels == 1 else
                        (299 * color[0] + 587 * color[1] + 114 * color[2]) / 1000)
        if darkness == 1:
            pen.addComponent("ink_cell", (1, 0, 0, 1, 0, 0))
        elif darkness:
            for row in range(4):
                for col in range(4):
                    if bayer[row][col] < round(darkness * 16):
                        rectangle(pen, col * 16, row * 16, 16, 16)
        add(cell, pen.glyph())
        if darkness:
            layers[cell] = [("ink_cell", value + 1)]
    # Preserve PBM's established two-entry palette and layer IDs.
    if format == PBM:
        palette = list(format.colors)
        layers["black_cell"] = [("ink_cell", 1)]
    headers, frames, boards, backgrounds = [], [], [], []
    for width in range(1, MAX_SIZE + 1):
        board = f"board_{width}"
        boards.append(board)
        add(board, advance=width * CELL)
        for height in range(1, MAX_SIZE + 1):
            header, frame = f"header_{width}_{height}", f"frame_{width}_{height}"
            headers.append(header)
            frames.append(frame)
            pen = TTGlyphPen(glyphs)
            pen.addComponent("error", (1, 0, 0, 1, 0, 0))
            add(header, pen.glyph(), ERROR_ADVANCE)
            add(frame)
            pen = TTGlyphPen(None)
            # The paper follows the advancing board. Its negative x origin
            # brings it back to the board's left edge without a GPOS anchor.
            rectangle(pen, -width * CELL, TOP - height * CELL, width * CELL, height * CELL)
            background = f"background_{width}_{height}"
            paper = f"paper_{width}_{height}"
            backgrounds.append(background)
            add(paper, pen.glyph())
            add(background)
            layers[background] = [(paper, 0)]

    tags = [f"pixel_{i}" for i in range(MAX_PIXELS)]
    ends = [f"end_{i}" for i in range(MAX_PIXELS)]
    drawn = [f"draw_{i}" for i in range(MAX_PIXELS)]
    samples = [f"sample_{i}" for i in range(len(format.colors))]
    tones = [f"tone_{i}" for i in range(len(format.colors))]
    channels = [f"channel_{i}" for i in range(format.maxval + 1)] if format.channels == 3 else []
    for name in ["cursor", *channels, *tags, *ends, *drawn, *samples, *tones,
                 *(f"index_{i}" for i in range(MAX_PIXELS))]:
        add(name)

    builder = FontBuilder(UPM, isTTF=True)
    builder.setupGlyphOrder(list(glyphs))
    cmap = {code: "raw_invalid" for code in range(32, 127)}
    cmap.update({ord("P"): "raw_P", ord(" "): "space"})
    cmap.update({ord(str(i)): f"digit_{i}" for i in range(10)})
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=TOP, descent=0)
    builder.setupNameTable({
        "familyName": f"{format.name} Renderer", "styleName": "Regular", "fullName": f"{format.name} Renderer",
        "psName": f"{format.name}Renderer-Regular", "uniqueFontIdentifier": f"{format.name}Renderer-1.2",
        "version": "Version 1.2", 16: f"{format.name} Renderer", 17: "Regular",
        "copyright": "Copyright 2026 Michael Brackx",
        "licenseDescription": "Licensed under the Apache License, Version 2.0",
        "licenseInfoURL": "https://www.apache.org/licenses/LICENSE-2.0",
    })
    builder.setupOS2(sTypoAscender=TOP, sTypoDescender=0, usWinAscent=TOP,
                     usWinDescent=0, fsType=0)
    builder.setupPost()
    builder.setupMaxp()
    builder.setupCOLR(layers, version=0)
    builder.setupCPAL([palette])
    font = builder.font

    def group(name, values):
        return f"@{name} = [{' '.join(values)}];"

    active_raw = [name for name in raw if name != "space"] + channels
    feature = [
        "languagesystem DFLT dflt;", "languagesystem latn dflt;",
        group("RAW", raw), group("ACTIVE_RAW", active_raw),
        group("HEADER", headers), group("FRAME", frames), group("BOARD", boards),
        group("TAG", tags), group("END", ends), group("DRAW", drawn),
        group("SAMPLE", samples), group("TONE", tones), group("PENDING", ["cursor", *channels]),
        group("MARKS", [*raw, "hidden", "eof", "cursor", *channels, *tags, *ends, *drawn, *samples, *tones, *backgrounds,
                        *(f"index_{i}" for i in range(MAX_PIXELS)), *format.cells]),
        "table GDEF { GlyphClassDef [error @HEADER @FRAME @BOARD], , @MARKS, ; } GDEF;",
        "lookup APPEND_END {",
        *(f"sub {name} by {name} eof;" for name in raw),
        "} APPEND_END;",
        "lookup END_OF_RUN useExtension {",
        "ignore sub @RAW' @RAW; sub @RAW' lookup APPEND_END;",
        "} END_OF_RUN;",
        "lookup PREPEND_ERROR {",
        *(f"sub {name} by error {name};" for name in raw),
        "} PREPEND_ERROR;",
        "lookup START_OF_RUN useExtension {",
        "ignore sub @RAW @RAW'; sub @RAW' lookup PREPEND_ERROR;",
        "} START_OF_RUN;",
        "lookup HEADER useExtension {",
    ]
    for width in range(1, MAX_SIZE + 1):
        for height in range(1, MAX_SIZE + 1):
            for w in (str(width), f"{width:02}") if width < 10 else (str(width),):
                for h in (str(height), f"{height:02}") if height < 10 else (str(height),):
                    dimensions = " space ".join(" ".join(f"digit_{d}" for d in n) for n in (w, h))
                    maxval = "" if format.maxval is None else " ".join(f"digit_{d}" for d in str(format.maxval)) + " space "
                    feature.append(f"sub error raw_P digit_{format.magic} space {dimensions} space {maxval}by header_{width}_{height};")
    feature.append("} HEADER;")
    feature.extend(sample_features(format))
    sample_lookups = "lookup SAMPLES; " + ("lookup RGB_TRIPLES; " if format.channels == 3 else "")
    feature.extend([
        "lookup EXPAND_SAMPLES {",
        *(f"sub sample_{i} by cursor tone_{i};" for i in range(len(format.colors))),
        "} EXPAND_SAMPLES;",
    ])
    for index in range(MAX_PIXELS):
        feature.append(f"lookup NUMBER_{index} {{ sub cursor by pixel_{index}; }} NUMBER_{index};")
    feature.extend([
        "lookup NUMBER useExtension { lookupflag UseMarkFilteringSet [@ACTIVE_RAW @TAG cursor eof];",
        "sub @HEADER cursor' lookup NUMBER_0;",
        *(f"sub pixel_{i - 1} cursor' lookup NUMBER_{i};" for i in range(1, MAX_PIXELS)),
        "} NUMBER;",
        "lookup FINISH useExtension { lookupflag UseMarkFilteringSet [@ACTIVE_RAW @TAG cursor eof];",
        *(f"sub pixel_{i} eof by end_{i};" for i in range(MAX_PIXELS)),
        "} FINISH;",
        # Colors and counted pixels are skipped. Unparsed raw characters,
        # uncounted cursors and the last counted pixel remain barriers.
        "lookup VALIDATE useExtension { lookupflag UseMarkFilteringSet [@ACTIVE_RAW @END cursor eof];",
        *(f"sub header_{w}_{h}' end_{w * h - 1} by frame_{w}_{h};"
          for w in range(1, MAX_SIZE + 1) for h in range(1, MAX_SIZE + 1)),
        "} VALIDATE;",
        "lookup DRAW_PIXEL {",
        *(f"sub {prefix}_{i} by draw_{i};" for prefix in ("pixel", "end") for i in range(MAX_PIXELS)),
        "} DRAW_PIXEL;",
        "lookup DRAW useExtension { lookupflag UseMarkFilteringSet [@ACTIVE_RAW @TAG @END @DRAW cursor eof];",
        "sub @FRAME [@TAG @END]' lookup DRAW_PIXEL;",
        "sub @DRAW [@TAG @END]' lookup DRAW_PIXEL;",
        "} DRAW;",
        "lookup COLOR useExtension { lookupflag UseMarkFilteringSet [@DRAW @TONE];",
        *(f"sub @DRAW tone_{i}' by {cell};" for i, cell in enumerate(format.cells)),
        "} COLOR;",
        "lookup CLEANUP useExtension {",
        "sub [@RAW @TAG @END @SAMPLE @TONE @PENDING eof] by hidden; sub @HEADER by error;",
        "} CLEANUP;",
        "lookup LAYOUT useExtension {",
        *(f"sub frame_{w}_{h} by board_{w} background_{w}_{h};"
          for w in range(1, MAX_SIZE + 1) for h in range(1, MAX_SIZE + 1)),
        *(f"sub draw_{i} by index_{i};" for i in range(MAX_PIXELS)),
        "} LAYOUT;",
        "feature rlig { lookup END_OF_RUN; lookup START_OF_RUN; lookup HEADER; " + sample_lookups + "lookup EXPAND_SAMPLES; lookup NUMBER; lookup FINISH; lookup VALIDATE; lookup DRAW; lookup COLOR; lookup CLEANUP; lookup LAYOUT; } rlig;",
        # A placeholder creates the standard mark feature and script wiring.
        "markClass index_0 <anchor 0 0> @ORIGIN;",
        "feature mark { pos base board_1 <anchor 0 0> mark @ORIGIN; } mark;",
        f"markClass [{' '.join(format.cells)}] <anchor 0 0> @CELL;",
        "feature mkmk {",
        *(f"pos mark index_{i} <anchor 0 0> mark @CELL;" for i in range(MAX_PIXELS)),
        "} mkmk;",
    ])
    addOpenTypeFeaturesFromString(font, "\n".join(feature))
    subtables = []
    for width in range(1, MAX_SIZE + 1):
        # Only indices that fit this width can occur. Narrow boards therefore
        # need fewer mark classes and never get out-of-range y coordinates.
        marks = {f"index_{i}": (i, buildAnchor(0, 0)) for i in range(width * MAX_SIZE)}
        anchors = {i: buildAnchor(i % width * CELL, TOP - (i // width + 1) * CELL)
                   for i in range(width * MAX_SIZE)}
        bases = {f"board_{width}": anchors}
        subtables.append(buildMarkBasePosSubtable(marks, bases, font.getReverseGlyphMap()))
    # One advancing base per width shares positioning across every height.
    # The separate paper marks supply the height-dependent white background.
    # Extension offsets avoid the 64 KiB distance limit between subtables.
    font["GPOS"].table.LookupList.Lookup[0] = buildLookup(subtables, table="GPOS", extension=True)
    # Each cell attaches to its positioned index mark. Reusing one black cell
    # avoids thousands of COLR entries and prevents PDF exporters from packing
    # long sequences of distinct zero-width color glyphs with rounded spacing.
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    font.save(output)
    font.close()
    print(f"Saved {output}: plain {format.name}, dimensions 1–{MAX_SIZE}, up to {MAX_PIXELS} pixels")
