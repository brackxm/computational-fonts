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

"""Dynamic Snake builder and shaping regressions; requires FontTools and hb-shape."""

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
FONT = SCRIPT.with_name("snake-dynamic-font.ttf")
SHAPER = shutil.which("hb-shape")
MOVES = {"w": (0, 1), "a": (-1, 0), "s": (0, -1), "d": (1, 0)}


def reference(width, height, commands):
    snake = [(0, height // 2), (1, height // 2), (2, height // 2)]
    food = (width - 1, min(height - 1, height // 2 + 8 - (width - 3)))
    terminal = 0
    for command in commands[:8]:
        x, y = snake[-1]
        dx, dy = MOVES[command]
        target = (x + dx, y + dy)
        if target == snake[-2] or not (0 <= target[0] < width and 0 <= target[1] < height):
            terminal = 1
            break
        if target == food:
            snake.append(target)
            terminal = 2
            break
        snake = snake[1:] + [target]
    return snake, terminal


class DynamicSnakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="snake-dynamic-tests-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.script = cls.directory / "build.py"
        shutil.copyfile(SCRIPT, cls.script)
        cls.generated = cls.directory / "snake-dynamic-font.ttf"
        subprocess.run([sys.executable, str(cls.script)], cwd=cls.directory,
                       check=True, capture_output=True, timeout=30)

    def test_import_does_not_write_a_font(self):
        original = self.generated.read_bytes()
        self.generated.unlink()
        code = ("import importlib.util; "
                "spec=importlib.util.spec_from_file_location('dynamic_snake', 'build.py'); "
                "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)")
        result = subprocess.run([sys.executable, "-c", code], cwd=self.directory,
                                check=True, capture_output=True, timeout=15)
        self.assertEqual(result.stdout, b"")
        self.assertFalse(self.generated.exists())
        self.generated.write_bytes(original)

    def test_explicit_output_from_an_unrelated_directory(self):
        cwd = self.directory / "work"
        cwd.mkdir()
        original = self.generated.read_bytes()
        subprocess.run([sys.executable, str(self.script), "--output", "nested/custom.ttf"],
                       cwd=cwd, check=True, capture_output=True, timeout=30)
        self.assertTrue((cwd / "nested/custom.ttf").is_file())
        self.assertEqual(self.generated.read_bytes(), original)

    def test_glyph_metrics_and_license(self):
        for path in (FONT, self.generated):
            with self.subTest(font=path), TTFont(path) as font:
                self.assertEqual(font["name"].getDebugName(0), "Copyright 2026 Michael Brackx")
                self.assertIn("Apache License, Version 2.0", font["name"].getDebugName(13))
                for name in font.getGlyphOrder():
                    glyph = font["glyf"][name]
                    if glyph.numberOfContours:
                        self.assertEqual(font["hmtx"].metrics[name][1], glyph.xMin, name)

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_all_board_sizes_match_reference(self):
        rng = random.Random(42)
        for width in range(4, 11):
            for height in range(4, 11):
                food_y = min(height - 1, height // 2 + 8 - (width - 3))
                win = "d" * (width - 3) + "w" * (food_y - height // 2)
                commands = ("", "a", win, win + "wasd", "d" * 9, "w" * 9,
                            "".join(rng.choice(tuple(MOVES)) for _ in range(9)))
                for path in (FONT, self.generated):
                    for moves in commands:
                        with self.subTest(size=(width, height), font=path, moves=moves):
                            output = subprocess.check_output(
                                [SHAPER, str(path), f"{width}x{height}b{moves}",
                                 "--output-format=json"], text=True)
                            glyphs = json.loads(output)
                            snake, terminal = reference(width, height, moves)
                            self.assertEqual(sum(g["ax"] for g in glyphs), terminal)
                            bodies = [tuple(map(int, g["g"].split("_")[1:]))
                                      for g in glyphs if g["g"].startswith("body_")]
                            self.assertEqual(bodies, snake[:-1])
                            if terminal != 2:
                                heads = [tuple(map(int, g["g"].split("_")[1:]))
                                         for g in glyphs if g["g"].startswith("head_")]
                                self.assertEqual(heads, [snake[-1]])


if __name__ == "__main__":
    unittest.main()
