# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build a multi-format validator whose rules execute inside OpenType GSUB."""

import argparse
import copy
from collections import deque
import hashlib
from itertools import product
import json
from pathlib import Path
import re
import string
import sys

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.otlLib.builder import (buildCoverage, buildLookup,
                                    buildLigatureSubstSubtable, buildMultipleSubstSubtable)
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib.tables import otTables

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from decoders.shared.font_metadata import DEFAULT_BASE, load_base_font, replace_font_names

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "validator-font.ttf"
REGISTRY = json.loads((HERE / "iban_registry.json").read_text())
MAX_STEPS = 100
MODES = ("iban", "isbn", "gtin", "gln", "sscc", "issn", "orcid", "imei",
         "rf", "ogm", "lei", "isin", "uuid4", "uuid7", "date", "mrz")
SEPARATORS = " -/+"


def expand_pattern(pattern):
    parts = re.findall(r"(\d+)!([nac])", pattern)
    if "".join(f"{count}!{kind}" for count, kind in parts) != pattern:
        raise ValueError(f"Unsupported registry pattern: {pattern}")
    return "".join(kind * int(count) for count, kind in parts)


def append97(remainder, char):
    value = str(ord(char) - 55) if char in string.ascii_uppercase else char
    return (remainder * 10 ** len(value) + int(value)) % 97


def font_identity(font, base_digest):
    """Identify generated computation, outlines, metrics, and optional colors."""
    digest = hashlib.sha256(base_digest)
    for tag in ("GSUB", "glyf", "hmtx", "COLR", "CPAL"):
        if tag in font:
            digest.update(tag.encode("ascii"))
            digest.update(font[tag].compile(font))
    return digest.hexdigest()[:12]


class Compiler:
    def __init__(self, font):
        self.font = font
        self.cmap = font.getBestCmap()
        self.names = []
        self.steps = []
        self.finals = []
        self.states = []
        self.glyph_set = font.getGlyphSet()
        self.display = {}
        self.tokens = {}

    def preserve_value(self, raw):
        """Keep visible outlines independent from invisible computation tokens."""
        for index, original in enumerate(raw):
            name = f"display_{index}"
            if name in self.font["glyf"]:
                raise ValueError(f"Base uses reserved validator glyph name: {name}")
            recording = DecomposingRecordingPen(self.glyph_set)
            self.glyph_set[original].draw(recording)
            pen = TTGlyphPen(None)
            recording.replay(pen)
            self.font["glyf"][name] = pen.glyph()
            self.font["hmtx"][name] = self.font["hmtx"][original]
            self.names.append(name)
            self.display[original] = name
            token = f"token_{index}"
            if token in self.font["glyf"]:
                raise ValueError(f"Base uses reserved validator glyph name: {token}")
            self.font["glyf"][token] = TTGlyphPen(None).glyph()
            self.font["hmtx"][token] = (0, 0)
            self.names.append(token)
            self.tokens[original] = token

    def glyph(self, name, text=""):
        if name in self.font["glyf"]:
            if name not in self.names:
                raise ValueError(f"Base uses reserved validator glyph name: {name}")
            return name
        pen = TTGlyphPen(self.glyph_set)
        x = 0
        for char in text:
            component = self.display.get(self.cmap[ord(char)], self.cmap[ord(char)])
            pen.addComponent(component, (1, 0, 0, 1, x, 0))
            x += self.font["hmtx"][component][0]
        self.font["glyf"][name] = pen.glyph()
        self.font["hmtx"][name] = (x, 0)
        self.names.append(name)
        return name

    def char(self, char):
        original = self.cmap[ord(char)]
        return self.tokens.get(original, original)

    def chars(self, text):
        return " ".join(self.char(c) for c in text)

    def machine(self, name, start, alphabet, transition, accepts):
        """Compile reachable finite states, never enumerate complete inputs."""
        known = {start: self.glyph(f"{name}_0")}
        pending = deque([start])
        while pending:
            state = pending.popleft()
            glyph = known[state]
            self.states.append(glyph)
            for char in alphabet:
                next_state = transition(state, char)
                if next_state is None:
                    target = "checksum_sink"
                else:
                    if next_state not in known:
                        known[next_state] = self.glyph(f"{name}_{len(known)}")
                        pending.append(next_state)
                    target = known[next_state]
                self.steps.append(f"sub {glyph} {self.char(char)} by {target};")
            result = "result_pass" if accepts(state) else "result_checksum"
            self.finals.append(f"sub {glyph} {self.char('?')} by {result};")
        return known[start], known


