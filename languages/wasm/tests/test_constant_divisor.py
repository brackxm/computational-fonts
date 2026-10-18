"""Constant-divisor circuits preserve full-width inputs and native Wasm semantics."""
import random

import pytest

from wasmfont.gsub.circuit import Circuit
from .test_compiler import differential


@pytest.mark.parametrize('width', [2, 4, 8])
def test_constant_dividers_exhaust_small_inputs(width):
    for divisor in (3, 5, 7, 10, 127, 128, 129, 255):
        if divisor >= 1 << width:
            continue
        circuit = Circuit()
        quotient, remainder = circuit.unsigned_divmod(circuit.argument(0, width), circuit.const(divisor, width))
        for value in range(1 << width):
            bits = circuit.evaluate_for_test([value])
            decode = lambda result: sum(bits[wire] << i for i, wire in enumerate(result.bits))
            assert (decode(quotient), decode(remainder)) == divmod(value, divisor)


@pytest.mark.parametrize('divisor', [3, 5, 7, 10, 255, 1000])
def test_full_i64_constant_divider_fits_font_budget(divisor):
    circuit = Circuit(max_gates=3000)
    quotient, remainder = circuit.unsigned_divmod(circuit.argument(0, 64), circuit.const(divisor, 64))
    assert quotient.width == remainder.width == 64
    assert circuit.gate_count < 3000
    assert remainder.bits[divisor.bit_length():] == (0,) * (64 - divisor.bit_length())
    rng = random.Random(4000 + divisor)
    for value in [0, divisor - 1, divisor, divisor + 1, (1 << 63), (1 << 64) - 1,
                  *[rng.getrandbits(64) for _ in range(20)]]:
        bits = circuit.evaluate_for_test([value])
        decode = lambda result: sum(bits[wire] << i for i, wire in enumerate(result.bits))
        assert (decode(quotient), decode(remainder)) == divmod(value, divisor)


@pytest.mark.parametrize('width', [32, 64])
@pytest.mark.parametrize('operation', ['div_u', 'rem_u', 'div_s', 'rem_s'])
@pytest.mark.parametrize('divisor', [3, 7, 10, 255, 1000])
def test_native_non_power_two_constants(tmp_path, width, operation, divisor):
    rng = random.Random(width * divisor)
    sign = 1 << (width - 1)
    values = [0, 1, divisor - 1, divisor, divisor + 1, sign - 1, sign, sign + 1, (1 << width) - 1]
    values += [rng.getrandbits(width) for _ in range(8)]
    signed_divisors = [divisor, -divisor] if operation.endswith('_s') else [divisor]
    for constant in signed_divisors:
        wat = f'''(module (func (export "run") (param i{width}) (result i{width})
            local.get 0 i{width}.const {constant} i{width}.{operation}))'''
        differential(tmp_path, wat, [(value,) for value in values])


@pytest.mark.parametrize('width', [32, 64])
@pytest.mark.parametrize('operation', ['div_u', 'rem_u', 'div_s', 'rem_s'])
def test_zero_divisor_still_traps(tmp_path, width, operation):
    wat = f'''(module (func (export "run") (param i{width}) (result i{width})
        local.get 0 i{width}.const 0 i{width}.{operation}))'''
    differential(tmp_path, wat, [(0,), (1,), ((1 << width) - 1,)])


@pytest.mark.parametrize('width', [32, 64])
@pytest.mark.parametrize('operation', ['div_u', 'rem_u', 'div_s', 'rem_s'])
@pytest.mark.parametrize('negative', [False, True])
def test_constants_near_the_sign_boundary(tmp_path, width, operation, negative):
    sign = 1 << (width - 1)
    divisor = -(sign - 1) if negative else sign - 1
    wat = f'''(module (func (export "run") (param i{width}) (result i{width})
        local.get 0 i{width}.const {divisor} i{width}.{operation}))'''
    differential(tmp_path, wat, [(value,) for value in (0, 1, sign - 2, sign - 1, sign, sign + 1, (1 << width) - 1)],
                 binary_input=True)
