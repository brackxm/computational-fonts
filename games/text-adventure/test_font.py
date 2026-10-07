# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Verify the shipped and freshly compiled adventure through actual shaping."""

from collections import deque
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

from fontTools.ttLib import TTFont
from story import (COMMANDS, INITIAL, MAX_COMMANDS, WINNING_COMMANDS,
                   state_name, transition)

DIRECTORY = Path(__file__).resolve().parent
SHAPER = shutil.which("hb-shape")


def history(commands):
    return "start;" + "".join(command + ";" for command in commands)


class FontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="font-adventure-tests-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        for name in ("build.py", "story.py"):
            shutil.copyfile(DIRECTORY / name, cls.directory / name)
        cls.generated = cls.directory / "text-adventure-font.ttf"
        subprocess.run([sys.executable, str(cls.directory / "build.py")], cwd=cls.directory,
                       check=True, capture_output=True, timeout=120)
        cls.fonts = [DIRECTORY / "text-adventure-font.ttf", cls.generated]

    def shape_many(self, font, inputs):
        result = subprocess.run([SHAPER, str(font), "--text-file=-", "--output-format=json"],
                                input="\n".join(inputs) + "\n", text=True, check=True,
                                capture_output=True, timeout=60)
        outputs = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(outputs), len(inputs))
        return outputs

    def assert_scene(self, glyphs, state, message):
        self.assertEqual([g["g"] for g in glyphs if g["g"].startswith("world_")], [state_name(state)])
        self.assertEqual([g["g"] for g in glyphs if g["g"].startswith("message_")], ["message_" + message])
        self.assertEqual(sum(g["ax"] for g in glyphs), 5760)

    def test_import_does_not_generate_files(self):
        generated_bytes = self.generated.read_bytes()
        self.generated.unlink()
        try:
            subprocess.run([sys.executable, "-c", "import build"], cwd=self.directory,
                           check=True, capture_output=True, timeout=15)
            self.assertFalse(self.generated.exists())
        finally:
            # Other checks need the already verified fresh build.
            self.generated.write_bytes(generated_bytes)

    def test_ascii_coverage_geometry_and_license(self):
        for path in self.fonts:
            with self.subTest(font=path), TTFont(path) as font:
                self.assertEqual(set(font.getBestCmap()), set(range(32, 127)))
                self.assertIn("Apache License, Version 2.0", font["name"].getDebugName(13))
                self.assertEqual(font["name"].getDebugName(0), "Copyright 2026 Michael Brackx")
                self.assertEqual(font["OS/2"].fsType, 0, "Allow editable font embedding in the ODT")
                for name in font.getGlyphOrder():
                    glyph = font["glyf"][name]
                    if glyph.numberOfContours:
                        self.assertEqual(font["hmtx"].metrics[name][1], glyph.xMin, name)
                        self.assertGreaterEqual(glyph.yMin, 0, name)
                        self.assertLessEqual(glyph.yMax, 4000, name)
                        self.assertLessEqual(glyph.xMax, 5760, name)

    @unittest.skipUnless(SHAPER, "Install hb-shape for actual game checks")
    def test_every_reachable_world_and_command_shapes_correctly(self):
        routes, queue = {INITIAL: ()}, deque([INITIAL])
        while queue:
            state = queue.popleft()
            for command in COMMANDS:
                target, _ = transition(state, command)
                if target not in routes:
                    routes[target] = routes[state] + (command,)
                    queue.append(target)
        inputs, expected = [], []
        for state, route in routes.items():
            for command in COMMANDS:
                inputs.append(history(route + (command,)))
                expected.append(transition(state, command))
        self.assertEqual(len(routes), 156)
        for font in self.fonts:
            for glyphs, (state, message), text in zip(self.shape_many(font, inputs), expected, inputs):
                with self.subTest(font=font, text=text):
                    self.assert_scene(glyphs, state, message)
                    self.assertTrue(all(g["g"] == "ghost" or g["g"].startswith(("world_", "message_"))
                                        for g in glyphs), glyphs)

    @unittest.skipUnless(SHAPER, "Install hb-shape for actual game checks")
    def test_puzzles_and_complete_escape_have_independent_expected_results(self):
        cases = [
            ((), (0, 0, 0, 0, 0, 0), "ready"),
            (("south",), (0, 0, 0, 0, 0, 0), "gate"),
            (("north", "east"), (1, 0, 0, 0, 0, 0), "locked"),
            (("north", "unlock door"), (1, 0, 0, 0, 0, 0), "need_key"),
            (("west", "north"), (3, 0, 0, 0, 0, 0), "dark"),
            (("light lamp",), (0, 0, 0, 0, 0, 0), "need_lamp"),
            (("take key",), (0, 0, 0, 0, 0, 0), "absent"),
            (("east", "take key", "take key"), (2, 1, 0, 0, 0, 0), "already"),
            (("east", "take key", "west", "north", "unlock door"), (1, 1, 1, 0, 0, 0), "unlocked"),
            (WINNING_COMMANDS[:-1], (0, 15, 1, 1, 1, 1), "installed"),
            (WINNING_COMMANDS, (7, 15, 1, 1, 1, 1), "won"),
            (WINNING_COMMANDS + ("north", "take key", "unknown"), (7, 15, 1, 1, 1, 1), "won"),
        ]
        for font in self.fonts:
            results = self.shape_many(font, [history(route) for route, _, _ in cases])
            for glyphs, (route, state, message) in zip(results, cases):
                with self.subTest(font=font, commands=route):
                    self.assert_scene(glyphs, state, message)

    @unittest.skipUnless(SHAPER, "Install hb-shape for actual game checks")
    def test_whole_command_boundaries_unknown_words_and_recovery(self):
        invalid = ["northeast", "xnorth", "north!", "take key please", "start", "", "!" * 24,
                   "north north", "takekey", "use crystal!", "e junk", "go north", "southwest"]
        rng = random.Random(15)
        invalid += ["x" + "".join(rng.choice("abcxyz123 !") for _ in range(22)) for _ in range(30)]
        inputs = [history((command,)) for command in invalid]
        inputs += [history((command, "east", "take key")) for command in invalid]
        for font in self.fonts:
            outputs = self.shape_many(font, inputs)
            for command, glyphs in zip(invalid, outputs[:len(invalid)]):
                with self.subTest(font=font, invalid=command):
                    self.assert_scene(glyphs, INITIAL, "unknown")
            for glyphs in outputs[len(invalid):]:
                self.assert_scene(glyphs, (2, 1, 0, 0, 0, 0), "key")

    @unittest.skipUnless(SHAPER, "Install hb-shape for actual game checks")
    def test_aliases_case_partial_input_and_move_limit(self):
        inputs = ["START;E;TAKE KEY;W;N;UNLOCK DOOR;",
                  "start;east;take key;west;north;unlock door;east;take crystal;west;south;install crystal;",
                  history(("look",) * MAX_COMMANDS + ("east",)),
                  "start;east;take k", "start;east;northgarbage", "xstart;east;",
                  history(("help",)),
                  history(("x" * 24,) * (MAX_COMMANDS - 1) + ("east",))]
        for font in self.fonts:
            outputs = self.shape_many(font, inputs)
            self.assert_scene(outputs[0], (1, 1, 1, 0, 0, 0), "unlocked")
            self.assert_scene(outputs[1], (0, 9, 1, 0, 0, 1), "installed")
            self.assert_scene(outputs[2], INITIAL, "look")
            self.assert_scene(outputs[3], (2, 0, 0, 0, 0, 0), "moved")
            self.assert_scene(outputs[4], (2, 0, 0, 0, 0, 0), "moved")
            self.assertFalse(any(g["g"].startswith("world_") for g in outputs[5]))
            self.assert_scene(outputs[6], INITIAL, "help")
            self.assert_scene(outputs[7], (2, 0, 0, 0, 0, 0), "moved")


if __name__ == "__main__":
    unittest.main()
