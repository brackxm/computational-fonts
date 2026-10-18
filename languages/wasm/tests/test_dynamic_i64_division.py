"""Full-width runtime dividers execute in GSUB, including signed traps."""
from itertools import product
import random

import pytest

from wasmfont.gsub.circuit import Circuit, Value, emit_font
from wasmfont.runtime import NativeFont, IncompleteShaping
from .test_compiler import differential
from wasmfont.compiler import Limits


@pytest.mark.parametrize('width', [1, 2, 4, 6])
def test_dynamic_divider_exhaustive_circuit(width):
    circuit = Circuit()
    quotient, remainder = circuit.unsigned_divmod(circuit.argument(0, width), circuit.argument(1, width))
    for a in range(1 << width):
        for b in range(1, 1 << width):
            bits = circuit.evaluate_for_test([a, b])
            decode = lambda value: sum(bits[wire] << i for i, wire in enumerate(value.bits))
            assert (decode(quotient), decode(remainder)) == divmod(a, b)


def test_dynamic_divider_exhaustive_harfbuzz(tmp_path):
    circuit = Circuit()
    quotient, remainder = circuit.unsigned_divmod(circuit.argument(0, 4), circuit.argument(1, 4))
    path = tmp_path / 'reduced.ttf'
    emit_font(circuit, [quotient, remainder], {}, ['i4', 'i4'], ['i4', 'i4'], path)
    with NativeFont(path) as font:
        for a in range(16):
            for b in range(1, 16):
                assert font.invoke(a, b) == divmod(a, b)


def test_four_input_gates_and_paired_outputs_shape_all_rows(tmp_path):
    circuit = Circuit()
    sources = tuple(circuit.argument(i, 1).bits[0] for i in range(4))
    parity = circuit.gate(sources, lambda a,b,c,d: a ^ b ^ c ^ d)
    selected = circuit.gate(sources, lambda a,b,c,d: (a & b) ^ (c | d))
    path = tmp_path / 'four-input.ttf'
    emit_font(circuit, [Value((parity,)), Value((selected,))], {}, ['i1'] * 4, ['i1'] * 2, path)
    with NativeFont(path) as font:
        for a,b,c,d in product((0, 1), repeat=4):
            assert font.invoke(a,b,c,d) == (a ^ b ^ c ^ d, (a & b) ^ (c | d))
    with pytest.raises(ValueError, match='four dynamic bits'):
        circuit.gate(sources + (circuit.argument(4, 1).bits[0],), lambda *bits: sum(bits) & 1)


@pytest.mark.parametrize('operation', ['div_u', 'rem_u', 'div_s', 'rem_s'])
def test_native_dynamic_i64_matches_v8(tmp_path, operation):
    sign = 1 << 63
    mask = (1 << 64) - 1
    anchors = [0, 1, sign - 1, sign, sign + 1, mask, (1 << 32) + 1]
    divisors = [0, 1, 3, sign, mask, (1 << 32) + 1]
    cases = list(product(anchors, divisors))
    rng = random.Random(20261016)
    cases += [(rng.getrandbits(64), rng.getrandbits(64)) for _ in range(8)]
    wat = f'''(module (func (export "run") (param i64 i64) (result i64)
        local.get 0 local.get 1 i64.{operation}))'''
    manifest, path = differential(tmp_path, wat, cases, binary_input=operation.endswith('_s'))
    assert manifest['metrics']['lookups'] < 5400
    assert manifest['metrics']['glyphs'] < 65535
    assert manifest['limits']['max_gates'] == Limits().max_gates
    with NativeFont(path) as font:
        with pytest.raises(IncompleteShaping):
            font.decode(font.shaper.shape(font.encode([mask, 3]), enabled=False))


@pytest.mark.parametrize('signed', [False, True])
def test_quotient_and_remainder_compose_with_following_instructions(tmp_path, signed):
    suffix = 's' if signed else 'u'
    wat = f'''(module (func (export "run") (param i64 i64) (result i64 i64)
        local.get 0 local.get 1 i64.div_{suffix} i64.const 1 i64.add
        local.get 0 local.get 1 i64.rem_{suffix} i64.const 3 i64.xor))'''
    differential(tmp_path, wat, [(0, 1), (17, 3), (-17, 3), (17, -3),
                                (-(1 << 63), -1), (-(1 << 63), 3), (-1, 1 << 63)])


def test_division_traps_only_on_the_taken_path(tmp_path):
    wat = '''(module (func (export "run") (param i64 i64 i32) (result i64)
        local.get 2 if (result i64)
          local.get 0 local.get 1 i64.div_s
        else i64.const 42 end))'''
    differential(tmp_path, wat, [(5, 0, 0), (5, 0, 1), (-(1 << 63), -1, 0),
                                (-(1 << 63), -1, 1), (-(1 << 63), 3, 1)])


def test_dynamic_divider_high_bits_and_smaller_gate_budget():
    circuit = Circuit(max_gates=4500)
    q,r = circuit.unsigned_divmod(circuit.argument(0,64),circuit.argument(1,64))
    mask = (1 << 64) - 1
    for bit in range(64):
        for divisor in {max(1,(1 << bit)-1),1 << bit,min(mask,(1 << bit)+1)}:
            for dividend in {divisor-1,divisor,(divisor+1)&mask,mask}:
                bits = circuit.evaluate_for_test([dividend,divisor])
                decode = lambda v: sum(bits[wire] << n for n,wire in enumerate(v.bits))
                assert (decode(q),decode(r)) == divmod(dividend,divisor)
