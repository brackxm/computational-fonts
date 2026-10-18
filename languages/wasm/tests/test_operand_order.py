import tempfile, unittest, random
from pathlib import Path
from wasmfont.reference.lowering import compile_module
from wasmfont.harfbuzz import run

class OperandOrderTests(unittest.TestCase):
    def test_reversed_operands_native(self):
        rng = random.Random(871)
        for width in (32, 64):
            for operation in ('add','sub','and','or','xor'):
                with self.subTest(width=width, operation=operation), tempfile.TemporaryDirectory() as td:
                    src=Path(td)/'reverse.wat'; font=Path(td)/'reverse.ttf'
                    src.write_text(f'(module (func (param i{width}) (param i{width}) (result i{width}) local.get 1 local.get 0 i{width}.{operation} i{width}.const -1 i{width}.xor))')
                    compiled=compile_module(src,font)
                    self.assertTrue(compiled.swapped)
                    for _ in range(8):
                        a,b=rng.getrandbits(width),rng.getrandbits(width)
                        result={'add':b+a,'sub':b-a,'and':b&a,'or':b|a,'xor':b^a}[operation]
                        expected=(~result)&((1<<width)-1)
                        self.assertEqual(compiled.decode(run(font,compiled.encode(a,b))),expected)
if __name__=='__main__': unittest.main()
