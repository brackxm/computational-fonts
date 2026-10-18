"""Differential HarfBuzz tests for symbolic literal-XOR fusion."""
import random
import pytest
from wasmfont.ir import Function
from wasmfont.reference.lowering import lower_function
from wasmfont.harfbuzz import run

@pytest.mark.parametrize('width', [32, 64])
@pytest.mark.parametrize('param', [0, 1])
@pytest.mark.parametrize('reverse', [False, True])
def test_chained_xor_literals(tmp_path, width, param, reverse):
    ty = f'i{width}'
    x, y = 0xDEADBEEF, 0x123456789ABCDEF
    code = [('local.get', param), (ty+'.const', x), (ty+'.xor', None)]
    code += ([(ty+'.const', y)] if not reverse else [])
    if reverse:
        code = [(ty+'.const', y)] + code
    code += [(ty+'.xor', None)]
    lowered = lower_function(Function([ty, ty], [ty], [], code))
    path = tmp_path/'xor.ttf'; lowered.build(path)
    rng = random.Random(width + param)
    for _ in range(10):
        a, b = rng.getrandbits(width), rng.getrandbits(width)
        expected = ((a,b)[param] ^ x ^ y) & ((1<<width)-1)
        assert lowered.decode(run(path, lowered.encode(a,b))) == expected

@pytest.mark.parametrize('width', [32, 64])
def test_xor_cancel_to_constant(tmp_path, width):
    ty=f'i{width}'
    code=[('local.get',0),(ty+'.const',0x1234),(ty+'.xor',None),('local.get',0),(ty+'.xor',None)]
    lowered=lower_function(Function([ty,ty],[ty],[],code))
    path=tmp_path/'constant.ttf';lowered.build(path)
    for a,b in [(0,0),(1,2),((1<<width)-1,5)]:
        assert lowered.decode(run(path,lowered.encode(a,b)))==0x1234
