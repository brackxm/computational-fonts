# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Retained third-party notices: see THIRD_PARTY_NOTICES.md at the project root.

"""Build a Snake font with a board size fixed at build time. Requires FontTools."""

import argparse
from pathlib import Path
import re

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildCoverage, buildLookup, buildSingleSubstSubtable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables import otTables

DEFAULT_WIDTH, DEFAULT_HEIGHT = 20, 11
MAX_MOVES = 128
MAX_FOODS = 8
MAX_CELLS = 1024
CELL, UPM = 100, 1000
MOVES = {"w": (0, 1), "a": (-1, 0), "s": (0, -1), "d": (1, 0)}
OPPOSITE = {"w": "s", "a": "d", "s": "w", "d": "a"}


def rectangle(pen, x, y, width, height):
    pen.moveTo((x, y))
    pen.lineTo((x + width, y))
    pen.lineTo((x + width, y + height))
    pen.lineTo((x, y + height))
    pen.closePath()


def outline(pen, x, y, size, thickness):
    rectangle(pen, x, y, size, thickness)
    rectangle(pen, x, y + size - thickness, size, thickness)
    rectangle(pen, x, y, thickness, size)
    rectangle(pen, x + size - thickness, y, thickness, size)


def board_glyph(width, height):
    pen = TTGlyphPen(None)
    rectangle(pen, 0, 0, width * CELL, 3)
    rectangle(pen, 0, height * CELL - 3, width * CELL, 3)
    rectangle(pen, 0, 0, 3, height * CELL)
    rectangle(pen, width * CELL - 3, 0, 3, height * CELL)
    return pen.glyph()


def overlay(kind, x, y, width):
    pen = TTGlyphPen(None)
    # The board supplies the run's advance. Every subsequent glyph overlays it.
    left, bottom = (x - width) * CELL, y * CELL
    if kind == "body":
        rectangle(pen, left + 22, bottom + 22, 56, 56)
    elif kind in ("head", "win"):
        outline(pen, left + 16, bottom + 16, 68, 8)
        if kind == "win":
            for dx, dy in ((20, 0), (42, 10), (64, 0)):
                rectangle(pen, left + dx, bottom + CELL + dy, 16, 16)
    elif kind == "food":
        pen.moveTo((left + 50, bottom + 72))
        pen.lineTo((left + 72, bottom + 50))
        pen.lineTo((left + 50, bottom + 28))
        pen.lineTo((left + 28, bottom + 50))
        pen.closePath()
    elif kind == "dead":
        for offset in range(18, 82, 9):
            rectangle(pen, left + offset, bottom + offset, 9, 9)
            rectangle(pen, left + 91 - offset, bottom + offset, 9, 9)
    return pen.glyph()


def head(x, y, direction):
    return f"head_{x}_{y}_{direction}"


