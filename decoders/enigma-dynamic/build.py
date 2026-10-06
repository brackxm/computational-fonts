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

Build one TrueType font that reads Enigma-I rotor order, starting positions,
and Ringstellung from the text itself.

Runtime syntax:
    ROTOR-ROTOR-ROTOR/POSITIONS/RINGS~CIPHERTEXT

Example:
    V-II-IV/QWE/BDF~...

Runtime settings:
  * any 3 distinct rotors from I, II, III, IV, V
  * any three starting window positions
  * any three ring settings

Fixed when generating the font:
  * reflector B
  * plugboard, supplied with --plugboard

Example:
    python build.py \
      --plugboard "AV BS CG DL FU HZ IN KM OW RX" \
      --output enigma-dynamic-font.ttf \
      --max-text 16

The configuration prefix renders invisibly. The underlying text remains the
full configuration plus ciphertext.

Requires:
    python -m pip install fonttools
"""

from __future__ import annotations

import argparse
import sys
import itertools
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


AZ = string.ascii_uppercase

ROTORS = {
    "I":   ("EKMFLGDQVZNTOWYHXUSPAIBRCJ", "Q"),
    "II":  ("AJDKSIRUXBLHWTMCQGZNPYFVOE", "E"),
    "III": ("BDFHJLCPRTXVZNYEIWGAKMUSQO", "V"),
    "IV":  ("ESOVPZJAYQUIRHXLNFTGKDCMWB", "J"),
    "V":   ("VZBRGITYUPSDNHLXAWMJQOFECK", "Z"),
}
ROTOR_NAMES = tuple(ROTORS)
REFLECTOR_B = "YRUHQSLDPXNGOKMIEBFZCWVJAT"


def idx(ch: str) -> int:
    return ord(ch) - 65


def inverse_wiring(wiring: str) -> list[int]:
    forward = [idx(c) for c in wiring]
    reverse = [0] * 26
    for i, v in enumerate(forward):
        reverse[v] = i
    return reverse


def parse_plugboard(spec: str) -> list[int]:
    mapping = list(range(26))
    cleaned = spec.upper().replace(",", " ").replace("-", " ")
    pairs = [x for x in cleaned.split() if x]

    if len(pairs) > 13:
        raise ValueError("plugboard can contain at most 13 disjoint pairs")

    used = set()
    for pair in pairs:
        if len(pair) != 2 or pair[0] not in AZ or pair[1] not in AZ or pair[0] == pair[1]:
            raise ValueError(f"invalid plugboard pair: {pair!r}")
        a, b = idx(pair[0]), idx(pair[1])
        if a in used or b in used:
            raise ValueError(f"plugboard letter reused in {pair!r}")
        used.update((a, b))
        mapping[a], mapping[b] = b, a
    return mapping


def normalized_plugboard(spec: str) -> str:
    cleaned = spec.upper().replace(",", " ").replace("-", " ")
    return " ".join(x for x in cleaned.split() if x)


def empty_glyph() -> Glyph:
    glyph = Glyph()
    glyph.numberOfContours = 0
    return glyph


def composite_glyph(source: str) -> Glyph:
    glyph = Glyph()
    glyph.numberOfContours = -1
    comp = GlyphComponent()
    comp.glyphName = source
    comp.x = 0
    comp.y = 0
    comp.flags = 0x0004
    glyph.components = [comp]
    return glyph


def safe_ps_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9-]", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:63] or "SelfKeyedEnigmaRings"


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


class EnigmaI:
    """Software reference matching the generated font."""

    def __init__(
        self,
        rotors=("I", "II", "III"),
        positions="AAA",
        rings="AAA",
        plugboard="",
    ):
        if len(rotors) != 3 or len(set(rotors)) != 3 or any(r not in ROTORS for r in rotors):
            raise ValueError("rotors must be three distinct choices from I-V")
        if any(c not in string.ascii_letters for c in positions + rings):
            raise ValueError("positions and rings must contain ASCII letters only")
        positions = positions.upper()
        rings = rings.upper()
        if len(positions) != 3 or any(c not in AZ for c in positions):
            raise ValueError("positions must be exactly three A-Z letters")
        if len(rings) != 3 or any(c not in AZ for c in rings):
            raise ValueError("rings must be exactly three A-Z letters")

        self.rotors = tuple(rotors)
        self.pos = [idx(c) for c in positions]
        self.ring = [idx(c) for c in rings]
        self.plug = parse_plugboard(plugboard)

        self.forward = []
        self.reverse = []
        self.notch = []
        for rotor in self.rotors:
            wiring, notch = ROTORS[rotor]
            self.forward.append([idx(c) for c in wiring])
            self.reverse.append(inverse_wiring(wiring))
            self.notch.append(idx(notch))

        self.reflector = [idx(c) for c in REFLECTOR_B]

    def step(self):
        middle_notch = self.pos[1] == self.notch[1]
        right_notch = self.pos[2] == self.notch[2]

        if middle_notch:
            self.pos[0] = (self.pos[0] + 1) % 26
        if middle_notch or right_notch:
            self.pos[1] = (self.pos[1] + 1) % 26
        self.pos[2] = (self.pos[2] + 1) % 26

    def through(self, value: int, rotor_i: int, reverse=False) -> int:
        offset = (self.pos[rotor_i] - self.ring[rotor_i]) % 26
        shifted = (value + offset) % 26
        table = self.reverse[rotor_i] if reverse else self.forward[rotor_i]
        return (table[shifted] - offset) % 26

    def transform_char(self, ch: str) -> str:
        if len(ch) != 1 or ch not in string.ascii_letters:
            return ch
        ch = ch.upper()
        if ch not in AZ:
            return ch
        self.step()

        v = self.plug[idx(ch)]
        for rotor_i in (2, 1, 0):
            v = self.through(v, rotor_i, False)
        v = self.reflector[v]
        for rotor_i in (0, 1, 2):
            v = self.through(v, rotor_i, True)
        v = self.plug[v]
        return AZ[v]

    def transform_text(self, text: str) -> str:
        return "".join(self.transform_char(c) for c in text)


def parse_runtime(text: str, delimiter="~"):
    validate_marker(delimiter, string.ascii_letters + "-/", "--delimiter")
    if delimiter not in text:
        raise ValueError(f"runtime text must contain {delimiter!r}")
    prefix, ciphertext = text.split(delimiter, 1)
    parts = prefix.split("/")
    if len(parts) != 3:
        raise ValueError("prefix must be ROTORS/POSITIONS/RINGS")
    if any(c not in "IViv-" for c in parts[0]):
        raise ValueError("rotor names must use ASCII Roman numerals I-V")

    if any(c not in string.ascii_letters for c in parts[1] + parts[2] + ciphertext):
        raise ValueError("positions, rings, and ciphertext must contain ASCII letters only")
    rotors = tuple(parts[0].upper().split("-"))
    positions = parts[1].upper()
    rings = parts[2].upper()

    if len(rotors) != 3 or len(set(rotors)) != 3 or any(r not in ROTORS for r in rotors):
        raise ValueError("rotors must be three distinct choices from I-V")
    if len(positions) != 3 or any(c not in AZ for c in positions):
        raise ValueError("positions must be exactly three A-Z letters")
    if len(rings) != 3 or any(c not in AZ for c in rings):
        raise ValueError("rings must be exactly three A-Z letters")
    if any(c not in AZ for c in ciphertext.upper()):
        raise ValueError("ciphertext must contain A-Z only")

    return rotors, positions, rings, ciphertext.upper()


def add_empty(font: TTFont, name: str, advance=0):
    if name in font["glyf"]:
        raise ValueError(f"glyph-name collision: {name}")
    font["glyf"][name] = empty_glyph()
    font["hmtx"].metrics[name] = (advance, 0)


def build_font(
    base_path: str,
    output_path: str,
    *,
    plugboard="",
    max_text=16,
    delimiter="~",
):
    if max_text < 1:
        raise ValueError("--max-text must be at least 1")
    # 32 pipeline lookups per letter, plus parser and electrical-map helpers.
    if 882 + 32 * max_text > 65535:
        raise ValueError("Requested text limit exceeds OpenType's 65,535-lookup capacity")
    validate_marker(delimiter, string.ascii_letters + "-/", "--delimiter")

    plug = parse_plugboard(plugboard)

    font = load_base_font(base_path, output_path)

    cmap = font.getBestCmap()
    validate_marker_glyph(cmap, delimiter, string.ascii_letters + "-/", "--delimiter")
    glyf = font["glyf"]
    hmtx = font["hmtx"].metrics
    if len(font.getGlyphOrder()) + 452 > 65535:
        raise ValueError("Base font leaves too few glyph slots for the Enigma decoder")

    upper = [cmap.get(ord(c)) for c in AZ]
    lower = [cmap.get(ord(c.lower())) for c in AZ]
    if any(g is None for g in upper + lower):
        raise ValueError("base font must contain A-Z and a-z")

    hyphen = cmap.get(ord("-"))
    slash = cmap.get(ord("/"))
    end_char = cmap.get(ord(delimiter))
    glyph_I = cmap.get(ord("I"))
    glyph_V = cmap.get(ord("V"))
    if None in (hyphen, slash, end_char, glyph_I, glyph_V):
        raise ValueError("base font lacks I, V, '-', '/', or the delimiter")

    orders = list(itertools.permutations(ROTOR_NAMES, 3))

    # Hidden rotor-order tokens.
    order_glyph = {}
    for order in orders:
        name = "esk.ORD." + "_".join(order)
        add_empty(font, name)
        order_glyph[order] = name

    # Position states.
    pos = {}
    pos_tmp = {}
    for slot in ("L", "M", "R"):
        pos[slot] = []
        for p in range(26):
            name = f"esk.P{slot}.{AZ[p]}"
            add_empty(font, name)
            pos[slot].append(name)

    for p in range(26):
        name = f"esk.PMSTEP.{AZ[p]}"
        add_empty(font, name)
        pos_tmp[p] = name

    # Electrical offsets d=(position-ring) mod 26.
    off = {}
    off_tmp = {}
    for slot in ("L", "M", "R"):
        off[slot] = []
        for d in range(26):
            name = f"esk.D{slot}.{AZ[d]}"
            add_empty(font, name)
            off[slot].append(name)

    for d in range(26):
        name = f"esk.DMSTEP.{AZ[d]}"
        add_empty(font, name)
        off_tmp[d] = name

    sep_hidden = "esk.SEP"
    end_hidden = "esk.END"
    add_empty(font, sep_hidden)
    add_empty(font, end_hidden)

    # Signal alphabets.
    signal = []
    for stage in range(1, 7):
        names = []
        for c in AZ:
            name = f"esk.S{stage}.{c}"
            add_empty(font, name)
            names.append(name)
        signal.append(names)

    # Visible final output.
    output = []
    for c, source in zip(AZ, upper):
        name = f"esk.OUT.{c}"
        if name in glyf:
            raise ValueError(f"reserved glyph name already exists: {name}")
        glyf[name] = composite_glyph(source)
        hmtx[name] = hmtx[source]
        output.append(name)

    f = ["languagesystem DFLT dflt;"]
    f.append("@U = [" + " ".join(upper) + "];")
    f.append("@LC = [" + " ".join(lower) + "];")
    f.append("@ALPHA = [" + " ".join(upper + lower) + "];")
    f.append("@ORDER = [" + " ".join(order_glyph[o] for o in orders) + "];")
    f.append("@PL = [" + " ".join(pos["L"]) + "];")
    f.append("@PM = [" + " ".join(pos["M"]) + "];")
    f.append("@PR = [" + " ".join(pos["R"]) + "];")
    f.append("@PMT = [" + " ".join(pos_tmp[p] for p in range(26)) + "];")
    f.append("@DL = [" + " ".join(off["L"]) + "];")
    f.append("@DM = [" + " ".join(off["M"]) + "];")
    f.append("@DR = [" + " ".join(off["R"]) + "];")
    f.append("@DMT = [" + " ".join(off_tmp[d] for d in range(26)) + "];")
    f.append("@RAW = [" + " ".join(upper) + "];")
    f.append("@OUT = [" + " ".join(output) + "];")
    for i, names in enumerate(signal, 1):
        f.append(f"@S{i} = [" + " ".join(names) + "];")

    # Rotor-order classes.
    for slot_i, slot in enumerate(("L", "M", "R")):
        for rotor in ROTOR_NAMES:
            members = [order_glyph[o] for o in orders if o[slot_i] == rotor]
            f.append(f"@ORD_{slot}_{rotor} = [" + " ".join(members) + "];")

    # Parse roman rotor order (e.g. V-II-IV/).
    def token(rotor: str):
        return [glyph_I if c == "I" else glyph_V for c in rotor]

    # Lookup definitions must also appear in execution order: HarfBuzz sorts
    # enabled lookups by their index, irrespective of feature reference order.
    f.append("lookup UPPERCASE { sub @LC by @U; } UPPERCASE;")
    f.append("lookup PARSE_ORDER {")
    for order in orders:
        seq = []
        for i, rotor in enumerate(order):
            if i:
                seq.append(hyphen)
            seq.extend(token(rotor))
        seq.append(slash)
        f.append("  sub " + " ".join(seq) + " by " + order_glyph[order] + ";")
    f.append("} PARSE_ORDER;")

    # Position mapping lookups.
    for slot in ("L", "M", "R"):
        f.append(f"lookup INIT_P{slot} {{")
        f.append("  sub @U by [" + " ".join(pos[slot]) + "];")
        f.append("  sub @LC by [" + " ".join(pos[slot]) + "];")
        f.append(f"}} INIT_P{slot};")

    # Convert each runtime ring letter into an electrical offset based on
    # the already-parsed position in that slot.
    make_offset_lookup = {slot: {} for slot in ("L", "M", "R")}
    for slot in ("L", "M", "R"):
        for p in range(26):
            targets = [off[slot][(p - ring) % 26] for ring in range(26)]
            lname = f"MAKE_D{slot}_{AZ[p]}"
            make_offset_lookup[slot][p] = lname
            f.append(f"lookup {lname} {{")
            f.append("  sub @U by [" + " ".join(targets) + "];")
            f.append("  sub @LC by [" + " ".join(targets) + "];")
            f.append(f"}} {lname};")

    f.append(f"lookup HIDE_SLASH {{ sub {slash} by {sep_hidden}; }} HIDE_SLASH;")
    f.append(f"lookup HIDE_END {{ sub {end_char} by {end_hidden}; }} HIDE_END;")

    # Simple state-advance lookups.
    for slot in ("L", "R"):
        f.append(
            f"lookup ADV_P{slot} {{ sub "
            f"[{' '.join(pos[slot])}] by "
            f"[{' '.join(pos[slot][1:] + pos[slot][:1])}]; }} ADV_P{slot};"
        )
        f.append(
            f"lookup ADV_D{slot} {{ sub "
            f"[{' '.join(off[slot])}] by "
            f"[{' '.join(off[slot][1:] + off[slot][:1])}]; }} ADV_D{slot};"
        )

    f.append(
        "lookup MARK_PM { sub @PM by @PMT; } MARK_PM;"
    )
    f.append(
        "lookup MARK_DM { sub @DM by @DMT; } MARK_DM;"
    )
    f.append(
        "lookup ADV_PM { sub @PMT by ["
        + " ".join(pos["M"][1:] + pos["M"][:1])
        + "]; } ADV_PM;"
    )
    f.append(
        "lookup ADV_DM { sub @DMT by ["
        + " ".join(off["M"][1:] + off["M"][:1])
        + "]; } ADV_DM;"
    )

    # Rotor electrical maps, indexed by electrical offset d.
    map_lookup = {}
    stage_info = {
        "RF": ("@RAW", signal[0], False),
        "MF": ("@S1", signal[1], False),
        "LF": ("@S2", signal[2], False),
        "LR": ("@S4", signal[4], True),
        "MR": ("@S5", signal[5], True),
        "RR": ("@S6", output, True),
    }

    for tag, (src_class, target_alpha, reverse) in stage_info.items():
        map_lookup[tag] = {}
        for rotor in ROTOR_NAMES:
            map_lookup[tag][rotor] = []
            wiring = ROTORS[rotor][0]
            table = inverse_wiring(wiring) if reverse else [idx(c) for c in wiring]

            for d in range(26):
                targets = []
                for incoming in range(26):
                    v = plug[incoming] if tag == "RF" else incoming
                    shifted = (v + d) % 26
                    wired = table[shifted]
                    v = (wired - d) % 26
                    if tag == "RR":
                        v = plug[v]
                    targets.append(target_alpha[v])

                cname = f"@MAP_{tag}_{rotor}_{AZ[d]}"
                f.append(cname + " = [" + " ".join(targets) + "];")
                lname = f"MAP_{tag}_{rotor}_{AZ[d]}"
                f.append(f"lookup {lname} {{ sub {src_class} by {cname}; }} {lname};")
                map_lookup[tag][rotor].append(lname)

    reflected = [signal[3][idx(c)] for c in REFLECTOR_B]
    f.append("@REFLECTED = [" + " ".join(reflected) + "];")
    f.append("lookup REFLECT { sub @S3 by @REFLECTED; } REFLECT;")

    # Normalize ASCII case before parsing Roman rotor names and ciphertext.
    feature = ["UPPERCASE", "PARSE_ORDER"]

    # Parse positions.
    f.append("lookup PARSE_POS_L {")
    f.append(f"  sub @ORDER @ALPHA' lookup INIT_PL @ALPHA @ALPHA {slash};")
    f.append("} PARSE_POS_L;")
    feature.append("PARSE_POS_L")

    f.append("lookup PARSE_POS_M {")
    f.append(f"  sub @ORDER @PL @ALPHA' lookup INIT_PM @ALPHA {slash};")
    f.append("} PARSE_POS_M;")
    feature.append("PARSE_POS_M")

    f.append("lookup PARSE_POS_R {")
    f.append(f"  sub @ORDER @PL @PM @ALPHA' lookup INIT_PR {slash};")
    f.append("} PARSE_POS_R;")
    feature.append("PARSE_POS_R")

    # Parse ring letters into electrical offsets.
    f.append("lookup PARSE_RING_L {")
    for p in range(26):
        f.append(
            f"  sub @ORDER {pos['L'][p]} @PM @PR {slash} "
            f"@ALPHA' lookup {make_offset_lookup['L'][p]} @ALPHA @ALPHA {end_char};"
        )
    f.append("} PARSE_RING_L;")
    feature.append("PARSE_RING_L")

    f.append("lookup PARSE_RING_M {")
    for p in range(26):
        f.append(
            f"  sub @ORDER @PL {pos['M'][p]} @PR {slash} "
            f"@DL @ALPHA' lookup {make_offset_lookup['M'][p]} @ALPHA {end_char};"
        )
    f.append("} PARSE_RING_M;")
    feature.append("PARSE_RING_M")

    f.append("lookup PARSE_RING_R {")
    for p in range(26):
        f.append(
            f"  sub @ORDER @PL @PM {pos['R'][p]} {slash} "
            f"@DL @DM @ALPHA' lookup {make_offset_lookup['R'][p]} {end_char};"
        )
    f.append("} PARSE_RING_R;")
    feature.append("PARSE_RING_R")

    # Hide slash and "~"; ring letters are already hidden offset glyphs.
    f.append("lookup HIDE_SLASH_CTX {")
    f.append(
        f"  sub @ORDER @PL @PM @PR {slash}' lookup HIDE_SLASH @DL @DM @DR {end_char};"
    )
    f.append("} HIDE_SLASH_CTX;")
    feature.append("HIDE_SLASH_CTX")

    f.append("lookup HIDE_END_CTX {")
    f.append(
        f"  sub @ORDER @PL @PM @PR {sep_hidden} @DL @DM @DR "
        f"{end_char}' lookup HIDE_END;"
    )
    f.append("} HIDE_END_CTX;")
    feature.append("HIDE_END_CTX")

    config = f"@ORDER @PL @PM @PR {sep_hidden} @DL @DM @DR {end_hidden}"

    # One stepping + electrical pipeline for each ciphertext position.
    for n in range(max_text):
        gap = " ".join(["@OUT"] * n)
        if gap:
            gap += " "

        # Left rotor steps when the middle rotor is at its own notch.
        for rotor in ROTOR_NAMES:
            notch = idx(ROTORS[rotor][1])

            lname = f"P{n:03d}_L_P_{rotor}"
            f.append(f"lookup {lname} {{")
            f.append(
                f"  sub @ORD_M_{rotor} @PL' lookup ADV_PL {pos['M'][notch]} @PR "
                f"{sep_hidden} @DL @DM @DR {end_hidden} {gap}@RAW;"
            )
            f.append(f"}} {lname};")
            feature.append(lname)

            lname = f"P{n:03d}_L_D_{rotor}"
            f.append(f"lookup {lname} {{")
            f.append(
                f"  sub @ORD_M_{rotor} @PL {pos['M'][notch]} @PR "
                f"{sep_hidden} @DL' lookup ADV_DL @DM @DR {end_hidden} {gap}@RAW;"
            )
            f.append(f"}} {lname};")
            feature.append(lname)

        # Mark middle rotor from its own notch.
        for rotor in ROTOR_NAMES:
            notch = idx(ROTORS[rotor][1])
            lname = f"P{n:03d}_MARK_M_SELF_{rotor}"
            f.append(f"lookup {lname} {{")
            f.append(
                f"  sub @ORD_M_{rotor} @PL {pos['M'][notch]}' lookup MARK_PM @PR "
                f"{sep_hidden} @DL @DM @DR {end_hidden} {gap}@RAW;"
            )
            f.append(f"}} {lname};")
            feature.append(lname)

        # Or from right-rotor notch. Already-marked PM no longer matches @PM.
        for rotor in ROTOR_NAMES:
            notch = idx(ROTORS[rotor][1])
            lname = f"P{n:03d}_MARK_M_RIGHT_{rotor}"
            f.append(f"lookup {lname} {{")
            f.append(
                f"  sub @ORD_R_{rotor} @PL @PM' lookup MARK_PM {pos['R'][notch]} "
                f"{sep_hidden} @DL @DM @DR {end_hidden} {gap}@RAW;"
            )
            f.append(f"}} {lname};")
            feature.append(lname)

        # If PM was marked, mark corresponding electrical offset too.
        lname = f"P{n:03d}_MARK_DM"
        f.append(f"lookup {lname} {{")
        f.append(
            f"  sub @ORDER @PL @PMT @PR {sep_hidden} @DL @DM' lookup MARK_DM "
            f"@DR {end_hidden} {gap}@RAW;"
        )
        f.append(f"}} {lname};")
        feature.append(lname)

        lname = f"P{n:03d}_ADV_PM"
        f.append(f"lookup {lname} {{")
        f.append(
            f"  sub @ORDER @PL @PMT' lookup ADV_PM @PR {sep_hidden} "
            f"@DL @DMT @DR {end_hidden} {gap}@RAW;"
        )
        f.append(f"}} {lname};")
        feature.append(lname)

        lname = f"P{n:03d}_ADV_DM"
        f.append(f"lookup {lname} {{")
        f.append(
            f"  sub @ORDER @PL @PM @PR {sep_hidden} @DL @DMT' lookup ADV_DM "
            f"@DR {end_hidden} {gap}@RAW;"
        )
        f.append(f"}} {lname};")
        feature.append(lname)

        # Right rotor always advances position and electrical offset.
        lname = f"P{n:03d}_ADV_PR"
        f.append(f"lookup {lname} {{")
        f.append(
            f"  sub @ORDER @PL @PM @PR' lookup ADV_PR {sep_hidden} "
            f"@DL @DM @DR {end_hidden} {gap}@RAW;"
        )
        f.append(f"}} {lname};")
        feature.append(lname)

        lname = f"P{n:03d}_ADV_DR"
        f.append(f"lookup {lname} {{")
        f.append(
            f"  sub @ORDER @PL @PM @PR {sep_hidden} @DL @DM @DR' lookup ADV_DR "
            f"{end_hidden} {gap}@RAW;"
        )
        f.append(f"}} {lname};")
        feature.append(lname)

        # Signal through right -> middle -> left.
        for tag, slot, dclass, sigclass in (
            ("RF", "R", "@DR", "@RAW"),
            ("MF", "M", "@DM", "@S1"),
            ("LF", "L", "@DL", "@S2"),
        ):
            lname = f"P{n:03d}_{tag}"
            f.append(f"lookup {lname} {{")
            for rotor in ROTOR_NAMES:
                for d in range(26):
                    dglyph = off[slot][d]
                    if slot == "R":
                        ctx = (
                            f"@ORD_R_{rotor} @PL @PM @PR {sep_hidden} "
                            f"@DL @DM {dglyph} {end_hidden} {gap}{sigclass}'"
                        )
                    elif slot == "M":
                        ctx = (
                            f"@ORD_M_{rotor} @PL @PM @PR {sep_hidden} "
                            f"@DL {dglyph} @DR {end_hidden} {gap}{sigclass}'"
                        )
                    else:
                        ctx = (
                            f"@ORD_L_{rotor} @PL @PM @PR {sep_hidden} "
                            f"{dglyph} @DM @DR {end_hidden} {gap}{sigclass}'"
                        )
                    f.append(f"  sub {ctx} lookup {map_lookup[tag][rotor][d]};")
            f.append(f"}} {lname};")
            feature.append(lname)

        lname = f"P{n:03d}_REFLECT"
        f.append(f"lookup {lname} {{")
        f.append(
            f"  sub {config} {gap}@S3' lookup REFLECT;"
        )
        f.append(f"}} {lname};")
        feature.append(lname)

        # Return left -> middle -> right.
        for tag, slot, sigclass in (
            ("LR", "L", "@S4"),
            ("MR", "M", "@S5"),
            ("RR", "R", "@S6"),
        ):
            lname = f"P{n:03d}_{tag}"
            f.append(f"lookup {lname} {{")
            for rotor in ROTOR_NAMES:
                for d in range(26):
                    dglyph = off[slot][d]
                    if slot == "R":
                        ctx = (
                            f"@ORD_R_{rotor} @PL @PM @PR {sep_hidden} "
                            f"@DL @DM {dglyph} {end_hidden} {gap}{sigclass}'"
                        )
                    elif slot == "M":
                        ctx = (
                            f"@ORD_M_{rotor} @PL @PM @PR {sep_hidden} "
                            f"@DL {dglyph} @DR {end_hidden} {gap}{sigclass}'"
                        )
                    else:
                        ctx = (
                            f"@ORD_L_{rotor} @PL @PM @PR {sep_hidden} "
                            f"{dglyph} @DM @DR {end_hidden} {gap}{sigclass}'"
                        )
                    f.append(f"  sub {ctx} lookup {map_lookup[tag][rotor][d]};")
            f.append(f"}} {lname};")
            feature.append(lname)

    f.append("feature rlig {")
    for lname in feature:
        f.append(f"  lookup {lname};")
    f.append("} rlig;")

    addOpenTypeFeaturesFromString(font, "\n".join(f))

    set_font_names(font, f"Self-Keyed Enigma Rings T{max_text}")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    mark_modified_font(font, "enigma-dynamic")
    font.save(out)
    font.close()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate a self-keyed Enigma-I decoder font. Runtime text supplies "
            "rotor order, start positions and ring settings; --plugboard is "
            "baked into the generated font."
        )
    )
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE,
                        help="base TrueType .ttf path (default: bundled Apache-2.0 Roboto 2)")
    parser.add_argument("--output", default=Path(__file__).resolve().with_name("enigma-dynamic-font.ttf"),
                        help="output .ttf path (default: enigma-dynamic-font.ttf beside this script)")
    parser.add_argument(
        "--plugboard",
        default="",
        help='plugboard pairs, e.g. "AV BS CG DL FU HZ IN KM OW RX"',
    )
    parser.add_argument("--max-text", type=int, default=16)
    parser.add_argument("--delimiter", default="~")
    parser.add_argument(
        "--test",
        metavar="ROTORS/POSITIONS/RINGS~CIPHERTEXT",
        help="print the expected decoded display",
    )
    args = parser.parse_args()

    build_font(
        args.base,
        args.output,
        plugboard=args.plugboard,
        max_text=args.max_text,
        delimiter=args.delimiter,
    )

    print(f"Wrote: {args.output}")
    print(f"Runtime syntax: I-II-III/AAA/AAA{args.delimiter}CIPHERTEXT")
    print("Runtime: rotor order + positions + Ringstellung")
    print("Reflector: B")
    print("Plugboard:", normalized_plugboard(args.plugboard) or "(none)")
    print("Maximum ciphertext letters:", args.max_text)

    if args.test:
        rotors, positions, rings, cipher = parse_runtime(args.test, args.delimiter)
        machine = EnigmaI(rotors, positions, rings, args.plugboard)
        print("Expected display:", machine.transform_text(cipher))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(f"Error: {exc}") from None
