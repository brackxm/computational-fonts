import unittest
from wasmfont.ir import Function
from wasmfont.reference.lowering import lower_function

class ComplementOptimizationTests(unittest.TestCase):
    def test_not_chain_tracked(self):
        for width in (32, 64):
            ty=f'i{width}'
            code=[('local.get',0),('local.get',1),(ty+'.add',None)]
            for _ in range(10):
                code += [(ty+'.const',-1),(ty+'.xor',None)]
            result=lower_function(Function([ty,ty],[ty],[],code))
            self.assertEqual((result.operation,result.inversions),('add',10))
    def test_complement_identities(self):
        for width in (32,64):
            ty=f'i{width}'
            for op in ('and','or','xor'):
                base=[('local.get',0),('local.get',1),(ty+'.add',None)]
                code=base + base + [(ty+'.const',-1),(ty+'.xor',None),(ty+'.'+op,None)]
                result = lower_function(Function([ty,ty],[ty],[],code))
                self.assertEqual((result.operation, result.input_mode), ('xor', 'zero'))
                self.assertEqual(result.inversions, 0 if op == 'and' else 1)

if __name__=='__main__': unittest.main()
