# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""Turtle generator and font-shaping regressions (FontTools and hb-shape)."""

import importlib.util
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

from fontTools.ttLib import TTFont

SCRIPT = Path(__file__).with_name("build.py")
FONT = SCRIPT.with_name("turtle-font.ttf")
SHAPER = shutil.which("hb-shape")


def reference(width, height, commands):
    x, y, direction, down = width // 2, height // 2, 0, 1
    lines, blocked, color = [], False, 0
    for command in commands.lower().replace(" ", "")[:128]:
        if command in "012345":
            color = int(command)
        elif command == "l":
            direction = (direction - 1) % 4
        elif command == "r":
            direction = (direction + 1) % 4
        elif command == "u":
            down = 0
        elif command == "d":
            down = 1
        else:
            dx, dy = ((1, 0), (0, -1), (-1, 0), (0, 1))[direction]
            tx, ty = x + dx, y + dy
            if not (0 <= tx < width and 0 <= ty < height):
                blocked = True
                break
            if down:
                line = f"line_{'h' if dx else 'v'}_{min(x, tx)}_{min(y, ty)}"
                lines.append(f"{line}_c{color}" if color else line)
            x, y = tx, ty
    marker = f"blocked_{x}_{y}" if blocked else f"turtle_{x}_{y}_{direction}_{down}"
    if color:
        marker += f"_c{color}"
    return lines, marker, width * 100 + int(blocked)


class TurtleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="turtle-font-tests-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.script = cls.directory / "build.py"
        shutil.copyfile(SCRIPT, cls.script)
        cls.generated = cls.directory / "turtle-font.ttf"
        subprocess.run([sys.executable, str(cls.script)], cwd=cls.directory,
                       check=True, capture_output=True, timeout=180)
        cls.custom = cls.directory / "nested" / "custom.ttf"
        subprocess.run([sys.executable, str(cls.script), "--size", "5x3",
                        "--output", "nested/custom.ttf"], cwd=cls.directory,
                       check=True, capture_output=True, timeout=60)
        cls.maximum = cls.directory / "maximum.ttf"
        subprocess.run([sys.executable, str(cls.script), "--size", "25x25",
                        "--output", str(cls.maximum)], cwd=cls.directory,
                       check=True, capture_output=True, timeout=180)

    def test_safe_import(self):
        target = self.directory / "import-check"
        target.mkdir()
        script = target / "build.py"
        shutil.copyfile(SCRIPT, script)
        spec = importlib.util.spec_from_file_location("turtle_builder", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertFalse(list(target.glob("*.ttf")))

    def test_output_and_custom_metadata(self):
        self.assertTrue(self.custom.is_file())
        with TTFont(self.custom) as font:
            self.assertEqual(font["name"].getDebugName(1), "Turtle Graphics 5x3")
            self.assertEqual(font["hmtx"].metrics["board"][0], 500)
        subprocess.run([sys.executable, str(self.script), "--size", "3x3"],
                       cwd=self.directory, check=True, capture_output=True, timeout=60)
        self.assertTrue((self.directory / "turtle-3x3-font.ttf").is_file())

    def test_invalid_sizes_leave_no_output(self):
        for size in ("2x21", "21x0", "26x21", "21.5x21", "21", "1000x1000"):
            with self.subTest(size=size):
                output = self.directory / "invalid.ttf"
                result = subprocess.run([sys.executable, str(self.script), "--size", size,
                                         "--output", str(output)], capture_output=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_metadata_metrics_and_bounds(self):
        for path, width, height in ((FONT, 21, 21), (self.generated, 21, 21), (self.custom, 5, 3)):
            with self.subTest(font=path), TTFont(path) as font:
                self.assertEqual(font["name"].getDebugName(0), "Copyright 2026 Michael Brackx")
                self.assertIn("Apache License, Version 2.0", font["name"].getDebugName(13))
                self.assertEqual(font["name"].getDebugName(14), "https://www.apache.org/licenses/LICENSE-2.0")
                for name in font.getGlyphOrder():
                    glyph = font["glyf"][name]
                    if not glyph.numberOfContours:
                        continue
                    self.assertEqual(font["hmtx"].metrics[name][1], glyph.xMin, name)
                    if name != "board":
                        self.assertGreaterEqual(glyph.xMin + width * 100, 0, name)
                        self.assertLessEqual(glyph.xMax + width * 100, width * 100, name)
                        self.assertGreaterEqual(glyph.yMin, 0, name)
                        self.assertLessEqual(glyph.yMax, height * 100, name)

    def shape(self, path, text, features=None):
        args = [SHAPER, str(path), text, "--output-format=json"]
        if features:
            args.append("--features=" + features)
        return json.loads(subprocess.check_output(args, text=True, timeout=15))

    def assert_drawing(self, path, width, height, commands):
        actual = self.shape(path, "b" + commands)
        lines, marker, advance = reference(width, height, commands)
        names = [glyph["g"] for glyph in actual]
        self.assertEqual([name for name in names if name.startswith("line_")], lines)
        self.assertEqual([name for name in names if name.startswith(("turtle_", "blocked_"))], [marker])
        self.assertEqual(sum(glyph["ax"] for glyph in actual), advance)
        self.assertEqual(names.count("board"), 1)
        self.assertFalse(any(name.startswith(("draw_", "next_", "fresh_")) for name in names))
        self.assertTrue(all(glyph["dx"] == glyph["dy"] == 0 for glyph in actual))

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_commands_paths_and_limits(self):
        cases = ("", "f", "l", "r", "u", "d", "ll", "rrr", "llll", "rrrr",
                 "ffffl" * 4, "fl" * 4, "fr" * 4, "fllf", "uflfdrff", "uuddufdf",
                 "FFF L FF R U F D F", "lr" * 64, "lr" * 64 + "u", "u" * 127 + "f",
                 "l" * 127 + "f", "u" * 128 + "f", "fludr" * 30)
        for path, width, height in ((FONT, 21, 21), (self.generated, 21, 21), (self.custom, 5, 3)):
            for commands in cases:
                with self.subTest(font=path, commands=commands):
                    self.assert_drawing(path, width, height, commands)

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_each_boundary_stops_following_commands(self):
        for path, width, height in ((FONT, 21, 21), (self.generated, 21, 21), (self.custom, 5, 3)):
            for turns in ("", "l", "ll", "r"):
                for pen in ("", "u"):
                    commands = pen + turns + "f" * 30 + "ldfruf"
                    with self.subTest(font=path, commands=commands):
                        self.assert_drawing(path, width, height, commands)

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_random_programs_match_reference(self):
        rng = random.Random(2026)
        for path, width, height in ((FONT, 21, 21), (self.generated, 21, 21), (self.custom, 5, 3)):
            for _ in range(24):
                commands = "".join(rng.choice("ffffllrrud012345") for _ in range(140))
                with self.subTest(font=path, commands=commands):
                    self.assert_drawing(path, width, height, commands)

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_ligatures_and_case_aliases(self):
        for path in (FONT, self.generated):
            normal = self.shape(path, "bflrufdf")
            upper = self.shape(path, "BFLRUFDF")
            self.assertEqual(normal, upper)
            disabled = self.shape(path, "bff", "liga=0")
            self.assertEqual([glyph["g"] for glyph in disabled], ["b", "f", "f"])

    def test_color_palette_and_fallback_outlines(self):
        palette = ("173f39", "d64045", "2563eb", "168047", "d97706", "9333ea")
        for path in (FONT, self.generated, self.custom):
            with self.subTest(font=path), TTFont(path) as font:
                self.assertEqual(font["COLR"].version, 0)
                colors = font["CPAL"].palettes[0]
                self.assertEqual(len(colors), len(palette))
                for index, expected in enumerate(palette):
                    self.assertEqual((colors[index].red, colors[index].green, colors[index].blue,
                                      colors[index].alpha),
                                     (*bytes.fromhex(expected), 255))
                for base in ("line_h_1_1", "turtle_1_1_0_1", "blocked_1_1"):
                    for color in range(6):
                        name = f"{base}_c{color}" if color else base
                        layers = font["COLR"].ColorLayers[name]
                        self.assertEqual([(layer.name, layer.colorID) for layer in layers], [(base, color)])
                        glyph = font["glyf"][name]
                        self.assertTrue(glyph.numberOfContours, "Retain monochrome fallback")
                        self.assertEqual(font["hmtx"].metrics[name], font["hmtx"].metrics[base])

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_color_changes_preserve_strokes_pen_state_and_limits(self):
        cases = ("123450", "1f2f0f", "f1", "f1l2r3u4d5", "1uf2f3df4llf",
                 "1ffffl2ffffl3ffffl5ffffl", " 1 F L 2 F L 3 F L 4 F L 5 ",
                 "1f2llf3llf", "5" + "f" * 30 + "0", "1" * 127 + "f",
                 "1" * 128 + "2f", "f" + "2" * 127 + "1", "123450" * 24)
        for path, width, height in ((FONT, 21, 21), (self.generated, 21, 21), (self.custom, 5, 3)):
            for commands in cases:
                with self.subTest(font=path, commands=commands):
                    self.assert_drawing(path, width, height, commands)

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_maximum_canvas_with_colors(self):
        with TTFont(self.maximum) as font:
            self.assertLess(len(font.getGlyphOrder()), 65536)
            self.assertEqual(font["hmtx"].metrics["board"][0], 2500)
        cases = ("1ffffl2ffffl3ffffl5ffffl", "123450fl" * 16,
                 "u" * 126 + "5f", "5" * 128 + "1f")
        cases += tuple("5" + turns + "f" * 14 + "1" for turns in ("", "l", "ll", "r"))
        for commands in cases:
            with self.subTest(commands=commands):
                self.assert_drawing(self.maximum, 25, 25, commands)


if __name__ == "__main__":
    unittest.main()
