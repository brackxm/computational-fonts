# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Independent exhaustive proof, binary policy readback, and real shaping."""
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from fontTools.ttLib import TTFont
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'shared'))
import exact_tests
from native_font import NativeFont
from policy import SimPolicy
import model


def subtables(lookup):
    for table in lookup.SubTable:
        yield table.ExtSubTable if lookup.LookupType == 7 else table


def contexts(table):
    """Read one-input/one-backtrack rules from any compiled chain format."""
    if table.Format == 3:
        assert table.BacktrackGlyphCount == table.InputGlyphCount == 1
        yield table.BacktrackCoverage[0].glyphs, table.InputCoverage[0].glyphs, table.SubstLookupRecord
    elif table.Format == 1:
        for glyph, rules in zip(table.Coverage.glyphs, table.ChainSubRuleSet):
            if rules:
                for rule in rules.ChainSubRule:
                    assert len(rule.Backtrack) == rule.InputGlyphCount == 1
                    yield rule.Backtrack, [glyph], rule.SubstLookupRecord
    elif table.Format == 2:
        back = {}
        for glyph, value in table.BacktrackClassDef.classDefs.items():
            back.setdefault(value, []).append(glyph)
        inputs = {}
        for glyph in table.Coverage.glyphs:
            inputs.setdefault(table.InputClassDef.classDefs.get(glyph, 0), []).append(glyph)
        for value, rules in enumerate(table.ChainSubClassSet):
            if rules:
                for rule in rules.ChainSubClassRule:
                    assert len(rule.Backtrack) == rule.InputGlyphCount == 1
                    yield back.get(rule.Backtrack[0], []), inputs.get(value, []), rule.SubstLookupRecord
    else:
        raise AssertionError(table.Format)


