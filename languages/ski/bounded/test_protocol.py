"""Build reproducibility, configuration limits and fail-closed protocol checks."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from .build import build
from .runtime import Machine, MachineError, InputOverflow
from .syntax import parse, prefix
from .layout import validate
from .config import DEFAULT_FONT, ROOT


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=Machine(DEFAULT_FONT)

    @classmethod
    def tearDownClass(cls):
        cls.m.close()

    def test_single_shaping_call(self):
        m=self.m
        with patch.object(m.hb,'shape',wraps=m.hb.shape) as shaping:
            # The oracle is deliberately unusable during production evaluation.
            with patch('bounded.reference.step',side_effect=AssertionError('oracle called')):
                r=m.run('S K K (S K K a)')
        self.assertEqual(shaping.call_count,1)
        self.assertEqual((r.expression,r.steps),('a',4))

    def test_feature_off_is_not_evaluation(self):
        text,fuel=self.m.encode('I a')
        gs=self.m.hb.shape(text,{'calt':0})
        self.assertEqual(gs[0],'seek')
        self.assertEqual(gs[1],'n0_A')
        with self.assertRaises(MachineError):self.m.decode(gs,fuel)

    def test_output_corruption(self):
        r=self.m.run('I a')
        for index,value in [(0,'seek'),(1,'n1_a'),(3,'n2_a'),(64,'vA'),(-1,'f99')]:
            gs=list(r.glyphs);gs[index]=value
            with self.subTest(index=index):
                with self.assertRaises(MachineError):self.m.decode(gs,32)
        with self.assertRaises(MachineError):self.m.decode(r.glyphs[:-1],32)

    def test_fuel_and_source_validation(self):
        for fuel in (-1,33,True,1.5):
            with self.subTest(fuel=fuel):
                with self.assertRaises(ValueError):self.m.run('I a',fuel)
        for text in ('','@','@Ia b','(',')','a$','()','I (a','@I','E'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):self.m.run(text)
        with self.assertRaises(InputOverflow):self.m.run(' '.join(['I']*1000))
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/'invalid'/'font.ttf'
            for depth,rounds in ((2,8),(7,8),(True,8),(5,-1),(5,33),(5,False),
                                 (6,17),(6,32),(6,None),(6,'16')):
                with self.subTest(depth=depth,rounds=rounds):
                    with self.assertRaises(ValueError):build(output,depth,rounds)
            self.assertFalse(output.parent.exists())
        for depth,rounds in ((3,0),(3,32),(5,32),(6,0),(6,8),(6,16)):
            with self.subTest(depth=depth,rounds=rounds):
                validate(depth,rounds)

    def test_sidecar_digest(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'bad.ttf'
            shutil.copyfile(DEFAULT_FONT,path)
            meta=dict(self.m.meta);meta['font_sha256']='0'*64
            path.with_suffix('.json').write_text(json.dumps(meta))
            with self.assertRaises(MachineError):Machine(path)

    def test_malformed_configuration_is_a_structured_cli_error(self):
        cases = [None, [], 1, 'machine', {}, {'schema': 1}, {'schema': True}]
        for field, values in {'depth': [None, True, '5', 100], 'rounds': [None, False, '32', 33, 16],
                              'capacity': [None, True, '63', 0],
                              'font_sha256': [None, 123, [], 'invalid'],
                              'chars': [None, [], '', {'seek': False}]}.items():
            missing = dict(self.m.meta)
            del missing[field]
            cases.append(missing)
            for value in values:
                cases.append(dict(self.m.meta, **{field: value}))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'bad.ttf'
            shutil.copyfile(DEFAULT_FONT, path)
            for case in cases:
                with self.subTest(case=repr(case)[:100]):
                    path.with_suffix('.json').write_text(json.dumps(case))
                    with patch('bounded.runtime.HarfBuzz') as shaper:
                        with self.assertRaises(MachineError):
                            Machine(path)
                        shaper.assert_not_called()
                    result = subprocess.run([sys.executable, str(ROOT / 'run.py'), 'I a', '--font', str(path)],
                                            text=True, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, '')
                    self.assertEqual(json.loads(result.stderr)['status'], 'error')
            path.with_suffix('.json').write_text('{')
            with self.assertRaises(MachineError):
                Machine(path)

    def test_small_configurations_and_reproducibility(self):
        with tempfile.TemporaryDirectory() as td:
            for depth,budget in ((3,0),(3,1),(4,8)):
                path=Path(td)/f'd{depth}b{budget}.ttf'
                build(path,depth,budget)
                with Machine(path) as m:
                    result=m.run('I a')
                    self.assertEqual((result.status,result.expression,result.steps),
                                     ('budget','@Ia',0) if budget==0 else ('normal','a',1))
                    self.assertEqual(m.run('S K K',0).status,'normal')
                    if budget>=2:self.assertEqual(m.run('S K K a').expression,'a')
            rebuilt=Path(td)/'repro.ttf'
            build(rebuilt,5,32)
            self.assertEqual(hashlib.sha256(rebuilt.read_bytes()).hexdigest(),
                             self.m.meta['font_sha256'])
            self.assertEqual(rebuilt.with_suffix('.json').read_bytes(),
                             DEFAULT_FONT.with_suffix('.json').read_bytes())


if __name__=='__main__':unittest.main()
