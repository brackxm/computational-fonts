"""Only mathematically valid specializations compile to native GSUB circuits."""
import pytest
from wasmfont.ir import Function
from wasmfont.reference.lowering import lower_function
from wasmfont.harfbuzz import run

@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('factor',[0,1,2,-1])
@pytest.mark.parametrize('reversed_order',[False,True])
def test_native_multiply_small_constant(tmp_path,width,factor,reversed_order):
    ty=f'i{width}'
    code=[('local.get',0),(ty+'.const',factor)]
    if reversed_order: code.reverse()
    code.append((ty+'.mul',None))
    lowered=lower_function(Function([ty,ty],[ty],[],code))
    font=tmp_path/'multiply.ttf';lowered.build(font)
    mask=(1<<width)-1
    for value in (0,1,2,17,mask,mask>>1,1<<(width-1)):
        actual=lowered.decode(run(font,lowered.encode(value,123)))
        assert actual == value*factor & mask

@pytest.mark.parametrize('width',[32,64])
def test_reject_general_multiplication(width):
    ty=f'i{width}'
    with pytest.raises(NotImplementedError):
        lower_function(Function([ty,ty],[ty],[],[('local.get',0),('local.get',1),(ty+'.mul',None)]))
