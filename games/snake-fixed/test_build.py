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

"""Builder regressions. Requires FontTools and hb-shape for shaping checks."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from fontTools.ttLib import TTFont

from build import build_font, parse_size, validate_size
from test_font import DELTAS, SHAPER, reference, shape, winning_route


class SnakeBuildTests(unittest.TestCase):
    def test_copyright_license_and_overlay_metrics(self):
        with TTFont(Path(__file__).with_name("snake-fixed-font.ttf")) as font:
            self.assertEqual(font["name"].getDebugName(0), "Copyright 2026 Michael Brackx")
            self.assertIn("Apache License, Version 2.0", font["name"].getDebugName(13))
            self.assertEqual(font["OS/2"].fsType, 0, "Allow editable document embedding")
            for name in font.getGlyphOrder():
                glyph = font["glyf"][name]
                if glyph.numberOfContours:
                    self.assertEqual(font["hmtx"].metrics[name][1], glyph.xMin, name)

    def test_size_validation(self):
        for value in ("16x10", "16X10", "16×10"):
            self.assertEqual(parse_size(value), (16, 10))
        for size in ((3, 11), (20, 0), (20.5, 11), (True, 11), (132, 1), (64, 64), (33, 32)):
            with self.subTest(size=size), self.assertRaises(ValueError):
                validate_size(*size)
        validate_size(131, 1)  # Food is reached on the final supported move.
        validate_size(32, 32)  # Largest supported cell count.

    def test_cli_output_and_default_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "build.py"
            shutil.copyfile(Path(__file__).with_name("build.py"), script)
            subprocess.run([sys.executable, str(script)], check=True, capture_output=True)
            default_font = root / "snake-fixed-font.ttf"
            original = default_font.read_bytes()
            subprocess.run([sys.executable, str(script), "--size", "8x6"],
                           check=True, capture_output=True)
            self.assertTrue((root / "snake-fixed-8x6-font.ttf").exists())
            self.assertEqual(default_font.read_bytes(), original)
            explicit = root / "nested" / "custom.ttf"
            subprocess.run([sys.executable, str(script), "--size", "16x10",
                            "--output", str(explicit)], check=True, capture_output=True)
            with TTFont(explicit) as font:
                self.assertEqual(font["name"].getDebugName(16), "Snake Fixed 16x10")
                self.assertEqual(font["OS/2"].fsType, 0)
            for value in ("20", "20x11.5", "3x11", "20x0", "132x1", "64x64", "33x32"):
                result = subprocess.run([sys.executable, str(script), "--size", value,
                                         "--output", str(root / "invalid.ttf")],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse((root / "invalid.ttf").exists())

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape to check custom boards")
    def test_custom_boards_shape_and_win(self):
        with tempfile.TemporaryDirectory() as directory:
            # Successive builds also check that dimensions do not leak between fonts.
            for width, height in ((8, 6), (16, 10), (4, 1), (131, 1), (32, 32)):
                with self.subTest(size=(width, height)):
                    output = Path(directory) / f"snake-{width}x{height}.ttf"
                    build_font(output, width, height)
                    with TTFont(output) as font:
                        self.assertEqual(font["glyf"]["board"].xMax, width * 100)
                        self.assertEqual(font["glyf"]["board"].yMax, height * 100)
                        self.assertEqual(font["name"].getDebugName(1),
                                         f"Snake Fixed {width}x{height}")
                    foods = ([(width - 2, height - 2), (1, height - 2),
                              (1, 1), (width - 2, 1)] * 2 if width >= 8 and height >= 6
                             else [(width - 1, height - 1)])
                    if (width, height) == (32, 32):
                        foods = [(30, 30), (1, 30), (1, 1)]
                    win = winning_route(foods, height)
                    for commands in ("", "a", "w" * height, "s" * height, win, win + "wasd"):
                        glyphs = shape("b" + commands, output)
                        visible = [g["g"] for g in glyphs if g["g"] not in ("ghost", *DELTAS)]
                        self.assertEqual(visible, reference(commands, width, height, foods))
                        marker = 2 if "win" in visible else int(any(g.startswith("dead_") for g in visible))
                        self.assertEqual(sum(g["ax"] for g in glyphs), width * 100 + marker)
                    self.assertIn("win", [g["g"] for g in shape("b" + win, output)])


if __name__ == "__main__":
    unittest.main()
