#!/usr/bin/env python3
# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build an International Morse code decoding font. Requires FontTools.

Dots and hyphens form signals, spaces separate letters, and / separates words.
The font changes their appearance through GSUB; copying retains the Morse text.
"""

import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.font_metadata import (DEFAULT_BASE, load_base_font, mark_modified_font,
                                  replace_font_names, validate_marker_glyph)

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.ttGlyphPen import TTGlyphPen


# Written characters from ITU-R M.1677-1, Annex 1, sections 1.1.1–1.1.3.
# ASCII apostrophe, quotation mark and hyphen represent their printed variants.
# X takes precedence over the multiplication sign, which has the same signal.
MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".",
    "F": "..-.", "G": "--.", "H": "....", "I": "..", "J": ".---",
    "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---",
    "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-",
    "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--",
    "Z": "--..", "É": "..-..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    ".": ".-.-.-", ",": "--..--", ":": "---...", "?": "..--..",
    "'": ".----.", "-": "-....-", "/": "-..-.", "(": "-.--.",
    ")": "-.--.-", '"': ".-..-.", "=": "-...-", "+": ".-.-.", "@": ".--.-.",
}
DECODE = {code: char for char, code in MORSE.items()}


def decode_text(text):
    """Build/test reference; never used by the browser or document."""
    if any(char not in ".-/ " for char in text):
        raise ValueError("Use ASCII dots, hyphens, spaces and / only")
    return " ".join("".join(DECODE.get(group, group) for group in word.split(" "))
                    for word in text.split("/"))


def output_name(char):
    return f"morse.out.{ord(char):04X}"


def build_font(base_path, output_path, family_name=None):
    font = load_base_font(base_path, output_path)
    try:
        cmap = font.getBestCmap()
        required = set(MORSE) | set(".-/ ")
        missing = sorted(char for char in required if ord(char) not in cmap)
        if missing:
            raise ValueError(f"Base font is missing required characters: {''.join(missing)!r}")
        for marker in ".-/ ":
            validate_marker_glyph(cmap, marker,
                                  "".join(chr(code) for code in range(32, 127)
                                          if code != ord(marker)), "Morse input")
        names = [output_name(char) for char in MORSE] + ["morse.gap", "morse.word"]
        collisions = set(names) & set(font.getGlyphOrder())
        if collisions:
            raise ValueError(f"Generated glyph name collision: {sorted(collisions)[0]}")
        if len(font.getGlyphOrder()) + len(names) >= 65535:
            raise ValueError("Base font has no room for Morse output glyphs")

        # Distinct output glyphs keep decoded dots, hyphens and slashes from
        # becoming input signals or word separators in later lookups.
        order = list(font.getGlyphOrder())
        for char in [*MORSE, " "]:
            name = "morse.word" if char == " " else output_name(char)
            original = cmap[ord(char)]
            pen = TTGlyphPen(font.getGlyphSet())
            pen.addComponent(original, (1, 0, 0, 1, 0, 0))
            glyph = pen.glyph()
            font["glyf"][name] = glyph
            glyph.recalcBounds(font["glyf"])
            font["hmtx"].metrics[name] = (font["hmtx"].metrics[original][0],
                                          getattr(glyph, "xMin", 0))
            order.append(name)
        font["glyf"]["morse.gap"] = TTGlyphPen(None).glyph()
        font["hmtx"].metrics["morse.gap"] = (0, 0)
        order.append("morse.gap")
        font.setGlyphOrder(order)
        if "GSUB" in font:
            del font["GSUB"]

        dot, dash, space, slash = [cmap[ord(char)] for char in ".- /"]
        # Every encoded non-separator blocks a partial match. In particular,
        # invalid groups cannot decode a known prefix or suffix by accident.
        token_glyphs = sorted(set(cmap.values()) - {space, slash} | {".notdef"})
        fea = ["languagesystem DFLT dflt;", "languagesystem latn dflt;",
               "@TOKEN = [" + " ".join(token_glyphs) + "];"]
        lookups = []
        for index, (char, code) in enumerate(sorted(MORSE.items(), key=lambda item: -len(item[1]))):
            signals = [dot if signal == "." else dash for signal in code]
            sequence = " ".join(signals)
            context = signals[0] + "'" + (" " + " ".join(signals[1:]) if signals[1:] else "")
            action, guarded = f"MORSE_CHAR_{index}", f"MORSE_GROUP_{index}"
            fea += [f"lookup {action} {{ sub {sequence} by {output_name(char)}; }} {action};",
                    f"lookup {guarded} {{",
                    f"ignore sub @TOKEN {context};",
                    f"ignore sub {context} @TOKEN;",
                    f"sub {signals[0]}' lookup {action}" +
                    (" " + " ".join(signals[1:]) if signals[1:] else "") + ";",
                    f"}} {guarded};"]
            lookups.append(guarded)
        fea += [f"lookup MORSE_GAPS {{ sub {space} by morse.gap; "
                f"sub {slash} by morse.word; }} MORSE_GAPS;",
                "feature rlig {"]
        fea.extend(f"lookup {name};" for name in lookups + ["MORSE_GAPS"])
        fea.append("} rlig;")
        addOpenTypeFeaturesFromString(font, "\n".join(fea))

        family = family_name or "Morse Decoder"
        ps_name = re.sub(r"[^A-Za-z0-9-]+", "-", family).strip("-") or "MorseDecoder"
        replace_font_names(font, {1: family, 2: "Regular", 3: "MorseDecoder",
                                 4: family + " Regular", 6: (ps_name + "-Regular")[:50],
                                 16: family, 17: "Regular"})
        mark_modified_font(font, "morse")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        font.save(output_path)
    finally:
        font.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().with_name("morse-font.ttf"))
    parser.add_argument("--name", help="Optional font family name")
    parser.add_argument("--test", help="Print reference plaintext for a Morse message")
    args = parser.parse_args()
    try:
        plain = decode_text(args.test) if args.test is not None else None
        build_font(args.base, args.output, args.name)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Saved {args.output}: {len(MORSE)} Morse characters")
    if plain is not None:
        print(f"Plain: {plain}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
