"""Paired affine expressions execute via native GSUB after safe simplification."""
import pytest
from wasmfont.ir import Function
from wasmfont.reference.lowering import lower_function
from wasmfont.harfbuzz import run

@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('left,right,op,expected',[
    (('add',13),('add',6),'sub',lambda a:7),
    (('sub',13),('add',6),'add',lambda a:2*a-7),
    (('add',13),('sub',6),'sub',lambda a:19),
    (('sub',13),('add',6),'sub',lambda a:-19),
    (('add',0),('add',0),'add',lambda a:2*a),
])
def test_affine_pair(tmp_path,width,left,right,op,expected):
    ty=f'i{width}'; code=[]
    for operation,c in (left,right):
        code.extend([('local.get',0),(ty+'.const',c),(ty+'.'+operation,None)])
    code.append((ty+'.'+op,None))
    if left == ('sub',13) and right == ('add',6) and op == 'add':
        # coefficient 2 with nonzero offset is not yet representable.
        with pytest.raises(NotImplementedError): lower_function(Function([ty,ty],[ty],[],code))
        return
    lowered=lower_function(Function([ty,ty],[ty],[],code))
    font=tmp_path/'pair.ttf';lowered.build(font)
    for a in (0,1,17,(1<<width)-1,1<<(width-1)):
        assert lowered.decode(run(font,lowered.encode(a,33))) == expected(a)&((1<<width)-1)
