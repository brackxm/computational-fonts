# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""PBM shaping and artifact regressions. Requires FontTools and hb-shape."""

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
from testing import FontFixture, odf_text


class BuildTests(FontFixture, unittest.TestCase):
    project = HERE
    def test_safe_import(self):
        script = HERE / "build.py"
        spec = importlib.util.spec_from_file_location("pbm_builder", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.MAX_SIZE, 32)
        self.assertFalse((self.directory / "pbm-font.ttf").exists())

    def test_bundled_font_matches_build(self):
        with TTFont(HERE / "pbm-font.ttf") as bundled, TTFont(self.generated) as generated:
            for tag in ("cmap", "glyf", "hmtx", "GSUB", "GPOS", "GDEF", "COLR", "CPAL", "name"):
                self.assertEqual(bundled[tag].compile(bundled), generated[tag].compile(generated), tag)

    def test_metadata_and_budgets(self):
        for path in (HERE / "pbm-font.ttf", self.generated):
            with self.subTest(font=path), TTFont(path) as font:
                self.assertEqual(font["name"].getDebugName(1), "PBM Renderer")
                self.assertIn("Michael Brackx", font["name"].getDebugName(0))
                self.assertIn("Apache License, Version 2.0", font["name"].getDebugName(13))
                self.assertEqual(font["OS/2"].fsType, 0)
                self.assertEqual(font["head"].unitsPerEm, 2048)
                self.assertLess(path.stat().st_size, 625_000)
                self.assertLess(len(font.getGlyphOrder()), 8_500)
                self.assertLess(len(font["GSUB"].compile(font)), 170_000)
                self.assertLess(len(font["GPOS"].compile(font)), 230_000)
                self.assertLess(font["GSUB"].table.LookupList.LookupCount, 1100)
                self.assertEqual(font["GPOS"].table.LookupList.Lookup[0].LookupType, 9)

    def test_color_and_monochrome_geometry(self):
        with TTFont(self.generated) as font:
            self.assertEqual(font["CPAL"].palettes[0][0].hex(), "#FFFFFFFF")
            self.assertEqual(font["CPAL"].palettes[0][1].hex(), "#000000FF")
            for width in range(1, 33):
                for height in range(1, 33):
                    self.assertEqual(font["hmtx"][f"board_{width}"][0], width * 64)
                    background = f"background_{width}_{height}"
                    self.assertEqual(font["glyf"][background].numberOfContours, 0,
                                     "Monochrome fallback must leave white pixels transparent")
                    self.assertEqual(font["hmtx"][background][0], 0)
                    layer = font["COLR"].ColorLayers[background][0]
                    self.assertEqual(layer.colorID, 0)
                    glyph = font["glyf"][layer.name]
                    self.assertEqual((glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax),
                                     (-width * 64, 2048 - height * 64, 0, 2048))
            self.assertEqual(font["glyf"]["white_cell"].numberOfContours, 0)
            glyph = font["glyf"]["black_cell"]
            self.assertEqual((glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax), (0, 0, 64, 64))
            self.assertEqual(font["COLR"].ColorLayers["black_cell"][0].colorID, 1)
            self.assertEqual(font["hmtx"]["black_cell"][0], 0)
            for index in range(1024):
                self.assertEqual(font["glyf"][f"index_{index}"].numberOfContours, 0)

    def test_positioning_is_shared_across_heights(self):
        with TTFont(self.generated) as font:
            lookup = font["GPOS"].table.LookupList.Lookup[0]
            self.assertEqual(len(lookup.SubTable), 32)
            for wrapper in lookup.SubTable:
                table = wrapper.ExtSubTable
                self.assertEqual(len(table.BaseCoverage.glyphs), 1)
                width = int(table.BaseCoverage.glyphs[0].split("_")[1])
                self.assertEqual(table.ClassCount, width * 32)
                for anchor in table.BaseArray.BaseRecord[0].BaseAnchor:
                    self.assertGreaterEqual(anchor.XCoordinate, 0)
                    self.assertLess(anchor.XCoordinate, width * 64)
                    self.assertGreaterEqual(anchor.YCoordinate, 0)
                    self.assertLess(anchor.YCoordinate, 2048)

    @unittest.skipUnless(SHAPER, "hb-shape is required")
    def test_odt_input_and_embedding(self):
        with ZipFile(HERE / "pbm.odt") as package:
            self.assertEqual(package.namelist()[0], "mimetype")
            embeds = [name for name in package.namelist() if name.endswith(".ttf")]
            self.assertIn((HERE / "pbm-font.ttf").read_bytes(), [package.read(name) for name in embeds])
            root = ET.fromstring(package.read("content.xml"))
            paragraphs = root.findall(".//{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p")
            sources = [odf_text(node) for node in paragraphs if odf_text(node).startswith("P1 ")]
            self.assertEqual(len(sources), 2)
            self.assertEqual(sources[0], sources[1])
            width, height = map(int, sources[0].split()[1:3])
            bits = "".join(sources[0].split()[3:])
            self.assertEqual(len(bits), width * height)
            output = json.loads(subprocess.check_output(
                [SHAPER, str(self.generated), sources[0], "--output-format=json"], timeout=10))
            self.assertEqual(output[0]["g"], f"board_{width}")


