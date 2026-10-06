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

Build a TrueType font that visually decodes Lorenz SZ40 / SZ42a / SZ42b
ciphertext represented as raw ITA2 symbols.

Historical model implemented:
  - 5 Chi wheels: 41, 31, 29, 26, 23 cams
  - 5 Psi wheels: 43, 47, 51, 53, 59 cams
  - Mu61 and Mu37 motor wheels
  - SZ40 motor stepping
  - SZ42a Chi-2 one-back limitation
  - SZ42b Chi-2/Psi-1 one-back limitation
  - Vernam XOR over the five ITA2 impulses

The optional P5 / KT-Schalter plaintext-feedback limitation is NOT generated
as a font, because it makes future wheel stepping depend on recovered plaintext.
The software decoder in this file deliberately rejects KT mode for the same
font-compatible path.

The font uses an invisible start marker (default "~") to initialize its
OpenType state.  Example:

    ~CH58USOQ...

The underlying text remains ciphertext.  The font merely renders the recovered
plaintext glyphs.

Raw ITA2 ciphertext notation used by the font:
    A-Z  : the 26 letter codes
    3    : carriage return code
    4    : line feed code
    5    : FIGS shift
    8    : LTRS shift
    9    : space code
    /    : blank/NUL code

Normal ASCII spaces may be inserted between ciphertext symbols for grouping;
they do NOT advance the Lorenz machine.

Requires:
    python -m pip install fonttools

Example using the built-in BREAM pattern and a published SZ42a test setup:

    python build.py \
      --model SZ42a \
      --preset BREAM \
      --starts "20,32,9,51,47,2,18,26,6,29,16,4" \
      --output lorenz-static-font.ttf \
      --max-symbols 256

Then type ciphertext beginning with "~" while using the generated font.

