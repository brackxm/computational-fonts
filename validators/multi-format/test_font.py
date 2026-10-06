# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Independent known-vector and mutation checks against actual HarfBuzz shaping."""

import datetime
import importlib.util
import json
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("validator_builder", HERE / "build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
SHAPER = shutil.which("hb-shape")
FIRST_MRZ = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
SECOND_MRZ = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
EXAMPLES = {
    "iban": "BE68539007547034", "isbn": "9780306406157", "gtin": "4006381333931",
    "gln": "9506000140445", "sscc": "106141411234567897", "issn": "0317-8471",
    "orcid": "0000-0002-1825-0097", "imei": "490154203237518", "rf": "RF541234",
    "ogm": "+++123/4567/89002+++", "lei": "5493001KJTIIGC8Y1R12", "isin": "US0378331005",
    "uuid4": "550e8400-e29b-41d4-a716-446655440000",
    "uuid7": "019069c9-7c48-7cc2-9f00-0b58ae76e2f4", "date": "2024-02-29",
    "mrz": FIRST_MRZ + "|" + SECOND_MRZ,
}


def numeric(text):
    return int("".join(str(ord(c) - 55) if c.isalpha() else c for c in text))


def gs1_check(body):
    return str((-sum(int(c) * (3 if i % 2 == 0 else 1)
                     for i, c in enumerate(reversed(body)))) % 10)


@unittest.skipUnless(SHAPER, "Install hb-shape to check computational font results")
class FontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.fresh = Path(cls.temp.name) / "fresh.ttf"
        cls.color = Path(cls.temp.name) / "color.ttf"
        for output, options in ((cls.fresh, []), (cls.color, ["--color"])):
            result = subprocess.run([sys.executable, str(HERE / "build.py"), "--output", str(output), *options],
                                    capture_output=True, text=True, timeout=180)
            if result.returncode:
                raise AssertionError(result.stderr)
        cls.paths = (HERE / "validator-font.ttf", cls.fresh, cls.color)
        with TTFont(builder.DEFAULT_BASE) as base:
            cmap = base.getBestCmap()
            originals = sorted(set(cmap.values()) | {".notdef"})
            cls.display_names = {glyph: f"display_{index}" for index, glyph in enumerate(originals)}
            cls.char_names = {char: cls.display_names[glyph] for char, glyph in cmap.items()}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def shape(self, text, font=None, features="liga=1"):
        result = subprocess.run([SHAPER, str(font or self.fresh), text, "--output-format=json",
                                 f"--features={features}"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [glyph["g"] for glyph in json.loads(result.stdout)]

    def expect(self, text, verdict, font=None):
        shaped = self.shape(text, font)
        visible = re.sub(r"(?i)(?:" + "|".join(builder.MODES) + r"):([^?]*)\?",
                         lambda match: match[1], text)
        expected = [self.char_names.get(ord(char), self.display_names[".notdef"]) for char in visible]
        self.assertEqual([name for name in shaped if name.startswith("display_")], expected, text)
        self.assertEqual([name for name in shaped if not name.startswith("display_")], ["result_" + verdict], text)
        if text.count("?") == 1 and text.endswith("?"):
            self.assertEqual(shaped[-1], "result_" + verdict, text)

    def test_known_vectors_bundled_and_fresh(self):
        for path in self.paths:
            for mode, value in EXAMPLES.items():
                with self.subTest(font=path.name, mode=mode):
                    self.expect(f"{mode}:{value}?", "pass", path)

    def test_every_iban_registry_example(self):
        for country, record in builder.REGISTRY["countries"].items():
            value = record["example"]
            with self.subTest(country=country):
                self.assertEqual(numeric(value[4:] + value[:4]) % 97, 1)
                self.expect("iban:" + value + "?", "pass")
                altered = value[:2] + f"{(int(value[2:4]) + 1) % 100:02}" + value[4:]
                self.expect("iban:" + altered + "?", "checksum")
                self.expect("iban:" + value[:-1] + "?", "format")

    def test_checksum_mutations(self):
        for mode in ("isbn", "gtin", "gln", "sscc", "issn", "orcid", "imei", "ogm", "lei", "isin"):
            value = re.sub(r"[ /+\-]", "", EXAMPLES[mode])
            altered = value[:-1] + str((int(value[-1]) + 1) % 10)
            self.expect(f"{mode}:{altered}?", "checksum")
        self.expect("rf:RF551234?", "checksum")
        self.expect("mrz:" + FIRST_MRZ + "|" + SECOND_MRZ[:-1] + "1?", "checksum")

    def test_lengths_characters_and_separators(self):
        invalid = ("iban:ZZ68539007547034?", "iban:BE6853900754703A?",
                   "iban:BE68/539007547034?", "isbn:9770306406158?", "isbn:978030640615?",
                   "gtin:40063813339?", "gln:40063813?", "sscc:4006381333931?",
                   "issn:X3178471?", "orcid:X000000218250097?", "imei:49015420323751A?",
                   "rf:BE68539007547034?", "rf:RF54?", "rf:RF54" + "1" * 22 + "?",
                   "ogm:+++123/4567/89002++?", "lei:5493001KJTIIGC8Y1R1X?", "isin:US037833100X?",
                   "uuid4:550e8400-e29b-71d4-a716-446655440000?",
                   "uuid7:019069c9-7c48-7cc2-7f00-0b58ae76e2f4?",
                   "uuid4:550e8400e29b41d4a716446655440000?",
                   "date:2025-02-29?", "date:2024-04-31?", "date:2024-00-10?",
                   "date:2024-12-00?", "date:20240229?", "date:2024 -02-29?",
                   "mrz:" + FIRST_MRZ + SECOND_MRZ + "?", "iban:BE68☃539007547034?")
        for text in invalid:
            with self.subTest(text=text):
                self.expect(text, "format")
        self.expect("IBAN:be68 5390 0754 7034?", "pass")
        self.expect("isbn:978-0-306-40615-7?", "pass")
        self.expect("ogm:123456789002?", "pass")

    def test_x_check_digits(self):
        self.expect("issn:2434-561X?", "pass")
        # Independent ORCID reference calculation, search a body ending in X.
        for body in (f"{i:015}" for i in range(20)):
            total = 0
            for digit in body:
                total = (total + int(digit)) * 2
            if (12 - total % 11) % 11 == 10:
                self.expect("orcid:" + body + "X?", "pass")
                break
        else:
            self.fail("No X fixture")

    def test_generated_checksums(self):
        rng = random.Random(1825)
        for length in (8, 12, 13, 14):
            for _ in range(8):
                body = "".join(str(rng.randrange(10)) for _ in range(length - 1))
                self.expect("gtin:" + body + gs1_check(body) + "?", "pass")
        for _ in range(12):
            body = "".join(rng.choice("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(18))
            check = 98 - numeric(body + "00") % 97
            self.expect(f"lei:{body}{check:02}?", "pass")
            body = "".join(rng.choice("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(rng.randrange(1, 22)))
            check = 98 - numeric(body + "RF00") % 97
            self.expect(f"rf:RF{check:02}{body}?", "pass")
            body = "US" + "".join(rng.choice("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(9))
            expanded = str(numeric(body))
            total = sum((int(ch) * 2 // 10 + int(ch) * 2 % 10) if i % 2 == 0 else int(ch)
                        for i, ch in enumerate(reversed(expanded)))
            self.expect(f"isin:{body}{(-total) % 10}?", "pass")
        self.expect("ogm:000000009797?", "pass")

    def test_calendar_centuries(self):
        for year in (1600, 1700, 1800, 1900, 2000, 2100, 2400, 9999):
            try:
                datetime.date(year, 2, 29)
                expected = "pass"
            except ValueError:
                expected = "format"
            self.expect(f"date:{year}-02-29?", expected)

    def test_mrz_field_checks_and_optional_data(self):
        for index in (9, 19, 27, 42, 43):
            altered = SECOND_MRZ[:index] + str((int(SECOND_MRZ[index]) + 1) % 10) + SECOND_MRZ[index + 1:]
            self.expect("mrz:" + FIRST_MRZ + "|" + altered + "?", "checksum")

        def composite(line):
            fields = line[:10] + line[13:20] + line[21:43]
            return str(sum((int(ch) if ch.isdigit() else ord(ch) - 55 if ch.isalpha() else 0)
                           * (7, 3, 1)[i % 3] for i, ch in enumerate(fields)) % 10)

        for check in ("<", "0"):
            line = SECOND_MRZ[:28] + "<" * 14 + check
            self.expect("mrz:" + FIRST_MRZ + "|" + line + composite(line) + "?", "pass")
        line = SECOND_MRZ[:28] + "A" + "<" * 14
        self.expect("mrz:" + FIRST_MRZ + "|" + line + composite(line) + "?", "format")

    def test_no_premature_success(self):
        for mode, value in EXAMPLES.items():
            text = f"{mode}:{value}"
            self.assertNotIn("result_pass", self.shape(text))
            # Data inside the request still invalidates the structure.
            self.expect(text + "!?", "format")
        self.assertNotIn("result_pass", self.shape("unknown:4006381333931?"))
        self.assertNotIn("result_pass", self.shape("iban:" + "1" * 150 + "?"))
        self.assertNotIn("result_pass", self.shape("gtin:4006381333931?", features="liga=0"))

    def assert_rendered(self, text, parts, font=None):
        expected = []
        for part in parts:
            if isinstance(part, tuple):
                expected.append("result_" + part[0])
            else:
                expected += [self.char_names.get(ord(char), self.display_names[".notdef"]) for char in part]
        self.assertEqual(self.shape(text, font), expected, text)

    def test_surrounding_text_is_independent(self):
        for path in self.paths:
            for mode, value in EXAMPLES.items():
                request = f"{mode}:{value}?"
                for before, after in (("0", "0"), ("/", "+---"), ("Before: ", " and after."),
                                      ("Why? ", "??")):
                    self.assert_rendered(before + request + after, [before, value, ("pass",), after], path)
            self.assert_rendered("Check? unknown:4006381333931?", ["Check? unknown:4006381333931?"], path)
            self.assert_rendered("Value: date:2025-02-29?+0", ["Value: 2025-02-29", ("format",), "+0"], path)
            self.assert_rendered("Ref: iban:BE69539007547034? end?",
                                 ["Ref: BE69539007547034", ("checksum",), " end?"], path)

    def test_multiple_requests_are_independent(self):
        for path in self.paths:
            self.assert_rendered("gtin:4006381333931?gtin:4006381333931?",
                                 ["4006381333931", ("pass",), "4006381333931", ("pass",)], path)
            self.assert_rendered("A date:2024-02-29? + date:2025-02-29? / iban:BE68539007547034? end?",
                                 ["A 2024-02-29", ("pass",), " + 2025-02-29", ("format",),
                                  " / BE68539007547034", ("pass",), " end?"], path)
            self.assert_rendered("date:bad? date:2024-02-29?",
                                 ["bad", ("format",), " 2024-02-29", ("pass",)], path)

    def test_nested_prefixes_are_literal_value_text(self):
        for path in self.paths:
            for outer in builder.MODES:
                self.assert_rendered(f"{outer}:dAtE:2024-02-29?",
                                     ["dAtE:2024-02-29", ("format",)], path)
            for inner, value in EXAMPLES.items():
                literal = inner.upper() + ":" + value
                self.assert_rendered("gtin:" + literal + "?", [literal, ("format",)], path)
            self.assert_rendered("gtin:date:gtin:4006381333931?",
                                 ["date:gtin:4006381333931", ("format",)], path)
            self.assert_rendered("gtin:date:2024-02-29", ["date:2024-02-29"], path)
            self.assert_rendered("gtin:date:2024-02-29?date:2024-02-29?",
                                 ["date:2024-02-29", ("format",), "2024-02-29", ("pass",)], path)
            self.assert_rendered("Before? gtin:bad date:2024-02-29? + gtin:4006381333931? After?",
                                 ["Before? bad date:2024-02-29", ("format",), " + 4006381333931",
                                  ("pass",), " After?"], path)

    def test_original_case_and_separators_remain_visible(self):
        for path in self.paths:
            self.expect("iBaN:be68 5390 0754 7034?", "pass", path)
            self.expect("isbn:978-0-306-40615-7?", "pass", path)
            self.expect("ogm:+++123/4567/89002+++?", "pass", path)
            self.expect("uuid4:550e8400-e29b-41d4-a716-446655440000?", "pass", path)
            self.expect("date:2025-02-29?", "format", path)

    def test_names_license_and_tables(self):
        with TTFont(self.fresh) as font:
            self.assertIn("Computational Validator", font["name"].getDebugName(1))
            self.assertIn("Google", font["name"].getDebugName(0))
            self.assertIn("Michael Brackx", font["name"].getDebugName(0))
            self.assertIn("Apache", font["name"].getDebugName(13))
            self.assertLess(len(font.getGlyphOrder()), 65535)
            self.assertIn("GSUB", font)

    def test_color_symbols_and_monochrome_fallback(self):
        with TTFont(self.fresh) as mono, TTFont(self.color) as color:
            self.assertNotIn("COLR", mono)
            self.assertNotIn("CPAL", mono)
            self.assertEqual(color["COLR"].version, 0)
            self.assertEqual(set(color["COLR"].ColorLayers),
                             {"result_pass", "result_format", "result_checksum"})
            palette = color["CPAL"].palettes[0]
            self.assertEqual([(entry.red, entry.green, entry.blue, entry.alpha) for entry in palette],
                             [(22, 163, 74, 255), (220, 38, 38, 255)])
            for kind in ("pass", "format", "checksum"):
                result = "result_" + kind
                layer, = color["COLR"].ColorLayers[result]
                self.assertEqual(layer.colorID, 0 if kind == "pass" else 1)
                self.assertEqual(color["glyf"][layer.name].compile(color["glyf"]),
                                 mono["glyf"][result].compile(mono["glyf"]))
                self.assertEqual(color["glyf"][result].compile(color["glyf"]),
                                 mono["glyf"][result].compile(mono["glyf"]))
                self.assertEqual(color["hmtx"][layer.name], mono["hmtx"][result])
            for name_id in (1, 3, 6):
                self.assertNotEqual(mono["name"].getDebugName(name_id), color["name"].getDebugName(name_id))
        for text, verdict in (("iban:BE69539007547034?", "checksum"),
                              ("date:2025-02-29?", "format")):
            self.expect(text, verdict, self.color)


class BuilderTests(unittest.TestCase):
    def test_identity_changes_with_outline_or_metrics(self):
        with TTFont(HERE / "validator-font.ttf") as font:
            base_digest = b"review-regression"
            identity = builder.font_identity(font, base_digest)
            glyph = font["glyf"]["result_pass"]
            glyph.coordinates[0] = (glyph.coordinates[0][0] + 20, glyph.coordinates[0][1])
            changed_outline = builder.font_identity(font, base_digest)
            self.assertNotEqual(identity, changed_outline)
            width, bearing = font["hmtx"]["result_pass"]
            font["hmtx"]["result_pass"] = (width + 20, bearing)
            self.assertNotEqual(changed_outline, builder.font_identity(font, base_digest))

    def test_base_overwrite_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Output must differ"):
            builder.build_font(builder.DEFAULT_BASE, builder.DEFAULT_BASE)

    def test_registry_patterns_and_lengths(self):
        self.assertEqual(len(builder.REGISTRY["countries"]), 89)
        for record in builder.REGISTRY["countries"].values():
            self.assertEqual(len(builder.expand_pattern(record["bban"])) + 4, len(record["example"]))


if __name__ == "__main__":
    unittest.main()