def food_positions(width, height):
    # Small boards cannot accommodate the growing snake's circuit.
    if width < 8 or height < 6:
        return [(width - 1, height - 1)]
    corners = [(width - 2, height - 2), (1, height - 2),
               (1, 1), (width - 2, 1)]
    targets, distance = [], 0
    previous = (2, height // 2)
    for index in range(MAX_FOODS):
        target = corners[index % len(corners)]
        distance += abs(target[0] - previous[0]) + abs(target[1] - previous[1])
        if distance > MAX_MOVES:
            break
        targets.append(target)
        previous = target
    return targets


def collision_lookup(font, targets, foods, die_index, mark_filter_set):
    # Class-based contexts avoid repeating a full-board coverage for every body
    # position. Class 0 is any other body, 1 is the occupied destination, and
    # 2 prevents contexts from crossing the board/food prefix into a vacating tail.
    by_cell = {}
    for token, (x, y, _) in targets.items():
        by_cell.setdefault((x, y), []).append(token)
    subtables = []
    for (x, y), tokens in by_cell.items():
        table = otTables.ChainContextSubst()
        table.Format = 2
        table.Coverage = buildCoverage(tokens, font.getReverseGlyphMap())
        table.BacktrackClassDef = otTables.ClassDef()
        table.BacktrackClassDef.classDefs = {
            "board": 2, **{f"food_{i}": 2 for i in range(len(foods))},
            **{f"pending_{i}": 2 for i in range(len(foods))},
            f"body_{x}_{y}": 1,
        }
        table.InputClassDef = otTables.ClassDef()
        table.InputClassDef.classDefs = {
            token: (1 if token.startswith("step_") else 2) for token in tokens
        }
        table.LookAheadClassDef = otTables.ClassDef()
        table.LookAheadClassDef.classDefs = {}
        table.ChainSubClassSet = [None]
        for token_class in (1, 2):
            rules = otTables.ChainSubClassSet()
            rules.ChainSubClassRule = []
            for distance in range(len(foods) + 1):
                rule = otTables.ChainSubClassRule()
                rule.Backtrack = [0] * distance + [1] + ([0] if token_class == 1 else [])
                rule.BacktrackGlyphCount = len(rule.Backtrack)
                rule.Input, rule.InputGlyphCount = [], 1
                rule.LookAhead, rule.LookAheadGlyphCount = [], 0
                record = otTables.SubstLookupRecord()
                record.SequenceIndex, record.LookupListIndex = 0, die_index
                rule.SubstLookupRecord, rule.SubstCount = [record], 1
                rules.ChainSubClassRule.append(rule)
            rules.ChainSubClassRuleCount = len(rules.ChainSubClassRule)
            table.ChainSubClassSet.append(rules)
        table.ChainSubClassSetCount = len(table.ChainSubClassSet)
        subtables.append(table)
    return buildLookup(subtables, markFilterSet=mark_filter_set, table="GSUB")


def pass_lookup(font, lookup_index):
    # A small context calls the shared rule table. Copying the entire collision
    # table for every pass exhausts shaping engines' table-validation budgets.
    table = otTables.ContextSubst()
    table.Format = 3
    table.Coverage = [buildCoverage(font.getGlyphOrder(), font.getReverseGlyphMap())]
    table.GlyphCount = 1
    record = otTables.SubstLookupRecord()
    record.SequenceIndex, record.LookupListIndex = 0, lookup_index
    table.SubstLookupRecord, table.SubstCount = [record], 1
    return buildLookup([table], table="GSUB")


def validate_size(width, height):
    if type(width) is not int or type(height) is not int:
        raise ValueError("Board dimensions must be whole numbers")
    if width < 4 or height < 1:
        raise ValueError("Board width must be at least 4 and height at least 1")
    if width * height > MAX_CELLS:
        raise ValueError(f"Board must contain at most {MAX_CELLS} cells")
    first_food = ((width - 1, height - 1) if width < 8 or height < 6
                  else (width - 2, height - 2))
    required_moves = abs(first_food[0] - 2) + abs(first_food[1] - height // 2)
    if required_moves > MAX_MOVES:
        raise ValueError(
            f"Food requires {required_moves} moves on a {width}×{height} board; "
            f"the font supports at most {MAX_MOVES}"
        )


def parse_size(value):
    match = re.fullmatch(r"([0-9]+)[xX×]([0-9]+)", value)
    if match is None:
        raise argparse.ArgumentTypeError("Use WIDTHxHEIGHT, for example 20x11")
    width, height = map(int, match.groups())
    try:
        validate_size(width, height)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return width, height


def build_font(output, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT):
    validate_size(width, height)
    output = Path(output)
    start_y = height // 2
    foods = food_positions(width, height)
    glyphs, metrics, order = {}, {}, []

    def add(name, glyph=None, advance=0):
        if name in glyphs:
            return
        if glyph is None:
            glyph = TTGlyphPen(None).glyph()
        glyph.recalcBounds(None)
        glyphs[name] = glyph
        metrics[name] = (advance, getattr(glyph, "xMin", 0))
        order.append(name)

    for name in (".notdef", "ghost", "b", *MOVES):
        add(name)
    add("board", board_glyph(width, height), width * CELL)
    for index, position in enumerate(foods):
        add(f"food_{index}", overlay("food", *position, width))
        add(f"pending_{index}")
    # One/two font units of advance report loss/win to the playground. These
    # terminal glyphs come last, so the board's visible coordinates do not move.
    add("win", overlay("win", *foods[-1], width), advance=2)
    heads, bodies = [], []
    steps, expansions, food_rules, advances = [], [], [], []
    normal_tokens, eat_tokens, targets = [], [], {}

    for y in range(height):
        for x in range(width):
            body = f"body_{x}_{y}"
            dead = f"dead_{x}_{y}"
            add(body, overlay("body", x, y, width))
            add(dead, overlay("dead", x, y, width), advance=1)
            bodies.append(body)
            for facing in MOVES:
                current = head(x, y, facing)
                add(current, overlay("head", x, y, width))
                heads.append(current)
                for command, (dx, dy) in MOVES.items():
                    tx, ty = x + dx, y + dy
                    if command == OPPOSITE[facing] or not (0 <= tx < width and 0 <= ty < height):
                        steps.append(f"sub {current} {command} by {dead};")
                    else:
                        token = f"step_{x}_{y}_{command}"
                        is_new = token not in glyphs
                        add(token)
                        steps.append(f"sub {current} {command} by {token};")
                        if is_new:
                            normal_tokens.append(token)
                            targets[token] = (tx, ty, dead)
                            expansions.append(f"sub {token} by {body} {head(tx, ty, command)};")
                        for index, position in enumerate(foods):
                            if (tx, ty) != position:
                                continue
                            eat_command = f"eat_{index}_{command}"
                            add(eat_command)
                            food_rules.append(
                                f"sub food_{index} {current} {command}' by {eat_command};"
                            )
                            eat_token = f"bite_{index}_{x}_{y}_{command}"
                            is_new_eat = eat_token not in glyphs
                            add(eat_token)
                            steps.append(f"sub {current} {eat_command} by {eat_token};")
                            if is_new_eat:
                                eat_tokens.append(eat_token)
                                targets[eat_token] = (tx, ty, dead)
                                destination = ("win" if index == len(foods) - 1
                                               else head(tx, ty, command))
                                expansions.append(f"sub {eat_token} by {body} {destination};")

    drops = []
    for index in range(len(foods)):
        # Eating preserves the tail. Normal moves remove exactly the oldest body.
        remaining_bodies = " ".join(["@BODY"] * (index + 1))
        drops.append(f"sub [food_{index} pending_{index}] @BODY' {remaining_bodies} @NORMAL by ghost;")
        bites = [token for token in eat_tokens if token.startswith(f"bite_{index}_")]
        next_food = f"food_{index + 1}" if index + 1 < len(foods) else "ghost"
        advances.append(f"sub food_{index}' [{' '.join(bites)}] by {next_food};")

    placements, placement_names = [], []
    if len(foods) > 1:
        by_position = {}
        for index, position in enumerate(foods):
            by_position.setdefault(position, []).append(index)
        for number, ((x, y), indices) in enumerate(by_position.items()):
            name = f"PLACE_{number}"
            placement_names.append(name)
            active = "[" + " ".join(f"food_{i}" for i in indices) + "]"
            pending = "[" + " ".join(f"pending_{i}" for i in indices) + "]"
            blockers = "[" + " ".join(head(x, y, facing) for facing in MOVES) + f" dead_{x}_{y}]"
            # Only this cell's body mark is included. Other body/ghost marks
            # are skipped, letting the food prefix see occupancy anywhere in
            # the snake. A pending target cannot be eaten until it reappears.
            placements += [
                f"lookup {name} {{ lookupflag UseMarkFilteringSet [body_{x}_{y}];",
                f"ignore sub {pending}' body_{x}_{y};",
                f"ignore sub {pending}' {blockers};",
                f"sub {pending}' by {active};",
                f"sub {active}' body_{x}_{y} by {pending};",
                f"sub {active}' {blockers} by {pending};",
                f"}} {name};",
            ]

    builder = FontBuilder(UPM, isTTF=True)
    builder.setupGlyphOrder(order)
    cmap = {ord(c): c for c in ("b", *MOVES)}
    cmap.update({ord(c): move for c, move in zip("2486", "wasd")})
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    ascent = height * CELL + 50
    builder.setupHorizontalHeader(ascent=ascent, descent=-50)
    family = f"Snake Fixed {width}x{height}"
    builder.setupNameTable({
        "familyName": family, "styleName": "Regular", "fullName": family,
        "psName": f"SnakeFixed{width}x{height}-Regular",
        "uniqueFontIdentifier": f"SnakeFixed{width}x{height}-3.1",
        "version": "Version 3.1", 16: family, 17: "Regular",
        "copyright": "Copyright 2026 Michael Brackx",
        "licenseDescription": "Licensed under the Apache License, Version 2.0",
        "licenseInfoURL": "https://www.apache.org/licenses/LICENSE-2.0",
    })
    builder.setupOS2(sTypoAscender=ascent, sTypoDescender=-50,
                     usWinAscent=ascent, usWinDescent=50)
    builder.setupPost()
    builder.setupMaxp()
    font = builder.font
    feature = [
        "languagesystem DFLT dflt;", "languagesystem latn dflt;",
        "@BODY = [" + " ".join(bodies) + "];",
        "@HEAD = [" + " ".join(heads) + "];",
        "@MOVES = [w a s d];",
        "@NORMAL = [" + " ".join(normal_tokens) + "];",
        "@MARKS = [ghost @BODY];",
        "table GDEF { GlyphClassDef , , @MARKS, ; } GDEF;",
        "lookup INIT {",
        f"sub b by board food_0 body_0_{start_y} body_1_{start_y} {head(2, start_y, 'd')};",
        "} INIT;",
        "lookup FOOD { lookupflag IgnoreMarks;", *food_rules, "} FOOD;",
        "lookup STEP {", *steps, "} STEP;",
        "lookup DROP_TAIL { lookupflag UseMarkFilteringSet @BODY;", *drops, "} DROP_TAIL;",
        "lookup COLLISION { lookupflag UseMarkFilteringSet @BODY; sub ghost by ghost; } COLLISION;",
        "lookup ADVANCE_FOOD { lookupflag IgnoreMarks;", *advances, "} ADVANCE_FOOD;",
        "lookup EXPAND {", *expansions, "} EXPAND;",
        *placements,
        "feature liga { lookup INIT; lookup FOOD; lookup STEP; lookup COLLISION; "
        "lookup DROP_TAIL; lookup ADVANCE_FOOD; lookup EXPAND; " +
        " ".join(f"lookup {name};" for name in placement_names) + " } liga;",
    ]
    addOpenTypeFeaturesFromString(font, "\n".join(feature))

    # Distinct lookup indices give each appended command its own shaping pass.
    liga = next(r.Feature for r in font["GSUB"].table.FeatureList.FeatureRecord if r.FeatureTag == "liga")
    lookups = font["GSUB"].table.LookupList
    top = list(liga.LookupListIndex)
    if len(top) != 7 + len(placement_names):
        raise RuntimeError(f"Unexpected move lookup indices: {top}")
    die_index = len(lookups.Lookup)
    lookups.Lookup.append(buildLookup([buildSingleSubstSubtable(
        {token: dead for token, (_, _, dead) in targets.items()}
    )], table="GSUB"))
    collision_index = top[3]
    mark_filter_set = lookups.Lookup[collision_index].MarkFilteringSet
    lookups.Lookup[collision_index] = collision_lookup(font, targets, foods, die_index, mark_filter_set)
    passes = [pass_lookup(font, index) for index in top[1:]]
    for _ in range(MAX_MOVES - 1):
        for lookup in passes:
            liga.LookupListIndex.append(len(lookups.Lookup))
            lookups.Lookup.append(lookup)
    liga.LookupCount = len(liga.LookupListIndex)
    lookups.LookupCount = len(lookups.Lookup)
    output.parent.mkdir(parents=True, exist_ok=True)
    font.save(output)
    font.close()
    print(f"Saved {output}: {width}×{height} cells, {len(foods)} food targets, up to {MAX_MOVES} moves")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=parse_size,
                        default=(DEFAULT_WIDTH, DEFAULT_HEIGHT), metavar="WIDTHxHEIGHT",
                        help="board dimensions baked into the font (default: 20x11)")
    parser.add_argument("--output", type=Path, help="output .ttf path")
    args = parser.parse_args()
    width, height = args.size
    filename = ("snake-fixed-font.ttf" if args.size == (DEFAULT_WIDTH, DEFAULT_HEIGHT)
                else f"snake-fixed-{width}x{height}-font.ttf")
    output = args.output or Path(__file__).resolve().with_name(filename)
    build_font(output, width, height)


if __name__ == "__main__":
    main()
