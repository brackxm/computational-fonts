import tempfile, unittest
from pathlib import Path
from fontTools.ttLib import TTFont
from wasmfont.reference.compiler import build, _check_add
from wasmfont.ir import Function

class BackendOps(unittest.TestCase):
    def test_four_real_gsub_circuits(self):
        for op in ('add','and','or','xor'):
            f=Function(['i32','i32'],['i32'],[],[('local.get',0),('local.get',1),(f'i32.{op}',None)])
            self.assertEqual(_check_add([f]),op)
            with tempfile.TemporaryDirectory() as d:
                path=Path(d)/'out.ttf';build(path,op)
                font=TTFont(path)
                self.assertIn('GSUB',font)
                self.assertEqual(len(font['GSUB'].table.LookupList.Lookup),64)
    def test_reject_other_backend_ops(self):
        with self.assertRaises(ValueError):build('/tmp/not-created.ttf','mul')
if __name__=='__main__':unittest.main()
