# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compile The Last Light into an OpenType font. Requires FontTools."""

import argparse
from pathlib import Path
import string
import textwrap

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables import otTables

from story import (ALIASES, COMMANDS, INITIAL, MAX_COMMAND_LENGTH, MAX_COMMANDS,
                   MESSAGES, TITLE, inventory, reachable_states, room_view,
                   state_name, transition)

# Original 5x7 geometric lettering. Scene glyphs share these outlines through
# TrueType components; no external font or third-party game content is used.
PIXELS = {
    "A": "01110/10001/10001/11111/10001/10001/10001",
    "B": "11110/10001/10001/11110/10001/10001/11110",
    "C": "01111/10000/10000/10000/10000/10000/01111",
    "D": "11110/10001/10001/10001/10001/10001/11110",
    "E": "11111/10000/10000/11110/10000/10000/11111",
    "F": "11111/10000/10000/11110/10000/10000/10000",
    "G": "01111/10000/10000/10111/10001/10001/01111",
    "H": "10001/10001/10001/11111/10001/10001/10001",
    "I": "11111/00100/00100/00100/00100/00100/11111",
    "J": "00111/00010/00010/00010/10010/10010/01100",
    "K": "10001/10010/10100/11000/10100/10010/10001",
    "L": "10000/10000/10000/10000/10000/10000/11111",
    "M": "10001/11011/10101/10101/10001/10001/10001",
    "N": "10001/11001/10101/10011/10001/10001/10001",
    "O": "01110/10001/10001/10001/10001/10001/01110",
    "P": "11110/10001/10001/11110/10000/10000/10000",
    "Q": "01110/10001/10001/10001/10101/10010/01101",
    "R": "11110/10001/10001/11110/10100/10010/10001",
    "S": "01111/10000/10000/01110/00001/00001/11110",
    "T": "11111/00100/00100/00100/00100/00100/00100",
    "U": "10001/10001/10001/10001/10001/10001/01110",
    "V": "10001/10001/10001/10001/10001/01010/00100",
    "W": "10001/10001/10001/10101/10101/10101/01010",
    "X": "10001/10001/01010/00100/01010/10001/10001",
    "Y": "10001/10001/01010/00100/00100/00100/00100",
    "Z": "11111/00001/00010/00100/01000/10000/11111",
    "0": "01110/10001/10011/10101/11001/10001/01110",
    "1": "00100/01100/00100/00100/00100/00100/01110",
    "2": "01110/10001/00001/00010/00100/01000/11111",
    "3": "11110/00001/00001/01110/00001/00001/11110",
    "4": "00010/00110/01010/10010/11111/00010/00010",
    "5": "11111/10000/10000/11110/00001/00001/11110",
    "6": "01110/10000/10000/11110/10001/10001/01110",
    "7": "11111/00001/00010/00100/01000/01000/01000",
    "8": "01110/10001/10001/01110/10001/10001/01110",
    "9": "01110/10001/10001/01111/00001/00001/01110",
    ".": "00000/00000/00000/00000/00000/00110/00110",
    ",": "00000/00000/00000/00000/00110/00110/00100",
    ":": "00000/00110/00110/00000/00110/00110/00000",
    "!": "00100/00100/00100/00100/00100/00000/00100",
    "/": "00001/00001/00010/00100/01000/10000/10000",
    "-": "00000/00000/00000/11111/00000/00000/00000",
    "(": "00010/00100/01000/01000/01000/00100/00010",
    ")": "01000/00100/00010/00010/00010/00100/01000",
}
CELL, COLS, ROWS = 20, 48, 20
WIDTH, HEIGHT = COLS * 6 * CELL, ROWS * 10 * CELL


def empty():
    return TTGlyphPen(None).glyph()


def input_name(char):
    return f"input_{ord(char):02x}"


def token_name(command):
    return "command_" + command.replace(" ", "_")


def prefix_name(prefix):
    return "prefix_" + (prefix.encode().hex() if prefix else "root")


