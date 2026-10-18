"""Division identities must not enumerate inputs or bypass Wasm traps."""
import pytest
from wasmfont.gsub.circuit import Circuit
from .test_compiler import differential

@pytest.mark.parametrize('width',[32,64])
def test_division_wire_identities_are_constant_size(width):
    c=Circuit(max_gates=100)
    a=c.argument(0,width)
    b=c.argument(1,width)
    for lhs,rhs in ((a,c.const(1,width)),(c.const(0,width),b),(a,a)):
        q,r=c.unsigned_divmod(lhs,rhs)
        assert q.width==r.width==width
    assert c.gate_count==0

@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('form',['one','zero_numerator','same_operand'])
@pytest.mark.parametrize('op',['div_u','rem_u'])
def test_native_division_identities(tmp_path,width,form,op):
    ty=f'i{width}'
    expression={
        'one':f'local.get 0 {ty}.const 1',
        'zero_numerator':f'{ty}.const 0 local.get 0',
        'same_operand':'local.get 0 local.get 0',
    }[form]
    wat=f'(module (func (export "run") (param {ty}) (result {ty}) {expression} {ty}.{op}))'
    differential(tmp_path,wat,[(0,),(1,),(2,),(17,),((1<<width)-1,)])
