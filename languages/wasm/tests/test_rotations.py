import unittest, tempfile
from pathlib import Path
from wasmfont.ir import parse_wat, parse_binary, execute

class RotationTests(unittest.TestCase):
 def test_rotations(self):
  for width in (32,64):
   mask=(1<<width)-1
   for op in ('rotl','rotr'):
    with tempfile.TemporaryDirectory() as d:
     p=Path(d)/'a.wat'
     p.write_text(f'(module (func (param i{width}) (param i{width}) (result i{width}) local.get 0 local.get 1 i{width}.{op}))')
     fn=parse_wat(p)[0]
     for a in (0,1,mask,1<<(width-1),0x123456789abcdef):
      for n in (0,1,width-1,width,width+1,255):
       k=n&(width-1);v=a&mask
       want=((v<<k)|(v>>(width-k)))&mask if op=='rotl' else ((v>>k)|(v<<(width-k)))&mask
       self.assertEqual(execute(fn,[a,n]),[want])
 def test_binary_rotations(self):
  # type (i32,i32)->i32, one function, body local.get 0, local.get 1, rotl
  raw=bytes.fromhex('0061736d01000000 01070160027f7f017f 03020100 0a0901070020002001770b')
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.wasm';p.write_bytes(raw)
   self.assertEqual(execute(parse_binary(p)[0],[0x80000000,1]),[1])
if __name__=='__main__':unittest.main()
