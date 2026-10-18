import tempfile, unittest, random
from pathlib import Path
from wasmfont.ir import parse_wat
from wasmfont.reference.lowering import compile_module, lower_function
from wasmfont.harfbuzz import run

class NativeLoweringTests(unittest.TestCase):
    def test_stack_locals_and_not(self):
        rng = random.Random(12345)
        with tempfile.TemporaryDirectory() as d:
            for width in (32, 64):
                for op in ('add', 'sub', 'and', 'or', 'xor'):
                    src = Path(d) / 'example.wat'; font = Path(d) / 'example.ttf'
                    src.write_text(f'''(module (func (export "f") (param i{width}) (param i{width})
                      (result i{width}) (local i{width})
                      local.get 0 local.get 1 i{width}.{op}
                      local.set 2 local.get 2 i{width}.const -1 i{width}.xor
                      i{width}.const -1 i{width}.xor))''')
                    lowered = compile_module(src, font)
                    self.assertEqual(lowered.inversions, 2)
                    mask = (1 << width) - 1
                    for _ in range(8):
                        a, b = rng.getrandbits(width), rng.getrandbits(width)
                        expected = {'add':a+b,'sub':a-b,'and':a&b,'or':a|b,'xor':a^b}[op] & mask
                        self.assertEqual(lowered.decode(run(font,lowered.encode(a,b))), expected)
    def test_reject_unimplemented_composition(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / 'bad.wat'
            src.write_text('(module (func (param i32) (param i32) (result i32) local.get 0 local.get 1 i32.add i32.const 1 i32.add))')
            with self.assertRaises(NotImplementedError): lower_function(parse_wat(src)[0])

if __name__ == '__main__': unittest.main()
