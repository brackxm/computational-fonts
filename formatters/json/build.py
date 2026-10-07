#!/usr/bin/env python3
# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build an inline JSON highlighting and spacing font. Requires FontTools."""

import argparse
from pathlib import Path
import re
import sys

from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "decoders"))
from shared.font_metadata import DEFAULT_BASE, load_base_font, mark_modified_font, replace_font_names

# These colors are embedded in the font, not applied by the playground.
PALETTE = ("#9C3F12", "#25663F", "#185DB2", "#723CA6", "#54656B")
NUMBER_CHARS = "0123456789.eE+-"
BOUNDARIES = " {}[]:,"


def build_font(output_path, family_name=None):
    font = load_base_font(DEFAULT_BASE, output_path)
    try:
        cmap = font.getBestCmap()
        required = [chr(code) for code in range(32, 127)]
        if any(ord(char) not in cmap for char in required):
            raise ValueError("Base must cover printable ASCII")
        if len({cmap[ord(char)] for char in required}) != len(required):
            raise ValueError("ASCII input glyphs must be distinct")
        order = list(font.getGlyphOrder())
        if any(name.startswith("json.") for name in order):
            raise ValueError("Base contains reserved json. glyph names")
        # Include every encoded source glyph (plus .notdef), so Unicode glyphs
        # carry lexical state within an explicitly controlled shaping run.
        # Clients may split Unicode scripts into independent runs; the browser
        # playground therefore restricts formatted input to printable ASCII.
        raw = sorted(set(cmap.values()) | {".notdef"}, key=font.getGlyphID)
        layers = {}

        def glyph(name, originals=(), color=None, extra=0):
            if name in font["glyf"]:
                raise ValueError(f"Generated glyph name collision: {name}")
            pen = TTGlyphPen(font["glyf"])
            offset = 0
            for original in originals:
                pen.addComponent(original, (1, 0, 0, 1, offset, 0))
                offset += font["hmtx"][original][0]
            painted = pen.glyph()
            painted.recalcBounds(font["glyf"])
            font["glyf"][name] = painted
            font["hmtx"][name] = (offset + extra, getattr(painted, "xMin", 0))
            order.append(name)
            if color is not None and originals:
                # A separate outline glyph prevents recursive COLR layers.
                layer = name + ".ink"
                font["glyf"][layer] = painted
                font["hmtx"][layer] = font["hmtx"][name]
                order.append(layer)
                layers[name] = [(layer, color)]
            return name

        outside, strings, keys = {}, {}, {}
        space_advance = font["hmtx"][cmap[32]][0]
        for original in raw:
            outside[original] = glyph("json.outside." + original, (original,))
            strings[original] = glyph("json.string." + original, (original,), color=1)
            keys[original] = glyph("json.key." + original, (original,), color=0)
        opening = glyph("json.open", (cmap[34],), color=1)
        closing = glyph("json.close", (cmap[34],), color=1)
        escape = glyph("json.escape", (cmap[92],), color=1)
        key_open = glyph("json.key.open", (cmap[34],), color=0)
        key_close = glyph("json.key.close", (cmap[34],), color=0)
        key_escape = glyph("json.key.escape", (cmap[92],), color=0)
        gap = glyph("json.gap")
        punct = {char: glyph("json.punct." + f"{ord(char):04X}", (cmap[ord(char)],),
                             color=4, extra=space_advance if char in ":," else 0)
                 for char in "{}[]:,"}
        numbers = {char: glyph("json.number." + f"{ord(char):04X}", (cmap[ord(char)],), color=2)
                   for char in NUMBER_CHARS}
        literals = {word: glyph("json.literal." + word, tuple(cmap[ord(char)] for char in word), color=3)
                    for word in ("true", "false", "null")}

        fea = ["languagesystem DFLT dflt;", "languagesystem latn dflt;"]
        steps = []

        def cls(name, glyphs):
            fea.append("@" + name + " = [" + " ".join(glyphs) + "];")
            return "@" + name

        def lookup(name, rules, ignore_gaps=False):
            fea.extend([f"lookup {name} {{", *( ["lookupflag IgnoreMarks;"] if ignore_gaps else []),
                        *rules, f"}} {name};"])
            steps.append(name)

        raw_class = cls("RAW", raw)
        outside_class = cls("OUTSIDE", [outside[name] for name in raw])
        string_class = cls("STRING", [strings[name] for name in raw])
        key_class = cls("KEY", [keys[name] for name in raw])
        inside = cls("INSIDE", [opening, *strings.values()])
        lookup("LEX", [
            f"sub {escape} {raw_class}' by {string_class};",
            f"sub {inside} {cmap[34]}' by {closing};",
            f"sub {inside} {cmap[92]}' by {escape};",
            f"sub {inside} {raw_class}' by {string_class};",
            f"sub {cmap[34]}' by {opening};",
            f"sub {raw_class}' by {outside_class};",
        ])

        ws = outside[cmap[32]]
        lookup("COLLAPSE_SPACES", [f"sub [{ws} {gap}] {ws}' by {gap};"])
        lookup("KEY_CLOSE", [
            f"sub {closing}' {outside[cmap[58]]} by {key_close};",
            f"sub {closing}' {ws} {outside[cmap[58]]} by {key_close};",
        ], ignore_gaps=True)
        lookup("KEY_BODY", [
            f"rsub {string_class}' [{key_class} {key_close} {key_escape}] by {key_class};",
            f"rsub {escape}' [{key_class} {key_close} {key_escape}] by {key_escape};",
            f"rsub {opening}' [{key_class} {key_close} {key_escape}] by {key_open};",
        ])

        # Number states implement JSON's sign, leading-zero, fraction and
        # exponent rules. Only an accepting state at a boundary is colored.
        states = {
            "minus": "-", "zero": "0", "int": "0123456789", "dot": ".",
            "frac": "0123456789", "exp": "eE", "sign": "+-", "expdigits": "0123456789",
        }
        candidates = {}
        state_classes = {}
        for state, chars in states.items():
            for char in chars:
                candidates[state, char] = glyph(f"json.cand.{state}.{ord(char):04X}", (cmap[ord(char)],))
            state_classes[state] = cls("NUM_" + state.upper(), [candidates[state, char] for char in chars])
        all_candidates = cls("CANDIDATES", list(candidates.values()))
        candidate_outputs = cls("CANDIDATE_OUTPUTS", [numbers[char] for _, char in candidates])
        candidate_originals = cls("CANDIDATE_ORIGINALS", [outside[cmap[ord(char)]] for _, char in candidates])
        number_class = cls("NUMBERS", list(numbers.values()))
        boundary_names = {outside[cmap[ord(char)]] for char in BOUNDARIES}
        nonboundary = cls("NONBOUNDARY", [name for name in order if name not in boundary_names and name != gap])
        transitions = (
            ("minus", "0", "zero"), ("minus", "123456789", "int"),
            ("int", "0123456789", "int"), ("zero", ".", "dot"), ("int", ".", "dot"),
            ("dot", "0123456789", "frac"), ("frac", "0123456789", "frac"),
            ("zero", "eE", "exp"), ("int", "eE", "exp"), ("frac", "eE", "exp"),
            ("exp", "+-", "sign"), ("exp", "0123456789", "expdigits"),
            ("sign", "0123456789", "expdigits"), ("expdigits", "0123456789", "expdigits"),
        )
        forward = [f"sub {state_classes[previous]} {outside[cmap[ord(char)]]}' by {candidates[next_state, char]};"
                   for previous, chars, next_state in transitions for char in chars]
        starters = cls("NUMBER_STARTERS", [outside[cmap[ord(char)]] for char in "-0123456789"])
        forward.append(f"ignore sub {nonboundary} {starters}';")
        forward.extend(f"sub {outside[cmap[ord(char)]]}' by {candidates[state, char]};"
                       for state, chars in (("minus", "-"), ("zero", "0"), ("int", "123456789"))
                       for char in chars)
        lookup("NUMBER_FORWARD", forward, ignore_gaps=True)
        accepted = [name for (state, _), name in candidates.items() if state in ("zero", "int", "frac", "expdigits")]
        accepted_class = cls("ACCEPTING", accepted)
        accepted_outputs = cls("ACCEPTING_OUTPUTS", [numbers[char] for (state, char) in candidates
                                                     if state in ("zero", "int", "frac", "expdigits")])
        lookup("NUMBER_END", [f"ignore sub {accepted_class}' {nonboundary};",
                              f"sub {accepted_class}' by {accepted_outputs};"], ignore_gaps=True)
        lookup("NUMBER_BODY", [f"rsub {all_candidates}' {number_class} by {candidate_outputs};"])
        lookup("NUMBER_RELEASE", [f"sub {all_candidates} by {candidate_originals};"])

        # Whole-word keyword matches must have boundaries on both sides.
        for word, output in literals.items():
            sequence = [outside[cmap[ord(char)]] for char in word]
            action = "LITERAL_" + word.upper() + "_ACTION"
            fea.append(f"lookup {action} {{ sub {' '.join(sequence)} by {output}; }} {action};")
            marked = sequence[0] + "' " + " ".join(sequence[1:])
            lookup("LITERAL_" + word.upper(), [f"ignore sub {nonboundary} {marked};",
                   f"ignore sub {marked} {nonboundary};",
                   f"sub {sequence[0]}' lookup {action} {' '.join(sequence[1:])};"], ignore_gaps=True)

        # Remove spaces next to structural punctuation. Colon/comma advances
        # already include exactly one display space; string glyphs are untouched.
        compact_left = cls("COMPACT_LEFT", [outside[cmap[ord(char)]] for char in "{[:,"])
        compact_right = cls("COMPACT_RIGHT", [outside[cmap[ord(char)]] for char in "{}[]:,"])
        lookup("PUNCT_SPACES", [f"sub {compact_left} {ws}' by {gap};",
                                f"sub {ws}' {compact_right} by {gap};"], ignore_gaps=True)
        lookup("PUNCTUATION", [f"sub {outside[cmap[ord(char)]]} by {name};" for char, name in punct.items()])

        font.setGlyphOrder(order)
        for tag in ("GSUB", "GPOS", "GDEF", "DSIG"):
            if tag in font:
                del font[tag]
        addOpenTypeFeaturesFromString(font, "\n".join(fea + [
            "table GDEF { GlyphClassDef , , [json.gap], ; } GDEF;",
            "feature rlig {", *(f"lookup {name};" for name in steps), "} rlig;",
        ]))
        font["COLR"] = buildCOLR(layers, version=0, glyphMap=font.getReverseGlyphMap())
        font["CPAL"] = buildCPAL([[
            (*[int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)], 1)
            for color in PALETTE]])
        family = family_name or "JSON Formatter"
        ps_name = re.sub(r"[^A-Za-z0-9-]+", "-", family).strip("-") or "JSONFormatter"
        replace_font_names(font, {1: family, 2: "Regular", 3: "JSONFormatter",
                                 4: family + " Regular", 6: (ps_name + "-Regular")[:50],
                                 16: family, 17: "Regular"})
        mark_modified_font(font, "json", kind="formatter")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        font.save(output_path)
        print(f"Saved {output_path}: {len(order)} glyphs")
    finally:
        font.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().with_name("json-font.ttf"))
    parser.add_argument("--name", help="Optional font family name")
    args = parser.parse_args()
    try:
        build_font(args.output, args.name)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
