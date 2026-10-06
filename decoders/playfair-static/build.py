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
Generate a TrueType font that visually decrypts Playfair ciphertext.

The output font uses OpenType required-ligature (rlig) substitutions. Each
ciphertext digraph is replaced by a single composite glyph containing the two
corresponding plaintext letter glyphs side-by-side. The underlying text remains
the ciphertext.

Requires: fontTools  (pip install fonttools)

Examples:
    python build.py --key "PLAYFAIR EXAMPLE" \
        --output playfair-static-font.ttf

    # If --key is omitted, the script prompts for it.
    python build.py
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

# Direct script execution starts in the project folder; shared helpers live one level up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.font_metadata import (
    DEFAULT_BASE,
    load_base_font,
    mark_modified_font,
    replace_font_names,
)

try:
    from fontTools.feaLib.builder import addOpenTypeFeatures
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
except ImportError as exc:
    raise SystemExit(
        "fontTools is required. Install it with:  python -m pip install fonttools"
    ) from exc

ALPHABET_25 = "ABCDEFGHIKLMNOPQRSTUVWXYZ"  # I/J share one Playfair cell
ALPHABET_INPUT = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # J accepted as an alias for I


def normalize_letter(ch: str) -> str:
    ch = ch.upper()
    return "I" if ch == "J" else ch


def build_square(key: str) -> str:
    """Return the standard 25-letter Playfair square as a flat string."""
    chars: list[str] = []
    for ch in key.upper():
        if "A" <= ch <= "Z":
            ch = normalize_letter(ch)
            if ch not in chars:
                chars.append(ch)
    for ch in ALPHABET_25:
        if ch not in chars:
            chars.append(ch)
    return "".join(chars)


def decrypt_pair(a: str, b: str, square: str) -> tuple[str, str]:
    """Decrypt one Playfair ciphertext digraph using `square`."""
    a = normalize_letter(a)
    b = normalize_letter(b)
    ia = square.index(a)
    ib = square.index(b)
    ra, ca = divmod(ia, 5)
    rb, cb = divmod(ib, 5)

    if ra == rb:  # same row: shift left
        return square[ra * 5 + (ca - 1) % 5], square[rb * 5 + (cb - 1) % 5]
    if ca == cb:  # same column: shift up
        return square[((ra - 1) % 5) * 5 + ca], square[((rb - 1) % 5) * 5 + cb]
    # rectangle: keep rows, swap columns
    return square[ra * 5 + cb], square[rb * 5 + ca]


def decrypt_text(ciphertext: str, key: str) -> str:
    """Reference decoder used for diagnostics; ignores nonletters."""
    letters = [c for c in ciphertext.upper() if "A" <= c <= "Z"]
    if len(letters) % 2:
        raise ValueError("Playfair ciphertext must contain an even number of letters")
    square = build_square(key)
    out: list[str] = []
    for i in range(0, len(letters), 2):
        out.extend(decrypt_pair(letters[i], letters[i + 1], square))
    return "".join(out)


def safe_slug(text: str, max_len: int = 36) -> str:
    text = "".join(ch for ch in text.upper() if ch.isascii() and ch.isalnum()) or "KEY"
    return text[:max_len]


def name_string(font: TTFont, name_id: int, fallback: str) -> str:
    table = font["name"]
    value = table.getDebugName(name_id)
    return value or fallback


def glyph_for_char(font: TTFont, ch: str) -> str:
    cmap = font.getBestCmap() or {}
    glyph = cmap.get(ord(ch))
    if not glyph:
        raise ValueError(f"Base font has no glyph for {ch!r}")
    return glyph


def add_pair_glyph(
    font: TTFont,
    new_name: str,
    left_glyph: str,
    right_glyph: str,
) -> None:
    glyf = font["glyf"]
    hmtx = font["hmtx"]

    left_advance, _left_lsb = hmtx.metrics[left_glyph]
    right_advance, _right_lsb = hmtx.metrics[right_glyph]

    glyph = Glyph()
    glyph.numberOfContours = -1
    glyph.components = []

    c1 = GlyphComponent()
    c1.glyphName = left_glyph
    c1.x = 0
    c1.y = 0
    c1.flags = 0
    glyph.components.append(c1)

    c2 = GlyphComponent()
    c2.glyphName = right_glyph
    c2.x = left_advance
    c2.y = 0
    c2.flags = 0
    glyph.components.append(c2)

    glyf[new_name] = glyph
    glyph.recalcBounds(glyf)
    hmtx.metrics[new_name] = (left_advance + right_advance, getattr(glyph, "xMin", 0))


