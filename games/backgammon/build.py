# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""Build a bounded SGF backgammon replay font. Requires FontTools."""

import argparse
import math
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildCoverage, buildLookup
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables import otTables

MAX_TURNS = 128
# One pass consumes a grammar token, die digit, or checker coordinate.
# A maximal turn costs 13 passes; framing and the three root properties cost 8.
CLOCK_PASSES = MAX_TURNS * 13 + 10
WIDTH, HEIGHT, UPM = 1800, 1100, 1000
START, END = "\ue000", "\ue001"
POINTS = "abcdefghijklmnopqrstuvwx"
INITIAL = {"f": ("W", 5), "h": ("W", 3), "m": ("W", 5), "x": ("W", 2),
           "a": ("B", 2), "l": ("B", 5), "q": ("B", 3), "s": ("B", 5)}
REGISTERS = [*POINTS, "barW", "barB", "offW", "offB", "die1", "die2", "turn"]
PALETTE = ("243e43", "f1dfba", "c68658", "34686a", "fff9ea", "273c47", "317557", "b84331")
STATUS = {"complete": 1, "malformed": 2, "unsupported": 3, "limit": 4, "state_error": 5}

# Original 3 by 5 lettering, used only for board labels and diagnostics.
PIXELS = dict(zip("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-",
    ("111101101101111", "010110010010111", "111001111100111", "111001111001111",
     "101101111001001", "111100111001111", "111100111101111", "111001010010010",
     "111101111101111", "111101111001111", "010101111101101", "110101110101110",
     "111100100100111", "110101101101110", "111100110100111", "111100110100100",
     "111100101101111", "101101111101101", "111010010010111", "001001001101111",
     "101101110101101", "100100100100111", "101111111101101", "101111111111101",
     "111101101101111", "111101111100100", "111101101111001", "110101110101101",
     "111100111001111", "111010010010010", "101101101101111", "101101101101010",
     "101101111111101", "101101010101101", "101101010010010", "111001010100111",
     "000000111000000")))
PIXELS.update(W="1000110001101011010101010", M="1000111011101011000110001",
              N="1000111001101011001110001")


def rect(pen, x, y, w, h):
    pen.moveTo((x, y))
    for point in ((x+w, y), (x+w, y+h), (x, y+h)):
        pen.lineTo(point)
    pen.closePath()


