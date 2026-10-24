# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""Fresh and bundled font checks against an independent replay model."""

import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from fontTools.ttLib import TTFont
from reference import MAX_TURNS, replay, glyph_registers

PROJECT = Path(__file__).resolve().parent
SHAPER = shutil.which("hb-shape")
START, END = "\ue000", "\ue001"


def shape(source, font, features=None, transport=False):
    source = source.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    if transport:
        source = "".join(chr(0xE100+ord(c)) for c in source)
    args = [SHAPER, str(font), "--text="+START+source+END, "--output-format=json"]
    if features:
        args.append("--features="+features)
    return json.loads(subprocess.check_output(args, text=True, timeout=15))


def maximal_record(turns=MAX_TURNS):
    # Four transfers every turn; preserve occupancy by moving back and forth.
    # This synthetic occupancy fixture is not claimed to be a legal game.
    return "(;FF[4]GM[6]CA[UTF-8]" + ";W[11hgghhggh]" * turns + ")"


class OracleTests(unittest.TestCase):
    def test_opening_and_separate_counters(self):
        board, status = replay("(;GM[6];W[31hefe])")
        self.assertEqual(status, "complete")
        self.assertEqual((board["h"], board["f"], board["e"]), (2, 4, 2))
        self.assertEqual([board[k] for k in ("barW", "barB", "offW", "offB")], [0]*4)


class BackgammonFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="backgammon-font-tests-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.fresh = cls.directory / "nested" / "fresh.ttf"
        subprocess.run([sys.executable, str(PROJECT / "build.py"), "--output", "nested/fresh.ttf"],
                       cwd=cls.directory, check=True, capture_output=True, timeout=180)
        cls.fonts = [PROJECT / "backgammon-font.ttf", cls.fresh]

    def test_safe_import_and_default_output(self):
        # Import from an unrelated working directory without producing output.
        subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {str(PROJECT)!r}); import build"],
                       cwd=self.directory, check=True)
        self.assertFalse((self.directory / "backgammon-font.ttf").exists())
        import importlib.util
        spec = importlib.util.spec_from_file_location('backgammon_builder', PROJECT / 'build.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        from unittest.mock import patch
        with patch.object(builder, 'build_font') as build, patch.object(sys, 'argv', [str(PROJECT / 'build.py')]):
            builder.main()
        build.assert_called_once_with(PROJECT / 'backgammon-font.ttf')

    def test_metadata_artwork_color_and_reproducibility(self):
        for path in self.fonts:
            with self.subTest(font=path), TTFont(path) as font:
                self.assertEqual(font["name"].getDebugName(1), "Backgammon SGF Replay")
                self.assertIn("Copyright 2026 Michael Brackx", font["name"].getDebugName(0))
                self.assertNotIn("Google", font["name"].getDebugName(0))
                self.assertIn("Game Sans", font["name"].getDebugName(10))
                self.assertIn("Apache License, Version 2.0", font["name"].getDebugName(13))
                self.assertEqual(font["OS/2"].fsType, 0)
                self.assertEqual(font["COLR"].version, 0)
                self.assertEqual(len(font["CPAL"].palettes[0]), 8)
                self.assertEqual(font["hmtx"]["board"][0], 1800)
                for name, code in (("complete", 1), ("malformed", 2), ("unsupported", 3), ("limit", 4), ("state_error", 5)):
                    self.assertEqual(font["hmtx"]["status_"+name][0], code)
                for name in font.getGlyphOrder():
                    glyph = font["glyf"][name]
                    if glyph.numberOfContours:
                        self.assertEqual(font["hmtx"][name][1], glyph.xMin, name)
                        self.assertGreaterEqual(glyph.yMin, 0, name)
                        self.assertLessEqual(glyph.yMax, 1100, name)
                self.assertLess(len(font.getGlyphOrder()), 3000, "No board/history enumeration")
        with TTFont(self.fonts[0]) as a, TTFont(self.fonts[1]) as b:
            for tag in ("GSUB", "glyf", "hmtx", "COLR", "CPAL", "cmap", "name"):
                self.assertEqual(a[tag].compile(a), b[tag].compile(b), tag)

    def assert_replay(self, source, status="complete"):
        expected, model_status = replay(source)
        self.assertEqual(model_status, status, source)
        for font in self.fonts:
            with self.subTest(font=font.name, source=source):
                output = shape(source, font)
                names = [g["g"] for g in output]
                self.assertEqual([n for n in names if n.startswith("status_")], ["status_"+status])
                code = {"complete": 1, "malformed": 2, "unsupported": 3, "limit": 4, "state_error": 5}[status]
                self.assertEqual(sum(g["ax"] for g in output), 1800+code)
                self.assertEqual(names.count("board"), 1)
                self.assertFalse(any(n.startswith(("p_", "source_", "dest_", "hit_", "die_", "begin_")) for n in names))
                self.assertTrue(all(g["dx"] == g["dy"] == 0 for g in output))
                if expected:
                    self.assertEqual([n for n in names if n.startswith("r_")], glyph_registers(expected))
                    for player, sign in (("W", 1), ("B", -1)):
                        self.assertEqual(sum(max(0, expected[c]*sign) for c in "abcdefghijklmnopqrstuvwx")+
                                         expected["bar"+player]+expected["off"+player], 15)

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_start_opening_both_colors_and_wrappers(self):
        for source in ("(;)", "(;GM[6])", "(;FF[4]GM[6]CA[UTF-8])", "(;CA[UTF-8]GM[6]FF[4])",
                       "(;GM[6]W[31hefe])", "(;GM[6];W[31hefe])", "(;GM[6];B[31qtst])",
                       "(;GM[6];W[31hefe];B[31qtst])", " ( ; GM [ 6 ] ; W [ 31 he fe ] ) "):
            self.assert_replay(source)

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_hits_bar_entry_and_bearing_off(self):
        turns = ["W[11hg]", "B[11ab]", "W[11hb]", "B[11sg]", "W[11yx]", "B[11ys]"]
        for length in range(1, len(turns)+1):
            self.assert_replay("(;GM[6];"+";".join(turns[:length])+")")
        for source in ("(;GM[6];W[66fefdfc];W[66fzezdzcz])",
                       "(;GM[6];B[66szszszsz])", "(;GM[6];W[11fz];B[11sz];W[11fz];B[11sz])",
                       "(;GM[6];W[66xhxhmhmh];W[66mhmhmhfh];W[66fhfhfhfh])",
                       "(;GM[6];B[66aqaqlqlq];B[66lqlqlqsq];B[66sqsqsqsq])",
                       "(;GM[6];W[66xzxzmzmz];B[66azazlzlz];W[66mzmzmzfz];B[66lzlzlzqz];"
                       "W[66fzfzfzfz];B[66qzqzszsz];W[66hzhzhz];B[66szszsz])"):
            self.assert_replay(source)

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_entry_hits_and_full_bar_counters(self):
        # Enter onto a blot, then hit back from the other player's bar. Each
        # transfer must decrement its own bar and increment only the opponent's.
        turns = ["W[11hg]", "B[11ag]", "W[11yg]", "B[11yg]"]
        for length in (3, 4):
            self.assert_replay("(;GM[6];"+";".join(turns[:length])+")")
        # Put all fifteen checkers on each player's bar in separate fixtures.
        # The attacker returns to its source after each hit, freeing the target.
        for player, sources, attacker, target in (("W", "xxmmmmmhhhfffff", "a", "b"),
                                                   ("B", "aalllllqqqsssss", "x", "v")):
            opponent = "B" if player == "W" else "W"
            turns = [f";{player}[11{source}{target}];{opponent}[11{attacker}{target}{target}{attacker}]"
                     for source in sources]
            record = "(;GM[6]"+"".join(turns)
            state, status = replay(record+")")
            self.assertEqual(status, "complete")
            self.assertEqual((state["bar"+player], state["bar"+opponent]), (15, 0))
            self.assert_replay(record+")")
            # Entry from a full bar into a growing stack, through the 32nd turn.
            entry = f";{player}[66"+("y"+target)*4+"]"
            self.assert_replay(record+entry+entry+")")
        for record in ("(;GM[6];W[11hg];B[11ag];B[11ys])",
                       "(;GM[6];B[11ab];W[11hb];W[11yx])"):
            self.assert_replay(record, "state_error")

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_doubles_no_movement_and_limits(self):
        for source in ("(;GM[6];B[66])", "(;GM[6];W[11];B[66])", "(;GM[6];W[66hgghhggh])",
                       "(;GM[6]"+";B[66]"*32+")", "(;GM[6]"+";B[66]"*33+")",
                       "(;GM[6]"+";B[66]"*MAX_TURNS+")", maximal_record()):
            self.assert_replay(source)
        self.assert_replay("(;GM[6]"+";B[66]"*(MAX_TURNS+1)+")", "limit")
        self.assert_replay(maximal_record()[:-1]+";B[66])", "limit")
        for font in self.fonts:
            accepted = shape("(;GM[6]"+";B[66]"*MAX_TURNS+")", font)
            rejected = shape("(;GM[6]"+";B[66]"*MAX_TURNS+";W[31hefe])", font)
            self.assertEqual([g["g"] for g in accepted if g["g"].startswith("r_")],
                             [g["g"] for g in rejected if g["g"].startswith("r_")],
                             "The rejected extra turn must not change board, counters, or dice")

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_late_moves_hits_and_entry_at_new_limit(self):
        # Make observable board changes at the very end, rather than only
        # cycling back to the same position in the maximal-workload fixture.
        self.assert_replay("(;GM[6]"+";B[66]"*(MAX_TURNS-1)+";W[31hefe])")
        self.assert_replay(maximal_record(MAX_TURNS-1)[:-1]+";B[31qtst])")
        self.assert_replay("(;GM[6]"+";B[66]"*(MAX_TURNS-4)+
                           ";W[11hg];B[11ag];W[11yg];B[11yg])")

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_malformed_unsupported_and_inconsistent(self):
        for source in ("", "()", "(;GM[6]", "(;GM[6];W[31hefe]", "(;GM[6];W[31hefe]))",
                       "(;GM[6];W[])", "(;GM[6];W[71])", "(;GM[6];W[31h])", "(;GM[6];W[31zh])",
                       "(;GM[6];W[31hgghhgghhg])", "(;GM[6];W[31hefe])junk", "(;GM[6];)"):
            self.assert_replay(source, "malformed")
        for source in ("(;GM[1])", "(;GM[6]GM[6])", "(;GM[6]FF[3])", "(;GM[6]C[note])",
                       "(;GM[6]MI[length:7])", "(;GM[6]AW[a])", "(;GM[6];W[double])",
                       "(;GM[6];B[take])", "(;GM[6];W[drop])", "(;GM[6];W[31hefe](;B[66]))",
                       "(;GM[6])(;GM[6])"):
            self.assert_replay(source, "unsupported")
        for source in ("(;GM[6];W[11ab])", "(;GM[6];W[11hl])", "(;GM[6];W[11yx])",
                       "(;GM[6];B[11as];W[11aa])"):
            self.assert_replay(source, "state_error")

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_random_occupancy_records_against_reference(self):
        rng = random.Random(20261019)
        for _ in range(30):
            source = "(;GM[6]"
            for turn in range(rng.randint(1, MAX_TURNS)):
                player = "WB"[turn % 2]
                pairs = ""
                for _ in range(rng.randint(0, 4)):
                    state, status = replay(source+f";{player}[11{pairs}])")
                    self.assertEqual(status, "complete")
                    sign = 1 if player == "W" else -1
                    starts = [c for c in "abcdefghijklmnopqrstuvwx" if state[c]*sign > 0]
                    if state["bar"+player]:
                        starts.append("y")
                    if not starts:
                        break
                    start = rng.choice(starts)
                    ends = [c for c in "abcdefghijklmnopqrstuvwx" if state[c]*sign >= -1 and c != start]+["z"]
                    pairs += start+rng.choice(ends)
                source += f";{player}[{rng.randint(1,6)}{rng.randint(1,6)}{pairs}]"
            self.assert_replay(source+")")

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_disabled_shaping_and_cost(self):
        disabled = shape("(;GM[6])", self.fonts[0], "liga=0")
        self.assertFalse(any(g["g"].startswith("status_") for g in disabled))
        start = time.monotonic()
        self.assert_replay(maximal_record())
        elapsed = time.monotonic()-start
        print(f"\nMaximal {MAX_TURNS}-turn replay, both fonts including process startup: {elapsed:.3f}s")
        self.assertLess(elapsed, 10, "Unexpected shaping cost / engine budget exhaustion")

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_browser_transport_aliases(self):
        for source in ("(;GM[6])", "(;GM[6];W[31hefe];B[31qtst])", maximal_record(),
                       maximal_record()[:-1]+";B[66])", "(;GM[6];W[double])", "(;GM[6];W[11ab])",
                       "(;GM[6];W[11hg];B[11ag];W[11yg];B[11yg])",
                       "(;GM[6];W[66fefdfc];W[66fzezdzcz])"):
            for font in self.fonts:
                raw = shape(source, font)
                encoded = shape(source, font, transport=True)
                self.assertEqual([g["g"] for g in raw], [g["g"] for g in encoded])
                self.assertEqual(sum(g["ax"] for g in raw), sum(g["ax"] for g in encoded))

    @unittest.skipUnless(SHAPER, "Install HarfBuzz's hb-shape for shaping checks")
    def test_truncations_and_mutations_never_report_false_completion(self):
        opening = "(;FF[4]GM[6]CA[UTF-8];W[31hefe];B[31qtst])"
        sources = {opening[:i] for i in range(len(opening))}
        # Damage complete records near both ends and near the clock-pass limit.
        # Diagnose success independently; exact error precedence is deliberately
        # not shared between the streaming font and the Python regex parser.
        rng = random.Random(20261020)
        for _ in range(64):
            source = rng.choice([opening, maximal_record()])
            index = rng.randrange(len(source)+1)
            char = rng.choice("()[];BWGM16hz\\! ")
            operation = rng.randrange(3)
            source = (source[:index]+char+source[index:] if operation == 0 else
                      source[:index]+source[index+1:] if operation == 1 else
                      source[:index]+char+source[index+1:])
            sources.add(source)
        for source in sorted(sources):
            state, expected_status = replay(source)
            for font in self.fonts:
                with self.subTest(source=source, font=font.name):
                    output = shape(source, font)
                    names = [g["g"] for g in output]
                    self.assertEqual("status_complete" in names, expected_status == "complete")
                    self.assertEqual(sum(g["ax"] for g in output) == 1801, expected_status == "complete")
                    if state:
                        self.assertEqual([n for n in names if n.startswith("r_")], glyph_registers(state))


if __name__ == "__main__":
    unittest.main()
