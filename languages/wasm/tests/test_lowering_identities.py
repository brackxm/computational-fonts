import tempfile, unittest, random
from pathlib import Path
from wasmfont.reference.lowering import compile_module
from wasmfont.harfbuzz import run

class IdentityLoweringTests(unittest.TestCase):
    def test_identity_sequences_native(self):
        rng = random.Random(554)
        for width in (32, 64):
            for operation in ('add', 'sub', 'and', 'or', 'xor'):
                with self.subTest(width=width, operation=operation), tempfile.TemporaryDirectory() as td:
                    src = Path(td)/'identity.wat'; font = Path(td)/'identity.ttf'
                    src.write_text(f'''(module (func (param i{width}) (param i{width}) (result i{width})
                        local.get 0 local.get 1 i{width}.{operation}
                        i{width}.const 0 i{width}.add
                        i{width}.const -1 i{width}.and
                        i{width}.const 0 i{width}.xor
                        i{width}.const 0 i{width}.or
                        i{width}.const 0 i{width}.sub))''')
                    compiled=compile_module(src,font)
                    mask=(1<<width)-1
                    for _ in range(6):
                        a,b=rng.getrandbits(width),rng.getrandbits(width)
                        expected={'add':a+b,'sub':a-b,'and':a&b,'or':a|b,'xor':a^b}[operation]&mask
                        self.assertEqual(compiled.decode(run(font,compiled.encode(a,b))),expected)
    def test_unsupported_still_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'bad.wat';src.write_text('(module (func (param i32) (param i32) (result i32) local.get 0 local.get 1 i32.add i32.const 2 i32.add))')
            with self.assertRaises(NotImplementedError):compile_module(src,Path(td)/'bad.ttf')
if __name__=='__main__': unittest.main()
