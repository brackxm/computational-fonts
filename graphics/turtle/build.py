# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""Build an OpenType turtle graphics font. Requires FontTools."""

import argparse
from pathlib import Path
import re

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildCoverage, buildLigatureSubstSubtable, buildLookup
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables import otTables

DEFAULT_WIDTH = DEFAULT_HEIGHT = 21
MAX_COMMANDS = 128
MAX_CELLS = 625
CELL, UPM = 100, 1000
# Clockwise, starting east. Coordinates use the font's upward y axis.
DIRECTIONS = ((1, 0), (0, -1), (-1, 0), (0, 1))
COMMANDS = "flrud"
PALETTE = (
    ("Ink", "173f39"), ("Red", "d64045"), ("Blue", "2563eb"),
    ("Green", "168047"), ("Orange", "d97706"), ("Purple", "9333ea"),
)
COLOR_COMMANDS = "".join(str(index) for index in range(len(PALETTE)))


def command_name(command):
    return f"digit{command}" if command.isdigit() else command


def colored_name(name, color):
    return f"{name}_c{color}" if color else name


def rectangle(pen, x, y, width, height):
    pen.moveTo((x, y))
    pen.lineTo((x + width, y))
    pen.lineTo((x + width, y + height))
    pen.lineTo((x, y + height))
    pen.closePath()


def board_glyph(width, height):
    pen = TTGlyphPen(None)
    rectangle(pen, 0, 0, width * CELL, 3)
    rectangle(pen, 0, height * CELL - 3, width * CELL, 3)
    rectangle(pen, 0, 0, 3, height * CELL)
    rectangle(pen, width * CELL - 3, 0, 3, height * CELL)
    return pen.glyph()


def marker_glyph(x, y, direction, down, width):
    pen = TTGlyphPen(None)
    cx, cy = (x - width) * CELL + CELL // 2, y * CELL + CELL // 2
    dx, dy = DIRECTIONS[direction]

    def triangle(size, reverse=False):
        points = [(size, 0), (-size, size * 0.7), (-size, -size * 0.7)]
        if reverse:
            points.reverse()
        points = [(round(cx + a * dx - b * dy), round(cy + a * dy + b * dx))
                  for a, b in points]
        pen.moveTo(points[0])
        for point in points[1:]:
            pen.lineTo(point)
        pen.closePath()

    triangle(25)
    if not down:
        triangle(15, reverse=True)
    return pen.glyph()


def blocked_glyph(x, y, width):
    pen = TTGlyphPen(None)
    cx, cy = (x - width) * CELL + CELL // 2, y * CELL + CELL // 2
    for sign in (-1, 1):
        pen.moveTo((cx - 25, cy - sign * 25 - 5))
        pen.lineTo((cx + 25, cy + sign * 25 - 5))
        pen.lineTo((cx + 25, cy + sign * 25 + 5))
        pen.lineTo((cx - 25, cy - sign * 25 + 5))
        pen.closePath()
    return pen.glyph()


def line_glyph(x, y, vertical, width):
    pen = TTGlyphPen(None)
    cx, cy = (x - width) * CELL + CELL // 2, y * CELL + CELL // 2
    # A little overlap closes the corners between consecutive segments.
    if vertical:
        rectangle(pen, cx - 4, cy - 4, 8, CELL + 8)
    else:
        rectangle(pen, cx - 4, cy - 4, CELL + 8, 8)
    return pen.glyph()


def state_name(x, y, direction, down):
    return f"turtle_{x}_{y}_{direction}_{down}"


def validate_size(width, height):
    if type(width) is not int or type(height) is not int:
        raise ValueError("Canvas dimensions must be whole numbers")
    if not (3 <= width <= 25 and 3 <= height <= 25) or width * height > MAX_CELLS:
        raise ValueError("Canvas dimensions must each be between 3 and 25")


def parse_size(value):
    match = re.fullmatch(r"([0-9]+)[xX×]([0-9]+)", value)
    if match is None:
        raise argparse.ArgumentTypeError("Use WIDTHxHEIGHT, for example 21x21")
    width, height = map(int, match.groups())
    try:
        validate_size(width, height)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return width, height


def pass_lookup(font, glyphs, lookup_index, flags=8):
    # Each clock pass has a distinct lookup index, but calls shared rule tables.
    # Repeating the large ligature tables exceeds shaping validation budgets.
    table = otTables.ContextSubst()
    table.Format = 3
    table.Coverage = [buildCoverage(glyphs, font.getReverseGlyphMap())]
    table.GlyphCount = 1
    record = otTables.SubstLookupRecord()
    record.SequenceIndex, record.LookupListIndex = 0, lookup_index
    table.SubstLookupRecord, table.SubstCount = [record], 1
    # Use 32-bit extension offsets up front. Large color glyph classes can
    # otherwise trigger hundreds of full-table packing retries on big canvases.
    return buildLookup([table], flags=flags, table="GSUB", extension=True)


