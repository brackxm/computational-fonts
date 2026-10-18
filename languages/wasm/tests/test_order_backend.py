"""Native GSUB unsigned and signed relational comparison differential tests."""
import random, tempfile, unittest
from pathlib import Path
from wasmfont.reference.compiler import build, encode, decode_comparison, _check_add
from wasmfont.harfbuzz import run
from wasmfont.ir import Function

class OrderBackend(unittest.TestCase):
 def test_relations(self):
  rng=random.Random(937)
  with tempfile.TemporaryDirectory() as d:
   for width in (32,64):
    mask=(1<<width)-1
    values=[0,1,2,mask,mask-1,1<<(width-1),(1<<(width-1))-1]
    cases=[(a,b) for a in values for b in values]+[(rng.getrandbits(width),rng.getrandbits(width)) for _ in range(30)]
    for op in ('lt_u','le_u','gt_u','ge_u','lt_s','le_s','gt_s','ge_s'):
     path=Path(d)/f'{width}_{op}.ttf';build(path,op,width)
     f=Function([f'i{width}',f'i{width}'],['i32'],[],[('local.get',0),('local.get',1),(f'i{width}.{op}',None)])
     self.assertEqual(_check_add([f]),op)
     for a,b in cases:
      x,y=a,b
      if op.endswith('_s'):
       x=x-(1<<width) if x>>(width-1) else x
       y=y-(1<<width) if y>>(width-1) else y
      relation=op[:2]
      expected={'lt':x<y,'le':x<=y,'gt':x>y,'ge':x>=y}[relation]
      self.assertEqual(decode_comparison(run(path,encode(a,b,op,width)),width,op),int(expected),(width,op,a,b))
if __name__=='__main__':unittest.main()