def build_font(base_path: Path, output_path: Path, key: str) -> tuple[str, int]:
    square = build_square(key)
    font = load_base_font(base_path, output_path)
    font.recalcTimestamp = False

    # Confirm all uppercase letters exist and cache glyph names.
    input_glyphs = {ch: glyph_for_char(font, ch) for ch in ALPHABET_INPUT}
    plain_glyphs = {ch: glyph_for_char(font, ch) for ch in ALPHABET_25}

    original_order = list(font.getGlyphOrder())
    if len(original_order) + 26 * 26 > 65535:
        raise ValueError("Base font leaves too few glyph slots for the Playfair decoder")
    new_names: list[str] = []
    rules: list[str] = []

    # 26x26 rules are generated so J is accepted as an input alias for I.
    for a in ALPHABET_INPUT:
        for b in ALPHABET_INPUT:
            p1, p2 = decrypt_pair(a, b, square)
            new_name = f"pfdec_{a}_{b}"
            if new_name in font["glyf"]:
                raise ValueError(f"Unexpected glyph-name collision: {new_name}")
            add_pair_glyph(font, new_name, plain_glyphs[p1], plain_glyphs[p2])
            new_names.append(new_name)
            rules.append(f"    sub {input_glyphs[a]} {input_glyphs[b]} by {new_name};")

    font.setGlyphOrder(original_order + new_names)
    font["glyf"].glyphOrder = font.getGlyphOrder()
    font["maxp"].numGlyphs = len(font.getGlyphOrder())

    # rlig = required ligatures. This makes the decoding substitution much less
    # likely to be disabled by an application than ordinary discretionary ligatures.
    feature_text = "\n".join([
        "languagesystem DFLT dflt;",
        "languagesystem latn dflt;",
        "feature rlig {",
        *rules,
        "} rlig;",
        "",
    ])
    addOpenTypeFeatures(font, io.StringIO(feature_text), tables=["GSUB"])

    # Give the derivative a distinct identity while preserving the base outlines.
    base_family = name_string(font, 1, "BaseFont")
    slug = safe_slug(key)
    family = "Playfair Decoder"
    full_name = f"{family} [{slug}]"
    ps_family = re.sub(r"[^A-Za-z0-9-]", "", family.replace(" ", "-"))[:45]
    ps_name = f"{ps_family}-{slug}"[:63]
    unique = f"PlayfairDecoder:{slug}:{base_family}"

    replace_font_names(font, {
        1: family, 2: "Regular", 3: unique, 4: full_name, 6: ps_name,
        16: family, 17: "Regular",
    })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mark_modified_font(font, "playfair-static")
    font.save(str(output_path), reorderTables=True)
    font.close()
    return square, len(new_names)


def print_square(square: str) -> None:
    print("Playfair square:")
    for row in range(5):
        print("  " + " ".join(square[row * 5 : row * 5 + 5]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a TrueType font that visually decrypts Playfair ciphertext."
    )
    parser.add_argument(
        "--key",
        help="Playfair keyword/phrase. If omitted, you will be prompted.",
    )
    parser.add_argument(
        "--base",
        type=Path, default=DEFAULT_BASE,
        help="Base TrueType .ttf path (default: bundled Apache-2.0 Roboto 2).",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output .ttf path. Default: playfair-static-font.ttf beside this script.",
    )
    parser.add_argument(
        "--test",
        metavar="CIPHERTEXT",
        help="Also print the reference plaintext for this ciphertext.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    key = args.key
    if key is None:
        try:
            key = input("Playfair key: ").strip()
        except EOFError:
            key = ""
    if not key or not any("A" <= ch.upper() <= "Z" for ch in key):
        print("Error: the key must contain at least one A-Z letter.", file=sys.stderr)
        return 2

    base = args.base
    if not base.is_file():
        print(f"Error: base font does not exist: {base}", file=sys.stderr)
        return 2

    output = args.output or Path(__file__).resolve().with_name("playfair-static-font.ttf")

    try:
        square, count = build_font(base, output, key)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created: {output.resolve()}")
    print(f"Base font: {base.resolve()}")
    print(f"Key: {key}")
    print_square(square)
    print(f"Generated {count} ciphertext-digraph substitutions.")
    print("Use uppercase ciphertext. J is accepted as an alias for I.")
    print("The visible text is plaintext; copied/stored text remains ciphertext.")

    if args.test:
        try:
            print(f"Reference decode: {decrypt_text(args.test, key)}")
        except ValueError as exc:
            print(f"Test error: {exc}", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
