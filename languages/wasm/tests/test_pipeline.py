import random, tempfile, unittest
from pathlib import Path
from wasmfont.reference.pipeline import build_not_pipeline,decode_not
from wasmfont.reference.compiler import encode
from wasmfont.harfbuzz import run

class PipelineTests(unittest.TestCase):
 def test_composed_gsub(self):
  rng=random.Random(432)
  with tempfile.TemporaryDirectory() as d:
   for width in (32,64):
    mask=(1<<width)-1
    for op in ('add','sub','and','or','xor'):
     path=Path(d)/f'{op}{width}.ttf'
     build_not_pipeline(path,op,width)
     for a,b in [(0,0),(1,2),(mask,1)]+[(rng.getrandbits(width),rng.getrandbits(width)) for _ in range(8)]:
      result=decode_not(run(path,encode(a,b,op,width)),width)
      raw={'add':lambda:a+b,'sub':lambda:a-b,'and':lambda:a&b,'or':lambda:a|b,'xor':lambda:a^b}[op]()
      self.assertEqual(result,(~raw)&mask,(op,width,a,b))
