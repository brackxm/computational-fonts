"""Repeated dynamic parameters are evaluated by real HarfBuzz GSUB adders."""
import random
import pytest
from wasmfont.ir import Function
from wasmfont.reference.lowering import lower_function
from wasmfont.harfbuzz import run

@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('index',[0,1])
def test_native_double_parameter(tmp_path,width,index):
    ty=f'i{width}'
    fn=Function([ty,ty],[ty],[],[('local.get',index),('local.get',index),(ty+'.add',None)])
    lowered=lower_function(fn)
    font=tmp_path/'double.ttf'
    lowered.build(font)
    mask=(1<<width)-1
    rng=random.Random(width*10+index)
    for value in [0,1,mask,mask>>1,1<<(width-1)]+[rng.getrandbits(width) for _ in range(15)]:
        a,b=(value,0) if index==0 else (0,value)
        actual=lowered.decode(run(font,lowered.encode(a,b)))
        assert actual==(value*2)&mask

@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('shift',[0,1])
def test_native_shift_left(tmp_path,width,shift):
    ty=f'i{width}'
    fn=Function([ty,ty],[ty],[],[('local.get',0),(ty+'.const',shift),(ty+'.shl',None)])
    lowered=lower_function(fn)
    font=tmp_path/'shift.ttf';lowered.build(font)
    mask=(1<<width)-1
    for value in [0,1,mask,1<<(width-1),0x123456789ABCDEF]:
        assert lowered.decode(run(font,lowered.encode(value,0)))==((value << shift)&mask)
