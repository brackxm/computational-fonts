# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""PGM font and artifact regressions. Requires FontTools and hb-shape."""

import importlib.util
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
SHAPER = shutil.which("hb-shape")
sys.path.insert(0, str(HERE.parent / "shared"))
from testing import BuilderOptionsTests, FontFixture, odf_text


class BuildTests(BuilderOptionsTests, FontFixture, unittest.TestCase):
    project = HERE

    def test_safe_import(self):
        spec = importlib.util.spec_from_file_location("pgm_builder", HERE / "build.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.MAX_SIZE, 64)
        self.assertFalse((self.directory / "pgm-font.ttf").exists())

    def test_bundled_font_matches_build(self):
        with TTFont(HERE / "pgm-font.ttf") as bundled, TTFont(self.generated) as generated:
            for tag in ("cmap", "glyf", "hmtx", "GSUB", "GPOS", "GDEF", "COLR", "CPAL", "name"):
                self.assertEqual(bundled[tag].compile(bundled), generated[tag].compile(generated), tag)

    def test_metadata_budgets_and_palette(self):
        with TTFont(self.generated) as font:
            self.assertEqual(font["name"].getDebugName(1), "PGM Renderer")
            self.assertIn("Michael Brackx", font["name"].getDebugName(0))
            self.assertIn("Apache License, Version 2.0", font["name"].getDebugName(13))
            self.assertEqual(font["OS/2"].fsType, 0)
            self.assertEqual(font["head"].unitsPerEm, 4096)
            self.assertLess(self.generated.stat().st_size, 3_525_000)
            self.assertLess(len(font.getGlyphOrder()), 33_500)
            self.assertLess(len(font["GSUB"].compile(font)), 525_000)
            self.assertLess(len(font["GPOS"].compile(font)), 1_700_000)
            self.assertLess(font["GSUB"].table.LookupList.LookupCount, 175)
            self.assertEqual(len(font["CPAL"].palettes[0]), 17)
            for value in range(16):
                color = font["CPAL"].palettes[0][value + 1]
                self.assertEqual((color.red, color.green, color.blue, color.alpha),
                                 (value * 17, value * 17, value * 17, 255))
                glyph = f"gray_{value}_cell"
                self.assertEqual(font["hmtx"][glyph][0], 0)
                if value < 15:
                    layer = font["COLR"].ColorLayers[glyph][0]
                    self.assertEqual((layer.name, layer.colorID), ("ink_cell", value + 1))
                else:
                    self.assertEqual(font["glyf"][glyph].numberOfContours, 0)
            # Counting state stays independent of the 16 color values.
            for prefix in ("pixel", "end", "draw", "index"):
                self.assertEqual(sum(g.startswith(prefix + "_") for g in font.getGlyphOrder()), 4096)
            self.assertEqual(len(font["GPOS"].table.LookupList.Lookup[0].SubTable), 64)
            self.assertEqual(font["GPOS"].table.LookupList.Lookup[1].SubTable[0].Mark1Array.MarkCount, 16)

    @unittest.skipUnless(SHAPER, "hb-shape is required")
    def test_odt_input_and_embedding(self):
        with ZipFile(HERE / "pgm.odt") as package:
            self.assertEqual(package.namelist()[0], "mimetype")
            embeds = [name for name in package.namelist() if name.endswith(".ttf")]
            self.assertIn((HERE / "pgm-font.ttf").read_bytes(), [package.read(n) for n in embeds])
            root = ET.fromstring(package.read("content.xml"))
            sources = [odf_text(n) for n in root.findall(
                ".//{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p") if odf_text(n).startswith("P2 ")]
            self.assertEqual(len(sources), 2)
            self.assertEqual(sources[0], sources[1])
            width, height, maxval = map(int, sources[0].split()[1:4])
            self.assertEqual((width, height), (64, 64))
            self.assertEqual(maxval, 15)
            self.assertEqual(len(sources[0].split()[4:]), width * height)
            output = json.loads(subprocess.check_output(
                [SHAPER, str(self.generated), sources[0], "--output-format=json"], timeout=10))
            self.assertEqual(output[0]["g"], f"board_{width}")


@unittest.skipUnless(SHAPER, "hb-shape is required")
class ShapingTests(FontFixture, unittest.TestCase):
    project = HERE

    def shape(self, source):
        return json.loads(subprocess.check_output(
            [SHAPER, str(self.generated), source, "--output-format=json"], timeout=10))

    def assert_image(self, source, width, height, samples):
        output = self.shape(source)
        self.assertEqual(output[0]["g"], f"board_{width}")
        self.assertEqual(output[1]["g"], f"background_{width}_{height}")
        self.assertEqual(sum(g["ax"] for g in output), width * 64)
        indices = [g for g in output if g["g"].startswith("index_")]
        cells = [g for g in output if g["g"].startswith("gray_")]
        self.assertEqual(len(indices), width * height)
        self.assertEqual(len(cells), width * height)
        self.assertTrue(all(g["g"] == "hidden" or g["g"].startswith(
            ("board_", "background_", "index_", "gray_")) for g in output))
        for i, (marker, cell, value) in enumerate(zip(indices, cells, samples)):
            self.assertEqual(marker["g"], f"index_{i}")
            self.assertEqual(cell["g"], f"gray_{value}_cell")
            self.assertEqual((cell["dx"] + width * 64, cell["dy"]),
                             (i % width * 64, 4096 - (i // width + 1) * 64))
            self.assertEqual((marker["dx"], marker["dy"]), (cell["dx"], cell["dy"]))
            self.assertEqual(cell["ax"], 0)

    def test_every_dimension_and_random_shades(self):
        rng = random.Random(402)
        for width in range(1, 65):
            for height in range(1, 65):
                with self.subTest(width=width, height=height):
                    samples = [rng.randrange(16) for _ in range(width * height)]
                    self.assert_image(f"P2 {width} {height} 15 " + " ".join(map(str, samples)),
                                      width, height, samples)

    def test_boundaries_separators_and_all_shades(self):
        for value in range(16):
            self.assert_image(f"P2 1 1 15 {value}", 1, 1, [value])
        for source in ("P2 02 02 15 0 5 10 15", "P2 2 2 15 0  5   10 15   "):
            self.assert_image(source, 2, 2, [0, 5, 10, 15])
        for width, height in ((1, 64), (64, 1), (64, 64)):
            for value in (0, 15):
                samples = [value] * (width * height)
                self.assert_image(f"P2 {width} {height} 15 " + " ".join(map(str, samples)),
                                  width, height, samples)

    def test_invalid_input_has_no_partial_image(self):
        cases = ["bad", "P2", "P2 1 1 15", "P2 1 1 15 ", "P2 1 1 15 16", "P2 1 1 15 -1",
                 "P2 1 1 15 1.0", "P2 1 1 15 015", "P2 1 1 15 00", "P2 1 1 15 1x",
                 "P2 1 1 15 0 0", "P2 2 1 15 10", "P2 2 1 15 015", "P2 2 1 15 1 0 0",
                 "P2 2 2 15 0 1 2", "P2 2 2 15 0 1 2 3 junk", "P2 1 1 15 0#comment",
                 "P2 1 1 15 ☃", "P2 0 1 15 0", "P2 65 1 15 " + "0 " * 65,
                 "P2 1 65 15 " + "0 " * 65, "P2 001 1 15 0", "P2 1 1 015 0",
                 "P2 1 1 255 0", "P2 1 1 3 0", "P2 1 1 0 0", "P2  1 1 15 0",
                 " P2 1 1 15 0", "P1 1 1 15 0", "P3 1 1 15 0", "P5 1 1 15 0",
                 "P2 64 64 15 " + "0 " * 4097, "P2 64 64 15 " + "15 " * 4095]
        for source in cases:
            with self.subTest(source=source[:40]):
                output = self.shape(source)
                self.assertEqual(output[0]["g"], "error")
                self.assertEqual(sum(g["ax"] for g in output), 4097)
                self.assertTrue(all(g["g"] in ("error", "hidden") for g in output))


if __name__ == "__main__":
    unittest.main()
