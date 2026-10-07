# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Shape the bundled and freshly built formatter; verify its actual outlines."""

import hashlib
import importlib.util
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
SHAPER = shutil.which("hb-shape")
spec = importlib.util.spec_from_file_location("markdown_builder", FOLDER / "build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

CHECKSUMS = {
    "Roboto-Regular.ttf": "56a45233d29f11b4dfb86d248e921939d115778f87325e7ae8cc108383d6664d",
    "Roboto-Bold.ttf": "61f89f8db49261c2f6106e8dccc35df7b2f7ed909020db40a3fc905e95f99334",
    "Roboto-Italic.ttf": "fa0b17bb4aaac4a1b2ee149dd4ca3b55e97d3077aa6ba9bb02541b316e7c46ce",
    "Roboto-BoldItalic.ttf": "40083ed54338397cf49d2c49f59eddcd963a30fdb301813d4bd3abbb37a13d12",
}


def outlines(font, name):
    pen = DecomposingRecordingPen(font.getGlyphSet())
    font.getGlyphSet()[name].draw(pen)
    return pen.value


class FormatterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.fresh = Path(cls.tmp.name) / "fresh.ttf"
        builder.build_font(cls.fresh)
        cls.paths = (FOLDER / "markdown-font.ttf", cls.fresh)
        cls.fonts = [TTFont(path) for path in cls.paths]
        cls.sources = {face: TTFont(builder.SOURCE_DIR / filename)
                       for face, filename in builder.SOURCES.items()}

    @classmethod
    def tearDownClass(cls):
        for font in [*cls.fonts, *cls.sources.values()]:
            font.close()
        cls.tmp.cleanup()

    def shape(self, path, font, text):
        result = subprocess.run([SHAPER, str(path), text, "--output-format=json",
                                 "--direction=ltr", "--script=latn", "--features=kern=0"],
                                capture_output=True, text=True, check=True, timeout=15)
        visible = []
        inverse = {glyph: chr(code) for code, glyph in font.getBestCmap().items()
                   if chr(code) in builder.CHARS}
        for row in json.loads(result.stdout):
            glyph = row["g"]
            self.assertNotEqual(glyph, ".notdef")
            self.assertFalse(glyph.startswith("md.cand."), "Unreleased candidate")
            if glyph == "md.gap" or glyph.startswith(("md.close.", "md.start.")):
                self.assertEqual(row["ax"], 0)
                self.assertEqual(font["glyf"][glyph].numberOfContours, 0)
                continue
            if glyph.startswith("md.out."):
                _, _, style, index = glyph.split(".")
                index = int(index)
                if index < len(builder.CHARS):
                    chars = builder.CHARS[index]
                else:
                    chars = builder.ESCAPES[index - len(builder.CHARS)]
                    if style == "code":
                        chars = "\\" + chars
            elif glyph.startswith("md.marker."):
                style = "regular"
                chars = builder.MARKERS[glyph.split(".")[-1]]
            elif glyph.startswith("md.escape.literal."):
                style, chars = "regular", chr(int(glyph.split(".")[-1], 16))
            else:
                style, chars = "regular", inverse[glyph]
            visible.extend((char, style) for char in chars)
        return visible

    def check_display(self, text, *segments):
        expected = [(char, style) for chars, style in segments for char in chars]
        for path, font in zip(self.paths, self.fonts):
            with self.subTest(font=path.name, text=text[:90]):
                self.assertEqual(self.shape(path, font, text), expected)

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_styles_and_plain_text(self):
        self.check_display("Plain **bold** *italic* ***both*** ~~gone~~ `x = 3`.",
                           ("Plain ", "regular"), ("bold", "bold"), (" ", "regular"),
                           ("italic", "italic"), (" ", "regular"), ("both", "both"),
                           (" ", "regular"), ("gone", "strike"), (" ", "regular"),
                           ("x = 3", "code"), (".", "regular"))
        self.check_display("a*b*c", ("a", "regular"), ("b", "italic"), ("c", "regular"))
        self.check_display("**café déjà vu**", ("café déjà vu", "bold"))
        self.check_display("`i W  m`", ("i W  m", "code"))

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_headings_require_start_of_run(self):
        for prefix, style in (("# ", "h1"), ("## ", "h2"), ("### ", "h3")):
            self.check_display(prefix + "Heading", ("Heading", style))
        for text in ("text # heading", " # heading", "#### heading", "#heading", "##heading"):
            self.check_display(text, (text, "regular"))
        self.check_display("# **literal** and `code`", ("**literal** and `code`", "h1"))
        self.check_display(r"# \*literal\*", ("*literal*", "h1"))

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_heading_body_prefixes_stay_literal(self):
        for prefix, style in (("# ", "h1"), ("## ", "h2"), ("### ", "h3")):
            for body in ("# Heading", "## Heading", "### Heading", "# ## ### Heading"):
                self.check_display(prefix + body, (body, style))

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_escapes_and_code_shielding(self):
        self.check_display(r"\*stars\* \~tilde\~ \`tick\` \# hash \\",
                           ("*stars* ~tilde~ `tick` # hash " + chr(92), "regular"))
        self.check_display(r"**a\*b**", ("a*b", "bold"))
        self.check_display(r"`**bold** ~~strike~~ \*star\*`",
                           (r"**bold** ~~strike~~ \*star\*", "code"))
        self.check_display(r"\# Heading", ("# Heading", "regular"))
        self.check_display("` code `", (" code ", "code"))
        self.check_display("` `", (" ", "code"))

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_incomplete_empty_and_oversized_markers(self):
        for text in ("*unfinished", "**unfinished", "***unfinished", "~~unfinished",
                     "`unfinished", "**", "***", "~~", "``", "****literal****",
                     "~~~literal~~~", "``literal``", "* spaced*", "*spaced *",
                     "** spaced**", "~~spaced ~~", "normal * text"):
            self.check_display(text, (text, "regular"))
        self.check_display("*one* plain *two* *unfinished",
                           ("one", "italic"), (" plain ", "regular"),
                           ("two", "italic"), (" *unfinished", "regular"))

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_long_and_varied_spans(self):
        body = "long text " * 120 + "end"
        self.check_display("**" + body + "** tail", (body, "bold"), (" tail", "regular"))
        rng = random.Random(1123)
        alphabet = "abcdef XYZ 0123.,;é"
        for _ in range(40):
            pieces, segments = [], []
            for marker, style in (("*", "italic"), ("**", "bold"), ("***", "both"),
                                  ("~~", "strike"), ("`", "code")):
                body = "a" + "".join(rng.choices(alphabet, k=rng.randrange(1, 70))) + "z"
                pieces.append(marker + body + marker + " / ")
                segments.extend(((body, style), (" / ", "regular")))
            self.check_display("".join(pieces), *segments)

    def test_style_outlines_are_the_actual_source_faces(self):
        for font in self.fonts:
            for style in ("bold", "italic", "both"):
                source = self.sources[style]
                for char in builder.CHARS:
                    name = f"md.out.{style}.{builder.CHARS.index(char)}"
                    original = source.getBestCmap()[ord(char)]
                    with self.subTest(style=style, char=char):
                        self.assertEqual(outlines(font, name), outlines(source, original))
                        self.assertEqual(font["hmtx"][name][0], source["hmtx"][original][0])

    def test_code_cells_heading_metrics_and_strike(self):
        for font in self.fonts:
            upm = font["head"].unitsPerEm
            for index, char in enumerate(builder.CHARS):
                name = f"md.out.code.{index}"
                glyph = font["glyf"][name]
                cell = font["hmtx"][name][0]
                self.assertEqual(cell, round(upm * .64))
                if glyph.numberOfContours:
                    self.assertGreaterEqual(glyph.xMin, 0)
                    self.assertLessEqual(glyph.xMax, cell)
                strike = font["glyf"][f"md.out.strike.{index}"]
                self.assertGreaterEqual(strike.numberOfContours, 1)
            bold = self.sources["bold"]
            for style, scale in (("h1", 1.5), ("h2", 1.25), ("h3", 1.1)):
                for index, char in enumerate(builder.CHARS):
                    glyph = font["glyf"][f"md.out.{style}.{index}"]
                    source = bold["glyf"][bold.getBestCmap()[ord(char)]]
                    source.recalcBounds(bold["glyf"])
                    self.assertEqual(font["hmtx"][f"md.out.{style}.{index}"][0],
                                     round(bold["hmtx"][bold.getBestCmap()[ord(char)]][0] * scale))
                    if glyph.numberOfContours:
                        self.assertAlmostEqual(glyph.yMax, source.yMax * scale, delta=1)
                        self.assertLessEqual(glyph.yMax, font["hhea"].ascent)
                        self.assertGreaterEqual(glyph.yMin, font["hhea"].descent)

    def test_source_integrity_attribution_and_specimen(self):
        for filename, checksum in CHECKSUMS.items():
            self.assertEqual(hashlib.sha256((builder.SOURCE_DIR / filename).read_bytes()).hexdigest(), checksum)
        for font in self.fonts:
            self.assertEqual(font["name"].getBestFamilyName(), "Markdown Formatter")
            for name_id in (0, 7, 13, 14):
                original = self.sources["regular"]["name"].getDebugName(name_id)
                self.assertIn(original, font["name"].getDebugName(name_id))
            self.assertIn("Formatter modifications", font["name"].getDebugName(0))
            self.assertIn("markdown formatter", font["name"].getDebugName(10))
        with ZipFile(FOLDER / "markdown.odt") as odt:
            self.assertEqual(odt.read("Fonts/computational.ttf"), self.paths[0].read_bytes())
            self.assertEqual(odt.read("Fonts/Roboto-Regular.ttf"),
                             (builder.SOURCE_DIR / "Roboto-Regular.ttf").read_bytes())
            self.assertEqual(odt.read("THIRD_PARTY_NOTICES.txt"), (ROOT / "THIRD_PARTY_NOTICES.md").read_bytes())

    def test_source_overwrite_protection_and_import(self):
        for filename in CHECKSUMS:
            with self.assertRaisesRegex(ValueError, "Output must differ"):
                builder.build_font(builder.SOURCE_DIR / filename)
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-c",
                                     "import runpy; runpy.run_path(" + repr(str(FOLDER / "build.py")) + ")"],
                                    cwd=directory, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_cli_output_and_family_name(self):
        original = self.paths[0].read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(FOLDER / "build.py"),
                                     "--output", "reading.ttf", "--name", "Reading Font"],
                                    cwd=directory, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            with TTFont(Path(directory) / "reading.ttf") as font:
                self.assertEqual(font["name"].getBestFamilyName(), "Reading Font")
                self.assertTrue(font["name"].getDebugName(6).startswith("Reading-Font-Regular-"))
        self.assertEqual(self.paths[0].read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
