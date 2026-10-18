"""Randomized, end-to-end Wasm comparison GSUB tests."""
import random
import tempfile
import unittest
from pathlib import Path
from wasmfont.reference.compiler import build, encode, decode_comparison, _check_add
from wasmfont.harfbuzz import run
from wasmfont.ir import Function

class ComparisonBackend(unittest.TestCase):
    def test_eq_ne_native(self):
        rng = random.Random(402)
        with tempfile.TemporaryDirectory() as d:
            for width in (32,64):
                mask = (1 << width) - 1
                for op in ('eq','ne'):
                    path = Path(d) / f'{width}_{op}.ttf'
                    build(path,op,width)
                    cases = [(0,0),(1,1),(0,1),(mask,mask),(mask,0), (1 << (width-1), 1 << (width-1))]
                    cases += [(rng.getrandbits(width),rng.getrandbits(width)) for _ in range(25)]
                    cases += [(x,x) for x in (rng.getrandbits(width) for _ in range(25))]
                    for a,b in cases:
                        output=run(path,encode(a,b,op,width))
                        self.assertEqual(decode_comparison(output,width,op), int((a==b) if op=='eq' else (a!=b)), (width,op,a,b))
    def test_signature(self):
        for width in (32,64):
            for op in ('eq','ne'):
                f=Function([f'i{width}',f'i{width}'],['i32'],[], [('local.get',0),('local.get',1),(f'i{width}.{op}',None)])
                self.assertEqual(_check_add([f]),op)
    def test_invalid_result(self):
        with self.assertRaises(ValueError):
            decode_comparison(['s0','c0'],32,'eq')

if __name__=='__main__': unittest.main()
