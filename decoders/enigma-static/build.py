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

Generate a TrueType font that visually decodes a fixed-key historical
three-rotor Enigma I machine as ciphertext is typed.

The underlying text remains ciphertext.  The font uses OpenType GSUB
state-carrying glyphs, so each successive A-Z letter is displayed using
the rotor state for that letter position.

Start each independently shaped message/run with the trigger character
(default: ~).  The trigger becomes invisible and initializes the state.

Requires:
    pip install fonttools

Example:
    python build.py \
        --key "I-II-III/AAA/AAA/B" \
        --output enigma-static-font.ttf

Known default-machine check:
    AAAAA -> BDZGO
so typing:
    ~BDZGO
with the generated font displays:
    AAAAA
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


ALPHABET = string.ascii_uppercase

# Wehrmacht/Luftwaffe Enigma I rotor wirings, left-to-right selectable.
ROTORS = {
    "I":   ("EKMFLGDQVZNTOWYHXUSPAIBRCJ", "Q"),
    "II":  ("AJDKSIRUXBLHWTMCQGZNPYFVOE", "E"),
    "III": ("BDFHJLCPRTXVZNYEIWGAKMUSQO", "V"),
    "IV":  ("ESOVPZJAYQUIRHXLNFTGKDCMWB", "J"),
    "V":   ("VZBRGITYUPSDNHLXAWMJQOFECK", "Z"),
}

REFLECTORS = {
    "B": "YRUHQSLDPXNGOKMIEBFZCWVJAT",
    "C": "FVPJIAOYEDRZXWGCTKUQSBNMHL",
}

DEFAULT_PASSTHROUGH = " .,:;!?-_/()[]{}'\""


def az_index(ch: str) -> int:
    return ord(ch) - ord("A")


def validate_triplet(value: str, label: str) -> str:
    if len(value) != 3 or any(ch not in string.ascii_letters for ch in value):
        raise ValueError(f"{label} must be exactly three letters A-Z")
    value = value.upper()
    if len(value) != 3 or any(ch not in ALPHABET for ch in value):
        raise ValueError(f"{label} must be exactly three letters A-Z")
    return value


def parse_plugboard(spec: str) -> list[int]:
    mapping = list(range(26))
    if not spec.strip():
        return mapping

    pairs = spec.upper().split()
    if len(pairs) > 10:
        raise ValueError("historical Enigma I used at most 10 plugboard pairs")

    used: set[int] = set()
    for pair in pairs:
        if (
            len(pair) != 2
            or pair[0] not in ALPHABET
            or pair[1] not in ALPHABET
            or pair[0] == pair[1]
        ):
            raise ValueError(f"invalid plugboard pair: {pair!r}")

        a, b = az_index(pair[0]), az_index(pair[1])
        if a in used or b in used:
            raise ValueError(f"plugboard letter reused in pair: {pair!r}")
        used.update((a, b))
        mapping[a], mapping[b] = b, a

    return mapping


def parse_key(key: str) -> tuple[list[str], str, str, str, str]:
    """
    Compact key syntax:
        ROTOR-ROTOR-ROTOR/POSITIONS/RINGS/REFLECTOR[/PLUGBOARD]

    Example:
        I-II-III/AAA/AAA/B/AV BS CG DL FU HZ IN KM OW RX
    """
    parts = key.strip().split("/", 4)
    if len(parts) < 4:
        raise ValueError(
            "key format is ROTOR-ROTOR-ROTOR/POSITIONS/RINGS/REFLECTOR[/PLUGBOARD]"
        )

    rotor_names = [x.upper() for x in parts[0].split("-")]
    if len(rotor_names) != 3:
        raise ValueError("exactly three rotors are required")
    if len(set(rotor_names)) != 3:
        raise ValueError("the three rotors must be distinct")
    for rotor in rotor_names:
        if rotor not in ROTORS:
            raise ValueError(f"unknown rotor {rotor!r}; choose I, II, III, IV, V")

    positions = validate_triplet(parts[1], "positions")
    rings = validate_triplet(parts[2], "rings")
    reflector = parts[3].upper()
    if reflector not in REFLECTORS:
        raise ValueError("reflector must be B or C")

    plugboard = parts[4].strip() if len(parts) == 5 else ""
    parse_plugboard(plugboard)  # validation

    return rotor_names, positions, rings, reflector, plugboard


