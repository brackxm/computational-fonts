import tempfile
from pathlib import Path
import pytest
from wasmfont.ir import parse_wat
from wasmfont.reference.lowering import lower_function
from wasmfont.harfbuzz import run

@pytest.mark.parametrize('width', [32,64])
@pytest.mark.parametrize('body,expected', [
    ('local.get 0 local.get 0 i{w}.xor', lambda a,b,m:0),
    ('local.get 0 local.get 0 i{w}.xor i{w}.const -1 i{w}.xor', lambda a,b,m:m),
    ('local.get 0', lambda a,b,m:a&m),
    ('local.get 1', lambda a,b,m:b&m),
])
def test_native_symbolic_outputs(width, body, expected, tmp_path):
    wat='(module (func (param i{w}) (param i{w}) (result i{w}) {body}))'.format(w=width,body=body.format(w=width))
    source=tmp_path / 'source.wat'; source.write_text(wat)
    lowered=lower_function(parse_wat(source)[0]); mask=(1<<width)-1
    with tempfile.TemporaryDirectory() as tmp:
        font=Path(tmp)/'test.ttf'; lowered.build(font)
        for a,b in [(0,0),(1,2),(mask,5),(0x123456789abcdef,0xfedcba987654321)]:
            actual=lowered.decode(run(font,lowered.encode(a,b)))
            assert actual==expected(a,b,mask)
