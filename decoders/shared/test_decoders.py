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

"""Decoder regressions: python3 -m unittest discover -s decoders -v.

Requires FontTools. Shaping checks additionally require HarfBuzz's hb-shape.
Fresh builds use a small original fixture font and the bundled Roboto base.
"""

import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import shutil
import string
import subprocess
import sys
import tempfile
import unittest

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parent.parent
SHAPER = shutil.which("hb-shape")
NEEDS_SHAPER = unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for font shaping checks")
PLUGBOARD = "AV BS CG DL FU HZ IN KM OW RX"
LORENZ_CIPHER = (
    "CH58USOQWRTRIMW/OGXR3Q5P//GDVYO3I4TWE3VTVISYIAGQ5H3ULPI4PASLA4"
    "JOINJRK3AMT485KRL3D3VFIXZGDQFKYQA"
)
LORENZ_PLAIN = (
    "HELLO CYBERCHEF USER, IF YOU CAN READ THIS, YOU HAVE RECEIVED A "
    "MESSAGE SUCCESSFULLY."
)
LORENZ_STARTS = "20,32,9,51,47,2,18,26,6,29,16,4"
EXAMPLES = {
    "morse": (".... . .-.. .-.. --- / .-- --- .-. .-.. -..", "HELLO WORLD"),
    "playfair-static": ("BMODZBXDNABEKUDMUIXMMOUVIF", "HIDETHEGOLDINTHETREXESTUMP"),
    "vigenere-static": ("LXFOPVEFRNHR", "ATTACKATDAWN"),
    "vigenere-dynamic": ("LEMON~LXFOPVEFRNHR", "ATTACKATDAWN"),
    "enigma-static": ("~BDZGO", "AAAAA"),
    "enigma-dynamic": ("V-II-IV/QWE/BDF~SXWQHHBR", "ENIGMART"),
    "lorenz-static": ("~" + LORENZ_CIPHER, LORENZ_PLAIN),
}
BUILD_ARGS = {
    "morse": [],
    "playfair-static": ["--key", "PLAYFAIR EXAMPLE"],
    "vigenere-static": ["--key", "LEMON"],
    "vigenere-dynamic": ["--max-key", "6", "--max-text", "24"],
    "enigma-static": ["--max-letters", "16"],
    "enigma-dynamic": ["--plugboard", PLUGBOARD, "--max-text", "8"],
    "lorenz-static": ["--model", "SZ42a", "--preset", "BREAM",
                      "--starts", LORENZ_STARTS, "--max-symbols", "128"],
}
# Destination checks need only a small font; shaping checks use the limits above.
SMALL_LIMITS = {
    "morse": [],
    "playfair-static": [], "vigenere-static": [],
    "vigenere-dynamic": ["--max-key", "2", "--max-text", "2"],
    "enigma-static": ["--max-letters", "2"],
    "enigma-dynamic": ["--max-text", "1"],
    "lorenz-static": ["--max-symbols", "2"],
}


def load_builder(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / name / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDERS = {name: load_builder(name) for name in EXAMPLES}


def fixture_font(path):
    """Original geometric outlines with unique metrics and stale preferred names."""
    chars = string.ascii_letters + string.digits + string.punctuation + " £É"
    cmap = {ord(ch): f"uni{ord(ch):04X}" for ch in chars}
    glyphs, metrics = {}, {}
    for code, name in [(0, ".notdef"), *cmap.items()]:
        pen = TTGlyphPen(None)
        if code != ord(" "):
            pen.moveTo((10, 0))
            pen.lineTo((200 + code, 0))
            pen.lineTo((40 + code, 500 + code))
            pen.closePath()
        glyphs[name] = pen.glyph()
        metrics[name] = (500 + code, 10 if code != ord(" ") else 0)
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder([".notdef", *cmap.values()])
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "Decoder Test Base", "styleName": "Regular",
                            "fullName": "Decoder Test Base", "psName": "DecoderTestBase",
                            "copyright": "Copyright 2026 Fixture Author",
                            "licenseDescription": "Fixture license: preserved verbatim",
                            "licenseInfoURL": "https://example.invalid/fixture-license",
                            16: "Stale Preferred Family", 17: "Stale Style"})
    for name_id in (1, 2, 3, 4, 6, 16, 17):
        builder.font["name"].setName(f"StaleLocalizedName{name_id}", name_id, 3, 1, 0x411)
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.setupMaxp()
    builder.save(path)


