"""Power-of-two division/remainder remains native at both integer widths."""
import pytest
from .test_compiler import differential

@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('op',['div_u','rem_u','div_s','rem_s'])
@pytest.mark.parametrize('divisor',[1,2,8,128])
def test_constant_power_two(tmp_path,width,op,divisor):
    ty=f'i{width}'
    sign=1<<(width-1)
    cases=[(x,) for x in [0,1,7,8,9,127,128,129,sign-1,sign,sign+1,(1<<width)-1]]
    wat=f'(module (func (export "run") (param {ty}) (result {ty}) local.get 0 {ty}.const {divisor} {ty}.{op}))'
    differential(tmp_path,wat,cases)

@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('op',['div_s','rem_s'])
@pytest.mark.parametrize('divisor',[-1,-2,-8,-128])
def test_negative_signed_power_two(tmp_path,width,op,divisor):
    ty=f'i{width}';sign=1<<(width-1)
    cases=[(x,) for x in [0,1,7,8,9,127,128,129,sign-1,sign,sign+1,(1<<width)-1]]
    wat=f'(module (func (export "run") (param {ty}) (result {ty}) local.get 0 {ty}.const {divisor} {ty}.{op}))'
    differential(tmp_path,wat,cases)

@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('op',['div_s','rem_s'])
@pytest.mark.parametrize('divisor',[-256,-8,-1,1,8,256])
def test_signed_division_bias_randomized(tmp_path,width,op,divisor):
    import random
    rng=random.Random(20261011+width)
    mask=(1<<width)-1
    boundary=[0,1,2,7,8,9,255,256,257,(1<<(width-1))-1,1<<(width-1),mask]
    values=boundary+[rng.getrandbits(width) for _ in range(12)]
    wat=f'(module (func (export "run") (param i{width}) (result i{width}) local.get 0 i{width}.const {divisor} i{width}.{op}))'
    differential(tmp_path,wat,[(v,) for v in values])
