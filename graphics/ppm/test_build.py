# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""PPM font and artifact regressions. Requires FontTools and hb-shape."""

import importlib.util
import json
from itertools import product
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
from testing import FontFixture, odf_text


class BuildTests(FontFixture, unittest.TestCase):
    project = HERE

    def test_safe_import(self):
        spec = importlib.util.spec_from_file_location("ppm_builder", HERE / "build.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.MAX_SIZE, 32)
        self.assertFalse((self.directory / "ppm-font.ttf").exists())

    def test_bundled_font_matches_build(self):
        with TTFont(HERE / "ppm-font.ttf") as bundled, TTFont(self.generated) as generated:
            for tag in ("cmap", "glyf", "hmtx", "GSUB", "GPOS", "GDEF", "COLR", "CPAL", "name"):
                self.assertEqual(bundled[tag].compile(bundled), generated[tag].compile(generated), tag)

    def test_metadata_budgets_and_palette(self):
        with TTFont(self.generated) as font:
            self.assertEqual(font["name"].getDebugName(1), "PPM Renderer")
            self.assertIn("Michael Brackx", font["name"].getDebugName(0))
            self.assertIn("Apache License, Version 2.0", font["name"].getDebugName(13))
            self.assertEqual(font["OS/2"].fsType, 0)
            self.assertEqual(font["head"].unitsPerEm, 2048)
            self.assertLess(self.generated.stat().st_size, 700_000)
            self.assertLess(len(font.getGlyphOrder()), 9_500)
            self.assertLess(len(font["GSUB"].compile(font)), 180_000)
            self.assertLess(len(font["GPOS"].compile(font)), 260_000)
            self.assertLess(font["GSUB"].table.LookupList.LookupCount, 1150)
            self.assertEqual(len(font["CPAL"].palettes[0]), 65)
            for value, (r, g, b) in enumerate(product(range(4), repeat=3)):
                color = font["CPAL"].palettes[0][value + 1]
                self.assertEqual((color.red, color.green, color.blue, color.alpha),
                                 (r * 85, g * 85, b * 85, 255))
                glyph = f"rgb_{r}_{g}_{b}_cell"
                self.assertEqual(font["hmtx"][glyph][0], 0)
                if (r, g, b) != (3, 3, 3):
                    layer = font["COLR"].ColorLayers[glyph][0]
                    self.assertEqual((layer.name, layer.colorID), ("ink_cell", value + 1))
                else:
                    self.assertEqual(font["glyf"][glyph].numberOfContours, 0)
            # Solid RGB colors must all have layers, including full-red colors.
            # Monochrome primaries use all channels when choosing their dither.
            for rgb, contours in (((3, 0, 0), 11), ((0, 3, 0), 7), ((0, 0, 3), 14)):
                self.assertEqual(font["glyf"]["rgb_%d_%d_%d_cell" % rgb].numberOfContours, contours)
            for prefix in ("pixel", "end", "draw", "index"):
                self.assertEqual(sum(g.startswith(prefix + "_") for g in font.getGlyphOrder()), 1024)
            self.assertEqual(len(font["GPOS"].table.LookupList.Lookup[0].SubTable), 32)
            self.assertEqual(font["GPOS"].table.LookupList.Lookup[1].SubTable[0].Mark1Array.MarkCount, 64)

    @unittest.skipUnless(SHAPER, "hb-shape is required")
    def test_odt_input_and_embedding(self):
        with ZipFile(HERE / "ppm.odt") as package:
            self.assertEqual(package.namelist()[0], "mimetype")
            embeds = [name for name in package.namelist() if name.endswith(".ttf")]
            self.assertIn((HERE / "ppm-font.ttf").read_bytes(), [package.read(n) for n in embeds])
            root = ET.fromstring(package.read("content.xml"))
            sources = [odf_text(n) for n in root.findall(
                ".//{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p") if odf_text(n).startswith("P3 ")]
            self.assertEqual(len(sources), 2)
            self.assertEqual(sources[0], sources[1])
            width, height, maxval = map(int, sources[0].split()[1:4])
            self.assertEqual(maxval, 3)
            self.assertEqual(len(sources[0].split()[4:]), width * height * 3)
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
        cells = [g for g in output if g["g"].startswith("rgb_")]
        self.assertEqual(len(indices), width * height)
        self.assertEqual(len(cells), width * height)
        self.assertTrue(all(g["g"] == "hidden" or g["g"].startswith(
            ("board_", "background_", "index_", "rgb_")) for g in output))
        for i, (marker, cell, value) in enumerate(zip(indices, cells, samples)):
            self.assertEqual(marker["g"], f"index_{i}")
            self.assertEqual(cell["g"], "rgb_%d_%d_%d_cell" % value)
            self.assertEqual((cell["dx"] + width * 64, cell["dy"]),
                             (i % width * 64, 2048 - (i // width + 1) * 64))
            self.assertEqual((marker["dx"], marker["dy"]), (cell["dx"], cell["dy"]))
            self.assertEqual(cell["ax"], 0)

    def test_every_dimension_and_random_rgb(self):
        rng = random.Random(403)
        for width in range(1, 33):
            for height in range(1, 33):
                with self.subTest(width=width, height=height):
                    samples = [tuple(rng.randrange(4) for _ in range(3)) for _ in range(width * height)]
                    source = f"P3 {width} {height} 3 " + " ".join(str(c) for rgb in samples for c in rgb)
                    self.assert_image(source, width, height, samples)

    def test_boundaries_separators_and_all_colors(self):
        for rgb in product(range(4), repeat=3):
            self.assert_image("P3 1 1 3 " + " ".join(map(str, rgb)), 1, 1, [rgb])
        samples = [(3, 0, 0), (0, 3, 0), (0, 0, 3), (3, 3, 3)]
        for source in ("P3 02 02 3 3 0 0 0 3 0 0 0 3 3 3 3",
                       "P3 2 2 3 3  0   0  0 3 0   0 0 3   3 3 3   "):
            self.assert_image(source, 2, 2, samples)
        for width, height in ((1, 32), (32, 1), (32, 32)):
            for rgb in ((0, 0, 0), (3, 3, 3), (3, 0, 0)):
                samples = [rgb] * (width * height)
                self.assert_image(f"P3 {width} {height} 3 " + " ".join(str(c) for pixel in samples for c in pixel),
                                  width, height, samples)

    def test_invalid_input_has_no_partial_image(self):
        cases = ["bad", "P3", "P3 1 1 3", "P3 1 1 3 ", "P3 1 1 3 0", "P3 1 1 3 0 0",
                 "P3 1 1 3 0 0 0 1", "P3 1 1 3 0 0 0 1 2", "P3 1 1 3 0 0 0 1 2 3",
                 "P3 1 1 3 4 0 0", "P3 1 1 3 0 4 0", "P3 1 1 3 0 0 4",
                 "P3 1 1 3 -1 0 0", "P3 1 1 3 1.0 0 0", "P3 1 1 3 01 0 0",
                 "P3 1 1 3 000", "P3 1 1 3 0 00", "P3 1 1 3 0 x 0", "P3 1 1 3 0 0 0x",
                 "P3 1 1 3 0 0 0 junk", "P3 1 1 3 0 0 0#comment", "P3 1 1 3 0 0 ☃",
                 "P3 0 1 3 0 0 0", "P3 001 1 3 0 0 0", "P3 1 1 03 0 0 0",
                 "P3 1 1 15 0 0 0", "P3 1 1 255 0 0 0", "P3 1 1 0 0 0 0",
                 "P3  1 1 3 0 0 0", " P3 1 1 3 0 0 0", "P1 1 1 3 0 0 0", "P2 1 1 3 0 0 0",
                 "P6 1 1 3 0 0 0", "P3 33 1 3 " + "0 0 0 " * 33,
                 "P3 1 33 3 " + "0 0 0 " * 33, "P3 32 32 3 " + "0 0 0 " * 1025,
                 "P3 32 32 3 " + "0 0 0 " * 1023,
                 "P3 32 32 3 " + "0 0 0 " * 1024 + "0",
                 "P3 32 32 3 " + "0 0 0 " * 1024 + "0 0"]
        for source in cases:
            with self.subTest(source=source[:40]):
                output = self.shape(source)
                self.assertEqual(output[0]["g"], "error")
                self.assertEqual(sum(g["ax"] for g in output), 2049)
                self.assertTrue(all(g["g"] in ("error", "hidden") for g in output))


if __name__ == "__main__":
    unittest.main()