class EnigmaI:
    """
    Three-rotor Enigma-I-style core with authentic stepping including
    the middle-rotor double step.

    Rotor order is LEFT, MIDDLE, RIGHT.
    Positions are the letters visible in the windows.
    """

    def __init__(
        self,
        rotors: list[str] | tuple[str, str, str] = ("I", "II", "III"),
        positions: str = "AAA",
        rings: str = "AAA",
        reflector: str = "B",
        plugboard: str = "",
    ):
        self.rotor_names = list(rotors)
        if len(self.rotor_names) != 3 or len(set(self.rotor_names)) != 3:
            raise ValueError("choose three distinct rotors")
        if any(r not in ROTORS for r in self.rotor_names):
            raise ValueError("rotors must be selected from I, II, III, IV, V")

        positions = validate_triplet(positions, "positions")
        rings = validate_triplet(rings, "rings")
        reflector = reflector.upper()
        if reflector not in REFLECTORS:
            raise ValueError("reflector must be B or C")

        self.positions = [az_index(c) for c in positions]
        self.rings = [az_index(c) for c in rings]
        self.reflector = [az_index(c) for c in REFLECTORS[reflector]]
        self.plugboard = parse_plugboard(plugboard)

        self.forward_maps: list[list[int]] = []
        self.reverse_maps: list[list[int]] = []
        self.notches: list[set[int]] = []

        for name in self.rotor_names:
            wiring, notch_letters = ROTORS[name]
            forward = [az_index(c) for c in wiring]
            reverse = [0] * 26
            for i, value in enumerate(forward):
                reverse[value] = i

            self.forward_maps.append(forward)
            self.reverse_maps.append(reverse)
            self.notches.append({az_index(c) for c in notch_letters})

    def at_notch(self, rotor_index: int) -> bool:
        # positions[] is the visible window letter, so the historical
        # turnover letter is independent of ring setting here.
        return self.positions[rotor_index] in self.notches[rotor_index]

    def step(self) -> None:
        # Evaluate notch states before movement.
        middle_at_notch = self.at_notch(1)
        right_at_notch = self.at_notch(2)

        # Double-step behavior.
        if middle_at_notch:
            self.positions[0] = (self.positions[0] + 1) % 26
        if middle_at_notch or right_at_notch:
            self.positions[1] = (self.positions[1] + 1) % 26
        self.positions[2] = (self.positions[2] + 1) % 26

    def rotor_forward(self, value: int, rotor_index: int) -> int:
        position = self.positions[rotor_index]
        ring = self.rings[rotor_index]
        shifted = (value + position - ring) % 26
        wired = self.forward_maps[rotor_index][shifted]
        return (wired - position + ring) % 26

    def rotor_reverse(self, value: int, rotor_index: int) -> int:
        position = self.positions[rotor_index]
        ring = self.rings[rotor_index]
        shifted = (value + position - ring) % 26
        wired = self.reverse_maps[rotor_index][shifted]
        return (wired - position + ring) % 26

    def transform_without_step(self, ch: str) -> str:
        value = az_index(ch)
        value = self.plugboard[value]

        # Keyboard -> right rotor -> middle -> left.
        for i in (2, 1, 0):
            value = self.rotor_forward(value, i)

        value = self.reflector[value]

        # Reflector -> left rotor -> middle -> right.
        for i in (0, 1, 2):
            value = self.rotor_reverse(value, i)

        value = self.plugboard[value]
        return chr(ord("A") + value)

    def transform_char(self, ch: str) -> str:
        self.step()
        return self.transform_without_step(ch.upper())

    def transform_text(self, text: str) -> str:
        """
        A-Z letters advance the machine. Everything else passes through.
        Enigma is reciprocal, so this is both encryption and decryption.
        """
        out: list[str] = []
        for ch in text:
            up = ch.upper()
            if len(up) == 1 and up in ALPHABET:
                out.append(self.transform_char(up))
            else:
                out.append(ch)
        return "".join(out)


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


def make_empty_glyph() -> Glyph:
    glyph = Glyph()
    glyph.numberOfContours = 0
    return glyph


def safe_ps_name(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9-]", "-", text)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:63] or "RotorDecoder"


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


def state_maps(
    max_letters: int,
    rotors: list[str],
    positions: str,
    rings: str,
    reflector: str,
    plugboard: str,
) -> list[dict[str, str]]:
    """
    Precompute the reciprocal substitution alphabet at every successive
    rotor position.  The machine steps before every character.
    """
    machine = EnigmaI(rotors, positions, rings, reflector, plugboard)
    result: list[dict[str, str]] = []

    for _ in range(max_letters):
        machine.step()
        mapping = {
            ch: machine.transform_without_step(ch)
            for ch in ALPHABET
        }
        result.append(mapping)

    return result


