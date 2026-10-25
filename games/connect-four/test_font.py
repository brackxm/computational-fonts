# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Distribution checks for the independently certified Connect Four font."""
import hashlib
import json
from pathlib import Path
import random
import sys
import unittest

from fontTools.misc.xmlWriter import XMLWriter

from fontTools.ttLib import TTFont
from shaping import Shaper

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'research'))
from kernel import STATUS
from policy_io import read_json, source_bytes
from runtime_reference import Reference, decode_shape
import independent as rules


class FontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = Reference(read_json(HERE/'research/controller.json.gz'))
        cls.proof = read_json(HERE/'research/winning-policy-verification.json')
        cls.shaper = Shaper(HERE/'connect-four-font.ttf')

    @classmethod
    def tearDownClass(cls):
        cls.shaper.close()

    def assert_history(self, source, transport=False):
        state = self.reference.replay(source)
        shaped = self.shaper.run(source, transport=transport)
        self.assertEqual(decode_shape(shaped),
                         (state.red, state.yellow, state.last, 1000+STATUS[state.status]), source)
        self.assertEqual(len(shaped), 64, source)
        return state

    def test_complete_certificate_and_build_identity(self):
        self.assertTrue(self.proof['verified'])
        self.assertTrue(self.proof['empty_board'])
        self.assertEqual(self.proof['maximum_plies'], 41)
        digest = hashlib.sha256(source_bytes(HERE/'research/winning-policy.json.gz')).hexdigest()
        self.assertEqual(digest, self.proof['certificate_sha256'])
        abi = read_json(HERE/'connect-four-font.abi.json')
        self.assertEqual(abi['certificate_sha256'], digest)
        self.assertEqual(abi['controller_sha256'], hashlib.sha256(source_bytes(HERE/'research/controller.json.gz')).hexdigest())
        self.assertEqual(abi['font_sha256'], hashlib.sha256((HERE/'connect-four-font.ttf').read_bytes()).hexdigest())
        self.assertEqual(len(abi['registers']), 63)
        self.assertFalse((HERE/'upstream').exists())

    def test_verification_records_match_distribution(self):
        report = read_json(HERE/'verification.json')
        implementation = read_json(HERE/'research/font-verification.json')
        measurements = read_json(HERE/'connect-four-font.json')
        abi = read_json(HERE/'connect-four-font.abi.json')
        artifacts = ('connect-four-font.ttf', 'connect-four-font.woff2',
                     'connect-four-font.abi.json', 'connect-four-font.json')
        for name in artifacts:
            with self.subTest(artifact=name):
                self.assertEqual(report['artifacts_sha256'].get(name),
                                 hashlib.sha256((HERE/name).read_bytes()).hexdigest())
        self.assertEqual(set(report['artifacts_sha256']), set(artifacts))
        self.assertEqual(report['implementation'], implementation)
        self.assertEqual(implementation['font_sha256'], report['artifacts_sha256']['connect-four-font.ttf'])
        self.assertEqual(implementation['font_sha256'], abi['font_sha256'])
        self.assertEqual(implementation['controller_sha256'], abi['controller_sha256'])
        self.assertEqual(implementation['certificate_sha256'], self.proof['certificate_sha256'])
        self.assertEqual(report['strategy'], self.proof)
        self.assertEqual(report['font'], measurements)
        self.assertEqual(measurements, {key: abi[key] for key in measurements})
        for suffix, key in (('ttf', 'ttf_bytes'), ('woff2', 'woff2_bytes')):
            self.assertEqual(measurements[key], (HERE/f'connect-four-font.{suffix}').stat().st_size)
        sizes = report['size_optimization']
        self.assertEqual(sizes['woff2_bytes'], measurements['woff2_bytes'])
        self.assertEqual(sizes['bytes_saved'], sizes['previous_woff2_bytes']-sizes['woff2_bytes'])
        self.assertAlmostEqual(sizes['reduction_percent'],
                               100*(1-sizes['woff2_bytes']/sizes['previous_woff2_bytes']), places=4)
        self.assertAlmostEqual(sizes['reduction_from_first_percent'],
                               100*(1-sizes['woff2_bytes']/sizes['first_independent_woff2_bytes']), places=4)
        self.assertAlmostEqual(sizes['ratio_to_historical_gpl3'],
                               sizes['woff2_bytes']/sizes['historical_gpl3_woff2_bytes'], places=4)
        browser = report['browser']
        self.assertEqual(browser['woff2_sha256'], report['artifacts_sha256']['connect-four-font.woff2'])
        self.assertIn(browser['woff2_url'], (HERE/'playground.html').read_text())
        self.assertEqual(browser['screenshot_sha256'],
                         hashlib.sha256((HERE/browser['screenshot']).read_bytes()).hexdigest())

    def test_license_and_woff2_payload(self):
        with TTFont(HERE/'connect-four-font.ttf', lazy=True) as font, TTFont(HERE/'connect-four-font.woff2', lazy=True) as web:
            self.assertIn('Apache License', font['name'].getDebugName(13))
            self.assertNotIn('GPL', font['name'].getDebugName(13))
            self.assertNotIn('Google', font['name'].getDebugName(0))
            self.assertIn('Game Sans', font['name'].getDebugName(10))
            for tag in ('GDEF', 'cmap', 'hmtx', 'glyf', 'COLR', 'CPAL'):
                self.assertEqual(font.reader[tag], web.reader[tag], tag)
            # Desktop and web use different physical packing, but every layout
            # field (including record order and lookup indices) stays identical.
            class Digest:
                def __init__(self):
                    self.hash = hashlib.sha256()
                def write(self, data):
                    self.hash.update(data.encode() if isinstance(data, str) else data)
                def flush(self):
                    pass
            a, b = Digest(), Digest()
            font['GSUB'].toXML(XMLWriter(a), font)
            web['GSUB'].toXML(XMLWriter(b), web)
            self.assertEqual(a.hash.digest(), b.hash.digest(), 'logical GSUB')

    def test_invalid_full_and_terminal_histories(self):
        witness = self.proof['longest_human_history']
        for source in ('b', 'b1', 'b135', 'b1351', 'b13511', 'b4444', 'bb', 'b0',
                       'b!', 'bλ', 'b🙂', 'b\ue162', 'b\n', 'x', witness, witness+'1'):
            self.assert_history(source, transport=True)
        self.assertEqual(sum(g[1] for g in self.shaper.run('b', enabled=False)), 0)

    def test_every_prefix_of_certified_longest_game(self):
        witness = self.proof['longest_human_history']
        for i in range(1, len(witness)+1):
            self.assert_history(witness[:i])
        state = self.assert_history(witness)
        self.assertEqual(state.status, 'win')
        self.assertEqual((state.red | state.yellow).bit_count(), 41)

    def test_legal_complete_games(self):
        rng = random.Random(20261024)
        for _ in range(30):
            source = 'b'
            while True:
                state = self.assert_history(source)
                if state.status != 'ready':
                    self.assertEqual(state.status, 'win', source)
                    break
                source += str(rng.choice(rules.legal(state.red, state.yellow))+1)


if __name__ == '__main__':
    unittest.main()
