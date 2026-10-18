"""Differential tests of real HarfBuzz GSUB computation."""
import random,tempfile,unittest
from pathlib import Path
from wasmfont.reference.compiler import build,encode
from wasmfont.harfbuzz import run

class HarfbuzzTests(unittest.TestCase):
 def test_integer_circuits(self):
  rng=random.Random(20261008)
  with tempfile.TemporaryDirectory() as d:
   for op in ('add','sub','and','or','xor'):
    path=Path(d)/(op+'.ttf');build(path,op)
    for a,b in [(0,0),(1,2),(0xffffffff,1),(0x80000000,0x7fffffff)]+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(24)]:
     glyphs=run(path,encode(a,b,op))
     self.assertEqual(len(glyphs),33)
     self.assertTrue(all(g in ('s0','s1') for g in glyphs[:32]))
     value=sum((g=='s1')<<i for i,g in enumerate(glyphs[:32]))
     expected={'add':lambda:a+b,'sub':lambda:a-b,'and':lambda:a&b,'or':lambda:a|b,'xor':lambda:a^b}[op]()&0xffffffff
     self.assertEqual(value,expected,(op,a,b))
if __name__=='__main__':unittest.main()