def build_font(output):
    states = reachable_states()
    glyphs, metrics = {}, {}

    def add(name, glyph=None, advance=0):
        glyphs[name] = glyph if glyph is not None else empty()
        metrics[name] = (advance, 0)

    add(".notdef")
    add("ghost")
    # Every printable ASCII character is in the font, so malformed commands
    # cannot trigger fallback runs that would split the state machine.
    chars = [chr(code) for code in range(32, 127)]
    for char in chars:
        add(input_name(char))
    for char, rows in PIXELS.items():
        pen = TTGlyphPen(None)
        for y, row in enumerate(rows.split("/")):
            for x, pixel in enumerate(row):
                if pixel == "1":
                    left, bottom = x * CELL, (6 - y) * CELL
                    pen.moveTo((left, bottom))
                    pen.lineTo((left + CELL, bottom))
                    pen.lineTo((left + CELL, bottom + CELL))
                    pen.lineTo((left, bottom + CELL))
                    pen.closePath()
        add(f"pixel_{ord(char):02x}", pen.glyph())

    text_cache = {}

    def text_glyph(text):
        text = text.upper()
        if len(text) > COLS:
            raise ValueError(f"Scene line is too long: {text}")
        if text not in text_cache:
            name = f"line_{len(text_cache)}"
            pen = TTGlyphPen(glyphs)
            for column, char in enumerate(text):
                if char != " ":
                    if char not in PIXELS:
                        raise ValueError(f"No scene outline for {char!r}")
                    pen.addComponent(f"pixel_{ord(char):02x}",
                                     (1, 0, 0, 1, column * 6 * CELL, 0))
            add(name, pen.glyph())
            text_cache[text] = name
        return text_cache[text]

    def panel(lines):
        pen = TTGlyphPen(glyphs)
        for row, text in lines:
            if not 0 <= row < ROWS:
                raise ValueError("Scene exceeds panel height")
            pen.addComponent(text_glyph(text), (1, 0, 0, 1, 0, HEIGHT - (row + 1) * 10 * CELL))
        return pen.glyph()

    def wrapped(text, start):
        return list(enumerate(textwrap.wrap(text.upper(), COLS), start))

    for message, text in MESSAGES.items():
        lines = []
        for paragraph in text.splitlines():
            lines.extend(textwrap.wrap(paragraph.upper(), COLS))
        if len(lines) > 4:
            raise ValueError(f"Feedback exceeds four lines: {message}")
        add(f"message_{message}", panel(list(enumerate(lines, 14))))
    # Share inventory/status panels across worlds, instead of duplicating
    # thousands of lettering components in every state glyph.
    hud_cache = {}
    scene_cache = {}
    for state in states:
        view = room_view(state)
        if view not in scene_cache:
            scene = f"scene_{len(scene_cache)}"
            title, description, exits = view
            add(scene, panel([(0, TITLE), (2, title)] + wrapped(description, 4)
                             + [(8, "EXITS: " + exits), (19, "TYPE HELP FOR COMMANDS.")]))
            scene_cache[view] = scene
        hud_key = state[1:]
        if hud_key not in hud_cache:
            hud = f"hud_{len(hud_cache)}"
            carried = ", ".join(inventory(state)) or "EMPTY"
            status = f"LAMP: {'LIT' if state[3] else 'OFF'} / POWER: {'ON' if state[4] else 'OFF'}"
            add(hud, panel(wrapped("INVENTORY: " + carried, 10) + [(12, status)]))
            hud_cache[hud_key] = hud
        pen = TTGlyphPen(glyphs)
        pen.addComponent(scene_cache[view], (1, 0, 0, 1, 0, 0))
        pen.addComponent(hud_cache[hud_key], (1, 0, 0, 1, 0, 0))
        add(state_name(state), pen.glyph(), WIDTH)

    spellings = {command: command for command in COMMANDS if command != "unknown"}
    spellings.update(ALIASES)
    prefixes = {""}
    for spelling in spellings:
        prefixes.update(spelling[:index] for index in range(1, len(spelling) + 1))
    for prefix in sorted(prefixes):
        add(prefix_name(prefix))
        add("next_" + prefix_name(prefix))
    add("prefix_bad")
    add("next_prefix_bad")
    add("boundary")
    for command in COMMANDS:
        add(token_name(command))
    add("init")
    # Intermediate action glyphs expand into feedback + the next world.
    results = sorted({(transition(state, command)[0], transition(state, command)[1])
                      for state in states for command in COMMANDS})
    result_names = {result: f"result_{index}" for index, result in enumerate(results)}
    for name in result_names.values():
        add(name)
    order = list(glyphs)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({ord(char): input_name(char) for char in chars})
    fb.setupGlyf(glyphs)
    # Composite left bearings must agree with xMin to avoid browser offsets.
    for name, glyph in glyphs.items():
        if glyph.numberOfContours:
            glyph.recalcBounds(fb.font["glyf"])
            metrics[name] = (metrics[name][0], glyph.xMin)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=HEIGHT, descent=0)
    fb.setupNameTable({"familyName": "The Last Light Adventure", "styleName": "Regular",
                       "uniqueFontIdentifier": "TheLastLightAdventure-1.0",
                       "fullName": "The Last Light Adventure", "psName": "TheLastLightAdventure-Regular",
                       "version": "Version 1.0", "copyright": "Copyright 2026 Michael Brackx",
                       "licenseDescription": "Licensed under the Apache License, Version 2.0",
                       "licenseInfoURL": "https://www.apache.org/licenses/LICENSE-2.0"})
    fb.setupOS2(sTypoAscender=HEIGHT, sTypoDescender=0, usWinAscent=HEIGHT, usWinDescent=0,
                fsType=0)
    fb.setupPost()
    fb.setupMaxp()

    root = prefix_name("")
    alphabet = [char for char in chars if not char.isupper() and char != ";"]
    fea = ["languagesystem DFLT dflt;", "languagesystem latn dflt;",
           "@INPUT = [" + " ".join(input_name(c) for c in chars) + "];",
           "@INIT_GUARD = [.notdef init " + " ".join(input_name(c) for c in chars) + "];"]
    fea.append("lookup LOWER {")
    for char in string.ascii_uppercase:
        fea.append(f"sub {input_name(char)} by {input_name(char.lower())};")
    fea.append("} LOWER;")
    start = " ".join(input_name(char) for char in "start;")
    fea += [f"lookup START {{ sub {start} by init; }} START;",
            "lookup INIT {",
            # Initialize only at the beginning, never inside an unknown word
            # or in a later command that happens to say 'start'.
            "ignore sub @INIT_GUARD " + input_name("s") + "' " + " ".join(input_name(c) for c in "tart;") + ";",
            "sub " + input_name("s") + "' lookup START " + " ".join(input_name(c) for c in "tart;") + ";",
            "} INIT;",
            f"lookup INIT_EXPAND {{ sub init by message_ready {state_name(INITIAL)} {root}; }} INIT_EXPAND;",
            f"lookup DELIMITERS {{ sub {input_name(';')} by boundary {root}; }} DELIMITERS;"]
    # A trie recognizes whole commands. Every delimiter starts a separate
    # lexer, so bounded passes scan all commands in parallel. Unknown words
    # consume the same ASCII alphabet and produce a harmless UNKNOWN token.
    fea.append("@PREFIX = [" + " ".join(prefix_name(p) for p in sorted(prefixes)) + " prefix_bad];")
    fea.append("@CHAR = [" + " ".join(input_name(c) for c in alphabet) + "];")
    fea.append("lookup LEX_VALID {")
    for prefix in sorted(prefixes):
        for char in alphabet:
            if prefix + char in prefixes:
                fea.append(f"sub {prefix_name(prefix)} {input_name(char)} by next_{prefix_name(prefix + char)};")
    fea.append("} LEX_VALID;")
    # Reject other characters with one class-based context, rather than a
    # long list of ligature candidates for every prefix. The staged outputs
    # keep the fallback from consuming a second character in the same pass.
    fea.append("lookup BAD_PREFIX { sub @PREFIX by next_prefix_bad; } BAD_PREFIX;")
    fea.append("lookup DROP_CHAR { sub @CHAR by NULL; } DROP_CHAR;")
    fea.append("lookup LEX_INVALID { sub @PREFIX' lookup BAD_PREFIX @CHAR' lookup DROP_CHAR; } LEX_INVALID;")
    fea.append("lookup LEX_COMMIT {")
    for prefix in sorted(prefixes):
        fea.append(f"sub next_{prefix_name(prefix)} by {prefix_name(prefix)};")
    fea.append("sub next_prefix_bad by prefix_bad;")
    fea.append("} LEX_COMMIT;")
    fea.append("lookup COMPLETE {")
    for prefix in sorted(prefixes):
        command = spellings.get(prefix, "unknown")
        fea.append(f"sub {prefix_name(prefix)}' boundary by {token_name(command)};")
    fea.append(f"sub prefix_bad' boundary by {token_name('unknown')};")
    fea.append("} COMPLETE;")
    fea.append(f"lookup SEPARATORS {{ sub boundary by NULL; sub {root} by NULL; }} SEPARATORS;")
    fea.append("@MESSAGE = [" + " ".join("message_" + key for key in MESSAGES) + "];")
    fea.append("lookup CLEAR { sub @MESSAGE by ghost; } CLEAR;")
    fea.append("lookup STEP {")
    for state in states:
        for command in COMMANDS:
            fea.append(f"sub {state_name(state)} {token_name(command)} by {result_names[transition(state, command)]};")
    fea.append("} STEP;")
    fea.append("lookup FEEDBACK {")
    for (state, message), name in result_names.items():
        fea.append(f"sub {name} by message_{message} {state_name(state)};")
    fea.append("} FEEDBACK;")
    # Clear feedback only when a complete command can actually be applied.
    fea.append("@WORLD = [" + " ".join(state_name(s) for s in states) + "];")
    fea.append("@COMMAND = [" + " ".join(token_name(c) for c in COMMANDS) + "];")
    fea.append("lookup CLEAR_CURRENT { sub @MESSAGE' lookup CLEAR @WORLD @COMMAND; } CLEAR_CURRENT;")
    fea.append("lookup DISPATCH { sub @WORLD' lookup STEP @COMMAND; } DISPATCH;")
    fea.append("@RESULT = [" + " ".join(result_names.values()) + "];")
    fea.append("lookup SHOW { sub @RESULT' lookup FEEDBACK; } SHOW;")
    fea.append("feature liga {")
    for lookup in ("LOWER", "INIT", "INIT_EXPAND", "DELIMITERS", "LEX_VALID", "LEX_INVALID", "LEX_COMMIT", "COMPLETE", "SEPARATORS",
                   "CLEAR_CURRENT", "DISPATCH", "SHOW"):
        fea.append(f"lookup {lookup};")
    fea.append("} liga;")
    addOpenTypeFeaturesFromString(fb.font, "\n".join(fea))
    gsub = fb.font["GSUB"].table
    feature = next(record.Feature for record in gsub.FeatureList.FeatureRecord if record.FeatureTag == "liga")
    if len(feature.LookupListIndex) != 12:
        raise RuntimeError(f"Expected twelve top-level lookups: {feature.LookupListIndex}")
    initial, lex_valid, lex_invalid, lex_commit, complete, separators, clear, step, feedback = (
        feature.LookupListIndex[:4], *feature.LookupListIndex[4:])
    lookups = gsub.LookupList
    sequence = list(initial)

    def clock_pass(index):
        # New top-level lookup indices are required: shaping engines deduplicate
        # repeated indices. The helper's subtable remains shared in the font.
        source = lookups.Lookup[index]
        wrapper = otTables.Lookup()
        wrapper.LookupType = source.LookupType
        wrapper.LookupFlag = source.LookupFlag
        wrapper.SubTable = source.SubTable
        wrapper.SubTableCount = len(wrapper.SubTable)
        lookups.Lookup.append(wrapper)
        return len(lookups.Lookup) - 1

    for _ in range(MAX_COMMAND_LENGTH):
        sequence.extend(clock_pass(index) for index in (lex_valid, lex_invalid, lex_commit))
    sequence.append(clock_pass(complete))
    sequence.append(clock_pass(separators))
    for _ in range(MAX_COMMANDS):
        sequence.extend(clock_pass(index) for index in (clear, step, feedback))
    feature.LookupListIndex, feature.LookupCount = sequence, len(sequence)
    lookups.LookupCount = len(lookups.Lookup)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fb.font.save(output)
    fb.font.close()
    print(f"Saved {output}: {len(states)} worlds, {MAX_COMMANDS} commands, {len(order)} glyphs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().with_name("text-adventure-font.ttf"))
    args = parser.parse_args()
    build_font(args.output)


if __name__ == "__main__":
    main()
