"""Verify 32/64-bit zero tests execute in HarfBuzz GSUB."""
import random, tempfile, unittest
from pathlib import Path
from wasmfont.reference.compiler import build, encode, decode_eqz, _check_add
from wasmfont.harfbuzz import run
from wasmfont.ir import Function

class EqzBackend(unittest.TestCase):
 def test_eqz_shaping(self):
  rng=random.Random(1984)
  with tempfile.TemporaryDirectory() as d:
   for width in (32,64):
    font=Path(d)/f'eqz{width}.ttf';build(font,'eqz',width)
    for x in [0,1,2,(1<<width)-1,1<<(width-1)]+[rng.getrandbits(width) for _ in range(25)]:
     shaped=run(font,encode(x,0,'eqz',width))
     self.assertEqual(decode_eqz(shaped,width),int(x==0))
 def test_wasm_signature(self):
  for width in (32,64):
   f=Function([f'i{width}'],['i32'],[],[('local.get',0),(f'i{width}.eqz',None)])
   self.assertEqual(_check_add([f]),'eqz')
if __name__=='__main__':unittest.main()
