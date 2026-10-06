#!/usr/bin/env python3
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

"""
build.py

Build ONE TrueType font that takes the Vigenere key from the text itself.

Example input, using the generated font:

    LEMON~LXFOPVEFRNHR

visually renders as:

    ATTACKATDAWN

The underlying/copied text is still:

    LEMON~LXFOPVEFRNHR

The key and "~" are rendered invisibly.

How it works
------------
The font uses OpenType GSUB contextual substitutions.  It first determines
the key length from the run of A-Z/a-z letters immediately before "~",
turns those key letters into invisible state glyphs that still remember
which letters they were, and then uses them as backtracking context while
decrypting successive ciphertext letters.

Because OpenType is not a general programming language, a generated font
has finite limits:
    --max-key   maximum key length supported
    --max-text  maximum ciphertext letters supported after "~"

The defaults are deliberately moderate so the font remains practical.
Larger limits work, but generation time and GSUB size grow quickly.

Requirements:
    python -m pip install fonttools

Example:
    python build.py \
        --output vigenere-dynamic-font.ttf \
        --max-key 6 \
        --max-text 24

Then apply the font and type:
    LEMON~LXFOPVEFRNHR

Notes:
  * Keys may use A-Z or a-z; case does not change the key value.
  * Ciphertext may use A-Z or a-z; plaintext preserves ciphertext case.
  * Use continuous alphabetic ciphertext. Spaces/punctuation after "~"
    currently break the state chain rather than being ignored.
  * The key should be the contiguous alphabetic run immediately before "~".
  * If the key is longer than --max-key, only the final --max-key letters
    can be recognized reliably.
"""

from __future__ import annotations

import argparse
import sys
import re
import string
from pathlib import Path

# Direct script execution starts in the project folder; shared helpers live one level up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.font_metadata import (
    DEFAULT_BASE,
    load_base_font,
    mark_modified_font,
    replace_font_names,
    validate_marker,
    validate_marker_glyph,
)

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent


UPPER = string.ascii_uppercase
LOWER = string.ascii_lowercase


def empty_glyph() -> Glyph:
    glyph = Glyph()
    glyph.numberOfContours = 0
    return glyph


def composite_glyph(source: str) -> Glyph:
    glyph = Glyph()
    glyph.numberOfContours = -1
    component = GlyphComponent()
    component.glyphName = source
    component.x = 0
    component.y = 0
    component.flags = 0x0004  # ROUND_XY_TO_GRID
    glyph.components = [component]
    return glyph


def safe_ps_name(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9-]", "-", text)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:63] or "SelfKeyedVigenere"


def set_font_names(font: TTFont, family: str) -> None:
    replace_font_names(font, {
        1: family,
        2: "Regular",
        3: f"{family};1.0",
        4: family,
        6: safe_ps_name(family),
        16: family,
        17: "Regular",
    })


def vigenere_decrypt(key: str, ciphertext: str) -> str:
    key_letters = [c.upper() for c in key if c.isascii() and c.isalpha()]
    if not key_letters:
        raise ValueError("key must contain at least one A-Z letter")

    out = []
    index = 0
    for ch in ciphertext:
        if ch.isascii() and ch.isalpha():
            shift = ord(key_letters[index % len(key_letters)]) - ord("A")
            base = ord("A") if ch.isupper() else ord("a")
            value = (ord(ch) - base - shift) % 26
            out.append(chr(base + value))
            index += 1
        else:
            out.append(ch)
    return "".join(out)


