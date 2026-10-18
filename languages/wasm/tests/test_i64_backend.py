"""Differential checks for native 64-bit GSUB circuits."""
import random, tempfile, unittest
from pathlib import Path
from wasmfont.reference.compiler import build, encode
from wasmfont.harfbuzz import run

class TestI64(unittest.TestCase):
 def test_i64(self):
  rng=random.Random(8463)
  mask=(1<<64)-1
  with tempfile.TemporaryDirectory() as d:
   for op in ('add','sub','and','or','xor'):
    path=Path(d)/(op+'.ttf');build(path,op,64)
    for a,b in [(0,0),(1,2),(mask,1),(1<<63,mask)]+[(rng.getrandbits(64),rng.getrandbits(64)) for _ in range(12)]:
     result=run(path,encode(a,b,op,64))
     self.assertEqual(len(result),65)
     self.assertTrue(all(g in ('s0','s1') for g in result[:64]))
     actual=sum((g=='s1')<<i for i,g in enumerate(result[:64]))
     expected={'add':a+b,'sub':a-b,'and':a&b,'or':a|b,'xor':a^b}[op]&mask
     self.assertEqual(actual,expected,(op,a,b))
if __name__=='__main__':unittest.main()
