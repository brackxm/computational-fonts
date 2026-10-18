import tempfile, random, unittest
from pathlib import Path
from wasmfont.reference.pipeline import build_not_pipeline, decode_not
from wasmfont.reference.compiler import encode
from wasmfont.harfbuzz import run

class MultistageTests(unittest.TestCase):
    def test_repeated_native_gsub_stages(self):
        rng=random.Random(994)
        with tempfile.TemporaryDirectory() as d:
            for width in (32,64):
                mask=(1<<width)-1
                for op in ('add','sub','and','or','xor'):
                    for stages in (0,1,2,3,4):
                        path=Path(d)/f'{op}_{width}_{stages}.ttf'
                        build_not_pipeline(path,op,width,stages)
                        for a,b in [(0,0),(mask,1)]+[(rng.getrandbits(width),rng.getrandbits(width)) for _ in range(3)]:
                            shaped=run(path,encode(a,b,op,width))
                            actual=decode_not(shaped,width,stages)
                            raw={'add':a+b,'sub':a-b,'and':a&b,'or':a|b,'xor':a^b}[op]&mask
                            expected=raw if stages%2==0 else (~raw)&mask
                            self.assertEqual(actual,expected,(op,width,stages,a,b))