def build_font(output=DEFAULT_OUTPUT, base=DEFAULT_BASE, *, color=False):
    font = load_base_font(base, output)
    for tag in ("GSUB", "GPOS", "GDEF", "DSIG"):
        if tag in font:
            del font[tag]
    c = Compiler(font)
    # Keep unsupported characters visible until a recognized request consumes them.
    for char in string.printable[:95]:
        if ord(char) not in c.cmap:
            raise ValueError("Base must contain printable ASCII")
    if len({c.char(char) for char in string.printable[:95]}) != 95:
        raise ValueError("Base must use distinct glyphs for printable ASCII characters")
    original_raw = sorted(set(c.cmap.values()) | {".notdef"})
    c.preserve_value(original_raw)
    raw = sorted(c.tokens.values())
    # Draw the verdict symbols directly so custom bases need no symbol coverage.
    for kind in ("pass", "format", "checksum"):
        name = c.glyph("result_" + kind)
        pen = TTGlyphPen(None)
        contours = ([(600, 700), (760, 850), (1060, 500), (1660, 1400),
                     (1840, 1280), (1080, 150)],) if kind == "pass" else (
            [(650, 1250), (820, 1420), (1800, 440), (1630, 270)],
            [(650, 440), (1630, 1420), (1800, 1250), (820, 270)])
        scale = font["head"].unitsPerEm / 2048
        for contour in contours:
            pen.moveTo(tuple(round(v * scale) for v in contour[0]))
            for point in contour[1:]:
                pen.lineTo(tuple(round(v * scale) for v in point))
            pen.closePath()
        font["glyf"][name] = pen.glyph()
        font["hmtx"][name] = (round(2050 * scale), round(600 * scale))
    for verdict in ("pass", "format", "checksum"):
        c.glyph("verdict_" + verdict)
    c.glyph("consumed")
    c.glyph("format_sink")
    c.glyph("checksum_sink")
    for mode in MODES:
        c.glyph(f"mode_{mode}")
    digits, letters = string.digits, string.ascii_uppercase
    alnum = digits + letters
    classes = {
        "N": c.chars(digits), "A": c.chars(letters), "C": c.chars(alnum),
        "X": c.chars(digits + "X"), "H": c.chars(digits + "ABCDEF"),
        "M": c.chars(alnum + "<"), "F": c.chars(letters + "<"),
        "Raw": " ".join(raw), "Sep": c.chars(SEPARATORS),
    }
    fea = ["languagesystem DFLT dflt;", "languagesystem latn dflt;"]
    fea += [f"@{name} = [{values}];" for name, values in classes.items()]
    fea += ["lookup Normalize {", *[f"sub {c.char(ch)} by {c.char(ch.upper())};"
                                     for ch in string.ascii_lowercase], "} Normalize;"]
    # Keep the spelling of each prefix candidate until request boundaries are
    # known. A candidate inside a value must be restored as literal value text.
    candidates, nested = {}, {}
    fea.append("lookup Prefix useExtension {")
    for mode in MODES:
        spellings = product(*[(ch, ch.upper()) if ch.isalpha() else (ch,) for ch in mode + ":"])
        for index, spelling in enumerate(spellings):
            text = "".join(spelling)
            candidate = c.glyph(f"candidate_{mode}_{index}")
            candidates[candidate] = (mode, text)
            nested[candidate] = c.glyph(f"nested_{mode}_{index}")
            fea.append(f"sub {' '.join(c.cmap[ord(ch)] for ch in text)} by {candidate};")
    fea.append("} Prefix;")
    body_originals = [name for name in original_raw if name != c.cmap[ord('?')]]
    body_tokens = [c.tokens[name] for name in body_originals]
    candidate_names = list(candidates)
    nested_names = [nested[name] for name in candidate_names]
    fea += [f"@BoundaryOriginal = [{' '.join(body_originals)}];",
            f"@BoundaryToken = [{' '.join(body_tokens)}];",
            f"@Candidate = [{' '.join(candidate_names)}];",
            f"@Nested = [{' '.join(nested_names)}];",
            "@BoundaryOpen = [@BoundaryToken @Candidate @Nested];",
            # A single forward scan carries the open-request state through the
            # previous glyph. '?' has no transition, so it resets the boundary.
            "lookup Boundary useExtension {",
            "sub @BoundaryOpen @BoundaryOriginal' by @BoundaryToken;",
            "sub @BoundaryOpen @Candidate' by @Nested;",
            "} Boundary;"]
    structure = []
    init = []

    def pattern_rule(mode, pattern, target, separators="space"):
        structure.append((separators, f"sub mode_{mode}' {' '.join(pattern)} {c.char('?')} by {target};"))

    def literal(text):
        return [c.char(ch) for ch in text]

    def positional(mode, pattern, target, separators="space"):
        c.glyph(target)
        pattern_rule(mode, pattern, target, separators)

    # Shared checksum engines.
    mod97, remainder_glyphs = c.machine("mod97", 0, alnum, append97, lambda r: r == 1)
    for parity in (0, 1):
        name = f"weighted{parity}"
        start, _ = c.machine(name, (parity, 0), digits,
                             lambda s, ch: (1 - s[0], (s[1] + int(ch) * (1 if s[0] == 0 else 3)) % 10),
                             lambda s: s[1] == 0)
        for mode, lengths in (("gtin", (8, 12, 13, 14)), ("gln", (13,)), ("sscc", (18,))):
            for length in lengths:
                if (length + 1) % 2 == parity:
                    positional(mode, ["@N"] * length, start)
        if parity == 0:
            positional("isbn", literal("97") + [f"[{c.chars('89')}]"] + ["@N"] * 10,
                       start, "hyphen")

    def luhn_step(s, char):
        parity, even, odd = s
        for digit in (str(ord(char) - 55) if char in letters else char):
            value = int(digit)
            doubled = value * 2 - (9 if value >= 5 else 0)
            even = (even + (doubled if parity == 0 else value)) % 10
            odd = (odd + (value if parity == 0 else doubled)) % 10
            parity = 1 - parity
        return parity, even, odd

    luhn, _ = c.machine("luhn", (0, 0, 0), alnum, luhn_step,
                         lambda s: (s[1] if s[0] == 0 else s[2]) == 0)
    positional("imei", ["@N"] * 15, luhn)
    positional("isin", ["@A"] * 2 + ["@C"] * 9 + ["@N"], luhn)
    positional("lei", ["@C"] * 18 + ["@N"] * 2, mod97)

    issn, _ = c.machine("issn", (0, 0), digits + "X",
                         lambda s, ch: (s[0] + 1, (s[1] + (10 if ch == 'X' else int(ch)) * (8 - s[0])) % 11)
                         if s[0] < 8 else None, lambda s: s == (8, 0))
    positional("issn", ["@N"] * 7 + ["@X"], issn, "hyphen")

    def orcid_step(s, char):
        pos, remainder = s
        if pos < 15 and char in digits:
            return pos + 1, ((remainder + int(char)) * 2) % 11
        if pos == 15 and (10 if char == "X" else int(char)) == (12 - remainder) % 11:
            return 16, 0
        return None

    orcid, _ = c.machine("orcid", (0, 0), digits + "X", orcid_step, lambda s: s[0] == 16)
    positional("orcid", ["@N"] * 15 + ["@X"], orcid, "hyphen")

    def ogm_step(s, char):
        pos, remainder = s
        if pos < 10:
            return pos + 1, append97(remainder, char)
        expected = remainder or 97
        if pos == 10 and int(char) == expected // 10:
            return 11, remainder
        if pos == 11 and int(char) == expected % 10:
            return 12, 0
        return None

    ogm, _ = c.machine("ogm", (0, 0), digits, ogm_step, lambda s: s[0] == 12)
    positional("ogm", ["@N"] * 12, ogm)
    positional("ogm", literal("+++") + ["@N"] * 3 + literal("/") + ["@N"] * 4
               + literal("/") + ["@N"] * 5 + literal("+++"), ogm)

    # Check structure first; save the first four characters as a mod-97 residue.
    # Body checksum runs left-to-right, then the saved prefix is appended numerically.
    prefixes = {}
    for country, entry in REGISTRY["countries"].items():
        target = c.glyph(f"iban_{country}")
        prefixes[target] = country
        pattern = literal(country) + ["@N"] * 2 + ["@" + {"n": "N", "a": "A", "c": "C"}[kind]
                                                   for kind in expand_pattern(entry["bban"])]
        pattern_rule("iban", pattern, target)
    rf = c.glyph("rf_ready")
    prefixes[rf] = "RF"
    for length in range(1, 22):
        pattern_rule("rf", literal("RF") + ["@N"] * 2 + ["@C"] * length, rf)
    for remainder in range(97):
        c.glyph(f"saved_{remainder}")
        init.append(f"sub saved_{remainder} by savedhead_{remainder} {mod97};")
        c.glyph(f"savedhead_{remainder}", "")
        for body, glyph in remainder_glyphs.items():
            result = "result_pass" if (body * 1000000 + remainder) % 97 == 1 else "result_checksum"
            c.finals.insert(0, f"sub savedhead_{remainder} {glyph} {c.char('?')} by {result};")
    capture = []
    for target, country in prefixes.items():
        country_value = int("".join(str(ord(ch) - 55) for ch in country)) * 100
        for check in range(100):
            capture.append(f"sub {target} {c.chars(country + f'{check:02}')} by saved_{(country_value + check) % 97};")

    # UUIDs validate the requested version and the RFC variant nibble.
    structural_start, _ = c.machine("structural", 0, alnum, lambda s, ch: 0, lambda s: True)
    for version in (4, 7):
        uuid = ["@H"] * 8 + literal("-") + ["@H"] * 4 + literal("-") + literal(str(version))
        uuid += ["@H"] * 3 + literal("-") + [f"[{c.chars('89AB')}]"] + ["@H"] * 3
        uuid += literal("-") + ["@H"] * 12
        positional(f"uuid{version}", uuid, structural_start, "none")

    def date_step(s, char):
        phase, value, leap, month = s
        if phase < 4:
            value = (value * 10 + int(char)) % 400
            if phase == 3:
                return 4, 0, value % 4 == 0 and (value % 100 != 0 or value == 0), 0
            return phase + 1, value, False, 0
        if phase == 4:
            return 5, int(char), leap, 0
        if phase == 5:
            month = value * 10 + int(char)
            return (6, 0, leap, month) if 1 <= month <= 12 else None
        if phase == 6:
            return 7, int(char), leap, month
        if phase == 7:
            day = value * 10 + int(char)
            limit = 29 if month == 2 and leap else 28 if month == 2 else 30 if month in (4, 6, 9, 11) else 31
            return (8, 0, False, 0) if 1 <= day <= limit else None
        return None

    date, _ = c.machine("date", (0, 0, False, 0), digits, date_step, lambda s: s[0] == 8)
    positional("date", ["@N"] * 4 + literal("-") + ["@N"] * 2 + literal("-") + ["@N"] * 2, date, "none")
    # Calendar failures are FORMAT, rather than checksum failures.
    # Date uses a separate failure sink to preserve that distinction.
    c.glyph("date_sink")
    c.steps = [rule.replace("by checksum_sink;", "by date_sink;") if rule.startswith("sub date_") else rule
               for rule in c.steps]
    c.finals = [rule.replace("result_checksum", "result_format") if rule.startswith("sub date_") else rule
                for rule in c.finals]

    # TD3 passports: first 44-character line, '|', second 44-character line.
    # Check each field and the composite; passport authenticity is outside scope.
    mrz_pattern = literal("P") + ["@F"] * 43 + literal("|")
    mrz_pattern += ["@M"] * 9 + ["@N"] + ["@F"] * 3 + ["@N"] * 7
    mrz_pattern += [f"[{c.chars('MF<')}]"] + ["@N"] * 7 + ["@M"] * 14 + ["@N"] * 2

    def mrz_step(s, char):
        pos, field, composite, weight_pos = s
        if pos >= 89:
            return None
        if pos < 45:
            return pos + 1, 0, 0, 0
        index = pos - 45
        value = int(char) if char in digits else ord(char) - 55 if char in letters else 0
        ranges = ((0, 9), (13, 19), (21, 27), (28, 42))
        checks = {9: 0, 19: 13, 27: 21, 42: 28}
        in_composite = index <= 9 or 13 <= index <= 19 or 21 <= index <= 42
        if index == 43:
            return (89, 0, 0, 0) if value == composite else None
        if index in checks:
            if value != field:
                return None
            field = 0
        else:
            for left, right in ranges:
                if left <= index < right:
                    field = (field + value * (7, 3, 1)[(index - left) % 3]) % 10
                    break
        if in_composite:
            composite = (composite + value * (7, 3, 1)[weight_pos % 3]) % 10
            weight_pos += 1
        return pos + 1, field, composite, weight_pos

    mrz, _ = c.machine("mrz", (0, 0, 0, 0), alnum + "<|", mrz_step, lambda s: s[0] == 89)
    positional("mrz", mrz_pattern, mrz, "none")
    pattern_rule("mrz", mrz_pattern[:-16] + literal("<" * 15) + ["@N"], mrz, "none")

    visible = set(c.display.values()) | set(original_raw) | {"result_pass", "result_format", "result_checksum"}
    computational = set(raw) | (set(c.names) - visible)
    active = computational - {c.char(ch) for ch in SEPARATORS} - {"consumed"}
    fea += [f"@Visible = [{' '.join(sorted(visible))}];",
            f"@Computational = [{' '.join(sorted(computational))}];",
            f"@Active = [{' '.join(sorted(active))}];",
            f"@Keep = [@Active {c.chars('-/+')}];",
            f"@KeepHyphen = [@Active {c.chars('/+')}];",
            "@KeepAll = [@Active @Sep];",
            "table GDEF { GlyphClassDef @Visible, , @Computational, ; } GDEF;"]
    # Structure lookups skip display copies, with format-specific separators.
    for policy in ("space", "hyphen", "none"):
        rules = [rule for kind, rule in structure if kind == policy]
        fea.append(f"lookup Structure_{policy} useExtension {{")
        mark_set = {"space": "Keep", "hyphen": "KeepHyphen", "none": "KeepAll"}[policy]
        fea.append(f"lookupflag IgnoreBaseGlyphs UseMarkFilteringSet @{mark_set};")
        fea += rules + [f"}} Structure_{policy};"]
    # Collapse recognized but malformed requests; do not produce a success on a prefix.
    fea += ["lookup BadStart {", *[f"sub mode_{mode} by format_sink;" for mode in MODES], "} BadStart;"]
    for sink in ("format_sink", "checksum_sink", "date_sink"):
        c.steps += [f"sub {sink} {glyph} by {sink};" for glyph in raw if glyph != c.char('?')]
    c.finals += [f"sub format_sink {c.char('?')} by result_format;",
                 f"sub checksum_sink {c.char('?')} by result_checksum;",
                 f"sub date_sink {c.char('?')} by result_format;"]
    fea += ["lookup Clean { sub @Computational by NULL; } Clean;",
            "feature liga { lookup Prefix; lookup Boundary; lookup Normalize;",
            "lookup Structure_space; lookup Structure_hyphen; lookup Structure_none;",
            "lookup BadStart; lookup Clean; } liga;"]
    font.setGlyphOrder(list(dict.fromkeys(font.getGlyphOrder() + c.names)))
    if len(font.getGlyphOrder()) >= 65535:
        raise ValueError("Validator exceeds OpenType glyph limit")
    addOpenTypeFeaturesFromString(font, "\n".join(fea))
    gsub = font["GSUB"].table
    feature = gsub.FeatureList.FeatureRecord[0].Feature
    clean_index = feature.LookupListIndex.pop()

    def append_lookup(lookup):
        index = len(gsub.LookupList.Lookup)
        gsub.LookupList.Lookup.append(lookup)
        gsub.LookupList.LookupCount += 1
        return index

    # This set omits visible copies, consumed tokens, and optional separators.
    mark_sets = font["GDEF"].table.MarkGlyphSetsDef.Coverage
    arithmetic_set = next((i for i, coverage in enumerate(mark_sets) if set(coverage.glyphs) == active), None)
    if arithmetic_set is None:
        arithmetic_set = len(mark_sets)
        mark_sets.append(buildCoverage(active, font.getReverseGlyphMap()))
        font["GDEF"].table.MarkGlyphSetsDef.MarkSetCount = len(mark_sets)

    def ligatures(rules):
        # Direct table construction avoids feaLib's quadratic overlap checks.
        # Small subtables also keep their internal 16-bit offsets in range.
        mapping = {}
        for rule in rules:
            before, after = rule[4:-1].split(" by ")
            mapping[tuple(before.split())] = after
        items = sorted(mapping.items())
        subtables = [buildLigatureSubstSubtable(dict(items[i:i + 1200]))
                     for i in range(0, len(items), 1200)]
        return append_lookup(buildLookup(subtables, flags=2, markFilterSet=arithmetic_set, table="GSUB", extension=True))

    # Restore protected value characters, expand nested prefixes literally, and
    # turn only candidates outside a value into active validator mode glyphs.
    resolve = {token: [original] for original, token in c.tokens.items()}
    for candidate, (mode, text) in candidates.items():
        resolve[candidate] = [f"mode_{mode}"]
        resolve[nested[candidate]] = [c.cmap[ord(ch)] for ch in text]
    resolve_index = append_lookup(buildLookup([buildMultipleSubstSubtable(resolve)], table="GSUB", extension=True))
    mirror = {original: [c.display[original], c.tokens[original]] for original in original_raw}
    # Keep ordinary question marks visible. A completed request replaces only
    # its own terminator: Finish writes a verdict beside this visible copy.
    question_display = c.display[c.cmap[ord('?')]]
    mirror[c.cmap[ord('?')]] = [c.char('?'), question_display]
    mirror_index = append_lookup(buildLookup([buildMultipleSubstSubtable(mirror)], table="GSUB"))
    feature.LookupListIndex[2:2] = [resolve_index, mirror_index]

    capture_index = ligatures(capture)
    init_mapping = {}
    for rule in init:
        before, after = rule[4:-1].split(" by ")
        init_mapping[before] = after.split()
    init_index = append_lookup(buildLookup([buildMultipleSubstSubtable(init_mapping)], table="GSUB"))
    # Reuse Step through small calling lookups, rather than duplicating its tables.
    step_index = ligatures(c.steps)
    state_names = c.states + ["format_sink", "checksum_sink", "date_sink"]
    wrapper = otTables.ContextSubst()
    wrapper.Format = 3
    wrapper.Coverage = [buildCoverage(state_names, font.getReverseGlyphMap())]
    wrapper.GlyphCount = 1
    record = otTables.SubstLookupRecord()
    record.SequenceIndex, record.LookupListIndex = 0, step_index
    wrapper.SubstLookupRecord, wrapper.SubstCount = [record], 1
    wrapper_indices = [append_lookup(buildLookup([copy.deepcopy(wrapper)], flags=2,
                       markFilterSet=arithmetic_set, table="GSUB")) for _ in range(MAX_STEPS)]
    # Write the verdict at the '?' position so it follows the preserved value.
    # Clear matched state tokens without moving the visible copies between them.
    from fontTools.otlLib.builder import buildSingleSubstSubtable
    clear_index = append_lookup(buildLookup([buildSingleSubstSubtable({name: "consumed" for name in active})], table="GSUB"))
    verdict_indices = {result: append_lookup(buildLookup([buildSingleSubstSubtable({c.char('?'): result.replace('result_', 'verdict_')})], table="GSUB"))
                       for result in ("result_pass", "result_format", "result_checksum")}
    finish_tables = []
    finish_groups = {}
    prefix_states, body_states = set(), set()
    # Successful IBAN/RF pairs are sparse. A shared fallback handles all others.
    # Group generic states by verdict to avoid thousands of extension headers.
    for rule in c.finals:
        before, result = rule[4:-1].split(" by ")
        inputs = before.split()
        if len(inputs) == 3:
            prefix_states.add(inputs[0])
            body_states.add(inputs[1])
            if result == "result_pass":
                finish_groups[(result, inputs[0])] = [{inputs[0]}, {inputs[1]}, {inputs[2]}]
        else:
            group = finish_groups.setdefault((result, "generic"), [set(), {c.char('?')}])
            group[0].add(inputs[0])
    finish_groups[("result_checksum", "prefix_fallback")] = [prefix_states, body_states, {c.char('?')}]
    for (result, _), inputs in finish_groups.items():
        table = otTables.ContextSubst()
        table.Format = 3
        table.Coverage = [buildCoverage(names, font.getReverseGlyphMap()) for names in inputs]
        table.GlyphCount = len(inputs)
        records = []
        for index in reversed(range(len(inputs))):
            record = otTables.SubstLookupRecord()
            record.SequenceIndex = index
            record.LookupListIndex = verdict_indices[result] if index == len(inputs) - 1 else clear_index
            records.append(record)
        table.SubstLookupRecord, table.SubstCount = records, len(records)
        finish_tables.append(table)
    finish_index = append_lookup(buildLookup(finish_tables, flags=2, markFilterSet=arithmetic_set, table="GSUB", extension=True))
    render_index = append_lookup(buildLookup([buildLigatureSubstSubtable({
        (f"verdict_{kind}", question_display): f"result_{kind}"
        for kind in ("pass", "format", "checksum")})], table="GSUB"))
    feature.LookupListIndex += [capture_index, init_index] + wrapper_indices
    # Cleanup removes computation, while the final render keeps the verdict.
    feature.LookupListIndex += [finish_index, render_index, clean_index]
    feature.LookupCount = len(feature.LookupListIndex)
    # Shapers apply feature lookups in LookupList order and deduplicate indices.
    # Put every top-level pass in execution order, then remap nested references.
    execution = feature.LookupListIndex
    order = execution + [i for i in range(gsub.LookupList.LookupCount) if i not in execution]
    remap = {old: new for new, old in enumerate(order)}
    gsub.LookupList.Lookup = [gsub.LookupList.Lookup[i] for i in order]
    visited = set()

    def remap_nested(table):
        if id(table) in visited:
            return
        visited.add(id(table))
        if isinstance(table, otTables.SubstLookupRecord):
            table.LookupListIndex = remap[table.LookupListIndex]
        elif isinstance(table, (list, tuple)):
            for item in table:
                remap_nested(item)
        elif hasattr(table, "__dict__"):
            for item in vars(table).values():
                remap_nested(item)

    remap_nested(gsub.LookupList.Lookup)
    feature.LookupListIndex = [remap[i] for i in execution]
    if color:
        layers = {}
        for kind in ("pass", "format", "checksum"):
            result = "result_" + kind
            layer = "color_" + result
            c.glyph(layer)
            font["glyf"][layer] = copy.deepcopy(font["glyf"][result])
            font["hmtx"][layer] = font["hmtx"][result]
            layers[result] = [(layer, 0 if kind == "pass" else 1)]
        font.setGlyphOrder(list(dict.fromkeys(font.getGlyphOrder() + c.names)))
        if len(font.getGlyphOrder()) >= 65535:
            raise ValueError("Validator exceeds OpenType glyph limit")
        # COLR v0 adds solid fills while the base outlines provide a mono fallback.
        font["COLR"] = buildCOLR(layers, version=0, glyphMap=font.getReverseGlyphMap())
        font["CPAL"] = buildCPAL([[(22 / 255, 163 / 255, 74 / 255, 1),
                                   (220 / 255, 38 / 255, 38 / 255, 1)]])
    identity = font_identity(font, font._decoder_base_digest)
    family = "Computational Validator" + (" Color" if color else "")
    replace_font_names(font, {1: family, 2: "Regular",
                             3: family + " 1.0;" + identity, 4: family + " Regular",
                             6: "ComputationalValidator" + ("Color" if color else "") + "-" + identity,
                             16: family, 17: "Regular"})
    notices = {0: "Copyright 2026 Michael Brackx. Validator modifications.",
               10: "OpenType validator rules added by Michael Brackx (2026). "
                   "The base font's attribution and license are retained."}
    for name_id, notice in notices.items():
        existing = font["name"].getDebugName(name_id) or ""
        records = [record for record in font["name"].names if record.nameID == name_id]
        for record in records:
            record.string = (record.toUnicode().rstrip() + "\n" + notice).encode(record.getEncoding(), errors="replace")
        if not any(record.platformID == 3 and record.platEncID == 1 and record.langID == 0x409 for record in records):
            font["name"].setName((existing + "\n" + notice).lstrip(), name_id, 3, 1, 0x409)
    font.save(output)
    return len(c.names)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--color", action="store_true",
                        help="Generate green checks and red crosses using COLR/CPAL color tables")
    args = parser.parse_args()
    try:
        count = build_font(args.output, args.base, color=args.color)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(f"Built {args.output} ({count} computational glyphs)")


if __name__ == "__main__":
    main()
