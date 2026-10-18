import unittest
from wasmfont.ir import Function
from wasmfont.reference.lowering import lower_function

class SymbolicOptimizationTests(unittest.TestCase):
    def lower(self, code, width=32):
        ty=f'i{width}'
        return lower_function(Function([ty,ty],[ty],[],code))
    def test_constant_folding_and_select(self):
        for width in (32,64):
            ty=f'i{width}'
            ops=[('local.get',0),('local.get',1),(ty+'.add',None),
                 (ty+'.const',7),(ty+'.const',3),(ty+'.sub',None),
                 (ty+'.const',1),('select',None),
                 (ty+'.const',0),(ty+'.xor',None)]
            lowered=self.lower(ops,width)
            self.assertEqual((lowered.operation,lowered.inversions),('add',0))
    def test_drop_and_equal_select(self):
        code=[('local.get',0),('local.get',1),('i32.xor',None),
              ('i32.const',123),('drop',None),
              ('local.get',0),('local.get',1),('i32.xor',None),
              ('local.get',0),('select',None)]
        self.assertEqual(self.lower(code).operation,'xor')
    def test_dynamic_select_rejected(self):
        code=[('local.get',0),('local.get',1),('local.get',0),('select',None)]
        with self.assertRaises(NotImplementedError): self.lower(code)
    def test_underflow(self):
        with self.assertRaises(ValueError): self.lower([('drop',None)])

if __name__=='__main__': unittest.main()
