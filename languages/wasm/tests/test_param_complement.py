import pytest
from wasmfont.reference.lowering import lower_function
from wasmfont.ir import Function

@pytest.mark.parametrize('width', [32,64])
@pytest.mark.parametrize('param', [0,1])
@pytest.mark.parametrize('reverse', [False,True])
def test_parameter_complement(tmp_path,width,param,reverse):
    from wasmfont.reference.lowering import Lowered
    ty=f'i{width}'
    ops=[('local.get',param),(ty+'.const',-1)]
    if reverse: ops.reverse()
    fn=Function([ty,ty],[ty],[],ops+[(ty+'.xor',None)])
    lowered=lower_function(fn)
    assert lowered.input_mode==f'param{param}' and lowered.inversions==1
    font=tmp_path/'complement.ttf'; lowered.build(font)
    from wasmfont.harfbuzz import run as shape
    for a,b in [(0,0),(1,2),((1<<width)-1,0),(0xdeadbeef,0x12345678)]:
        output=shape(font,lowered.encode(a,b))
        assert lowered.decode(output)==(~(a,b)[param])&((1<<width)-1)
