"""Fused partial-product adders preserve wrapping integer multiplication."""
from itertools import product
import random

import pytest

from wasmfont.gsub.circuit import Circuit, Value


@pytest.mark.parametrize('width', [1, 2, 4, 8, 32, 64])
def test_fused_multiplier_circuit(width):
    circuit = Circuit(max_gates=4200)
    a, b = circuit.argument(0, width), circuit.argument(1, width)
    result = circuit.mul(a, b)
    mask = (1 << width) - 1
    if width <= 4:
        cases = product(range(1 << width), repeat=2)
    else:
        anchors = [0, 1, 2, mask, mask >> 1, 1 << (width - 1)]
        rng = random.Random(20261017 + width)
        cases = [*product(anchors, repeat=2),
                 *((rng.getrandbits(width), rng.getrandbits(width)) for _ in range(24))]
    for x,y in cases:
        bits = circuit.evaluate_for_test([x, y])
        assert sum(bits[wire] << bit for bit,wire in enumerate(result.bits)) == (x * y) & mask


@pytest.mark.parametrize('constant_on_left', [False, True])
@pytest.mark.parametrize('factor', [0, 1, 2, 3, 10, -1, 1 << 63])
def test_fused_multiplier_constant_operands(factor, constant_on_left):
    circuit = Circuit(max_gates=4200)
    value, constant = circuit.argument(0, 64), circuit.const(factor, 64)
    result = circuit.mul(constant, value) if constant_on_left else circuit.mul(value, constant)
    mask = (1 << 64) - 1
    for x in (0, 1, -1, 17, 1 << 63, 0x123456789abcdef0):
        bits = circuit.evaluate_for_test([x])
        assert sum(bits[wire] << bit for bit,wire in enumerate(result.bits)) == (x * factor) & mask


def test_fused_multiplier_square_and_width_validation():
    circuit = Circuit(max_gates=4200)
    value = circuit.argument(0, 64)
    square = circuit.mul(value, value)
    mask = (1 << 64) - 1
    for x in (0, 1, -1, (1 << 63) - 1, 0x123456789abcdef0):
        bits = circuit.evaluate_for_test([x])
        assert sum(bits[wire] << bit for bit,wire in enumerate(square.bits)) == (x * x) & mask
    with pytest.raises(ValueError, match='width mismatch'):
        circuit.mul(value, Value(value.bits[:32]))