def lettering(pen, text, x, y, scale=5):
    for char in text:
        pattern = PIXELS.get(char, "0" * 15)
        columns = len(pattern)//5
        for i, pixel in enumerate(pattern):
            if pixel == "1":
                rect(pen, x + (i % columns) * scale, y + (4 - i // columns) * scale, scale, scale)
        x += (columns+1) * scale


def circle(pen, x, y, radius, reverse=False):
    vertices = [(round(x + radius * math.cos(i * math.pi / 12)),
                 round(y + radius * math.sin(i * math.pi / 12))) for i in range(24)]
    if reverse:
        vertices.reverse()
    pen.moveTo(vertices[0])
    for point in vertices[1:]:
        pen.lineTo(point)
    pen.closePath()


def point_x(i):
    col = 11 - i if i < 12 else i - 12
    return 95 + col * 120 + (90 if col >= 6 else 0)


def wrapper(font, coverage, index):
    """A tiny clock lookup calls the shared transition/effect table."""
    table = otTables.ContextSubst()
    table.Format = 3
    table.Coverage = [buildCoverage(coverage, font.getReverseGlyphMap())]
    table.GlyphCount = 1
    record = otTables.SubstLookupRecord()
    record.SequenceIndex, record.LookupListIndex = 0, index
    table.SubstLookupRecord, table.SubstCount = [record], 1
    return buildLookup([table], table="GSUB", extension=True)


def build_font(output):
    glyphs, metrics, order, layers = {}, {}, [], {}

    def add(name, draw=None, advance=0, color=None, overlay=True):
        if name in glyphs:
            return name
        pen = TTGlyphPen(None)
        if draw:
            draw(pen, -WIDTH if overlay else 0)
        glyph = pen.glyph()
        glyph.recalcBounds(None)
        glyphs[name] = glyph
        metrics[name] = (advance, getattr(glyph, "xMin", 0))
        order.append(name)
        if color is not None:
            layers[name] = [(name, color)]
        return name

    add(".notdef", lambda p, x: lettering(p, "BAD CHARACTER", x+60, 60), color=7)
    add("hidden")
    raw = {chr(i): add(f"c{i:02x}") for i in range(32, 128)}
    add("begin")
    add("end")

    def board(p, x):
        for args in ((20, 260, 1740, 8), (20, 1010, 1740, 8), (20, 260, 8, 750),
                     (1752, 260, 8, 750), (795, 260, 8, 750), (1640, 260, 8, 750)):
            rect(p, *args)
        for i in range(24):
            cx = point_x(i)
            lettering(p, str(i+1), cx-18, 230 if i < 12 else 1060, 5)
            lettering(p, POINTS[i].upper(), cx-8, 200 if i < 12 else 1028, 4)
        for label, cx in (("W BAR", 80), ("B BAR", 350), ("W OFF", 620), ("B OFF", 890), ("DICE", 1260)):
            lettering(p, label, cx, 150, 6)
        lettering(p, "SGF BACKGAMMON", 60, 45, 5)

    add("board_frame", board, overlay=False)
    add("wood", lambda p, x: rect(p, x+28, 268, 1724, 742), overlay=False)
    for parity in (0, 1):
        def triangles(p, x, parity=parity):
            for i in range(parity, 24, 2):
                cx, base, tip = x+point_x(i), (276 if i < 12 else 1002), (605 if i < 12 else 675)
                p.moveTo((cx-51, base))
                p.lineTo((cx+51, base))
                p.lineTo((cx, tip))
                p.closePath()
        add(f"triangles{parity}", triangles, overlay=False)
    def guides(p, x):
        # Outline triangles in monochrome so solid backgrounds do not hide
        # either player's checker glyphs. Color layers use the filled versions.
        for i in range(24):
            cx, base, tip = point_x(i), (276 if i < 12 else 1002), (605 if i < 12 else 675)
            points = [(cx-51, base), (cx+51, base), (cx, tip)]
            cy = (2*base+tip)/3
            p.moveTo(points[0])
            for point in points[1:]:
                p.lineTo(point)
            p.closePath()
            inside = [(round(cx+(xx-cx)*.94), round(cy+(yy-cy)*.94)) for xx, yy in points]
            p.moveTo(inside[-1])
            for point in reversed(inside[:-1]):
                p.lineTo(point)
            p.closePath()
    add("triangle_guides", guides, overlay=False)
    pen = TTGlyphPen(glyphs)
    for component in ("board_frame", "triangle_guides"):
        pen.addComponent(component, (1, 0, 0, 1, 0, 0))
    add("board", advance=WIDTH)
    glyphs["board"] = pen.glyph()
    layers["board"] = [("wood", 1), ("triangles0", 2), ("triangles1", 3), ("board_frame", 0)]

    register_glyphs = {}
    for point in POINTS:
        i = POINTS.index(point)
        names = [add(f"r_{point}_0")]
        for player in "WB":
            for count in range(1, 16):
                def checkers(p, x, i=i, player=player, count=count):
                    for n in range(min(count, 5)):
                        cy = 315+n*62 if i < 12 else 965-n*62
                        circle(p, x+point_x(i), cy, 30)
                        if player == "W":
                            circle(p, x+point_x(i), cy, 24, reverse=True)
                    lettering(p, str(count), x+point_x(i)-17, 608 if i < 12 else 645, 5)
                name = add(f"r_{point}_{player}{count}", checkers, color=0 if player == "W" else 5)
                # White checkers have an ivory fill in color, a ring in monochrome.
                if player == "W":
                    def fill(p, x, i=i, count=count):
                        for n in range(min(count, 5)):
                            circle(p, x+point_x(i), 315+n*62 if i < 12 else 965-n*62, 24)
                    inside = add(name+"_fill", fill)
                    layers[name] = [(inside, 4), (name, 0)]
                names.append(name)
        register_glyphs[point] = names
    for slot, cx in zip(("barW", "barB", "offW", "offB"), (110, 380, 650, 920)):
        register_glyphs[slot] = [add(f"r_{slot}_{n}",
            lambda p, x, n=n, cx=cx: lettering(p, str(n), x+cx, 90, 9), color=0) for n in range(16)]
    for slot, cx in (("die1", 1400), ("die2", 1510)):
        names = [add(f"r_{slot}_0")]
        for player in "WB":
            for n in range(1, 7):
                def die(p, x, n=n, player=player, cx=cx):
                    # Outline and original geometric pips.
                    for args in ((cx, 85, 80, 3), (cx, 162, 80, 3), (cx, 85, 3, 80), (cx+77, 85, 3, 80)):
                        xx, yy, w, h = args
                        rect(p, x+xx, yy, w, h)
                    dots = [(40, 40)] if n % 2 else []
                    if n >= 2:
                        dots += [(18, 18), (62, 62)]
                    if n >= 4:
                        dots += [(18, 62), (62, 18)]
                    if n == 6:
                        dots += [(18, 40), (62, 40)]
                    for dx, dy in dots:
                        circle(p, x+cx+dx, 85+dy, 7)
                    lettering(p, player, x+cx+32, 175, 4)
                names.append(add(f"r_{slot}_{player}{n}", die, color=0))
        register_glyphs[slot] = names
    register_glyphs["turn"] = [add(f"r_turn_{n}",
        lambda p, x, n=n: lettering(p, f"TURN {n}", x+420, 45, 5), color=0) for n in range(MAX_TURNS+1)]
    for status, code in STATUS.items():
        label = {"complete": "REPLAYED", "state_error": "STATE ERROR"}.get(status, status.upper())
        add("status_"+status, lambda p, x, label=label: lettering(p, label, x+740, 45, 6),
            advance=code, color=6 if code == 1 else 7)

    classes, rules, transitions, next_events = [], {}, {}, {}
    def cls(name, members):
        classes.append(f"@{name} = [{' '.join(members)}];")
        return "@"+name

    regs = cls("REG", [name for members in register_glyphs.values() for name in members])
    for slot, names in register_glyphs.items():
        cls("R_"+slot, names)

    def rule(table, text):
        rules.setdefault(table, []).append(text)

    def context(slot, event, target, replacement):
        tail = " ".join([regs] * (len(REGISTERS)-1-REGISTERS.index(slot)))
        return f"sub {target}' {tail} {event} by {replacement};"

    def guard(slot, event, bad):
        tail = " ".join([regs] * (len(REGISTERS)-1-REGISTERS.index(slot)))
        rule("CHECK", f"sub {bad} {tail} {event}' by status_state_error;")

    def transition(state, text, target):
        add(state)
        add(target)
        transitions[(state, text)] = target

    def event(name, after):
        add(name)
        add(after)
        next_events[name] = after
        return name

    transition("p_start", "(", "p_tree")
    transition("p_tree", ";", "p_header0")
    for mask in range(8):
        state = f"p_header{mask}"
        add(state)
        for bit, text in enumerate(("GM[6]", "FF[4]", "CA[UTF-8]")):
            if not mask & (1 << bit):
                transition(state, text, f"p_header{mask | (1 << bit)}")
        transition(state, ";", "p_node")
        transition(state, ")", "p_closed")
    for state in ("p_after",):
        transition(state, ";", "p_node")
        transition(state, ")", "p_closed")
    transition("p_closed", END, "status_complete")

    for player in "WB":
        begin = event(f"begin_{player}", f"p_{player}_die1")
        for state in ("p_node", *(f"p_header{mask}" for mask in range(8))):
            transition(state, player+"[", begin)
        guard("turn", begin, f"r_turn_{MAX_TURNS}")
        # Exhausted turns are a capacity error, rather than an inconsistent board.
        rules["CHECK"][-1] = rules["CHECK"][-1].replace("status_state_error", "status_limit")
        rule("COUNT", context("turn", begin,
            "["+" ".join(register_glyphs["turn"][:-1])+"]",
            "["+" ".join(register_glyphs["turn"][1:])+"]"))
        for die_index in (1, 2):
            for digit in "123456":
                name = event(f"die_{player}_{die_index}_{digit}",
                    f"p_{player}_die2" if die_index == 1 else f"p_{player}_source0")
                transition(f"p_{player}_die{die_index}", digit, name)
                rule("DICE", context(f"die{die_index}", name, f"@R_die{die_index}", f"r_die{die_index}_{player}{digit}"))
        for pair in range(5):
            source = f"p_{player}_source{pair}"
            transition(source, "]", "p_after")
            if pair == 4:
                continue
            for coord in POINTS+"y":
                slot = "bar"+player if coord == "y" else coord
                name = event(f"source_{player}_{coord}_{pair}", f"p_{player}_dest{pair}")
                transition(source, coord, name)
            for coord in POINTS+"z":
                name = event(f"dest_{player}_{coord}_{pair}", f"p_{player}_source{pair+1}")
                transition(f"p_{player}_dest{pair}", coord, name)
                if coord != "z":
                    event(f"hit_{player}_{coord}_{pair}", f"p_{player}_source{pair+1}")

        opponent = "B" if player == "W" else "W"
        hit_all = cls("HIT_"+player, [f"hit_{player}_{c}_{k}" for c in POINTS for k in range(4)])
        # Hits are recognized while the opponent's blot is still present.
        for coord in POINTS:
            dest = cls(f"DEST_{player}_{coord}", [f"dest_{player}_{coord}_{k}" for k in range(4)])
            hits = cls(f"HITS_{player}_{coord}", [f"hit_{player}_{coord}_{k}" for k in range(4)])
            tail = " ".join([regs] * (len(REGISTERS)-1-REGISTERS.index(coord)))
            rule("HIT", f"sub r_{coord}_{opponent}1 {tail} {dest}' by {hits};")
        rule("BAR", context("bar"+opponent, hit_all,
            "["+" ".join(register_glyphs["bar"+opponent][:-1])+"]",
            "["+" ".join(register_glyphs["bar"+opponent][1:])+"]"))
        guard("bar"+opponent, hit_all, f"r_bar{opponent}_15")

        for coord in POINTS+"y":
            slot = "bar"+player if coord == "y" else coord
            active = cls(f"SOURCE_{player}_{coord}", [f"source_{player}_{coord}_{k}" for k in range(4)])
            good = ([f"r_{slot}_{n}" for n in range(1, 16)] if coord == "y" else
                    [f"r_{slot}_{player}{n}" for n in range(1, 16)])
            result = [f"r_{slot}_0", *good[:-1]]
            bad = "["+" ".join(n for n in register_glyphs[slot] if n not in good)+"]"
            guard(slot, active, bad)
            rule("SOURCE", context(slot, active, "["+" ".join(good)+"]", "["+" ".join(result)+"]"))
        for coord in POINTS+"z":
            slot = "off"+player if coord == "z" else coord
            active = cls(f"LAND_{player}_{coord}", [f"dest_{player}_{coord}_{k}" for k in range(4)]+
                ([] if coord == "z" else [f"hit_{player}_{coord}_{k}" for k in range(4)]))
            good = ([f"r_{slot}_{n}" for n in range(15)] if coord == "z" else
                    [f"r_{slot}_0", *[f"r_{slot}_{player}{n}" for n in range(1, 15)]])
            result = ([f"r_{slot}_{n}" for n in range(1, 16)] if coord == "z" else
                      [f"r_{slot}_{player}{n}" for n in range(1, 16)])
            # An opponent blot becomes one checker of the moving player.
            if coord != "z":
                good.append(f"r_{slot}_{opponent}1")
                result.append(f"r_{slot}_{player}1")
            guard(slot, active, "["+" ".join(n for n in register_glyphs[slot] if n not in good)+"]")
            rule("DEST", context(slot, active, "["+" ".join(good)+"]", "["+" ".join(result)+"]"))

    parsers = [n for n in order if n.startswith("p_")]
    # Default transitions are part of the same ligature lookup. Long supported
    # property tokens win over their two-glyph unsupported-property fallback.
    for state in [*parsers, "status_complete"]:
        for char, glyph in [*raw.items(), (END, "end"), (START, "begin")]:
            if (state, char) not in transitions:
                unsupported = char == "(" or char.isupper() or char == "\x7f"
                if "_die1" in state and char.islower():
                    unsupported = True  # double, take, drop
                transitions[(state, char)] = "status_unsupported" if unsupported else "status_malformed"

    step = []
    for (state, text), target in sorted(transitions.items(), key=lambda item: -len(item[0][1])):
        tokens = ["end" if c == END else "begin" if c == START else raw[c] for c in text]
        step.append(f"sub {state} {' '.join(tokens)} by {target};")
    rules = {"STEP": step, **rules,
             "NEXT": [f"sub {a} by {b};" for a, b in next_events.items()]}
    # Root whitespace is insignificant; hosts flatten line breaks to keep one run.
    feature = ["languagesystem DFLT dflt;", "languagesystem latn dflt;", *classes,
        f"lookup SPACE {{ sub {raw[' ']} by NULL; }} SPACE;",
        "lookup INIT useExtension { sub begin by board "+" ".join(
            f"r_{slot}_{INITIAL[slot][0]}{INITIAL[slot][1]}" if slot in INITIAL else f"r_{slot}_0"
            for slot in REGISTERS)+" p_start; } INIT;"]
    # All effect tables run before NEXT restores a parser state.
    stages = ["STEP", "HIT", "CHECK", "SOURCE", "DEST", "BAR", "DICE", "COUNT", "NEXT"]
    for name in stages:
        feature += [f"lookup {name} useExtension {{", *rules[name], f"}} {name};"]
    feature += ["lookup FINAL {", f"sub [{' '.join(parsers)}] by status_malformed;", "} FINAL;",
                "lookup HIDE {", "sub ["+" ".join([*raw.values(), "end", ".notdef"])+"] by hidden;", "} HIDE;",
                "feature liga { lookup SPACE; lookup INIT; "+" ".join(f"lookup {n};" for n in stages)+
                " lookup FINAL; lookup HIDE; } liga;"]

    builder = FontBuilder(UPM, isTTF=True)
    builder.setupGlyphOrder(order)
    cmap = {ord(c): name for c, name in raw.items()}
    # A uniform private-use transport avoids browser script/font-run boundaries
    # between SGF punctuation, digits, Latin letters, and the framing sentinels.
    # These are aliases of raw characters, not pre-parsed SGF instructions.
    cmap.update({0xE100+ord(c): name for c, name in raw.items()})
    cmap.update({ord(START): "begin", ord(END): "end"})
    cmap.update({i: raw[' '] for i in (9, 10, 13)})
    builder.setupCharacterMap(cmap)
    # Recalculate composite metrics after assembling the artwork.
    for name, glyph in glyphs.items():
        glyph.recalcBounds(glyphs)
        metrics[name] = (metrics[name][0], getattr(glyph, "xMin", 0))
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=HEIGHT, descent=-30)
    builder.setupNameTable({"familyName": "Backgammon SGF Replay", "styleName": "Regular",
        "fullName": "Backgammon SGF Replay Regular", "psName": "BackgammonSGFReplay-Regular",
        "uniqueFontIdentifier": "BackgammonSGFReplay-1.1", "version": "Version 1.1",
        16: "Backgammon SGF Replay", 17: "Regular", "copyright": "Copyright 2026 Michael Brackx",
        "licenseDescription": "Licensed under the Apache License, Version 2.0",
        "licenseInfoURL": "https://www.apache.org/licenses/LICENSE-2.0"})
    builder.setupOS2(sTypoAscender=HEIGHT, sTypoDescender=-30, usWinAscent=HEIGHT, usWinDescent=30, fsType=0)
    builder.setupPost()
    builder.setupMaxp()
    builder.setupCOLR(layers, version=0)
    builder.setupCPAL([[tuple(int(c[i:i+2], 16)/255 for i in (0, 2, 4))+(1.0,) for c in PALETTE]])
    font = builder.font
    addOpenTypeFeaturesFromString(font, "\n".join(feature))
    liga = next(r.Feature for r in font["GSUB"].table.FeatureList.FeatureRecord if r.FeatureTag == "liga")
    lookups = font["GSUB"].table.LookupList
    space, init, *rest = liga.LookupListIndex
    effects, final, hide = rest[:-2], rest[-2], rest[-1]
    if len(effects) != len(stages):
        raise RuntimeError("Unexpected shared lookup indices")
    # A distinct wrapper index is necessary: shapers deduplicate repeated indices.
    # Shared lookups themselves are only reachable through these tiny wrappers.
    liga.LookupListIndex = [space, init]
    coverages = {"STEP": [*parsers, "status_complete"],
                 "HIT": [n for n in next_events if n.startswith("dest_")],
                 "CHECK": list(next_events),
                 "SOURCE": [n for members in register_glyphs.values() for n in members],
                 "DEST": [n for members in register_glyphs.values() for n in members],
                 "BAR": register_glyphs["barW"]+register_glyphs["barB"],
                 "DICE": register_glyphs["die1"]+register_glyphs["die2"],
                 "COUNT": register_glyphs["turn"], "NEXT": list(next_events)}
    for _ in range(CLOCK_PASSES):
        for name, index in zip(stages, effects):
            liga.LookupListIndex.append(len(lookups.Lookup))
            lookups.Lookup.append(wrapper(font, coverages[name], index))
    for coverage, index in ((parsers, final), ([*raw.values(), "end", ".notdef"], hide)):
        liga.LookupListIndex.append(len(lookups.Lookup))
        lookups.Lookup.append(wrapper(font, coverage, index))
    liga.LookupCount = len(liga.LookupListIndex)
    lookups.LookupCount = len(lookups.Lookup)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    font.save(output)
    font.close()
    print(f"Saved {output}: {MAX_TURNS} turns, {CLOCK_PASSES} shared shaping passes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().with_name("backgammon-font.ttf"))
    build_font(parser.parse_args().output)


if __name__ == "__main__":
    main()
