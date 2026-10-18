import unittest
from wasmfont.ir import Function
from wasmfont.reference.interpreter import run,WasmTrap
class Features(unittest.TestCase):
 def test_call(self):
  fs=[Function(['i32'],['i32'],[],[('local.get',0),('i32.const',1),('i32.add',None)]),Function(['i32'],['i32'],[],[('local.get',0),('call',0)])]
  self.assertEqual(run(fs,1,[41]),[42])
 def test_if(self):
  f=Function(['i32'],['i32'],['i32'],[('local.get',0),('if',None),('i32.const',11),('local.set',1),('else',None),('i32.const',22),('local.set',1),('end',None),('local.get',1)])
  self.assertEqual(run([f],0,[1]),[11]);self.assertEqual(run([f],0,[0]),[22])
 def test_loop(self):
  f=Function([],['i32'],['i32'],[('block',None),('loop',None),('local.get',0),('i32.const',5),('i32.ge_u',None),('br_if',1),('local.get',0),('i32.const',1),('i32.add',None),('local.set',0),('br',0),('end',None),('end',None),('local.get',0)])
  self.assertEqual(run([f],0,[]),[5])
 def test_traps(self):
  f=Function([],['i32'],[],[('i32.const',1),('i32.const',0),('i32.div_u',None)])
  with self.assertRaises(WasmTrap):run([f],0,[])
 def test_signed_remainder(self):
  f=Function([],['i32'],[],[('i32.const',-7),('i32.const',3),('i32.rem_s',None)])
  self.assertEqual(run([f],0,[]),[0xffffffff])
if __name__=='__main__':unittest.main()
