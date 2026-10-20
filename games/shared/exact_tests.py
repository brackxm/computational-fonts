# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Real-font conformance checks shared by finite-policy game implementations."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from exactgame import Policy, STATUS
from native_font import NativeFont, transport


class ExactFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = Policy(cls.rules)
        cls.native = NativeFont(cls.font)
        cls.ids = {node: i for i, node in enumerate(cls.policy.nodes)}
        with TTFont(cls.font) as font:
            cls.last_tokens = {name: token for name, token in zip(
                [n for n in font.getGlyphOrder() if n.startswith('r_last_') and n != 'r_last_none'],
                cls.rules.TOKENS)}

    @classmethod
    def tearDownClass(cls):
        cls.native.close()

    def decode(self, names):
        states = [n for n in names if n.startswith('r_') and not n.startswith('r_last_')]
        lasts = [n for n in names if n.startswith('r_last_')]
        statuses = [n[7:] for n in names if n.startswith('status_')]
        self.assertEqual((len(names), len(states), len(lasts), len(statuses)), (4, 1, 1, 1), names)
        node = self.rules.INITIAL if states[0] == 'r_header' else self.policy.nodes[int(states[0].rsplit('_', 1)[1])]
        return node, self.last_tokens.get(lasts[0]), statuses[0]

    def check_source(self, source):
        self.assertEqual(self.decode(self.native.shape(source)), self.policy.replay(source), source)

    def test_policy_recurrence(self):
        for node, options in self.policy.graph.items():
            winner, distance = self.policy.solve(node)
            terminal = self.rules.winner(node)
            if terminal is not None:
                self.assertEqual((winner, distance), (terminal, 0))
                continue
            outcomes = [self.policy.solve(child) for child in options.values()]
            wins = [d for w, d in outcomes if w == node[1]]
            self.assertEqual((winner, distance), (node[1], 1+min(wins)) if wins
                             else (1-node[1], 1+max(d for _, d in outcomes)))
            self.assertEqual(self.policy.solve(options[self.policy.choose(node)]), (winner, distance-1))

    def test_every_compiled_action(self):
        with TTFont(self.font) as font, tempfile.TemporaryDirectory() as temp:
            codes = {name: chr(0xf0000+i) for i, name in enumerate(font.getGlyphOrder())}
            table = CmapSubtable.newSubtable(12)
            table.platformID, table.platEncID, table.language = 3, 10, 0
            table.cmap = dict(font.getBestCmap())
            table.cmap.update({ord(c): name for name, c in codes.items()})
            font['cmap'].tables.append(table)
            path = Path(temp)/'test.ttf'
            font.save(path)
            native = NativeFont(path)
            try:
                def run(state, text):
                    return self.decode(native.shape_text(codes['board']+codes[state]+codes['r_last_none']+transport(text)[1:]))
                for name in codes:
                    if name.startswith('r_active_'):
                        node = self.policy.nodes[int(name.rsplit('_', 1)[1])]
                        for token in self.rules.TOKENS:
                            expected = (self.policy.settle(self.policy.graph[node][token], node[1])
                                        if token in self.policy.graph[node] else (node, None, 'invalid'))
                            self.assertEqual(run(name, token), expected, (name, token))
                        for text in ('?', 'h', 'b', self.rules.TOKENS[0][:-1], '🙂', '\ue000', '\0'):
                            self.assertEqual(run(name, text), (node, None, 'malformed'), (name, text))
                    elif name.startswith(('r_invalid_', 'r_malformed_', 'r_computer_won_', 'r_human_won_')):
                        status = name[2:].rsplit('_', 2)[0]
                        node = self.policy.nodes[int(name.rsplit('_', 1)[1])]
                        self.assertEqual(run(name, 'h?🙂'+self.rules.TOKENS[0]*4), (node, None, status))
            finally:
                native.close()

    def test_reachable_policy_histories(self):
        for mode in 'hb':
            pending, seen = [mode], set()
            while pending:
                source = pending.pop()
                self.check_source(source)
                node, last, status = self.policy.replay(source)
                if status != 'ready':
                    self.check_source(source+'garbage🙂')
                elif (node, last) not in seen:
                    seen.add((node, last))
                    pending.extend(source+token for token in self.policy.graph[node])

    def test_transport_and_metrics(self):
        for source in ('', '?', 'H', 'h?', 'h🙂', 'h\0', 'h\ue001', 'h'+self.rules.TOKENS[0][:-1],
                       ' \th\r\n ', 'h'+self.rules.TOKENS[-1]):
            self.check_source(source)
        args = ['hb-shape', str(self.font), '--text=\ue000h\ue001', '--output-format=json']
        glyphs = json.loads(subprocess.check_output(args, text=True))
        self.assertEqual(sum(g['ax'] for g in glyphs), 1800+STATUS[self.policy.replay('h')[2]])
        glyphs = json.loads(subprocess.check_output(args+['--features=-liga'], text=True))
        self.assertFalse(any(g['g'].startswith('status_') for g in glyphs))
        with TTFont(self.font) as font:
            self.assertEqual(font['OS/2'].fsType, 0)
            self.assertEqual(font['head'].unitsPerEm, 1000)
            self.assertLess(len(font.getGlyphOrder()), 65536)

    def test_smooth_typography(self):
        with TTFont(self.font) as font:
            self.assertIn('Copyright 2015 Google Inc.', font['name'].getDebugName(0))
            self.assertIn('Michael Brackx', font['name'].getDebugName(0))
            self.assertIn('Roboto', font['name'].getDebugName(7))
            for name in ('board', 'role_0', 'status_ready'):
                glyph = font['glyf'][name]
                _, _, flags = glyph.getCoordinates(font['glyf'])
                self.assertTrue(any(not flag & 1 for flag in flags), name)
            board = font['glyf']['board']
            self.assertGreaterEqual(board.xMin, 0)
            self.assertLessEqual(board.xMax, 1800)
            self.assertLessEqual(board.yMax, 1250)
