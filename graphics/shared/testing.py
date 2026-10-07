# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""Shared Netpbm test fixtures; no font is built on import."""

from pathlib import Path
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile

from fontTools.ttLib import TTFont

def odf_text(node):
    value = node.text or ""
    for child in node:
        if child.tag == "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}s":
            value += " " * int(child.get("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}c", "1"))
        else:
            value += odf_text(child)
        value += child.tail or ""
    return value


class FontFixture:
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="netpbm-tests-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.generated = cls.directory / "nested" / "test.ttf"
        subprocess.run([sys.executable, str(cls.project / "build.py"), "--output", "nested/test.ttf"],
                       cwd=cls.directory, check=True, capture_output=True, timeout=60)


class BuilderOptionsTests:
    """Shared option checks, mixed into each project's build suite."""

    def builder_module(self):
        spec = importlib.util.spec_from_file_location("options_builder", self.project / "build.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def check_custom_font(self, path, size):
        with TTFont(path) as font:
            self.assertEqual(font["head"].unitsPerEm, size * 64)
            self.assertEqual(font["hhea"].ascent, size * 64)
            self.assertEqual(font["hmtx"]["error"][0], size * 64 + 1)
            self.assertLessEqual(font["glyf"]["error"].xMax, size * 64)
            self.assertNotIn(f"board_{size + 1}", font.getGlyphOrder())
            self.assertEqual(font["GPOS"].table.LookupList.Lookup[0].SubTableCount, size)
        shaper = shutil.which("hb-shape")
        if not shaper:
            return
        magic, maxval, sample, cell = {
            "pbm": (1, "", "1", "black_cell"),
            "pgm": (2, "15 ", "7", "gray_7_cell"),
            "ppm": (3, "3 ", "3 0 1", "rgb_3_0_1_cell"),
        }[self.project.name]

        def shape(width, height, count):
            source = f"P{magic} {width} {height} {maxval}" + " ".join([sample] * count)
            return json.loads(subprocess.check_output(
                [shaper, str(path), "--text=" + source, "--output-format=json"], timeout=10))

        output = shape(size, size, size * size)
        self.assertEqual(output[0]["g"], f"board_{size}")
        self.assertEqual(output[1]["g"], f"background_{size}_{size}")
        self.assertEqual(sum(g["ax"] for g in output), size * 64)
        cells = [g for g in output if g["g"] == cell]
        indices = [g for g in output if g["g"].startswith("index_")]
        self.assertEqual(len(cells), size * size)
        self.assertEqual(len(indices), size * size)
        for i, (marker, pixel) in enumerate(zip(indices, cells)):
            self.assertEqual(marker["g"], f"index_{i}")
            self.assertEqual((pixel["dx"] + size * 64, pixel["dy"]),
                             (i % size * 64, size * 64 - (i // size + 1) * 64))
        for width, height, count in ((size + 1, 1, size + 1), (1, size + 1, size + 1),
                                     (size, size, size * size - 1), (size, size, size * size + 1)):
            output = shape(width, height, count)
            self.assertEqual(output[0]["g"], "error")
            self.assertEqual(sum(g["ax"] for g in output), size * 64 + 1)
            self.assertTrue(all(g["g"] in ("error", "hidden") for g in output))

    def test_configurable_max_size(self):
        module = self.builder_module()
        for size in (1, 3):
            path = self.directory / f"api-{size}.ttf"
            module.build_font(path, max_size=size)
            self.check_custom_font(path, size)
        path = self.directory / "cli-5.ttf"
        subprocess.run([sys.executable, str(self.project / "build.py"), "--max-size", "5",
                        "--output", path.name], cwd=self.directory, check=True,
                       capture_output=True, timeout=60)
        self.check_custom_font(path, 5)
        # An omitted option still uses 64 after custom builds in the same process.
        path = self.directory / "default-again.ttf"
        module.build_font(path)
        with TTFont(path) as font, TTFont(self.generated) as expected:
            for tag in ("head", "GSUB", "GPOS", "glyf", "hmtx"):
                if tag == "head":
                    self.assertEqual(font[tag].unitsPerEm, expected[tag].unitsPerEm)
                else:
                    self.assertEqual(font[tag].compile(font), expected[tag].compile(expected))

    def test_invalid_max_size_does_not_write(self):
        module = self.builder_module()
        path = self.directory / "invalid" / "font.ttf"
        for size in (0, -1, 65, True, 1.5, "3", None):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, "integer from 1 to 64"):
                module.build_font(path, max_size=size)
        for size in ("0", "-1", "65", "bad", "1.5"):
            result = subprocess.run([sys.executable, str(self.project / "build.py"),
                                     "--max-size", size, "--output", str(path)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(path.parent.exists())
