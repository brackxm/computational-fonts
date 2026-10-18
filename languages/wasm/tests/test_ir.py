import unittest,tempfile
from pathlib import Path
from wasmfont.ir import parse_wat,parse_binary,execute

class IRTests(unittest.TestCase):
 def test_wat_locals(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.wat';p.write_text('(module (func (param $x i32) (result i32) (local $y i32) local.get $x i32.const 3 i32.mul local.set $y local.get $y i32.const 7 i32.add))')
   f=parse_wat(p)[0];self.assertEqual(execute(f,[12]),[43])
 def test_wrapping_and_signed_shift(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.wat';p.write_text('(module (func (param i64) (result i64) local.get 0 i64.const 1 i64.add))')
   self.assertEqual(execute(parse_wat(p)[0],[(1<<64)-1]),[0])
   p.write_text('(module (func (param i32) (result i32) local.get 0 i32.const 2 i32.shr_s))')
   self.assertEqual(execute(parse_wat(p)[0],[0xfffffff8]),[0xfffffffe])
 def test_binary(self):
  # type (i32,i32)->i32, function 0, code with locals and arithmetic
  sections=[bytes([1,7,1,0x60,2,0x7f,0x7f,1,0x7f]),bytes([3,2,1,0]),bytes([10,9,1,7,0,0x20,0,0x20,1,0x6a,0x0b])]
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.wasm';p.write_bytes(b'\0asm\x01\0\0\0'+b''.join(sections))
   self.assertEqual(execute(parse_binary(p)[0],[0xffffffff,2]),[1])
if __name__=='__main__':unittest.main()
