import unittest,tempfile
from pathlib import Path
from wasmfont.ir import parse_binary
class BinaryValidationTests(unittest.TestCase):
 def check_bad(self,raw):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bad.wasm';p.write_bytes(raw)
   with self.assertRaises(ValueError):parse_binary(p)
 def test_duplicate_section(self):
  self.check_bad(b'\0asm\1\0\0\0'+bytes([1,1,0,1,1,0]))
 def test_section_order(self):
  self.check_bad(b'\0asm\1\0\0\0'+bytes([3,1,0,1,1,0]))
 def test_unknown_section(self):
  self.check_bad(b'\0asm\1\0\0\0'+bytes([13,1,0]))
if __name__=='__main__':unittest.main()
