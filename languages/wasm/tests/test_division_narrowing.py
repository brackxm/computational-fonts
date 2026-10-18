"""Structural and native-shaping tests for zero-extended division."""
import pytest
from wasmfont.gsub.circuit import Circuit, Value
from .test_compiler import differential

@pytest.mark.parametrize('width',[8,16,32])
def test_zero_extended_division_is_narrow(width):
    c=Circuit(max_gates=8000)
    a=c.argument(0,width)
    b=c.argument(1,width)
    padded=lambda v: Value(v.bits+(0,)*(64-width))
    q,r=c.unsigned_divmod(padded(a),padded(b))
    assert q.bits[width:]==(0,)*(64-width)
    assert r.bits[width:]==(0,)*(64-width)
    assert c.gate_count<6000
    for x,y in [(0,1),(17,3),(255,7),(2**width-1,11)]:
        out=c.evaluate_for_test([x,y])
        decode=lambda v:sum(out[bit]<<i for i,bit in enumerate(v.bits))
        assert decode(q)==x//y
        assert decode(r)==x%y

@pytest.mark.parametrize('op',['div_u','rem_u'])
def test_native_i64_zero_extended_i32(tmp_path,op):
    wat=f'''(module (func (export "run") (param i32 i32) (result i64)
        local.get 0 i64.extend_i32_u
        local.get 1 i64.extend_i32_u
        i64.{op}))'''
    differential(tmp_path,wat,[(17,3),(4294967295,7),(100,9),(0,1)])
