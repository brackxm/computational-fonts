import tempfile, unittest
from pathlib import Path
from wasmfont.module import load_binary
from wasmfont.reference.interpreter import run

def leb(n):
 out=[]
 while True:
  x=n&127;n>>=7;out.append(x|(128 if n else 0))
  if not n:return bytes(out)
def section(n,b):return bytes([n])+leb(len(b))+b
class ModuleTests(unittest.TestCase):
 def make(self,extra):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'m.wasm';p.write_bytes(b'\0asm\1\0\0\0'+extra)
   return load_binary(p)
 def test_memory_data(self):
  m=self.make(section(5,b'\1\1\1\2')+section(11,b'\1\0\x41\x08\x0b\3abc'))
  s=m.instantiate();self.assertEqual(s.memory[8:11],b'abc');self.assertEqual(s.pages,1)
 def test_globals(self):
  m=self.make(section(6,b'\1\x7f\1\x41\x2a\x0b'))
  s=m.instantiate();self.assertEqual(s.globals,[42]);self.assertEqual(s.mutable,[True])
 def test_oob_segment(self):
  with self.assertRaises(Exception):self.make(section(5,b'\1\0\0')+section(11,b'\1\0\x41\0\x0b\1x'))
 def test_reject_imports(self):
  with self.assertRaises(NotImplementedError):self.make(section(2,b'\0'))
if __name__=='__main__':unittest.main()
