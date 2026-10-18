import random
import tempfile
import unittest
from pathlib import Path
from wasmfont.reference.compiler import build, encode, decode_count
from wasmfont.harfbuzz import run
from wasmfont.ir import Function, execute

class CountBackend(unittest.TestCase):
    def test_native_counts(self):
        rng=random.Random(931)
        with tempfile.TemporaryDirectory() as td:
            for width in (32,64):
                mask=(1<<width)-1
                for op in ('clz','ctz','popcnt'):
                    font=Path(td)/f'{width}_{op}.ttf'
                    build(font,op,width)
                    fn=Function([f'i{width}'],[f'i{width}'],[],[('local.get',0),(f'i{width}.{op}',None)])
                    values=[0,1,2,3,mask,1<<(width-1),1<<(width-2)]+[rng.getrandbits(width) for _ in range(25)]
                    for v in values:
                        shaped=run(font,encode(v,0,op,width))
                        self.assertEqual(decode_count(shaped,width,op),execute(fn,[v])[0],(width,op,v))

if __name__=='__main__':unittest.main()