def build_font(output, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
    validate_size(width, height)
    glyphs, metrics, order, color_layers = {}, {}, [], {}

    def add(name, glyph=None, advance=0):
        if name in glyphs:
            return
        if glyph is None:
            glyph = TTGlyphPen(None).glyph()
        glyph.recalcBounds(glyphs)
        order.append(name)
        glyphs[name] = glyph
        metrics[name] = (advance, getattr(glyph, "xMin", 0))

    def add_colors(base, advance=0):
        # COLR layers reuse the original outline. Composites also preserve
        # monochrome fallback outlines in renderers without color support.
        color_layers[base] = [(base, 0)]
        for color in range(1, len(PALETTE)):
            name = colored_name(base, color)
            pen = TTGlyphPen(glyphs)
            pen.addComponent(base, (1, 0, 0, 1, 0, 0))
            add(name, pen.glyph(), advance)
            color_layers[name] = [(base, color)]

    for name in (".notdef", "space", "b", *COMMANDS,
                 *(command_name(c) for c in COLOR_COMMANDS),
                 *(f"color_{c}" for c in COLOR_COMMANDS)):
        add(name)
    add("board", board_glyph(width, height), width * CELL)
    lines, fresh_lines, markers = [], [], []
    for y in range(height):
        for x in range(width):
            for axis, valid in (("h", x + 1 < width), ("v", y + 1 < height)):
                if valid:
                    name = f"line_{axis}_{x}_{y}"
                    add(name, line_glyph(x, y, axis == "v", width))
                    add_colors(name)
                    lines.append(name)
                    fresh = f"fresh_{name}"
                    add(fresh, glyphs[name])
                    fresh_lines.append(fresh)
            # A final blocked marker has a one-unit advance, read by the demo.
            blocked = f"blocked_{x}_{y}"
            add(blocked, blocked_glyph(x, y, width), advance=1)
            add_colors(blocked, advance=1)
            markers.append(blocked)
            for direction in range(4):
                for down in range(2):
                    marker = state_name(x, y, direction, down)
                    add(marker, marker_glyph(x, y, direction, down, width))
                    add_colors(marker)
                    markers.append(marker)

    states, tokens, steps, expansions = [], [], {}, {}
    for y in range(height):
        for x in range(width):
            for direction, (dx, dy) in enumerate(DIRECTIONS):
                for down in range(2):
                    current = state_name(x, y, direction, down)
                    states.append(current)
                    for command in COMMANDS + COLOR_COMMANDS:
                        tx, ty, facing, pen_down = x, y, direction, down
                        if command == "f":
                            tx, ty = x + dx, y + dy
                            if not (0 <= tx < width and 0 <= ty < height):
                                steps[(current, "f")] = f"blocked_{x}_{y}"
                                continue
                        elif command == "l":
                            facing = (direction - 1) % 4
                        elif command == "r":
                            facing = (direction + 1) % 4
                        elif command == "u":
                            pen_down = 0
                        elif command == "d":
                            pen_down = 1
                        destination = state_name(tx, ty, facing, pen_down)
                        if command == "f" and down:
                            line = f"fresh_line_{'h' if dx else 'v'}_{min(x, tx)}_{min(y, ty)}"
                            token = f"draw_{x}_{y}_{direction}"
                            expansion = f"{line} {destination}"
                        else:
                            token = f"next_{tx}_{ty}_{facing}_{pen_down}"
                            expansion = destination
                        if token not in expansions:
                            add(token)
                            tokens.append(token)
                            expansions[token] = expansion
                        steps[(current, command_name(command))] = token

    builder = FontBuilder(UPM, isTTF=True)
    builder.setupGlyphOrder(order)
    cmap = {ord(c): command_name(c) for c in "b" + COMMANDS + COLOR_COMMANDS}
    cmap.update({ord(c.upper()): c for c in "b" + COMMANDS})
    # Spaces are ignored by movement rules; newlines must be flattened to spaces
    # by the host to avoid separate shaping runs.
    cmap[ord(" ")] = "space"
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    ascent = height * CELL + 50
    builder.setupHorizontalHeader(ascent=ascent, descent=-50)
    family = f"Turtle Graphics {width}x{height}"
    builder.setupNameTable({
        "familyName": family, "styleName": "Regular", "fullName": family,
        "psName": f"TurtleGraphics{width}x{height}-Regular",
        "uniqueFontIdentifier": f"TurtleGraphics{width}x{height}-1.1",
        "version": "Version 1.1", 16: family, 17: "Regular",
        "copyright": "Copyright 2026 Michael Brackx",
        "licenseDescription": "Licensed under the Apache License, Version 2.0",
        "licenseInfoURL": "https://www.apache.org/licenses/LICENSE-2.0",
    })
    builder.setupOS2(sTypoAscender=ascent, sTypoDescender=-50,
                     usWinAscent=ascent, usWinDescent=50, fsType=0)
    builder.setupPost()
    builder.setupMaxp()
    builder.setupCOLR(color_layers, version=0)
    builder.setupCPAL([[
        tuple(int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1.0,)
        for _, hex_color in PALETTE
    ]])
    font = builder.font
    colors = [f"color_{c}" for c in COLOR_COMMANDS]
    colored_lines = [colored_name(line, color) for color in range(len(PALETTE)) for line in lines]
    feature = [
        "languagesystem DFLT dflt;", "languagesystem latn dflt;",
        "@STATE = [" + " ".join(states) + "];",
        "@COLORS = [" + " ".join(colors) + "];",
        "@FRESH = [" + " ".join(fresh_lines) + "];",
        "@MARKER = [" + " ".join(markers) + "];",
        "@MARKS = [space @COLORS @FRESH " + " ".join(colored_lines) + "];",
        "table GDEF { GlyphClassDef , , @MARKS, ; } GDEF;",
        "lookup INIT useExtension {",
        f"sub b by board {state_name(width // 2, height // 2, 0, 1)} color_0;",
        "} INIT;",
        # The color mark survives state/command ligatures and travels after
        # the new state. Selecting a color consumes one ordinary clock pass.
        "lookup SELECT_COLOR useExtension { lookupflag UseMarkFilteringSet @COLORS;",
        *(f"sub @STATE @COLORS' digit{c} by color_{c};" for c in COLOR_COMMANDS),
        "} SELECT_COLOR;",
        # A placeholder reserves the feature index; the large transition map
        # is installed directly below to avoid feaLib's per-rule mapping scans.
        "lookup STEP useExtension { lookupflag IgnoreMarks; sub b f by b; } STEP;",
        "lookup EXPAND useExtension {",
        *(f"sub {token} by {expansion};" for token, expansion in expansions.items()),
        "} EXPAND;",
        "lookup PAINT useExtension { lookupflag UseMarkFilteringSet [@FRESH @COLORS];",
        *(f"sub @FRESH' @STATE color_{color} by [{' '.join(colored_name(line, color) for line in lines)}];"
          for color in range(len(PALETTE))),
        "} PAINT;",
        # Paint the final turtle or boundary marker only after all commands.
        # Movement rules therefore need only the original, color-free states.
        "lookup PAINT_MARKER useExtension { lookupflag UseMarkFilteringSet @COLORS;",
        *(f"sub @MARKER' color_{color} by [{' '.join(colored_name(marker, color) for marker in markers)}];"
          for color in range(1, len(PALETTE))),
        "} PAINT_MARKER;",
        "feature liga { lookup INIT; lookup SELECT_COLOR; lookup STEP; lookup EXPAND; lookup PAINT; lookup PAINT_MARKER; } liga;",
    ]
    addOpenTypeFeaturesFromString(font, "\n".join(feature))
    liga = next(record.Feature for record in font["GSUB"].table.FeatureList.FeatureRecord
                if record.FeatureTag == "liga")
    lookups = font["GSUB"].table.LookupList
    init, select_color, step, expand, paint, paint_marker = liga.LookupListIndex
    # Bound each GSUB4 subtable's 16-bit internal offsets before packing, and
    # use extension offsets between subtables. All entries for a state stay
    # together. This also avoids repeated overflow repair on the biggest canvas.
    subtables = []
    for start in range(0, len(states), 512):
        group = set(states[start:start + 512])
        mapping = {pair: target for pair, target in steps.items() if pair[0] in group}
        subtables.append(buildLigatureSubstSubtable(mapping))
    lookups.Lookup[step] = buildLookup(subtables, flags=8, table="GSUB", extension=True)
    liga.LookupListIndex = [init, select_color, step, expand, paint]
    passes = [pass_lookup(font, colors, select_color, flags=0),
              pass_lookup(font, states, step), pass_lookup(font, tokens, expand),
              pass_lookup(font, fresh_lines, paint, flags=0)]
    for _ in range(MAX_COMMANDS - 1):
        for lookup in passes:
            liga.LookupListIndex.append(len(lookups.Lookup))
            lookups.Lookup.append(lookup)
    # Shapers execute lookup indices in order. A new final wrapper keeps
    # marker painting after every clock pass, leaving the movement states intact.
    liga.LookupListIndex.append(len(lookups.Lookup))
    lookups.Lookup.append(pass_lookup(font, markers, paint_marker, flags=0))
    liga.LookupCount = len(liga.LookupListIndex)
    lookups.LookupCount = len(lookups.Lookup)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    font.save(output)
    font.close()
    print(f"Saved {output}: {width}×{height} canvas, up to {MAX_COMMANDS} commands")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=parse_size, default=(DEFAULT_WIDTH, DEFAULT_HEIGHT),
                        metavar="WIDTHxHEIGHT", help="canvas baked into font (default: 21x21)")
    parser.add_argument("--output", type=Path, help="output .ttf path")
    args = parser.parse_args()
    width, height = args.size
    filename = ("turtle-font.ttf" if args.size == (DEFAULT_WIDTH, DEFAULT_HEIGHT)
                else f"turtle-{width}x{height}-font.ttf")
    build_font(args.output or Path(__file__).resolve().with_name(filename), width, height)


if __name__ == "__main__":
    main()