The BREAM wheel pattern data and the test vector are compatible with the
Lorenz implementation in GCHQ CyberChef / Virtual Colossus.
"""

from __future__ import annotations

import argparse
import sys
import json
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


# ---------------------------------------------------------------------------
# ITA2
# ---------------------------------------------------------------------------

ITA2 = {
    "A": "11000", "B": "10011", "C": "01110", "D": "10010",
    "E": "10000", "F": "10110", "G": "01011", "H": "00101",
    "I": "01100", "J": "11010", "K": "11110", "L": "01001",
    "M": "00111", "N": "00110", "O": "00011", "P": "01101",
    "Q": "11101", "R": "01010", "S": "10100", "T": "00001",
    "U": "11100", "V": "01111", "W": "11001", "X": "10111",
    "Y": "10101", "Z": "10001",
    "3": "00010",  # CR
    "4": "01000",  # LF
    "9": "00100",  # SPACE
    "/": "00000",  # BLANK/NUL
    "8": "11111",  # LTRS
    "5": "11011",  # FIGS
}
RAW_SYMBOLS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ34589/"
BITS_TO_RAW = {bits: symbol for symbol, bits in ITA2.items()}

# In figures mode, these raw letter codes print these characters.
FIGURES = {
    "Q": "1", "W": "2", "E": "3", "R": "4", "T": "5",
    "Y": "6", "U": "7", "I": "8", "O": "9", "P": "0",
    "A": "-", "B": "?", "C": ":", "D": "#", "F": "%",
    "G": "@", "H": "£", "J": "", "K": "(", "L": ")",
    "M": ".", "N": ",", "S": "'", "V": "=", "X": "/", "Z": "+",
}

# Wheel order used by --starts and pattern JSON.
START_NAMES = (
    "psi1", "psi2", "psi3", "psi4", "psi5",
    "mu37", "mu61",
    "chi1", "chi2", "chi3", "chi4", "chi5",
)
WHEEL_LENGTHS = {
    "psi1": 43, "psi2": 47, "psi3": 51, "psi4": 53, "psi5": 59,
    "mu37": 37, "mu61": 61,
    "chi1": 41, "chi2": 31, "chi3": 29, "chi4": 26, "chi5": 23,
}


# ---------------------------------------------------------------------------
# BREAM pattern
# ---------------------------------------------------------------------------
# 1 = active cam, 0 = inactive cam.

BREAM = {
    "chi1": [0,1,1,1,1,0,1,0,1,1,0,1,0,1,1,0,0,1,0,0,1,1,0,1,0,0,0,0,1,1,0,0,0,0,1,1,1,1,0,0,0],
    "chi2": [0,1,1,1,0,0,0,0,1,0,0,0,1,1,0,1,0,1,0,0,0,1,1,0,1,1,1,0,0,1,1],
    "chi3": [1,1,0,0,1,1,0,1,1,0,0,1,1,1,0,0,0,0,1,0,0,1,1,0,1,1,1,0,0],
    "chi4": [1,1,1,1,0,0,1,0,0,1,1,0,0,1,0,0,1,1,0,1,0,0,1,1,0,0],
    "chi5": [0,1,1,1,0,1,1,1,0,0,0,1,0,0,1,1,0,1,0,0,0,1,0],

    "psi1": [0,0,0,1,1,1,0,0,1,1,1,0,1,1,0,0,1,0,1,0,1,1,0,1,1,0,1,0,0,1,0,0,1,0,1,0,1,0,1,0,1,0,0],
    "psi2": [1,1,0,1,0,0,1,1,1,0,0,0,0,0,1,1,1,1,0,1,0,0,1,0,1,1,0,0,1,1,0,1,0,1,0,1,0,1,0,1,0,1,1,0,1,0,0],
    "psi3": [1,0,0,1,0,0,1,1,0,1,1,1,0,0,0,1,1,1,0,0,0,0,1,1,1,1,0,1,0,1,0,1,1,0,0,1,0,0,1,0,1,0,1,0,1,0,1,0,1,0,1],
    "psi4": [0,1,0,0,0,0,1,0,0,1,0,1,1,1,1,1,0,1,1,0,0,1,1,0,0,1,1,0,0,0,0,1,0,1,1,0,1,0,1,0,1,0,1,0,1,0,1,1,0,0,1,0,1],
    "psi5": [1,0,1,0,1,0,0,1,1,0,0,1,1,0,1,1,0,0,1,0,0,0,1,0,0,0,0,1,0,1,1,0,1,1,1,1,0,1,1,1,0,0,1,0,1,0,0,0,1,1,0,1,0,1,0,1,0,1,0],

    "mu61": [1,0,0,0,0,1,1,0,0,0,1,1,0,0,1,1,0,1,1,1,1,0,0,0,0,1,1,0,0,0,1,1,0,1,1,0,1,0,1,1,1,1,0,0,0,1,1,0,0,1,1,0,0,1,1,0,1,0,1,1,1],
    "mu37": [0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,1,1,0,1,0,1,0,0,1,0,1,0,1,0,1,0,1,1,1,0,1],
}

PRESETS = {"BREAM": BREAM}


# ---------------------------------------------------------------------------
# Lorenz machine
# ---------------------------------------------------------------------------


def validate_patterns(patterns: dict[str, list[int]]) -> dict[str, list[int]]:
    if not isinstance(patterns, dict):
        raise ValueError("wheel patterns must be an object mapping wheel names to cam lists")
    out = {}
    for name, length in WHEEL_LENGTHS.items():
        if name not in patterns:
            raise ValueError(f"missing wheel pattern {name!r}")
        values = patterns[name]
        if not isinstance(values, (list, tuple)):
            raise ValueError(f"{name} cams must be a list of 0/1 values")
        if len(values) != length:
            raise ValueError(
                f"{name} must contain exactly {length} cams; got {len(values)}"
            )
        if any(type(v) not in (int, bool) or v not in (0, 1) for v in values):
            raise ValueError(f"{name} cams must contain only 0/1 values")
        out[name] = [int(v) for v in values]
    return out


def load_patterns(preset: str, pattern_file: str | None) -> dict[str, list[int]]:
    if pattern_file:
        data = json.loads(Path(pattern_file).read_text(encoding="utf-8"))
        return validate_patterns(data)

    preset = preset.upper()
    if preset not in PRESETS:
        raise ValueError(
            f"unknown preset {preset!r}; available: {', '.join(PRESETS)}"
        )
    return validate_patterns(PRESETS[preset])


def parse_starts(text: str) -> dict[str, int]:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 12:
        raise ValueError(
            "--starts requires 12 comma-separated positions in this order:\n"
            + ",".join(START_NAMES)
        )
    values = [int(p) for p in parts]
    result = dict(zip(START_NAMES, values))
    for name, value in result.items():
        length = WHEEL_LENGTHS[name]
        if not 1 <= value <= length:
            raise ValueError(f"{name} start must be 1..{length}; got {value}")
    return result


class Lorenz:
    def __init__(
        self,
        patterns: dict[str, list[int]],
        starts: dict[str, int],
        model: str = "SZ40",
    ):
        self.patterns = validate_patterns(patterns)
        for name, length in WHEEL_LENGTHS.items():
            value = starts.get(name)
            if type(value) is not int or not 1 <= value <= length:
                raise ValueError(f"{name} start must be a whole number in 1..{length}")
        self.pos = dict(starts)
        self.model = model.upper()
        if self.model not in ("SZ40", "SZ42A", "SZ42B"):
            raise ValueError("model must be SZ40, SZ42a, or SZ42b")

        # These are the lugs at the current motor positions before the
        # first symbol, matching the historical/CyberChef stepping order.
        self.mu61_lug = self.patterns["mu61"][self.pos["mu61"] - 1]
        self.mu37_lug = self.patterns["mu37"][self.pos["mu37"] - 1]

    @staticmethod
    def _back(value: int, length: int) -> int:
        value -= 1
        return length if value < 1 else value

    @staticmethod
    def _forward(value: int, length: int) -> int:
        value += 1
        return 1 if value > length else value

    def keystream_bits(self) -> list[int]:
        chi = [
            self.patterns["chi1"][self.pos["chi1"] - 1],
            self.patterns["chi2"][self.pos["chi2"] - 1],
            self.patterns["chi3"][self.pos["chi3"] - 1],
            self.patterns["chi4"][self.pos["chi4"] - 1],
            self.patterns["chi5"][self.pos["chi5"] - 1],
        ]
        psi = [
            self.patterns["psi1"][self.pos["psi1"] - 1],
            self.patterns["psi2"][self.pos["psi2"] - 1],
            self.patterns["psi3"][self.pos["psi3"] - 1],
            self.patterns["psi4"][self.pos["psi4"] - 1],
            self.patterns["psi5"][self.pos["psi5"] - 1],
        ]
        return [chi[i] ^ psi[i] for i in range(5)]

    def step_after_symbol(self) -> None:
        # The "one back" limitation references are captured from the
        # position used for the symbol just processed.
        chi2_one_back_pos = self._forward(self.pos["chi2"], 31)
        psi1_one_back_pos = self._forward(self.pos["psi1"], 43)

        # All Chi wheels move every symbol.
        for name in ("chi1", "chi2", "chi3", "chi4", "chi5"):
            self.pos[name] = self._back(self.pos[name], WHEEL_LENGTHS[name])

        # Mu61 moves every symbol.
        self.pos["mu61"] = self._back(self.pos["mu61"], 61)

        # Mu37 moves depending on the PREVIOUS Mu61 lug.
        if self.mu61_lug:
            self.pos["mu37"] = self._back(self.pos["mu37"], 37)

        basic_motor = self.mu37_lug

        if self.model == "SZ40":
            total_motor = basic_motor
        elif self.model == "SZ42A":
            limitation = self.patterns["chi2"][chi2_one_back_pos - 1]
            total_motor = 0 if (basic_motor == 0 and limitation == 1) else 1
        else:  # SZ42B
            chi2_lug = self.patterns["chi2"][chi2_one_back_pos - 1]
            psi1_lug = self.patterns["psi1"][psi1_one_back_pos - 1]
            limitation = chi2_lug ^ psi1_lug
            total_motor = 0 if (basic_motor == 0 and limitation == 1) else 1

        if total_motor:
            for name in ("psi1", "psi2", "psi3", "psi4", "psi5"):
                self.pos[name] = self._back(self.pos[name], WHEEL_LENGTHS[name])

        self.mu61_lug = self.patterns["mu61"][self.pos["mu61"] - 1]
        self.mu37_lug = self.patterns["mu37"][self.pos["mu37"] - 1]

    def transform_raw_symbol(self, symbol: str) -> str:
        symbol = symbol.upper()
        if symbol not in ITA2:
            raise ValueError(f"invalid raw ITA2 symbol: {symbol!r}")
        input_bits = [int(x) for x in ITA2[symbol]]
        key = self.keystream_bits()
        result_bits = "".join(str(input_bits[i] ^ key[i]) for i in range(5))
        result = BITS_TO_RAW[result_bits]
        self.step_after_symbol()
        return result

    def transform_raw(self, text: str, ignore_ascii_spaces: bool = True) -> str:
        out = []
        for ch in text:
            if ignore_ascii_spaces and ch == " ":
                continue
            out.append(self.transform_raw_symbol(ch))
        return "".join(out)


def raw_to_plaintext(raw: str, initial_shift: str = "letters") -> str:
    figures = initial_shift.lower().startswith("fig")
    out = []
    for symbol in raw:
        if symbol == "5":
            figures = True
        elif symbol == "8":
            figures = False
        elif symbol == "9":
            out.append(" ")
        elif symbol == "3":
            # A font cannot create an actual line break by GSUB; software can.
            out.append("\n")
        elif symbol == "4":
            # LF normally follows CR; suppress here.
            pass
        elif symbol == "/":
            out.append("/")
        else:
            out.append(FIGURES.get(symbol, symbol) if figures else symbol)
    return "".join(out)


def decode_ciphertext(
    ciphertext: str,
    patterns: dict[str, list[int]],
    starts: dict[str, int],
    model: str,
    initial_shift: str = "letters",
) -> tuple[str, str]:
    machine = Lorenz(patterns, starts, model)
    raw = machine.transform_raw(ciphertext)
    return raw, raw_to_plaintext(raw, initial_shift)


def precompute_keystream(
    count: int,
    patterns: dict[str, list[int]],
    starts: dict[str, int],
    model: str,
) -> list[int]:
    machine = Lorenz(patterns, starts, model)
    result = []
    for _ in range(count):
        bits = machine.keystream_bits()
        value = 0
        for bit in bits:
            value = (value << 1) | bit
        result.append(value)
        machine.step_after_symbol()
    return result


# ---------------------------------------------------------------------------
# Font generation
# ---------------------------------------------------------------------------


def make_empty_glyph() -> Glyph:
    glyph = Glyph()
    glyph.numberOfContours = 0
    return glyph


def make_composite(source_glyph: str) -> Glyph:
    glyph = Glyph()
    glyph.numberOfContours = -1
    component = GlyphComponent()
    component.glyphName = source_glyph
    component.x = 0
    component.y = 0
    component.flags = 0x0004  # ROUND_XY_TO_GRID
    glyph.components = [component]
    return glyph


def safe_ps_name(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9-]", "-", text)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:63] or "LorenzDecoder"


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


def decoded_display(raw_symbol: str, current_mode: str) -> tuple[str | None, str]:
    """
    Return (visible_character, next_mode).

    For CR we render a normal space in the font, because GSUB cannot create
    a line break. LF is invisible. Shift codes are invisible.
    """
    if raw_symbol == "5":
        return None, "F"
    if raw_symbol == "8":
        return None, "L"
    if raw_symbol == "9":
        return " ", current_mode
    if raw_symbol == "3":
        return " ", current_mode
    if raw_symbol == "4":
        return None, current_mode
    if raw_symbol == "/":
        return "/", current_mode

    if current_mode == "F":
        return FIGURES.get(raw_symbol, raw_symbol), current_mode
    return raw_symbol, current_mode


def build_font(
    base_path: str,
    output_path: str,
    *,
    patterns: dict[str, list[int]],
    starts: dict[str, int],
    model: str,
    max_symbols: int,
    trigger: str = "~",
    initial_shift: str = "letters",
) -> None:
    if max_symbols < 1:
        raise ValueError("--max-symbols must be at least 1")
    validate_marker(trigger, RAW_SYMBOLS + string.ascii_lowercase, "--trigger")

    initial_mode = "F" if initial_shift.lower().startswith("fig") else "L"

    font = load_base_font(base_path, output_path)

    cmap = font.getBestCmap()
    validate_marker_glyph(cmap, trigger, RAW_SYMBOLS + string.ascii_lowercase, "--trigger")
    glyf = font["glyf"]
    hmtx = font["hmtx"].metrics

    # Input glyphs for raw ITA2 ciphertext symbols.
    input_glyphs = {}
    for symbol in RAW_SYMBOLS:
        g = cmap.get(ord(symbol))
        if g is None:
            raise ValueError(f"base font has no glyph for ciphertext symbol {symbol!r}")
        input_glyphs[symbol] = g

    trigger_glyph = cmap.get(ord(trigger))
    if trigger_glyph is None:
        raise ValueError(f"base font has no glyph for trigger {trigger!r}")

    space_glyph = cmap.get(ord(" "))
    if space_glyph is None:
        raise ValueError("base font has no space glyph")
    space_metrics = hmtx[space_glyph]

    # Determine output glyphs that may be needed.
    output_chars = set(string.ascii_uppercase)
    output_chars.update("0123456789-?:#%@£().,'=/+")
    output_glyphs = {}
    fallback = cmap.get(ord("?"))
    for ch in output_chars:
        g = cmap.get(ord(ch))
        if g is None:
            if fallback is None:
                raise ValueError(f"base font lacks output glyph {ch!r} and '?' fallback")
            g = fallback
        output_glyphs[ch] = g

    current_glyphs = len(font.getGlyphOrder())
    # 2 shift states * 32 possible ciphertext symbols per machine position,
    # plus 2 state-carrying grouping spaces per position, plus starter space.
    extra = max_symbols * (2 * len(RAW_SYMBOLS) + 2) + 2
    if current_glyphs + extra >= 65535:
        per_pos = 2 * len(RAW_SYMBOLS) + 2
        safe = max(1, (65534 - current_glyphs - 2) // per_pos)
        raise ValueError(
            f"font would exceed TrueType's glyph limit; use --max-symbols {safe} or less"
        )

    keystream = precompute_keystream(max_symbols, patterns, starts, model)

    starter = "lorenz.start"
    if starter in glyf:
        raise ValueError(f"glyph-name collision: {starter}")
    glyf[starter] = make_empty_glyph()
    hmtx[starter] = (0, 0)

    start_sep = "lorenz.start.sep"
    if start_sep in glyf:
        raise ValueError(f"glyph-name collision: {start_sep}")
    glyf[start_sep] = make_empty_glyph()
    hmtx[start_sep] = space_metrics

    # carriers[position]["L"/"F"] contains all glyphs whose machine position
    # is after position+1 processed raw symbols and whose teleprinter shift
    # mode for the NEXT symbol is L/F.
    carriers: list[dict[str, list[str]]] = []

    def add_variant(name: str, visible: str | None) -> None:
        if name in glyf:
            raise ValueError(f"glyph-name collision: {name}")

        if not visible:
            glyf[name] = make_empty_glyph()
            hmtx[name] = (0, 0)
        elif visible == " ":
            glyf[name] = make_empty_glyph()
            hmtx[name] = space_metrics
        else:
            source = output_glyphs[visible]
            glyf[name] = make_composite(source)
            hmtx[name] = hmtx[source]

    variant_for: list[dict[str, dict[str, str]]] = []

    for position in range(max_symbols):
        key = keystream[position]
        pos_variants = {"L": {}, "F": {}}
        state_carriers = {"L": [], "F": []}

        for mode in ("L", "F"):
            for symbol in RAW_SYMBOLS:
                in_value = int(ITA2[symbol], 2)
                out_value = in_value ^ key
                out_bits = f"{out_value:05b}"
                raw_plain = BITS_TO_RAW[out_bits]

                visible, next_mode = decoded_display(raw_plain, mode)
                safe_sym = "SLASH" if symbol == "/" else symbol
                variant = f"lz{position:04d}_{mode}_{safe_sym}"
                add_variant(variant, visible)

                pos_variants[mode][symbol] = variant
                state_carriers[next_mode].append(variant)

        # Grouping ASCII spaces are visible but do not consume a Lorenz symbol.
        for mode in ("L", "F"):
            sep = f"lz{position:04d}_{mode}_SEP"
            if sep in glyf:
                raise ValueError(f"glyph-name collision: {sep}")
            glyf[sep] = make_empty_glyph()
            hmtx[sep] = space_metrics
            state_carriers[mode].append(sep)

        variant_for.append(pos_variants)
        carriers.append(state_carriers)

    # OpenType feature code.
    fea = [
        "languagesystem DFLT dflt;",
        "feature rlig {",
        f"  sub {trigger_glyph} by {starter};",
        f"  @LZSTART = [{starter} {start_sep}];",
        "  lookup LZSTEP0000 {",
        f"    sub @LZSTART {space_glyph}' by {start_sep};",
    ]

    # First raw symbol uses the configured initial shift state.
    for symbol in RAW_SYMBOLS:
        fea.append(
            f"    sub @LZSTART {input_glyphs[symbol]}' "
            f"by {variant_for[0][initial_mode][symbol]};"
        )
    fea.append("  } LZSTEP0000;")

    # Remaining positions.
    for position in range(1, max_symbols):
        prev = position - 1
        fea.append(
            f"  @LZ{prev:04d}L = [{' '.join(carriers[prev]['L'])}];"
        )
        fea.append(
            f"  @LZ{prev:04d}F = [{' '.join(carriers[prev]['F'])}];"
        )
        sep_l = f"lz{prev:04d}_L_SEP"
        sep_f = f"lz{prev:04d}_F_SEP"

        fea.append(f"  lookup LZSTEP{position:04d} {{")
        fea.append(
            f"    sub @LZ{prev:04d}L {space_glyph}' by {sep_l};"
        )
        fea.append(
            f"    sub @LZ{prev:04d}F {space_glyph}' by {sep_f};"
        )

        for symbol in RAW_SYMBOLS:
            inp = input_glyphs[symbol]
            fea.append(
                f"    sub @LZ{prev:04d}L {inp}' "
                f"by {variant_for[position]['L'][symbol]};"
            )
            fea.append(
                f"    sub @LZ{prev:04d}F {inp}' "
                f"by {variant_for[position]['F'][symbol]};"
            )

        fea.append(f"  }} LZSTEP{position:04d};")

    fea.append("} rlig;")
    feature_text = "\n".join(fea)
    addOpenTypeFeaturesFromString(font, feature_text)

    family = f"Lorenz {model.upper()} Decoder"
    set_font_names(font, family)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    mark_modified_font(font, "lorenz-static")
    font.save(out)
    font.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

EXAMPLE_CIPHER = (
    "CH58USOQWRTRIMW/OGXR3Q5P//GDVYO3I4TWE3VTVISYIAGQ5H3ULPI4PASLA4"
    "JOINJRK3AMT485KRL3D3VFIXZGDQFKYQA"
)
EXAMPLE_STARTS = "20,32,9,51,47,2,18,26,6,29,16,4"
EXAMPLE_PLAIN = (
    "HELLO CYBERCHEF USER, IF YOU CAN READ THIS, YOU HAVE RECEIVED A "
    "MESSAGE SUCCESSFULLY."
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a Lorenz SZ40/SZ42a/SZ42b visual decoder TrueType font."
    )
    parser.add_argument(
        "--model",
        default="SZ42a",
        choices=["SZ40", "SZ42a", "SZ42b", "SZ40".lower(), "SZ42a".lower(), "SZ42b".lower()],
        help="Lorenz model (default: SZ42a)",
    )
    parser.add_argument(
        "--preset",
        default="BREAM",
        help="built-in wheel pattern preset (default: BREAM)",
    )
    parser.add_argument(
        "--pattern-file",
        help="JSON file with custom 0/1 arrays for all twelve wheels",
    )
    parser.add_argument(
        "--starts",
        default=EXAMPLE_STARTS,
        help=(
            "12 comma-separated start positions in order: "
            "psi1,psi2,psi3,psi4,psi5,mu37,mu61,chi1,chi2,chi3,chi4,chi5"
        ),
    )
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE,
                        help="base TrueType .ttf path (default: bundled Apache-2.0 Roboto 2)")
    parser.add_argument("--output", default=Path(__file__).resolve().with_name("lorenz-static-font.ttf"), help="output .ttf path (default: lorenz-static-font.ttf beside this script)")
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=256,
        help="maximum Lorenz symbols per shaping run (default: 256)",
    )
    parser.add_argument(
        "--trigger",
        default="~",
        help="one-character invisible initializer typed before ciphertext",
    )
    parser.add_argument(
        "--initial-shift",
        choices=["letters", "figures"],
        default="letters",
        help="initial ITA2 shift state (default: letters)",
    )
    parser.add_argument(
        "--test",
        metavar="CIPHERTEXT",
        help="also decode raw ITA2 ciphertext in software and print the result",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run the published BREAM/SZ42a HELLO CYBERCHEF test vector",
    )

    args = parser.parse_args()
    model = args.model.upper()

    patterns = load_patterns(args.preset, args.pattern_file)
    starts = parse_starts(args.starts)

    if args.self_test:
        raw, plain = decode_ciphertext(
            EXAMPLE_CIPHER, BREAM, parse_starts(EXAMPLE_STARTS), "SZ42A"
        )
        print("Self-test plaintext:")
        print(plain)
        if plain != EXAMPLE_PLAIN:
            raise SystemExit("SELF-TEST FAILED")
        print("SELF-TEST OK")

    build_font(
        args.base,
        args.output,
        patterns=patterns,
        starts=starts,
        model=model,
        max_symbols=args.max_symbols,
        trigger=args.trigger,
        initial_shift=args.initial_shift,
    )

    print(f"Wrote: {args.output}")
    print(f"Model: {model}")
    print(f"Wheel pattern: {'custom file' if args.pattern_file else args.preset.upper()}")
    print("Starts:", ",".join(str(starts[n]) for n in START_NAMES))
    print(f"Type {args.trigger!r} before raw ITA2 ciphertext.")

    if args.test is not None:
        raw, plain = decode_ciphertext(
            args.test.replace(" ", ""),
            patterns,
            starts,
            model,
            args.initial_shift,
        )
        print("Decoded raw ITA2:", raw)
        print("Decoded plaintext:")
        print(plain)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(f"Error: {exc}") from None
