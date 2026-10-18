"""Affine Wasm chains are reduced to one actual GSUB arithmetic circuit."""
import random
import pytest
from wasmfont.ir import Function
from wasmfont.reference.lowering import lower_function
from wasmfont.harfbuzz import run

@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('param',[0,1])
@pytest.mark.parametrize('sequence',[
    [('add',7),('sub',11),('add',19)],
    [('rsub',100),('sub',17),('add',5)],
    [('add',0xffffffff),('rsub',42),('rsub',31)],
])
def test_affine_chain_harfbuzz(tmp_path,width,param,sequence):
    ty=f'i{width}'; mask=(1<<width)-1
    code=[('local.get',param)]
    for op,c in sequence:
        if op=='rsub':
            # Store intermediate on the Wasm stack via a temporary local.
            code += [('local.set',2),(ty+'.const',c),('local.get',2),(ty+'.sub',None)]
        else:
            code += [(ty+'.const',c),(ty+'.'+op,None)]
    lowered=lower_function(Function([ty,ty],[ty],[ty],code))
    path=tmp_path/'affine.ttf'; lowered.build(path)
    rng=random.Random(width+param)
    for _ in range(8):
        a,b=rng.getrandbits(width),rng.getrandbits(width)
        value=(a,b)[param]
        for op,c in sequence:
            value={'add':lambda:value+c,'sub':lambda:value-c,'rsub':lambda:c-value}[op]()&mask
        assert lowered.decode(run(path,lowered.encode(a,b)))==value
