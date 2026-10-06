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

"""Regression checks for the shipped font. Run with python3 test_font.py."""

import itertools
import json
from pathlib import Path
import shutil
import subprocess
import unittest

FONT = Path(__file__).with_name("snake-fixed-font.ttf")
SHAPER = shutil.which("hb-shape")
DELTAS = {"w": (0, 1), "a": (-1, 0), "s": (0, -1), "d": (1, 0)}
REVERSE = {"w": "s", "a": "d", "s": "w", "d": "a"}
FOODS = [(18, 9), (1, 9), (1, 1), (18, 1)] * 2
MAX_MOVES = 128


def shape(text, font=FONT):
    output = subprocess.check_output(
        [SHAPER, str(font), text, "--output-format=json"], text=True
    )
    return json.loads(output)


def winning_route(foods, height=11):
    x, y = 2, height // 2
    route = ""
    for tx, ty in foods:
        route += ("d" if tx >= x else "a") * abs(tx - x)
        route += ("w" if ty >= y else "s") * abs(ty - y)
        x, y = tx, ty
    return route


def reference(commands, width=20, height=11, foods=FOODS):
    snake = [(0, height // 2), (1, height // 2), (2, height // 2)]
    facing = "d"
    terminal = None
    eaten = 0
    active = True
    for command in commands[:MAX_MOVES]:
        x, y = snake[-1]
        dx, dy = DELTAS[command]
        target = (x + dx, y + dy)
        if command == REVERSE[facing] or not (0 <= target[0] < width and 0 <= target[1] < height):
            terminal = f"dead_{x}_{y}"
            break
        eating = active and target == foods[eaten]
        occupied = snake if eating else snake[1:]
        if target in occupied:
            terminal = f"dead_{x}_{y}"
            break
        snake = (snake if eating else snake[1:]) + [target]
        facing = command
        if eating:
            eaten += 1
            if eaten == len(foods):
                terminal = "win"
                break
        active = foods[eaten] not in snake
    visible = [f"body_{x}_{y}" for x, y in snake[:-1]]
    x, y = snake[-1]
    visible.append(terminal or f"head_{x}_{y}_{facing}")
    food = f"{'food' if active else 'pending'}_{eaten}"
    return ["board", *([] if terminal == "win" else [food]), *visible]


@unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape to check font shaping")
class SnakeFontTests(unittest.TestCase):
    def test_start_and_board_advance(self):
        glyphs = shape("b")
        self.assertEqual([g["g"] for g in glyphs], reference(""))
        self.assertEqual(sum(g["ax"] for g in glyphs), 2000)

    def test_short_histories_match_reference(self):
        for length in range(1, 5):
            for commands in itertools.product(DELTAS, repeat=length):
                commands = "".join(commands)
                with self.subTest(commands=commands):
                    actual = [g["g"] for g in shape("b" + commands)
                              if g["g"] not in ("ghost", *DELTAS)]
                    self.assertEqual(actual, reference(commands))

    def test_walls_win_and_terminal_states(self):
        for commands in ("d" * 18, "w" * 6, "s" * 6, "waaa", winning_route(FOODS),
                         "a" + "dwas" * 10, winning_route(FOODS) + "dwas" * 4):
            with self.subTest(commands=commands):
                glyphs = shape("b" + commands)
                # Commands after a terminal state are empty control glyphs.
                actual = [g["g"] for g in glyphs if g["g"] not in ("ghost", *DELTAS)]
                self.assertEqual(actual, reference(commands))
                marker = 2 if "win" in actual else int(any(g.startswith("dead_") for g in actual))
                self.assertEqual(sum(g["ax"] for g in glyphs), 2000 + marker)

    def test_keypad_aliases(self):
        for letters, digits in (("ddwwa", "66224"), ("dwasdwas", "62486248")):
            self.assertEqual([g["g"] for g in shape("b" + letters)],
                             [g["g"] for g in shape("b" + digits)])

    def test_move_budget(self):
        moves = "dwas" * 32
        glyphs = shape("b" + moves)
        self.assertEqual([g["g"] for g in glyphs if g["g"] != "ghost"], reference(moves))
        self.assertEqual(shape("b" + moves + "d")[-1]["g"], "d")

    def test_food_pickups_grow_and_continue(self):
        route = "d" * 16 + "w" * 4
        for commands, length, food in ((route, 4, "food_1"), (route + "a" * 17, 5, "food_2")):
            glyphs = [g["g"] for g in shape("b" + commands) if g["g"] != "ghost"]
            self.assertEqual(glyphs, reference(commands))
            self.assertIn(food, glyphs)
            self.assertEqual(sum(g.startswith(("body_", "head_")) for g in glyphs), length)

    def test_self_collision_and_vacating_tail(self):
        first = "d" * 16 + "w" * 4
        for commands in (first + "asdw", first + "a" * 17 + "sdw"):
            glyphs = [g["g"] for g in shape("b" + commands) if g["g"] != "ghost"]
            self.assertEqual(glyphs, reference(commands))
        self.assertEqual(shape("b" + first + "a" * 17 + "sdw")[-1]["g"], "dead_2_8")

    def test_food_waits_until_the_target_is_unoccupied(self):
        commands = ("d" * 16 + "w" * 4 + "a" * 17 + "s" * 8 + "d" * 17 + "w" * 8
                    + "a" * 16 + "s" * 8 + "a" + "w" * 8)
        for suffix in ("", "d", "ad", "dss", "dsssss"):
            actual = [g["g"] for g in shape("b" + commands + suffix)
                      if g["g"] not in ("ghost", *DELTAS)]
            self.assertEqual(actual, reference(commands + suffix))
        blocked = [g["g"] for g in shape("b" + commands)]
        self.assertIn("pending_6", blocked)
        self.assertIn("body_1_1", blocked)
        self.assertNotIn("food_6", blocked)
        cleared = [g["g"] for g in shape("b" + commands + "d")]
        self.assertIn("food_6", cleared)
        self.assertNotIn("body_1_1", cleared)


if __name__ == "__main__":
    unittest.main()
