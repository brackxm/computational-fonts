"""Constant bit operations must lower to native constant-output GSUB fonts."""
import pytest
from wasmfont.ir import Function
from wasmfont.reference.lowering import lower_function
from wasmfont.harfbuzz import run

@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('operation,value,amount,expected',[
    ('shr_u',0x80000000,3,0x10000000),
    ('shr_s',-1,5,-1),
    ('rotl',0x81,4,0x810),
    ('rotr',0x81,4,None),
    ('clz',0, None,None),
    ('ctz',0, None,None),
    ('popcnt',0xf0f0,None,8),
    ('eqz',0,None,1),
    ('eqz',17,None,0),
])
def test_constant_bitops_native(tmp_path,width,operation,value,amount,expected):
    ty=f'i{width}'; mask=(1<<width)-1
    code=[(ty+'.const',value)]
    if amount is not None: code.append((ty+'.const',amount))
    code.append((ty+'.'+operation,None))
    lowered=lower_function(Function([ty,ty],[ty],[],code))
    font=tmp_path/'bitops.ttf'; lowered.build(font)
    actual=lowered.decode(run(font,lowered.encode(0x1234,0x5678)))
    if expected is None:
        if operation=='rotr': expected=((value>>amount)|(value<<(width-amount)))&mask
        else: expected=width
    assert actual==expected&mask

@pytest.mark.parametrize('width',[32,64])
def test_zero_shift_dynamic_passthrough(tmp_path,width):
    ty=f'i{width}'
    for op in ('shr_u','shr_s','rotl','rotr'):
        fn=Function([ty,ty],[ty],[],[('local.get',0),(ty+'.const',width),(ty+'.'+op,None)])
        lowered=lower_function(fn)
        font=tmp_path/(op+'.ttf'); lowered.build(font)
        assert lowered.decode(run(font,lowered.encode(0x12345678,42)))==0x12345678
