import unittest
from wasmfont.ir import Function
from wasmfont.reference.interpreter import run, WasmTrap
from wasmfont.state import MachineState, MemoryTrap

class MemoryTests(unittest.TestCase):
 def test_store_load(self):
  f=Function([],['i32'],[],[('i32.const',12),('i32.const',0x12345678),('i32.store',0),('i32.const',12),('i32.load',0)])
  self.assertEqual(run([f],0,[]),[0x12345678])
 def test_sign_extension(self):
  f=Function([],['i32'],[],[('i32.const',0),('i32.const',255),('i32.store8',0),('i32.const',0),('i32.load8_s',0)])
  self.assertEqual(run([f],0,[]),[0xffffffff])
 def test_bounds(self):
  f=Function([],['i32'],[],[('i32.const',65535),('i32.load',0)])
  with self.assertRaises(MemoryTrap):run([f],0,[])
 def test_grow(self):
  f=Function([],['i32'],[],[('i32.const',1),('memory.grow',None)])
  state=MachineState(max_pages=2)
  self.assertEqual(run([f],0,[],state=state),[1]);self.assertEqual(state.pages,2)
  self.assertEqual(run([f],0,[],state=state),[0xffffffff])
 def test_globals(self):
  state=MachineState(globals=[3],global_types=['i32'],mutable=[True])
  f=Function([],['i32'],[],[('global.get',0),('i32.const',2),('i32.add',None),('global.set',0),('global.get',0)])
  self.assertEqual(run([f],0,[],state=state),[5]);self.assertEqual(state.globals,[5])
 def test_immutable(self):
  state=MachineState(globals=[3],global_types=['i32'],mutable=[False])
  f=Function([],[],[],[('i32.const',4),('global.set',0)])
  with self.assertRaises(WasmTrap):run([f],0,[],state=state)
if __name__=='__main__':unittest.main()
