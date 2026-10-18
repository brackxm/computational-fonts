import pytest
from wasmfont.ir import Function
from wasmfont.reference.lowering import lower_function
from wasmfont.harfbuzz import run

@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('value',[0,1,0x1234,-1,-1234567])
def test_arbitrary_constant_output(tmp_path,width,value):
    ty=f'i{width}'
    fn=Function([ty,ty],[ty],[],[(ty+'.const',value)])
    lowered=lower_function(fn)
    path=tmp_path/'literal.ttf';lowered.build(path)
    for a,b in [(0,0),(1,2),(0xffffffff,0x1234)]:
        assert lowered.decode(run(path,lowered.encode(a,b)))==value&((1<<width)-1)

@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('param',[0,1])
@pytest.mark.parametrize('value',[1,0x1234567,0xabcdef0123456789])
def test_parameter_xor_literal(tmp_path,width,param,value):
    ty=f'i{width}'
    fn=Function([ty,ty],[ty],[],[('local.get',param),(ty+'.const',value),(ty+'.xor',None)])
    lowered=lower_function(fn)
    path=tmp_path/'literal.ttf';lowered.build(path)
    mask=(1<<width)-1
    for a,b in [(0,0),(1,2),(mask,0x123456789)]:
        assert lowered.decode(run(path,lowered.encode(a,b)))==((a,b)[param]^value)&mask