@unittest.skipUnless(SHAPER, "hb-shape is required")
class ShapingTests(FontFixture, unittest.TestCase):
    project = HERE
    def shape(self, source, path=None):
        return json.loads(subprocess.check_output(
            [SHAPER, str(path or self.generated), source, "--output-format=json"], timeout=10))

    def assert_image(self, source, width, height, bits, path=None):
        output = self.shape(source, path)
        self.assertEqual(output[0]["g"], f"board_{width}")
        self.assertEqual(output[1]["g"], f"background_{width}_{height}")
        self.assertEqual(sum(item["ax"] for item in output), width * 64)
        indices = [item for item in output if item["g"].startswith("index_")]
        pixels = [item for item in output if item["g"] in ("white_cell", "black_cell")]
        self.assertEqual(len(indices), width * height)
        self.assertEqual(len(pixels), width * height)
        cursor = width * 64
        for index, (marker, item, bit) in enumerate(zip(indices, pixels, bits)):
            self.assertEqual(marker["g"], f"index_{index}")
            self.assertEqual(item["g"], "black_cell" if bit == "1" else "white_cell")
            self.assertEqual(item["ax"], 0)
            self.assertEqual(cursor + item["dx"], (index % width) * 64)
            self.assertEqual(item["dy"], 2048 - (index // width + 1) * 64)
            self.assertEqual((marker["dx"], marker["dy"]), (item["dx"], item["dy"]))
        self.assertFalse(any(item["g"].startswith(("pixel_", "end_", "header_", "draw_")) for item in output))

    def test_every_dimension_and_random_rasters(self):
        rng = random.Random(401)
        for width in range(1, 33):
            for height in range(1, 33):
                with self.subTest(width=width, height=height):
                    bits = "".join(str(rng.randrange(2)) for _ in range(width * height))
                    self.assert_image(f"P1 {width} {height} {bits}", width, height, bits)

    def test_spaced_pixels_and_leading_zero_dimensions(self):
        for source in ("P1 2 2 0 1  1 0", "P1 02 02 01 10", "P1 2 2 0110   "):
            self.assert_image(source, 2, 2, "0110")
        bits = "01" * 512
        self.assert_image("P1 32 32 " + " ".join(bits), 32, 32, bits)

    def test_extreme_rasters_with_bundled_font(self):
        for width, height in ((1, 1), (1, 32), (32, 1), (32, 32)):
            for bit in "01":
                bits = bit * (width * height)
                self.assert_image(f"P1 {width} {height} {bits}", width, height, bits,
                                  HERE / "pbm-font.ttf")

    def test_invalid_input_has_only_error_and_hidden_glyphs(self):
        cases = ["bad", "P1", "P1 2 2", "P1 2 2 ", "P1 2 2 011", "P1 2 2 01100",
                 "P1 2 2 01x0", "P1 2 2 01 2 0", "P1 2 2 0110 junk", "P1 2 2 0110 P1 1 1 0",
                 "P4 2 2 0110", "p1 2 2 0110", "P2 2 2 0110", "P3 2 2 0110",
                 "P1 0 2 00", "P1 33 1 " + "0" * 33, "P1 1 33 " + "0" * 33,
                 "P1 -2 2 0110", "P1 2.0 2 0110", "P1 002 2 0110", "P1 2 02. 0110",
                 "P1 22 0110", "P1 2 20110", "P1  2 2 0110", " P1 2 2 0110",
                 "P1 32 32 " + "0" * 1025, "P1 32 32 " + "0" * 1023,
                 "P1 2 2 0110#comment", "P1 2 2 01☃0"]
        for source in cases:
            with self.subTest(source=source[:40]):
                output = self.shape(source)
                self.assertEqual(output[0]["g"], "error")
                self.assertEqual(sum(item["ax"] for item in output), 2049)
                self.assertTrue(all(item["g"] in ("error", "hidden") for item in output))


if __name__ == "__main__":
    unittest.main()