def build_font(
    base_path: str,
    output_path: str,
    *,
    max_key: int = 6,
    max_text: int = 24,
    delimiter: str = "~",
) -> None:
    if max_key < 1:
        raise ValueError("--max-key must be at least 1")
    if max_text < 1:
        raise ValueError("--max-text must be at least 1")
    # DETECT + HIDE + DEC lookups, plus the 26 shifts and key-hiding helper.
    lookup_count = max_key + max_key * (max_key + 1) // 2 + max_key * max_text + 27
    if lookup_count > 65535:
        raise ValueError("Requested limits exceed OpenType's 65,535-lookup capacity")
    validate_marker(delimiter, string.ascii_letters, "--delimiter")

    font = load_base_font(base_path, output_path)

    cmap = font.getBestCmap()
    validate_marker_glyph(cmap, delimiter, string.ascii_letters, "--delimiter")
    glyf = font["glyf"]
    hmtx = font["hmtx"].metrics
    if len(font.getGlyphOrder()) + 78 + max_key > 65535:
        raise ValueError("Requested key limit exceeds TrueType's glyph capacity")

    upper_base = []
    lower_base = []
    for ch in UPPER:
        name = cmap.get(ord(ch))
        if name is None:
            raise ValueError(f"base font has no glyph for {ch!r}")
        upper_base.append(name)

    for ch in LOWER:
        name = cmap.get(ord(ch))
        if name is None:
            raise ValueError(f"base font has no glyph for {ch!r}")
        lower_base.append(name)

    delimiter_glyph = cmap.get(ord(delimiter))
    if delimiter_glyph is None:
        raise ValueError(f"base font has no glyph for delimiter {delimiter!r}")

    # Invisible key-state glyphs, one per alphabet letter.
    key_hidden = []
    for ch in UPPER:
        name = f"vsk.key.{ch}"
        if name in glyf:
            raise ValueError(f"reserved glyph name already exists: {name}")
        glyf[name] = empty_glyph()
        hmtx[name] = (0, 0)
        key_hidden.append(name)

    # Delimiter variants encode the detected key length.
    for length in range(1, max_key + 1):
        name = f"vsk.delim.{length}"
        if name in glyf:
            raise ValueError(f"reserved glyph name already exists: {name}")
        glyf[name] = empty_glyph()
        hmtx[name] = (0, 0)

    # Output glyphs keep plaintext appearance while identifying already
    # processed ciphertext characters to later contextual lookups.
    out_upper = []
    out_lower = []

    for ch, source in zip(UPPER, upper_base):
        name = f"vsk.out.{ch}"
        if name in glyf:
            raise ValueError(f"reserved glyph name already exists: {name}")
        glyf[name] = composite_glyph(source)
        hmtx[name] = hmtx[source]
        out_upper.append(name)

    for ch, source in zip(LOWER, lower_base):
        name = f"vsk.out.{ch}"
        if name in glyf:
            raise ValueError(f"reserved glyph name already exists: {name}")
        glyf[name] = composite_glyph(source)
        hmtx[name] = hmtx[source]
        out_lower.append(name)

    fea = ["languagesystem DFLT dflt;"]

    fea.append("@KU = [" + " ".join(upper_base) + "];")
    fea.append("@KL = [" + " ".join(lower_base) + "];")
    fea.append("@KBASE = [" + " ".join(upper_base + lower_base) + "];")
    fea.append("@KH = [" + " ".join(key_hidden) + "];")
    fea.append("@CU = [" + " ".join(upper_base) + "];")
    fea.append("@CL = [" + " ".join(lower_base) + "];")
    fea.append("@CIPHER = [" + " ".join(upper_base + lower_base) + "];")
    fea.append("@OUT = [" + " ".join(out_upper + out_lower) + "];")

    # 26 simple substitution lookups.  Each is "decrypt one character
    # using this key letter".
    for shift in range(26):
        dec_upper = [out_upper[(i - shift) % 26] for i in range(26)]
        dec_lower = [out_lower[(i - shift) % 26] for i in range(26)]

        fea.append(
            f"@DU{shift} = [" + " ".join(dec_upper) + "];"
        )
        fea.append(
            f"@DL{shift} = [" + " ".join(dec_lower) + "];"
        )
        fea.append(
            f"lookup SHIFT{shift} {{ "
            f"sub @CU by @DU{shift}; "
            f"sub @CL by @DL{shift}; "
            f"}} SHIFT{shift};"
        )

    # Upper- and lowercase key letters map to the same invisible state glyphs.
    fea.append(
        "lookup HIDEKEY { "
        "sub @KU by @KH; "
        "sub @KL by @KH; "
        "} HIDEKEY;"
    )

    feature_lookups = []

    # Detect key length.  Longest first is important: once "~" has been
    # replaced with vsk.delim.N, the shorter rules cannot fire.
    for length in range(max_key, 0, -1):
        lookup = f"DETECT{length}"
        context = " ".join(["@KBASE"] * length)
        fea.append(
            f"lookup {lookup} {{ "
            # Do not mistake the suffix of an oversized key for a valid key.
            f"ignore sub @KBASE {context} {delimiter_glyph}'; "
            f"sub {context} {delimiter_glyph}' by vsk.delim.{length}; "
            f"}} {lookup};"
        )
        feature_lookups.append(lookup)

    # Hide the key from right to left while preserving its identity.
    # Each pass sees already-hidden key glyphs to its right.
    for length in range(1, max_key + 1):
        for distance_from_right in range(length):
            lookup = f"HIDE{length}_{distance_from_right}"
            tail = " ".join(
                ["@KH"] * distance_from_right + [f"vsk.delim.{length}"]
            )
            fea.append(
                f"lookup {lookup} {{ "
                f"sub @KBASE' lookup HIDEKEY {tail}; "
                f"}} {lookup};"
            )
            feature_lookups.append(lookup)

    # Ciphertext decoding.
    #
    # For ciphertext position j and key length L, key index j mod L is
    # known.  The contextual rule reaches backward to that runtime key
    # glyph.  There are only 26 possibilities for its value, so 26 rules
    # are enough for each (L, j) pair; we do NOT enumerate whole keys.
    #
    # Separate contextual lookups are intentional: they avoid OpenType
    # subtable offset overflows that occur if thousands of long rules are
    # compiled into a single contextual lookup.
    for length in range(1, max_key + 1):
        for position in range(max_text):
            key_index = position % length
            remaining_key = length - key_index - 1

            lookup = f"DEC{length}_{position}"
            fea.append(f"lookup {lookup} {{")

            for shift in range(26):
                backtrack = (
                    [key_hidden[shift]]
                    + ["@KH"] * remaining_key
                    + [f"vsk.delim.{length}"]
                    + ["@OUT"] * position
                )
                fea.append(
                    "  sub "
                    + " ".join(backtrack)
                    + f" @CIPHER' lookup SHIFT{shift};"
                )

            fea.append(f"}} {lookup};")
            feature_lookups.append(lookup)

    fea.append("feature rlig {")
    for lookup in feature_lookups:
        fea.append(f"  lookup {lookup};")
    fea.append("} rlig;")

    feature_text = "\n".join(fea)

    addOpenTypeFeaturesFromString(font, feature_text)

    family = f"Self-Keyed Vigenere K{max_key} T{max_text}"
    set_font_names(font, family)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    mark_modified_font(font, "vigenere-dynamic")
    font.save(output)
    font.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a single Vigenere decoder font whose key is supplied "
            "inside the text as KEY~CIPHERTEXT."
        )
    )
    parser.add_argument(
        "--base",
        type=Path, default=DEFAULT_BASE,
        help="base TrueType .ttf path (default: bundled Apache-2.0 Roboto 2)",
    )
    parser.add_argument(
        "--output",
        default=Path(__file__).resolve().with_name("vigenere-dynamic-font.ttf"),
        help="output .ttf path (default: vigenere-dynamic-font.ttf beside this script)",
    )
    parser.add_argument(
        "--max-key",
        type=int,
        default=6,
        help="maximum runtime key length (default: 6)",
    )
    parser.add_argument(
        "--max-text",
        type=int,
        default=24,
        help="maximum runtime ciphertext letters (default: 24)",
    )
    parser.add_argument(
        "--delimiter",
        default="~",
        help="single separator character between key and ciphertext (default: ~)",
    )
    parser.add_argument(
        "--test",
        metavar="KEY~CIPHERTEXT",
        help="print the expected software decryption for a test string",
    )

    args = parser.parse_args()

    build_font(
        args.base,
        args.output,
        max_key=args.max_key,
        max_text=args.max_text,
        delimiter=args.delimiter,
    )

    print(f"Wrote: {args.output}")
    print(f"Runtime syntax: KEY{args.delimiter}CIPHERTEXT")
    print(f"Maximum key length: {args.max_key}")
    print(f"Maximum ciphertext letters: {args.max_text}")

    if args.test:
        if args.delimiter not in args.test:
            raise SystemExit(
                f"--test must contain delimiter {args.delimiter!r}"
            )
        key, ciphertext = args.test.split(args.delimiter, 1)
        print("Expected display:", vigenere_decrypt(key, ciphertext))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(f"Error: {exc}") from None