class SimTests(exact_tests.ExactFontTests):
    rules = model
    font = Path(__file__).with_name('sim-font.ttf')

    @classmethod
    def setUpClass(cls):
        cls.policy = SimPolicy()
        cls.native = NativeFont(cls.font)
        cls.ids = {node: i for i, node in enumerate(cls.policy.nodes)}

    def decode(self, names):
        states = [n for n in names if n.startswith(('r_active_', 'r_computer_won_', 'r_human_won_')) or n == 'r_header']
        errors = [n for n in names if n in ('r_invalid', 'r_malformed')]
        statuses = [n[7:] for n in names if n.startswith('status_')]
        self.assertEqual((len(states), len(statuses), len(names)), (1, 1, 3+len(errors)), names)
        if errors:
            self.assertEqual(errors, ['r_'+statuses[0]])
        node = model.INITIAL if states[0] == 'r_header' else self.policy.nodes[int(states[0].rsplit('_', 1)[1])]
        return node, None, statuses[0]

    def check_source(self, source):
        node, _, status = self.policy.replay(source)
        self.assertEqual(self.decode(self.native.shape(source)), (node, None, status), source)

    def test_policy_recurrence(self):
        """An independent bottom-up solver checks every table entry, including unreachable slots."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            table = path/'values.bin'
            table.write_bytes(self.policy.table.tobytes())
            subprocess.run(['c++', '-std=c++17', '-O3', str(Path(__file__).with_name('verify.cpp')),
                            '-o', str(path/'verify')], check=True)
            subprocess.run([str(path/'verify'), str(table)], check=True)
        self.assertEqual(self.policy.solve(model.INITIAL), (1, 15))
        for node in self.policy.nodes:
            if model.winner(node) is None:
                child = model.moves(node)[self.policy.choose(node)]
                self.assertEqual(self.policy.solve(child)[0], self.policy.solve(node)[0])

    def test_every_compiled_action(self):
        """Read back every legal/illegal action from the binary, including error lookups."""
        with TTFont(self.font) as font:
            lookups = font['GSUB'].table.LookupList.Lookup
            feature = next(r.Feature for r in font['GSUB'].table.FeatureList.FeatureRecord if r.FeatureTag == 'liga')
            def scheduled(index):
                wrapper = next(subtables(lookups[feature.LookupListIndex[index]]))
                return lookups[wrapper.SubstLookupRecord[0].LookupListIndex]
            legal, errors = {}, {}
            for table in subtables(scheduled(4)):
                for state, ligatures in table.ligatures.items():
                    for ligature in ligatures:
                        self.assertEqual(len(ligature.Component), 1)
                        key = state, ligature.Component[0]
                        self.assertNotIn(key, legal)
                        legal[key] = ligature.LigGlyph
            for table in subtables(scheduled(3)):
                for back, inputs, records in contexts(table):
                    targets = {}
                    for glyph in inputs:
                        output = [glyph]
                        for record in records:
                            self.assertEqual(record.SequenceIndex, 0)
                            for sub in subtables(lookups[record.LookupListIndex]):
                                if output and output[0] in sub.mapping:
                                    replacement = sub.mapping[output[0]]
                                    output[:1] = replacement if isinstance(replacement, list) else [replacement]
                                    break
                        targets[glyph] = output
                    for state in back:
                        if state.startswith('r_active_'):
                            for glyph, output in targets.items():
                                self.assertNotIn(glyph, errors.setdefault(state, {}))
                                errors[state][glyph] = output
            expected_legal, seen, pending = {}, set(), []
            for mode, human in (('h', 0), ('b', 1)):
                node, _, status = self.policy.settle(model.INITIAL, human)
                name = f'r_active_h{human}_{self.ids[node]}'
                expected_legal['r_header', f'input_{ord(mode)}'] = name
                pending.append(node)
            while pending:
                node = pending.pop()
                if node in seen or model.winner(node) is not None:
                    continue
                seen.add(node)
                name = f'r_active_h{node[1]}_{self.ids[node]}'
                options = model.moves(node)
                for i, token in enumerate(model.TOKENS):
                    key = name, f'move_{i}'
                    if token not in options:
                        self.assertEqual(errors[name].pop(key[1]), ['r_invalid'])
                    else:
                        child, _, status = self.policy.settle(options[token], node[1])
                        pending.append(child)
                        kind = 'active' if status == 'ready' else status
                        expected_legal[key] = f'r_{kind}_h{node[1]}_{self.ids[child]}'
                for c in range(32, 128):
                    self.assertEqual(errors[name].pop(f'input_{c}'), ['r_malformed'])
                self.assertEqual(errors.pop(name), {})
            self.assertEqual(legal, expected_legal)
            self.assertEqual(errors, {})
            self.assertEqual(len(seen), 15054)
            self.assertEqual(font['COLR'].version, 1)
            # One setup pass + eight human moves, followed by tail cleanup and status.
            self.assertEqual(len(feature.LookupListIndex), 23)

    def test_every_color_scene_retains_its_ordered_edges_and_role(self):
        import re
        with TTFont(self.font) as font:
            colr = font['COLR'].table
            cache = {}
            def leaves(paint):
                key = id(paint)
                if key not in cache:
                    if paint.Format == 1:
                        parts = [leaves(part) for part in colr.LayerList.Paint[
                            paint.FirstLayerIndex:paint.FirstLayerIndex+paint.NumLayers]]
                        cache[key] = (tuple(leaf for seq, _ in parts for leaf in seq),
                                      1+max(depth for _, depth in parts))
                    else:
                        self.assertEqual(paint.Format, 10)
                        self.assertEqual(paint.Paint.Format, 2)
                        self.assertEqual(paint.Paint.Alpha, 1.0)
                        cache[key] = (((paint.Glyph, paint.Paint.PaletteIndex),), 2)
                return cache[key]
            records = colr.BaseGlyphList.BaseGlyphPaintRecord
            self.assertGreater(len(records), 44000)
            for record in records:
                name = record.BaseGlyph
                if name.startswith('status_'):
                    # The build colors normal outcomes with palette 1 and errors with 2.
                    expected = ((name, 1 if name[7:] in ('ready', 'computer_won', 'human_won') else 2),)
                else:
                    if name == 'r_header':
                        board, human = model.INITIAL[0], 0
                    else:
                        human, index = map(int, re.search(r'_h([01])_(\d+)$', name).groups())
                        board = self.policy.nodes[index][0]
                    expected = tuple((f'edge_{i}_{side}', side)
                                     for i, power in enumerate(model.POWERS)
                                     if (side := board//power % 3)) + ((f'role_{human}', 0),)
                actual, depth = leaves(record.Paint)
                self.assertEqual(actual, expected, name)
                self.assertLessEqual(depth, 16, name)

    def test_reachable_policy_histories(self):
        rng = random.Random(20261024)
        for mode in 'hb':
            for token in model.TOKENS:
                self.check_source(mode+token)
                self.check_source(mode+token+token)
            # Real HarfBuzz, both roles, full games, invalid edges and terminal tails.
            for _ in range(150):
                source = mode
                while True:
                    node, _, status = self.policy.replay(source)
                    self.check_source(source)
                    if status != 'ready':
                        self.assertIn(status, ('computer_won', 'human_won'))
                        if mode == 'h':
                            self.assertEqual(status, 'computer_won')
                        self.check_source(source+'?🙂AB;')
                        break
                    source += rng.choice(tuple(model.moves(node)))

    def test_input_and_triangle_rules(self):
        for source in ('hAB;AB;', 'bAB;', 'hBA;', 'hAA;', 'hAG;', 'hAB;;', 'hAB',
                       'h\tAB;\nCD; ', 'hAB;🙂', 'hAB;\ue000', 'hAB;\0'):
            self.check_source(source)
        # All twenty triangles, for either colour, are losses; crossing segments do not count.
        from itertools import combinations
        for vertices in combinations('ABCDEF', 3):
            for side in (0, 1):
                code = sum((side+1)*model.POWERS[model.TOKENS.index(a+b+';')]
                           for a, b in combinations(vertices, 2))
                self.assertEqual(model.winner((code, 1-side)), 1-side)
        self.assertIsNone(model.winner((sum(model.POWERS[model.TOKENS.index(t)] for t in ('AD;', 'BE;', 'CF;')), 1)))

    def test_maximum_length_and_tail(self):
        from functools import lru_cache
        @lru_cache(None)
        def longest(node, human):
            if model.winner(node) is not None:
                return ''
            return max((token+longest(self.policy.settle(child, human)[0], human)
                        for token, child in model.moves(node).items()), key=len)
        for mode, human, maximum in (('h', 0, 8), ('b', 1, 7)):
            root = self.policy.settle(model.INITIAL, human)[0]
            suffix = longest(root, human)
            self.assertEqual(suffix.count(';'), maximum)
            self.check_source(mode+suffix)
            self.check_source(mode+suffix+'AB;?🙂'+('CD;'*100))
            self.check_source(mode+suffix[:-1])


if __name__ == '__main__':
    unittest.main()