def build_font(
    base_path: str,
    output_path: str,
    *,
    rotors: list[str],
    positions: str,
    rings: str,
    reflector: str,
    plugboard: str,
    max_letters: int,
    trigger: str,
    passthrough: str,
) -> None:
    if max_letters < 1:
        raise ValueError("--max-letters must be at least 1")
    validate_marker(trigger, string.ascii_letters, "--trigger")
    if any(ch in ALPHABET for ch in passthrough):
        raise ValueError("--passthrough must not contain ciphertext letters A-Z")

    font = load_base_font(base_path, output_path)

    cmap = font.getBestCmap()
    validate_marker_glyph(cmap, trigger, string.ascii_letters, "--trigger")
    for ch in passthrough:
        validate_marker_glyph(cmap, ch, ALPHABET, "--passthrough")
    glyf = font["glyf"]
    hmtx = font["hmtx"].metrics

    letter_glyphs: dict[str, str] = {}
    for ch in ALPHABET:
        glyph_name = cmap.get(ord(ch))
        if glyph_name is None:
            raise ValueError(f"base font has no glyph for {ch!r}")
        letter_glyphs[ch] = glyph_name

    trigger_glyph = cmap.get(ord(trigger))
    if trigger_glyph is None:
        raise ValueError(f"base font has no glyph for trigger {trigger!r}")

    # Deduplicate pass-through characters by actual glyph name.
    pass_items: list[tuple[str, str]] = []
    seen_pass_glyphs: set[str] = set()
    for ch in passthrough:
        if ch == trigger:
            continue
        glyph_name = cmap.get(ord(ch))
        if glyph_name and glyph_name not in seen_pass_glyphs:
            seen_pass_glyphs.add(glyph_name)
            pass_items.append((ch, glyph_name))

    current_glyphs = len(font.getGlyphOrder())
    extra_glyphs = (
        1
        + (26 * max_letters)
        + (len(pass_items) * (max_letters + 1))
    )
    if current_glyphs + extra_glyphs >= 65535:
        per_state = 26 + len(pass_items)
        safe_max = max(
            1,
            (65534 - current_glyphs - 1 - len(pass_items)) // per_state,
        )
        raise ValueError(
            f"this font would exceed TrueType's glyph limit; "
            f"try --max-letters {safe_max} or less"
        )

    maps = state_maps(
        max_letters, rotors, positions, rings, reflector, plugboard
    )

    starter = "rotor.start"
    if starter in glyf:
        raise ValueError(f"base font already contains reserved glyph {starter!r}")
    glyf[starter] = make_empty_glyph()
    hmtx[starter] = (0, 0)

    def add_variant(name: str, source: str) -> None:
        if name in glyf:
            raise ValueError(f"glyph-name collision: {name}")
        glyf[name] = make_composite(source)
        hmtx[name] = hmtx[source]

    # Each processed letter has 26 possible ciphertext glyph variants.
    # The outline of each variant is the corresponding plaintext letter.
    letter_states: list[list[str]] = []
    separator_states: list[list[str]] = []

    for position_index in range(max_letters):
        letter_variant_names: list[str] = []
        for cipher_ch in ALPHABET:
            variant = f"rt{position_index:04d}_{cipher_ch}"
            plain_ch = maps[position_index][cipher_ch]
            add_variant(variant, letter_glyphs[plain_ch])
            letter_variant_names.append(variant)
        letter_states.append(letter_variant_names)

        separator_variant_names: list[str] = []
        for sep_index, (_, source_glyph) in enumerate(pass_items):
            variant = f"rs{position_index:04d}_{sep_index:02d}"
            add_variant(variant, source_glyph)
            separator_variant_names.append(variant)
        separator_states.append(separator_variant_names)

    # Pass-through variants before the first letter.
    start_separators: list[str] = []
    for sep_index, (_, source_glyph) in enumerate(pass_items):
        variant = f"rsSTART_{sep_index:02d}"
        add_variant(variant, source_glyph)
        start_separators.append(variant)

    # Build OpenType feature code.
    #
    # The visible glyph at each decoded letter also carries the state for
    # the *next* letter.  State-specific separator glyphs let spaces and
    # punctuation preserve that state without advancing the rotors.
    fea: list[str] = [
        "languagesystem DFLT dflt;",
        "feature rlig {",
        f"  sub {trigger_glyph} by {starter};",
    ]

    if pass_items:
        base_sep_class = " ".join(glyph for _, glyph in pass_items)
        start_sep_class = " ".join(start_separators)
        start_carriers = " ".join([starter] + start_separators)

        fea.extend(
            [
                f"  @SEPBASE = [{base_sep_class}];",
                f"  @SEPSTART = [{start_sep_class}];",
                f"  @CSTART = [{start_carriers}];",
                "  lookup STEP0000 {",
                "    sub @CSTART @SEPBASE' by @SEPSTART;",
            ]
        )
        first_context = "@CSTART"
    else:
        fea.append("  lookup STEP0000 {")
        first_context = starter

    for i, ch in enumerate(ALPHABET):
        fea.append(
            f"    sub {first_context} {letter_glyphs[ch]}' "
            f"by {letter_states[0][i]};"
        )
    fea.append("  } STEP0000;")

    for state_index in range(max_letters - 1):
        carriers = letter_states[state_index] + separator_states[state_index]
        fea.append(
            f"  @C{state_index:04d} = [{' '.join(carriers)}];"
        )

        if pass_items:
            fea.append(
                f"  @SEP{state_index:04d} = "
                f"[{' '.join(separator_states[state_index])}];"
            )

        next_step = state_index + 1
        fea.append(f"  lookup STEP{next_step:04d} {{")

        if pass_items:
            fea.append(
                f"    sub @C{state_index:04d} @SEPBASE' "
                f"by @SEP{state_index:04d};"
            )

        for i, ch in enumerate(ALPHABET):
            fea.append(
                f"    sub @C{state_index:04d} {letter_glyphs[ch]}' "
                f"by {letter_states[next_step][i]};"
            )

        fea.append(f"  }} STEP{next_step:04d};")

    fea.append("} rlig;")
    feature_text = "\n".join(fea)

    addOpenTypeFeaturesFromString(font, feature_text)

    family = (
        f"Enigma I Decoder {rotors[0]}-{rotors[1]}-{rotors[2]} "
        f"{positions} R{rings} {reflector}"
    )
    set_font_names(font, family)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    mark_modified_font(font, "enigma-static")
    font.save(output)
    font.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a fixed-key historical Enigma I visual decoder TrueType font."
    )
    parser.add_argument(
        "--key",
        default="I-II-III/AAA/AAA/B",
        help=(
            "ROTORS/POSITIONS/RINGS/REFLECTOR[/PLUGBOARD], e.g. "
            "'I-II-III/AAA/AAA/B/AV BS CG DL FU HZ IN KM OW RX'"
        ),
    )
    parser.add_argument(
        "--base",
        type=Path, default=DEFAULT_BASE,
        help="base TrueType .ttf path (default: bundled Apache-2.0 Roboto 2)",
    )
    parser.add_argument(
        "--output",
        default=Path(__file__).resolve().with_name("enigma-static-font.ttf"),
        help="output .ttf path (default: enigma-static-font.ttf beside this script)",
    )
    parser.add_argument(
        "--max-letters",
        type=int,
        default=512,
        help="maximum decoded A-Z letters per shaping run (default: 512)",
    )
    parser.add_argument(
        "--trigger",
        default="~",
        help="one character typed before ciphertext to initialize the machine",
    )
    parser.add_argument(
        "--passthrough",
        default=DEFAULT_PASSTHROUGH,
        help=(
            "characters allowed between letters without advancing the rotors; "
            "unsupported characters break the state chain"
        ),
    )
    parser.add_argument(
        "--test",
        metavar="TEXT",
        help="also print the software transformation for TEXT using the same key",
    )
    args = parser.parse_args()

    rotors, positions, rings, reflector, plugboard = parse_key(args.key)

    build_font(
        args.base,
        args.output,
        rotors=rotors,
        positions=positions,
        rings=rings,
        reflector=reflector,
        plugboard=plugboard,
        max_letters=args.max_letters,
        trigger=args.trigger,
        passthrough=args.passthrough,
    )

    print(f"Wrote: {args.output}")
    print(
        "Configuration:",
        f"rotors={'-'.join(rotors)}",
        f"positions={positions}",
        f"rings={rings}",
        f"reflector={reflector}",
        f"plugboard={plugboard or '(none)'}",
    )
    print(
        f"Use: type {args.trigger!r} immediately before ciphertext. "
        "The trigger renders invisibly."
    )

    if args.test is not None:
        machine = EnigmaI(rotors, positions, rings, reflector, plugboard)
        print("Software transform:", machine.transform_text(args.test))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(f"Error: {exc}") from None