def run_build(script, base, arguments, cwd):
    base_args = ["--base", str(base)] if base is not None else []
    result = subprocess.run([sys.executable, str(script), *base_args, *arguments],
                            cwd=cwd, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise AssertionError(f"{script}: exit {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result


def shape(font, text):
    result = subprocess.run([SHAPER, str(font), text, "--output-format=json", "--no-glyph-names",
                             "--direction=ltr", "--script=latn",
                             "--features=rlig=1,liga=1,clig=1,kern=0"],
                            capture_output=True, text=True, check=True, timeout=15)
    return json.loads(result.stdout)


def display(font, glyphs):
    """Read actual source outlines/components, rather than decoder glyph names."""
    cmap = {name: chr(code) for code, name in font.getBestCmap().items()
            if 32 <= code < 127 or code in (163, 201)}

    def character(name):
        if name == ".notdef":
            raise AssertionError("Shaping returned a missing glyph")
        glyph = font["glyf"][name]
        advance = font["hmtx"].metrics[name][0]
        if not glyph.numberOfContours:
            if not advance:
                return ""
            if advance != font["hmtx"].metrics[font.getBestCmap()[32]][0]:
                raise AssertionError(f"Unexpected advancing empty glyph: {name}")
            return " "
        if name in cmap:
            return cmap[name]
        if glyph.isComposite():
            offset = 0
            for component in glyph.components:
                if (component.x, component.y) != (offset, 0):
                    raise AssertionError(f"Misplaced plaintext component in {name}")
                if getattr(component, "transform", [[1, 0], [0, 1]]) != [[1, 0], [0, 1]]:
                    raise AssertionError(f"Scaled plaintext component in {name}")
                offset += font["hmtx"].metrics[component.glyphName][0]
            return "".join(character(component.glyphName) for component in glyph.components)
        raise AssertionError(f"Unresolved visible state glyph: {name}")

    return "".join(character(font.getGlyphName(glyph["g"])) for glyph in glyphs)


class BaseFontTests(unittest.TestCase):
    def test_morse_rejects_missing_characters_and_aliased_signals(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.ttf"
            output = Path(directory) / "out.ttf"
            fixture_font(base)
            for missing, marker, alias, error in (
                ("É", None, None, "missing required characters"),
                (None, ".", "-", "glyph must be distinct"),
                (None, " ", "/", "glyph must be distinct"),
            ):
                invalid = Path(directory) / "invalid.ttf"
                with TTFont(base) as font:
                    for table in font["cmap"].tables:
                        if table.isUnicode():
                            if missing:
                                table.cmap.pop(ord(missing), None)
                            else:
                                table.cmap[ord(marker)] = table.cmap[ord(alias)]
                    font.save(invalid)
                with self.subTest(missing=missing, marker=marker), self.assertRaisesRegex(ValueError, error):
                    BUILDERS["morse"].build_font(invalid, output)
                self.assertFalse(output.exists())

    def test_pinned_roboto_base_integrity_and_coverage(self):
        directory = ROOT / "shared" / "fonts" / "roboto-2"
        path = directory / "Roboto-Regular.ttf"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         "56a45233d29f11b4dfb86d248e921939d115778f87325e7ae8cc108383d6664d")
        self.assertEqual(hashlib.sha256((directory / "LICENSE").read_bytes()).hexdigest(),
                         "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4")
        with TTFont(path) as font:
            self.assertIn("glyf", font)
            self.assertIn("Apache License, Version 2.0", font["name"].getDebugName(13))
            self.assertTrue(set(map(ord, string.printable.rstrip() + " £"))
                            .issubset(font.getBestCmap()))


    def test_playfair_composite_bearing_includes_right_overhang(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "base.ttf"
            fixture_font(path)
            with TTFont(path) as font:
                cmap = font.getBestCmap()
                left, right = cmap[ord("A")], cmap[ord("B")]
                font["glyf"][right].coordinates.translate((-1000, 0))
                advance = font["hmtx"].metrics[right][0]
                font["hmtx"].metrics[right] = (advance, -990)
                BUILDERS["playfair-static"].add_pair_glyph(font, "overhang", left, right)
                glyph = font["glyf"]["overhang"]
                self.assertLess(glyph.xMin, font["glyf"][left].xMin)
                self.assertEqual(font["hmtx"].metrics["overhang"][1], glyph.xMin)

    def test_base_loader_closes_reader_on_table_validation_failure(self):
        from shared import font_metadata
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "base.ttf"
            fixture_font(path)
            with TTFont(path) as font:
                offset = font.reader.tables["cmap"].offset
            path.write_bytes(path.read_bytes()[:offset + 1])
            opened = []

            def track_reader(*args, **kwargs):
                reader = TTFont(*args, **kwargs)
                opened.append(reader.reader.file)
                return reader

            with patch.object(font_metadata, "TTFont", side_effect=track_reader):
                with self.assertRaisesRegex(ValueError, "Cannot read base font"):
                    font_metadata.load_base_font(path, Path(directory) / "out.ttf")
            self.assertEqual(len(opened), 1)
            self.assertTrue(opened[0].closed)

    def test_shared_names_supply_missing_platform_records(self):
        from shared.font_metadata import replace_font_names
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "base.ttf"
            fixture_font(path)
            with TTFont(path) as font:
                font["name"].names = [r for r in font["name"].names if r.nameID != 4]
                replace_font_names(font, {4: "Replacement"})
                for platform, encoding, language in ((3, 1, 0x409), (1, 0, 0)):
                    self.assertEqual(font["name"].getName(4, platform, encoding, language)
                                     .toUnicode(), "Replacement")


class ReferenceTests(unittest.TestCase):
    def test_morse_known_plaintexts_and_separators(self):
        decoder = BUILDERS["morse"].decode_text
        for text, plain in (("... --- ...", "SOS"), EXAMPLES["morse"],
                            (" ..--- ----- ..--- -.... / ..-.. .-.-.- ", "2026 É."),
                            (".   -", "ET"), ("-..-. / -....- / .-.-.-", "/ - ."),
                            ("........ ...", "........S"), ("", "")):
            with self.subTest(text=text):
                self.assertEqual(decoder(text), plain)
        with self.assertRaises(ValueError):
            decoder("··· ——— ···")

    def test_playfair_known_plaintext(self):
        cipher, plain = EXAMPLES["playfair-static"]
        self.assertEqual(BUILDERS["playfair-static"].decrypt_text(cipher, "PLAYFAIR EXAMPLE"), plain)

    def test_playfair_rows_columns_rectangles_and_j(self):
        builder = BUILDERS["playfair-static"]
        for cipher, plain in (("BC", "AB"), ("AF", "VA"), ("AG", "BF")):
            with self.subTest(cipher=cipher):
                self.assertEqual(builder.decrypt_text(cipher, ""), plain)
        self.assertEqual(builder.decrypt_text("JB", ""), builder.decrypt_text("IB", ""))
        with self.assertRaises(ValueError):
            builder.decrypt_text("ABC", "KEY")

    def test_vigenere_known_plaintext_and_case(self):
        for cipher, plain in (("LXFOPVEFRNHR", "ATTACKATDAWN"),
                              ("Lxfopv, Efrnhr!", "Attack, Atdawn!")):
            with self.subTest(cipher=cipher):
                self.assertEqual(BUILDERS["vigenere-static"].vigenere_decrypt(cipher, "LEMON"), plain)
                self.assertEqual(BUILDERS["vigenere-dynamic"].vigenere_decrypt("LEMON", cipher), plain)

    def test_vigenere_rejects_empty_keys(self):
        for key in ("", "123?!"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    BUILDERS["vigenere-static"].clean_key(key)
                with self.assertRaises(ValueError):
                    BUILDERS["vigenere-dynamic"].vigenere_decrypt(key, "ABC")
                with self.assertRaises(ValueError):
                    BUILDERS["vigenere-static"].vigenere_decrypt("ABC", key)

    def test_static_vigenere_normalizes_reference_keys(self):
        self.assertEqual(BUILDERS["vigenere-static"].vigenere_decrypt("LXFOPVEFRNHR", "le-mon"),
                         "ATTACKATDAWN")

    def test_enigma_known_plaintext_and_reciprocity(self):
        for name in ("enigma-static", "enigma-dynamic"):
            with self.subTest(decoder=name):
                machine = BUILDERS[name].EnigmaI
                self.assertEqual(machine().transform_text("AAAAA"), "BDZGO")
                self.assertEqual(machine().transform_text("BDZGO"), "AAAAA")
                self.assertEqual(machine(rotors=("V", "II", "IV"), positions="QWE",
                                         rings="BDF", plugboard=PLUGBOARD).transform_text("SXWQHHBR"),
                                 "ENIGMART")

    def test_enigma_double_step(self):
        for name, attribute in (("enigma-static", "positions"), ("enigma-dynamic", "pos")):
            for rings in ("AAA", "BDF"):
                machine = BUILDERS[name].EnigmaI(positions="ADV", rings=rings)
                for expected in ("AEW", "BFX"):
                    machine.step()
                    with self.subTest(decoder=name, rings=rings, position=expected):
                        self.assertEqual("".join(chr(65 + n) for n in getattr(machine, attribute)), expected)

    def test_enigma_rejects_invalid_settings(self):
        for name in ("enigma-static", "enigma-dynamic"):
            for settings in ({"rotors": ("I", "I", "III")}, {"positions": "AA"},
                             {"rings": "A1A"}, {"plugboard": "AB AC"}, {"plugboard": "AA"}):
                with self.subTest(decoder=name, settings=settings), self.assertRaises(ValueError):
                    BUILDERS[name].EnigmaI(**settings)
        for text in ("I-II-III/AAA/AAA", "I-I-III/AAA/AAA~ABC", "I-II-III/A1A/AAA~ABC",
                     "I-II-III/AAA/AAA~ß", "I-II-III/ßA/AAA~ABC"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                BUILDERS["enigma-dynamic"].parse_runtime(text)

    def test_enigma_preserves_non_ascii_text(self):
        for name in ("enigma-static", "enigma-dynamic"):
            with self.subTest(decoder=name):
                self.assertEqual(BUILDERS[name].EnigmaI().transform_text("ß!"), "ß!")

    def test_lorenz_known_plaintext(self):
        builder = BUILDERS["lorenz-static"]
        _, plain = builder.decode_ciphertext(LORENZ_CIPHER, builder.BREAM,
                                             builder.parse_starts(LORENZ_STARTS), "SZ42A")
        self.assertEqual(plain, LORENZ_PLAIN)

    def test_lorenz_reciprocity_for_all_models(self):
        builder = BUILDERS["lorenz-static"]
        text = builder.RAW_SYMBOLS * 2
        for model in ("SZ40", "SZ42A", "SZ42B"):
            def machine():
                return builder.Lorenz(builder.BREAM, builder.parse_starts(LORENZ_STARTS), model)
            with self.subTest(model=model):
                self.assertEqual(machine().transform_raw(machine().transform_raw(text)), text)

    def test_lorenz_rejects_invalid_settings(self):
        builder = BUILDERS["lorenz-static"]
        for starts in ("1,2", "0," + ",".join(["1"] * 11), ",".join(["100"] * 12)):
            with self.subTest(starts=starts), self.assertRaises(ValueError):
                builder.parse_starts(starts)
        for starts in (LORENZ_STARTS + ",", "," + LORENZ_STARTS, LORENZ_STARTS.replace(",", ",,", 1)):
            with self.subTest(starts=starts), self.assertRaises(ValueError):
                builder.parse_starts(starts)
        for starts in ({}, {**builder.parse_starts(LORENZ_STARTS), "chi1": 0},
                       {**builder.parse_starts(LORENZ_STARTS), "mu61": 62}):
            with self.subTest(starts=starts), self.assertRaises(ValueError):
                builder.Lorenz(builder.BREAM, starts)
        for patterns in ({}, {**builder.BREAM, "chi1": [0]},
                         {**builder.BREAM, "chi1": [2] * builder.WHEEL_LENGTHS["chi1"]}):
            with self.assertRaises(ValueError):
                builder.validate_patterns(patterns)


class FontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="decoder-tests-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.base = cls.directory / "base.ttf"
        fixture_font(cls.base)
        cls.cwd = cls.directory / "working-directory"
        cls.cwd.mkdir()
        shutil.copytree(ROOT / "shared", cls.directory / "shared",
                        ignore=shutil.ignore_patterns("test_decoders.py", "__pycache__"))
        cls.generated = {}
        for name, arguments in BUILD_ARGS.items():
            project = cls.directory / name
            project.mkdir()
            script = project / "build.py"
            shutil.copyfile(ROOT / name / "build.py", script)
            run_build(script, cls.base, arguments, cls.cwd)
            cls.generated[name] = project / f"{name}-font.ttf"

    def sources(self, name):
        return (ROOT / name / f"{name}-font.ttf", self.generated[name])

    def assert_display(self, path, text, expected):
        glyphs = shape(path, text)
        with TTFont(path) as font:
            self.assertEqual(display(font, glyphs), expected)
            cmap = font.getBestCmap()
            expected_advance = sum(font["hmtx"].metrics[cmap[ord(ch)]][0] for ch in expected)
            self.assertEqual(sum(g["ax"] for g in glyphs), expected_advance)

    def test_default_output_is_beside_builder(self):
        for name, path in self.generated.items():
            with self.subTest(decoder=name):
                self.assertTrue(path.is_file())
                self.assertEqual(path.parent.name, name)
        self.assertFalse(list(self.cwd.glob("*.ttf")))

    def test_explicit_output_preserves_default_font(self):
        for name, arguments in BUILD_ARGS.items():
            default = self.generated[name]
            before = hashlib.sha256(default.read_bytes()).digest()
            output = Path("nested") / f"{name}.ttf"
            with self.subTest(decoder=name):
                run_build(default.with_name("build.py"), self.base,
                          [*arguments, *SMALL_LIMITS[name], "--output", str(output)], self.cwd)
                self.assertTrue((self.cwd / output).is_file())
                self.assertEqual(hashlib.sha256(default.read_bytes()).digest(), before)
                with TTFont(self.cwd / output) as font:
                    self.assertIn("GSUB", font)

    def test_invalid_cli_settings_do_not_write_a_font(self):
        invalid = {
            "morse": ["--test", "not Morse"],
            "playfair-static": ["--key", "123"],
            "vigenere-static": ["--key", "123"],
            "vigenere-dynamic": ["--max-text", "0"],
            "enigma-static": ["--key", "I-I-III/AAA/AAA/B"],
            "enigma-dynamic": ["--delimiter", "::"],
            "lorenz-static": ["--starts", ",".join(["0"] * 12)],
        }
        for name, arguments in invalid.items():
            default = self.generated[name]
            before = hashlib.sha256(default.read_bytes()).digest()
            output = self.cwd / f"invalid-{name}.ttf"
            result = subprocess.run(
                [sys.executable, str(default.with_name("build.py")), "--base", str(self.base),
                 *BUILD_ARGS[name], *arguments, "--output", str(output)],
                cwd=self.cwd, capture_output=True, text=True, timeout=15)
            with self.subTest(decoder=name):
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())
                self.assertEqual(hashlib.sha256(default.read_bytes()).digest(), before)

    def test_markers_and_passthrough_cannot_overlap_input(self):
        invalid = {
            "vigenere-dynamic": [["--delimiter", c] for c in ("A", "a", " ")],
            "enigma-static": [["--trigger", c] for c in ("A", " ")] + [["--passthrough", " A"]],
            "enigma-dynamic": [["--delimiter", c] for c in ("A", "-", "/", " ")],
            "lorenz-static": [["--trigger", c] for c in ("A", "5", "/", " ")],
        }
        for name, cases in invalid.items():
            output = self.cwd / f"invalid-marker-{name}.ttf"
            for args in cases:
                with self.subTest(decoder=name, args=args):
                    result = subprocess.run(
                        [sys.executable, str(self.generated[name].with_name("build.py")),
                         "--base", str(self.base), *BUILD_ARGS[name], *SMALL_LIMITS[name],
                         *args, "--output", str(output)],
                        cwd=self.cwd, capture_output=True, text=True, timeout=15)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertFalse(output.exists())

    def test_dynamic_limits_reject_lookup_overflow(self):
        cases = (("vigenere-dynamic", ["--max-key", "65535"]),
                 ("vigenere-dynamic", ["--max-text", "1000000000"]),
                 ("enigma-dynamic", ["--max-text", "1000000000"]))
        for name, options in cases:
            output = self.cwd / f"oversized-{name}.ttf"
            with self.subTest(decoder=name, options=options):
                result = subprocess.run(
                    [sys.executable, str(self.generated[name].with_name("build.py")),
                     "--base", str(self.base), *BUILD_ARGS[name], *options,
                     "--output", str(output)], cwd=self.cwd,
                    capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("lookup capacity", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(output.exists())

    def test_builders_cannot_overwrite_the_base_font(self):
        before = hashlib.sha256(self.base.read_bytes()).digest()
        alias = self.directory / "base-alias.ttf"
        alias.symlink_to(self.base)
        for name, arguments in BUILD_ARGS.items():
            for output in (self.base, alias):
                with self.subTest(decoder=name, output=output):
                    result = subprocess.run(
                        [sys.executable, str(self.generated[name].with_name("build.py")),
                         "--base", str(self.base), *arguments, *SMALL_LIMITS[name],
                         "--output", str(output)], cwd=self.cwd,
                        capture_output=True, text=True, timeout=15)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Output must differ", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual(hashlib.sha256(self.base.read_bytes()).digest(), before)

    def test_builders_reject_bases_without_a_unicode_cmap(self):
        missing_cmap = self.directory / "no-cmap.ttf"
        with TTFont(self.base) as font:
            del font["cmap"]
            font.save(missing_cmap)
        for name, arguments in BUILD_ARGS.items():
            output = self.cwd / f"no-cmap-{name}.ttf"
            with self.subTest(decoder=name):
                result = subprocess.run(
                    [sys.executable, str(self.generated[name].with_name("build.py")),
                     "--base", str(missing_cmap), *arguments, *SMALL_LIMITS[name],
                     "--output", str(output)], cwd=self.cwd,
                    capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("no usable Unicode cmap", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(output.exists())

    def test_truncated_base_tables_report_clean_cli_errors(self):
        base = self.directory / "truncated-base.ttf"
        output = self.directory / "truncated-font.ttf"
        for table in ("cmap", "glyf", "hmtx", "name"):
            with TTFont(self.base) as font:
                offset = font.reader.tables[table].offset
            base.write_bytes(self.base.read_bytes()[:offset + 1])
            for name in EXAMPLES:
                with self.subTest(table=table, decoder=name):
                    result = subprocess.run(
                        [sys.executable, str(ROOT / name / "build.py"),
                         "--base", str(base), *BUILD_ARGS[name], *SMALL_LIMITS[name],
                         "--output", str(output)], cwd=self.cwd,
                        capture_output=True, text=True, timeout=15)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Cannot read base font", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertFalse(output.exists())

    def test_malformed_lorenz_pattern_files_report_clean_errors(self):
        builder = BUILDERS["lorenz-static"]
        invalid = [None, [], "BREAM", 1, {**builder.BREAM, "chi1": None},
                   {**builder.BREAM, "chi1": 1},
                   {**builder.BREAM, "chi1": [0.0] * builder.WHEEL_LENGTHS["chi1"]}]
        path = self.directory / "malformed-patterns.json"
        output = self.directory / "invalid-pattern-font.ttf"
        for value in invalid:
            with self.subTest(value=value):
                path.write_text(json.dumps(value), encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(ROOT / "lorenz-static" / "build.py"),
                     "--pattern-file", str(path), "--output", str(output)],
                    cwd=self.cwd, capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Error:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(output.exists())

    def test_reserved_glyph_collisions_do_not_write_fonts(self):
        collisions = [("vigenere-static", "vigP00.s0"),
                      ("morse", "morse.out.0041"),
                      ("vigenere-dynamic", "vsk.delim.1"),
                      ("vigenere-dynamic", "vsk.out.A"),
                      ("enigma-dynamic", "esk.OUT.A"),
                      ("lorenz-static", "lorenz.start"),
                      ("lorenz-static", "lorenz.start.sep"),
                      ("lorenz-static", "lz0000_L_SEP")]
        for name, glyph_name in collisions:
            with self.subTest(decoder=name, glyph=glyph_name):
                base = self.directory / "collision-base.ttf"
                with TTFont(self.base) as font:
                    order = list(font.getGlyphOrder())
                    font["glyf"][glyph_name] = TTGlyphPen(None).glyph()
                    font["hmtx"].metrics[glyph_name] = (0, 0)
                    font.setGlyphOrder(order + [glyph_name])
                    font.save(base)
                output = self.directory / "collision-font.ttf"
                result = subprocess.run(
                    [sys.executable, str(ROOT / name / "build.py"), "--base", str(base),
                     *BUILD_ARGS[name], *SMALL_LIMITS[name], "--output", str(output)],
                    cwd=self.cwd, capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr, "collision|reserved glyph")
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(output.exists())

    def test_marker_aliases_in_custom_bases_are_rejected(self):
        base = self.directory / "aliased-base.ttf"
        with TTFont(self.base) as font:
            for table in font["cmap"].tables:
                if table.isUnicode():
                    table.cmap[ord("~")] = table.cmap[ord("A")]
                    table.cmap[ord("!")] = table.cmap[ord("B")]
            font.save(base)
        cases = [(name, []) for name in
                 ("vigenere-dynamic", "enigma-dynamic", "enigma-static", "lorenz-static")]
        cases.append(("enigma-static", ["--trigger", "@", "--passthrough", "!"]))
        output = self.directory / "aliased-marker.ttf"
        for name, arguments in cases:
            with self.subTest(decoder=name, arguments=arguments):
                result = subprocess.run(
                    [sys.executable, str(ROOT / name / "build.py"), "--base", str(base),
                     *BUILD_ARGS[name], *SMALL_LIMITS[name], *arguments,
                     "--output", str(output)], cwd=self.cwd,
                    capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("glyph must be distinct", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(output.exists())

    def test_unicode_playfair_key_has_ascii_postscript_names(self):
        output = self.directory / "unicode-playfair.ttf"
        BUILDERS["playfair-static"].build_font(self.base, output, "Aé 日本語")
        with TTFont(output) as font:
            for record in font["name"].names:
                if record.nameID == 6:
                    self.assertRegex(record.toUnicode(), r"^[A-Za-z0-9-]{1,63}$")

    def test_generated_font_names_replace_base_names(self):
        for name, path in self.generated.items():
            with self.subTest(decoder=name), TTFont(path) as font:
                self.assertEqual(font["name"].getDebugName(16), font["name"].getDebugName(1))
                self.assertEqual(font["name"].getDebugName(17), "Regular")
                self.assertNotEqual(font["name"].getDebugName(16), "Stale Preferred Family")
                for record in font["name"].names:
                    if record.nameID in (1, 2, 3, 4, 6, 16, 17):
                        common = font["name"].getName(record.nameID, 3, 1, 0x409)
                        self.assertIsNotNone(common)
                        self.assertEqual(record.toUnicode(), common.toUnicode())

    def test_font_identity_distinguishes_machine_settings(self):
        builder = BUILDERS["enigma-static"]
        names = []
        for plugboard in ("", "AB"):
            output = self.directory / f"identity-{plugboard or 'none'}.ttf"
            builder.build_font(self.base, output, rotors=["I", "II", "III"],
                               positions="AAA", rings="AAA", reflector="B",
                               plugboard=plugboard, max_letters=2, trigger="~", passthrough=" ")
            with TTFont(output) as font:
                names.append(tuple(font["name"].getDebugName(i) for i in (1, 3, 6)))
        self.assertEqual(names[0][0], names[1][0])
        self.assertNotEqual(names[0][1], names[1][1])
        self.assertNotEqual(names[0][2], names[1][2])

    def test_custom_base_license_and_copyright_are_retained(self):
        for name, path in self.generated.items():
            with self.subTest(decoder=name), TTFont(path) as font:
                self.assertIn("Copyright 2026 Fixture Author", font["name"].getDebugName(0))
                self.assertIn("Michael Brackx", font["name"].getDebugName(0))
                self.assertEqual(font["name"].getDebugName(13),
                                 "Fixture license: preserved verbatim")
                self.assertEqual(font["name"].getDebugName(14),
                                 "https://example.invalid/fixture-license")

    def assert_roboto_derivative(self, path, decoder):
        base_path = ROOT / "shared" / "fonts" / "roboto-2" / "Roboto-Regular.ttf"
        with TTFont(path) as font, TTFont(base_path) as base:
            self.assertIn("Copyright 2015 Google Inc.", font["name"].getDebugName(0))
            self.assertIn("Copyright 2026 Michael Brackx", font["name"].getDebugName(0))
            self.assertIn("Modified by Michael Brackx", font["name"].getDebugName(10))
            self.assertIn(decoder, font["name"].getDebugName(10))
            for name_id in (7, 9, 11, 13, 14):
                expected = [(r.platformID, r.platEncID, r.langID, r.toUnicode())
                            for r in base["name"].names if r.nameID == name_id]
                actual = [(r.platformID, r.platEncID, r.langID, r.toUnicode())
                          for r in font["name"].names if r.nameID == name_id]
                self.assertEqual(actual, expected)
            self.assertNotIn("Roboto", font["name"].getDebugName(1))
            self.assertNotIn("DSIG", font)
            for ch in "Aa£":
                self.assertEqual(
                    font["glyf"][font.getBestCmap()[ord(ch)]].getCoordinates(font["glyf"]),
                    base["glyf"][base.getBestCmap()[ord(ch)]].getCoordinates(base["glyf"]))

    def test_bundled_decoder_fonts_are_attributed_roboto_derivatives(self):
        for name in EXAMPLES:
            with self.subTest(decoder=name):
                self.assert_roboto_derivative(ROOT / name / f"{name}-font.ttf", name)

    def test_default_base_builds_from_an_unrelated_directory(self):
        for name, arguments in BUILD_ARGS.items():
            output = self.cwd / "default-base" / f"{name}.ttf"
            with self.subTest(decoder=name):
                run_build(self.generated[name].with_name("build.py"), None,
                          [*arguments, *SMALL_LIMITS[name], "--output", str(output)], self.cwd)
                self.assert_roboto_derivative(output, name)

    @NEEDS_SHAPER
    def test_known_plaintexts_in_bundled_and_fresh_fonts(self):
        for name, (cipher, plain) in EXAMPLES.items():
            for path in self.sources(name):
                with self.subTest(decoder=name, font=path):
                    self.assert_display(path, cipher, plain)

    @NEEDS_SHAPER
    def test_morse_all_characters_and_punctuation_outputs(self):
        builder = BUILDERS["morse"]
        text = " ".join(builder.MORSE.values())
        expected = "".join(builder.MORSE)
        for path in self.sources("morse"):
            with self.subTest(font=path):
                self.assert_display(path, text, expected)
                self.assert_display(path, "  ...   --- ... / -..-. / -....- / .-.-.-  ", "SOS / - .")
                self.assert_display(path, ". / - / .. / --", "E T I M")
                self.assert_display(path, ".../---/...", "S O S")
                self.assert_display(path, "... " * 200, "S" * 200)

    @NEEDS_SHAPER
    def test_morse_exhaustive_group_boundaries_and_unknown_recovery(self):
        builder = BUILDERS["morse"]
        # Every dot/dash group through eight signals, including all supported
        # codes and invalid groups containing valid prefixes and suffixes.
        groups = ["".join(signals) for length in range(1, 9)
                  for signals in itertools.product(".-", repeat=length)]
        inputs = [f"{group} / ... {group} ---" for group in groups]
        expected = [builder.DECODE.get(group, group) + " S" +
                    builder.DECODE.get(group, group) + "O" for group in groups]
        for path in self.sources("morse"):
            result = subprocess.run(
                [SHAPER, str(path), "--text-file=-", "--output-format=json", "--no-glyph-names",
                 "--direction=ltr", "--script=latn", "--features=rlig=1,liga=1,clig=1,kern=0"],
                input="\n".join(inputs) + "\n", text=True, capture_output=True, check=True, timeout=30)
            outputs = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(len(outputs), len(inputs))
            with TTFont(path) as font:
                for text, glyphs, plain in zip(inputs, outputs, expected):
                    with self.subTest(font=path, text=text):
                        self.assertEqual(display(font, glyphs), plain)
            self.assert_display(path, "x... ...x x.-x / ...", "x......xx.-x S")

    @NEEDS_SHAPER
    def test_playfair_all_digraphs_including_j(self):
        cipher = "".join(a + b for a, b in itertools.product(string.ascii_uppercase, repeat=2))
        plain = BUILDERS["playfair-static"].decrypt_text(cipher, "PLAYFAIR EXAMPLE")
        for path in self.sources("playfair-static"):
            with self.subTest(font=path):
                self.assert_display(path, cipher, plain)

    @NEEDS_SHAPER
    def test_static_vigenere_case_and_punctuation(self):
        for path in self.sources("vigenere-static"):
            with self.subTest(font=path):
                self.assert_display(path, "Lxfopv, Efrnhr!", "Attack, Atdawn!")

    @NEEDS_SHAPER
    def test_dynamic_vigenere_runtime_keys_and_case(self):
        for path in self.sources("vigenere-dynamic"):
            for key, cipher, plain in (("A", "AbCd", "AbCd"), ("B", "BbBb", "AaAa"),
                                      ("lemon", "LxfopvEfrnhr", "AttackAtdawn"),
                                      ("ABCDEF", "ABCDEFABCDEF", "AAAAAAAAAAAA")):
                with self.subTest(font=path, key=key):
                    self.assert_display(path, key + "~" + cipher, plain)

    @NEEDS_SHAPER
    def test_dynamic_vigenere_oversized_keys_are_not_decoded_as_suffixes(self):
        for path in self.sources("vigenere-dynamic"):
            for key in ("ABCDEFG", "abcdefg", "LEMONAA", "A" * 30):
                text = key + "~LXFOPVEFRNHR"
                with self.subTest(font=path, key=key):
                    self.assert_display(path, text, text)
            # A separator establishes a fresh key boundary within a longer run.
            self.assert_display(path, "ABC ABCDEF~ABCDEF", "ABC AAAAAA")
            self.assert_display(path, "A~B B~C", "B B")

    @NEEDS_SHAPER
    def test_runtime_prefixes_are_invisible(self):
        for name, prefix in (("vigenere-dynamic", "LEMON~"),
                             ("enigma-dynamic", "V-II-IV/QWE/BDF~")):
            for path in self.sources(name):
                with self.subTest(decoder=name, font=path):
                    self.assert_display(path, prefix, "")

    @NEEDS_SHAPER
    def test_enigma_static_punctuation_does_not_step_rotors(self):
        for path in self.sources("enigma-static"):
            with self.subTest(font=path):
                self.assert_display(path, "~BD, ZGO!", "AA, AAA!")

    @NEEDS_SHAPER
    def test_enigma_dynamic_rotors_rings_plugboard_and_turnover(self):
        cases = (("I-II-III", "AAA", "AAA"), ("III-I-V", "QEV", "BDF"),
                 ("V-IV-II", "ZZZ", "XYZ"), ("I-II-III", "ADV", "AAA"),
                 ("V-II-IV", "QWE", "BDF"))
        for rotors, positions, rings in cases:
            cipher = "ABCDEFGH"
            # The independently implemented static core checks the dynamic font.
            plain = BUILDERS["enigma-static"].EnigmaI(
                rotors=rotors.split("-"), positions=positions, rings=rings,
                plugboard=PLUGBOARD).transform_text(cipher)
            for path in self.sources("enigma-dynamic"):
                with self.subTest(font=path, settings=(rotors, positions, rings)):
                    self.assert_display(path, f"{rotors}/{positions}/{rings}~{cipher}", plain)
                    self.assert_display(path, f"{rotors}/{positions}/{rings}~{cipher}".lower(), plain)

    @NEEDS_SHAPER
    def test_dynamic_text_limits(self):
        for path in self.sources("vigenere-dynamic"):
            with self.subTest(font=path):
                self.assert_display(path, "B~" + "A" * 25, "Z" * 24 + "A")
        cipher = "B" * 9
        plain = BUILDERS["enigma-static"].EnigmaI(plugboard=PLUGBOARD).transform_text(cipher[:8])
        for path in self.sources("enigma-dynamic"):
            with self.subTest(font=path):
                self.assert_display(path, "I-II-III/AAA/AAA~" + cipher, plain + cipher[-1])

    @NEEDS_SHAPER
    def test_static_enigma_text_limit(self):
        plain = BUILDERS["enigma-static"].EnigmaI().transform_text("B" * 16)
        self.assert_display(self.generated["enigma-static"], "~" + "B" * 17, plain + "B")

    @NEEDS_SHAPER
    def test_lorenz_grouping_spaces_do_not_advance_wheels(self):
        builder = BUILDERS["lorenz-static"]
        cipher = builder.Lorenz(builder.BREAM, builder.parse_starts(LORENZ_STARTS),
                                "SZ42A").transform_raw("HELLOWORLD")
        for path in self.sources("lorenz-static"):
            with self.subTest(font=path):
                self.assert_display(path, "~" + cipher[:5] + " " + cipher[5:], "HELLO WORLD")

    @NEEDS_SHAPER
    def test_lorenz_all_models_and_shift_controls(self):
        builder = BUILDERS["lorenz-static"]
        raw_plain = "HELLO95QWER8934WORLD"
        # Includes spaces, figures/letters shifts, CR and LF. The font renders
        # CR as a space and LF/shift controls invisibly, unlike software newlines.
        expected = "HELLO 1234  WORLD"
        for model in ("SZ40", "SZ42A", "SZ42B"):
            starts = builder.parse_starts(LORENZ_STARTS)
            cipher = builder.Lorenz(builder.BREAM, starts, model).transform_raw(raw_plain)
            path = self.directory / f"lorenz-{model}.ttf"
            builder.build_font(self.base, path, patterns=builder.BREAM, starts=starts,
                               model=model, max_symbols=len(cipher))
            with self.subTest(model=model):
                self.assert_display(path, "~" + cipher, expected)


if __name__ == "__main__":
    unittest.main()
