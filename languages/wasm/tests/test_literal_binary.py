import random
import pytest
from wasmfont.ir import Function
from wasmfont.reference.lowering import lower_function
from wasmfont.harfbuzz import run

@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('operation',['add','sub','and','or'])
@pytest.mark.parametrize('reverse',[False,True])
def test_literal_binary(tmp_path,width,operation,reverse):
    ty=f'i{width}'; mask=(1<<width)-1; literal=0x123456789abcdef
    code=([ (ty+'.const',literal),('local.get',1)] if reverse else [('local.get',1),(ty+'.const',literal)]) + [(ty+'.'+operation,None)]
    lowered=lower_function(Function([ty,ty],[ty],[],code))
    font=tmp_path/'binary.ttf'; lowered.build(font)
    rng=random.Random(120+width)
    for _ in range(8):
        a=rng.getrandbits(width); b=rng.getrandbits(width)
        x,y=(literal,b) if reverse else (b,literal)
        expected={'add':lambda:x+y,'sub':lambda:x-y,'and':lambda:x&y,'or':lambda:x|y}[operation]()&mask
        assert lowered.decode(run(font,lowered.encode(a,b)))==expected
