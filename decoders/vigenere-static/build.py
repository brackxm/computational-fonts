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
Generate a TrueType font that visually DECODES Vigenere ciphertext.

The underlying text remains ciphertext. OpenType GSUB rules carry a hidden
position state through the glyph stream, then replace each ciphertext glyph
with the plaintext glyph for the corresponding key position.

Example:
    python build.py \
        --key LEMON \
        --output vigenere-static-font.ttf \
        --test LXFOPVEFRNHR

The rendered text should read ATTACKATDAWN.

Requirements:
    python -m pip install fonttools

Notes:
- Designed for glyf-based TrueType (.ttf) fonts, not CFF/CFF2 .otf fonts.
- A-Z/a-z letters consume key positions.
- Common printable ASCII punctuation is carried through without consuming a
  key position when the shaping engine keeps the run intact.
- Shaping boundaries (some spaces, line breaks, font/script changes, etc.) can
  reset the state depending on the application. Continuous letters are the
  most portable input.
- Uses the OpenType 'rlig' feature; the application must perform OpenType
  shaping (most modern apps do).
"""

from __future__ import annotations

import argparse
import copy
import re
import string
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

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont

LETTERS = string.ascii_uppercase + string.ascii_lowercase


def clean_key(key: str) -> str:
    cleaned = "".join(ch for ch in key.upper() if "A" <= ch <= "Z")
    if not cleaned:
        raise ValueError("The key must contain at least one A-Z letter.")
    return cleaned


def vigenere_decrypt(ciphertext: str, key: str) -> str:
    """Reference decryptor: key advances on ASCII letters only."""
    key = clean_key(key)
    out = []
    k = 0
    for ch in ciphertext:
        if "A" <= ch <= "Z" or "a" <= ch <= "z":
            shift = ord(key[k % len(key)]) - ord("A")
            base = ord("A") if ch.isupper() else ord("a")
            out.append(chr((ord(ch) - base - shift) % 26 + base))
            k += 1
        else:
            out.append(ch)
    return "".join(out)


def ps_safe(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9-]+", "-", s).strip("-")
    return (s or "VigenereDecoder")[:60]


def best_cmap(font: TTFont) -> dict[int, str]:
    cmap = font.getBestCmap()
    if not cmap:
        raise ValueError("Base font has no usable Unicode cmap.")
    return cmap


def add_name_records(font: TTFont, family: str, subfamily: str = "Regular") -> None:
    replace_font_names(font, {
        1: family,
        2: subfamily,
        4: f"{family} {subfamily}".strip(),
        6: ps_safe(f"{family}-{subfamily}"),
        16: family,
        17: subfamily,
    })


def glyph_name_for_char(cmap: dict[int, str], ch: str) -> str:
    try:
        return cmap[ord(ch)]
    except KeyError as exc:
        raise ValueError(f"Base font does not contain required character {ch!r}.") from exc


def build_font(base_path: Path, output_path: Path, key: str, family_name: str | None) -> None:
    key = clean_key(key)
    font = load_base_font(base_path, output_path)

    cmap = best_cmap(font)
    letter_base = [glyph_name_for_char(cmap, ch) for ch in LETTERS]

    # Printable ASCII non-letters that exist in the base font. These act as
    # state carriers, so punctuation does not consume Vigenere key positions.
    sep_chars = [
        ch for ch in string.printable
        if ch not in LETTERS and ch not in "\r\n\t\x0b\x0c" and ord(ch) in cmap
    ]
    # De-duplicate while preserving order.
    sep_chars = list(dict.fromkeys(sep_chars))
    sep_base = [cmap[ord(ch)] for ch in sep_chars]

    key_len = len(key)
    glyphs_per_state = len(LETTERS) + len(sep_chars)
    projected = len(font.getGlyphOrder()) + key_len * glyphs_per_state
    if projected >= 65535:
        raise ValueError(
            f"Key is too long for this base font: projected {projected} glyphs exceeds TrueType's limit."
        )

    glyf = font["glyf"]
    hmtx = font["hmtx"]
    order = list(font.getGlyphOrder())

    letter_states: list[list[str]] = []
    sep_states: list[list[str]] = []

    # Duplicate glyph outlines/metrics into unencoded hidden state glyphs.
    for state in range(key_len):
        ls = []
        for idx, base_glyph in enumerate(letter_base):
            new_name = f"vigL{idx:02d}.s{state}"
            if new_name in glyf.glyphs:
                raise ValueError(f"Generated glyph name collision: {new_name}")
            glyf.glyphs[new_name] = copy.deepcopy(glyf[base_glyph])
            hmtx.metrics[new_name] = hmtx.metrics[base_glyph]
            order.append(new_name)
            ls.append(new_name)
        letter_states.append(ls)

        ss = []
        for idx, base_glyph in enumerate(sep_base):
            new_name = f"vigP{idx:02d}.s{state}"
            if new_name in glyf:
                raise ValueError(f"Generated glyph name collision: {new_name}")
            glyf.glyphs[new_name] = copy.deepcopy(glyf[base_glyph])
            hmtx.metrics[new_name] = hmtx.metrics[base_glyph]
            order.append(new_name)
            ss.append(new_name)
        sep_states.append(ss)

    font.setGlyphOrder(order)
    font["maxp"].numGlyphs = len(order)

    # Replace existing GSUB so unrelated substitutions cannot interfere with
    # the hidden-state mechanism. GPOS/kerning is retained.
    if "GSUB" in font:
        del font["GSUB"]

    fea: list[str] = []
    fea.append("languagesystem DFLT dflt;")
    fea.append("languagesystem latn dflt;")
    fea.append("@VIG_BASE = [" + " ".join(letter_base) + "];")
    if sep_base:
        fea.append("@VIG_SEPBASE = [" + " ".join(sep_base) + "];")

    for s in range(key_len):
        fea.append(f"@VIG_L{s} = [" + " ".join(letter_states[s]) + "];")
        if sep_base:
            fea.append(f"@VIG_P{s} = [" + " ".join(sep_states[s]) + "];")
            fea.append(
                f"@VIG_C{s} = [" + " ".join(letter_states[s] + sep_states[s]) + "];"
            )
        else:
            fea.append(f"@VIG_C{s} = [" + " ".join(letter_states[s]) + "];")

    # 1) Initialize every encoded letter as state 0.
    fea.append("lookup VIG_INIT {")
    fea.append("  sub @VIG_BASE by @VIG_L0;")
    fea.append("} VIG_INIT;")

    # 2) Walk state forward. The current letter begins in state 0; its previous
    # state-carrying glyph determines which state it should actually occupy.
    # At the final key position, the next letter naturally remains state 0.
    fea.append("lookup VIG_STATE {")
    for s in range(key_len - 1):
        fea.append(f"  sub @VIG_C{s} @VIG_L0' by @VIG_L{s + 1};")
    if sep_base:
        for s in range(key_len):
            fea.append(f"  sub @VIG_C{s} @VIG_SEPBASE' by @VIG_P{s};")
    fea.append("} VIG_STATE;")

    # 3) Decode each hidden (cipher letter, key-position) glyph to plaintext.
    fea.append("lookup VIG_DECODE {")
    for s, key_ch in enumerate(key):
        shift = ord(key_ch) - ord("A")
        for idx, ch in enumerate(LETTERS):
            if ch.isupper():
                p = chr((ord(ch) - ord("A") - shift) % 26 + ord("A"))
            else:
                p = chr((ord(ch) - ord("a") - shift) % 26 + ord("a"))
            plain_glyph = glyph_name_for_char(cmap, p)
            fea.append(f"  sub {letter_states[s][idx]} by {plain_glyph};")
        if sep_base:
            for hidden, base in zip(sep_states[s], sep_base):
                fea.append(f"  sub {hidden} by {base};")
    fea.append("} VIG_DECODE;")

    fea.append("feature rlig {")
    fea.append("  lookup VIG_INIT;")
    fea.append("  lookup VIG_STATE;")
    fea.append("  lookup VIG_DECODE;")
    fea.append("} rlig;")

    feature_text = "\n".join(fea) + "\n"
    addOpenTypeFeaturesFromString(font, feature_text)

    family = family_name or f"Vigenere Decoder {key}"
    add_name_records(font, family)

    replace_font_names(font, {3: f"VigenereDecoder:{key}:{base_path.name}"})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mark_modified_font(font, "vigenere-static")
    font.save(str(output_path))
    font.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Vigenere-decoding TrueType font from a key."
    )
    parser.add_argument("--key", help="Vigenere key, e.g. LEMON. Nonletters are ignored.")
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE,
                        help="Base TrueType .ttf path (default: bundled Apache-2.0 Roboto 2).")
    parser.add_argument("--output", type=Path, help="Output .ttf path. Default: vigenere-static-font.ttf beside this script.")
    parser.add_argument("--name", help="Optional font family name.")
    parser.add_argument("--test", help="Print reference plaintext for this ciphertext.")
    args = parser.parse_args()

    key_input = args.key
    if not key_input:
        try:
            key_input = input("Vigenere key: ")
        except EOFError:
            parser.error("--key is required when input is not interactive")
    try:
        key = clean_key(key_input)
    except ValueError as e:
        parser.error(str(e))

    base = args.base
    if not base.exists():
        parser.error(f"Base font not found: {base}")

    output = args.output or Path(__file__).resolve().with_name("vigenere-static-font.ttf")

    try:
        build_font(base, output, key, args.name)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"Key:      {key}")
    print(f"Base:     {base}")
    print(f"Output:   {output}")
    print(f"Key len:  {len(key)}")
    if args.test is not None:
        print(f"Cipher:   {args.test}")
        print(f"Plain:    {vigenere_decrypt(args.test, key)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
