import unittest,tempfile
from pathlib import Path
from fontTools.ttLib import TTFont
from wasmfont.reference.compiler import build,read_wat,read_wasm,encode,expected

class TestCompiler(unittest.TestCase):
    def test_wat(self):self.assertEqual(read_wat(Path(__file__).resolve().parents[1] / 'examples' / 'add.wat'),'add')
    def test_font_structure(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.ttf';build(p);f=TTFont(p)
            self.assertEqual(len(f['GSUB'].table.LookupList.Lookup),64)
            self.assertEqual([x.LookupType for x in f['GSUB'].table.LookupList.Lookup],[4,2]*32)
    def test_encoder(self):
        for a,b in [(0,0),(0xffffffff,1),(0xdeadbeef,0x12345678)]:
            g=encode(a,b);self.assertEqual(len(g),33)
            self.assertEqual(sum(int(x[1])<<i for i,x in enumerate(g[1:])),a&0xffffffff)
            self.assertEqual(sum(int(x[2])<<i for i,x in enumerate(g[1:])),b&0xffffffff)
            self.assertEqual(expected(a,b),(a+b)&0xffffffff)
if __name__=='__main__':unittest.main()
