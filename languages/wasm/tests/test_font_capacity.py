"""Packed fonts execute composed expensive operations in one shaping call."""
from itertools import product
from pathlib import Path
import random

import pytest

from wasmfont.gsub.circuit import Circuit, Value, emit_font, ResourceLimit, MAX_GATES
from wasmfont.runtime import NativeFont, IncompleteShaping
from .test_compiler import differential
from wasmfont.compiler import compile_source, Limits, NativeCompiler
from wasmfont.frontend import load
from wasmfont.gsub.tables import truth_suffixes


@pytest.mark.parametrize('coalesce', [False, True])
@pytest.mark.parametrize('batch_size', [1, 2, 4, 8, 16, 32, 64])
def test_packed_rules_exhaustive_harfbuzz(tmp_path, batch_size, coalesce):
    circuit = Circuit()
    quotient, remainder = circuit.unsigned_divmod(circuit.argument(0, 4), circuit.argument(1, 4))
    path = tmp_path / 'packed.ttf'
    emit_font(circuit, [quotient, remainder], {}, ['i4', 'i4'], ['i4', 'i4'], path,
              lookup_batch_size=batch_size,lookup_coalescing=coalesce)
    with NativeFont(path) as font:
        for a, b in product(range(16), range(1, 16)):
            assert font.invoke(a, b) == divmod(a, b)


@pytest.mark.parametrize('coalesce', [False, True])
def test_packed_noncontiguous_pairs_and_four_input_rules(tmp_path, coalesce):
    circuit = Circuit()
    bits = tuple(circuit.argument(i, 1).bits[0] for i in range(4))
    first = circuit.gate(bits, lambda a,b,c,d: a ^ b ^ c ^ d)
    dependent = circuit.gate((first, bits[0]), lambda p,a: p & a)
    late_pair = circuit.gate(bits, lambda a,b,c,d: (a & b) ^ (c | d))
    path = tmp_path / 'interleaved.ttf'
    emit_font(circuit, [Value((first,)), Value((dependent,)), Value((late_pair,))], {},
              ['i1'] * 4, ['i1'] * 3, path, lookup_batch_size=4,lookup_coalescing=coalesce)
    with NativeFont(path) as font:
        for a,b,c,d in product((0, 1), repeat=4):
            p = a ^ b ^ c ^ d
            assert font.invoke(a,b,c,d) == (p, p & a, (a & b) ^ (c | d))


def test_short_truth_rules_partition_every_input():
    # Every Boolean function of up to three inputs, plus a four-input select
    # whose newest operand can make its oldest inputs irrelevant.
    for width in range(4):
        patterns=list(product((0,1),repeat=width))
        for table in product((0,1),repeat=1<<width):
            rules=list(truth_suffixes(table))
            for pattern,result in zip(patterns,table):
                matches=[value for suffix,value in rules
                         if not suffix or pattern[-len(suffix):]==suffix]
                assert matches==[result]
    table=tuple((a^b) if d else c for a,b,c,d in product((0,1),repeat=4))
    rules=list(truth_suffixes(table))
    assert len(rules)<16
    for pattern,result in zip(product((0,1),repeat=4),table):
        assert [value for suffix,value in rules if pattern[-len(suffix):]==suffix]==[result]


@pytest.mark.parametrize('coalesce', [False, True])
def test_full_sixty_four_group_batches_with_four_input_truth_tables(tmp_path, coalesce):
    # The reduced divider has only 26 groups. Exercise genuinely full batches
    # here, including paired outputs and many intervening wildcard cells.
    circuit=Circuit()
    bits=circuit.argument(0,8).bits
    rng=random.Random(20261021)
    tables=[tuple((rng.getrandbits(16)>>i)&1 for i in range(16)) for _ in range(128)]
    selections=[tuple(sorted(rng.sample(range(8),4))) for _ in tables]
    outputs=[circuit.gate([bits[i] for i in selection],
                         lambda a,b,c,d,t=table:t[(a<<3)|(b<<2)|(c<<1)|d])
             for table,selection in zip(tables,selections)]
    path=tmp_path/'wide-truth-tables.ttf'
    manifest=emit_font(circuit,[Value(tuple(outputs[:64])),Value(tuple(outputs[64:]))],{},
                       ['i8'],['i64','i64'],path,lookup_batch_size=64,lookup_coalescing=coalesce)
    assert manifest['metrics']['gate_groups']>128
    if coalesce:assert manifest['metrics']['coalesced_gate_groups']>0
    with NativeFont(path) as font:
        for argument in range(256):
            values=[table[sum(((argument>>bit)&1)<<(3-i) for i,bit in enumerate(selection))]
                    for table,selection in zip(tables,selections)]
            expected=tuple(sum(value<<i for i,value in enumerate(values[start:start+64]))
                           for start in (0,64))
            assert font.invoke(argument)==expected


def test_three_full_width_dividers_cross_previous_offset_capacity(tmp_path):
    source=Path(__file__).resolve().parents[1] / 'examples'/'three_divs64.wat'
    mask=(1<<64)-1
    cases=[(100,3,200,7,300,11),(mask,1,mask,1,mask,1),
           (1<<63,3,(1<<63)-1,7,mask,11),(0,1,0,1,0,1),
           (1,mask,mask,mask,mask,1)]
    cases += [tuple(0 if i==divisor else value for i,value in enumerate(cases[0]))
              for divisor in (1,3,5)]
    rng=random.Random(20261020)
    cases += [tuple(rng.getrandbits(64) for _ in range(6)) for _ in range(4)]
    manifest,path=differential(tmp_path,source.read_text(),cases,binary_input=True)
    metrics=manifest['metrics']
    assert metrics['gate_groups']>12500
    assert 1<metrics['lookup_batch_size']<=64
    assert metrics['coalesced_gate_groups']>8000
    assert metrics['font_bytes']<3*1024*1024
    assert metrics['font_bytes']<32*1024*1024
    assert metrics['glyphs']<65535
    with NativeFont(path) as font:
        with pytest.raises(IncompleteShaping):
            font.decode(font.shaper.shape(font.encode(cases[0]),enabled=False))
    # The same circuit still fails at the old maximum batch size. The change
    # therefore exercises lookup-offset capacity, rather than smaller gates.
    compiler=NativeCompiler(load(source)[0])
    values,fn,_,_=compiler.lower('run')
    old=tmp_path/'old-offset-limit.ttf'
    with pytest.raises(ResourceLimit,match='lookup layout capacity'):
        emit_font(compiler.c,values,compiler.flags,fn.params,fn.results,old,
                  lookup_batch_size=16,lookup_coalescing=False)
    assert not old.exists()


@pytest.mark.parametrize('conditional', [False, True])
def test_four_full_width_dividers_cross_extension_wrapper_capacity(tmp_path, conditional):
    source=Path(__file__).resolve().parents[1] / 'examples'/'four_divs64.wat'
    wat=source.read_text()
    if conditional:
        body=' '.join(f'local.get {i*2} local.get {i*2+1} i64.div_u'+(' i64.add' if i else '')
                      for i in range(4))
        wat=f'''(module (func (export "run") (param {'i64 '*8}i32) (result i64)
          local.get 8 if (result i64) {body} else i64.const 42 end))'''
    mask=(1<<64)-1
    ordinary=(100,3,200,7,300,11,400,13)
    cases=[ordinary,(mask,1)*4,(0,1)*4,
           (1<<63,3,(1<<63)-1,7,mask,11,1,mask),
           (mask,1,1,1,0,1,0,1)]
    cases += [tuple(0 if i==divisor else value for i,value in enumerate(ordinary))
              for divisor in (1,3,5,7)]
    rng=random.Random(20261022)
    cases += [tuple(rng.getrandbits(64) for _ in range(8)) for _ in range(4)]
    if conditional:cases=[(*args,active) for args in cases for active in (0,1)]
    manifest,path=differential(tmp_path,wat,cases,binary_input=True)
    metrics=manifest['metrics']
    assert metrics['gate_groups']>16000
    assert metrics['gate_subtables']<10000
    assert metrics['coalesced_gate_groups']>15000
    assert metrics['font_bytes']<32*1024*1024
    assert metrics['glyphs']<65535
    with NativeFont(path) as font:
        active=(*ordinary,1) if conditional else ordinary
        with pytest.raises(IncompleteShaping):
            font.decode(font.shaper.shape(font.encode(active),enabled=False))
        assert font.invoke(*active)==118
    compiler=NativeCompiler(load(tmp_path/'program.wat')[0])
    values,fn,_,_=compiler.lower('run')
    old=tmp_path/'separate-wrappers.ttf'
    with pytest.raises(ResourceLimit,match='lookup layout capacity'):
        emit_font(compiler.c,values,compiler.flags,fn.params,fn.results,old,
                  lookup_coalescing=False)
    assert not old.exists()


def test_two_independent_signed_dividers_cross_old_font_limits(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'examples' / 'expensive64.wat'
    sign = 1 << 63
    cases = [(100, 3, 200, 7), (-17, 3, 17, -3), (0, 1, 0, 1),
             (-sign, -7, sign - 1, 3), (sign - 1, 1, sign - 1, 1),
             (1, 0, 2, 1), (1, 1, 2, 0), (-sign, -1, 2, 1), (1, 1, -sign, -1)]
    rng = random.Random(20261017)
    cases += [tuple(rng.getrandbits(64) for _ in range(4)) for _ in range(6)]
    manifest, path = differential(tmp_path, source.read_text(), cases, binary_input=True)
    metrics = manifest['metrics']
    assert metrics['gates'] < 12000  # The smaller divider now fits this construction budget too.
    assert metrics['gate_groups'] > 5400
    assert metrics['lookups'] < 5400
    assert metrics['lookup_batch_size'] > 1
    assert metrics['glyphs'] < 65535
    with NativeFont(path) as font:
        with pytest.raises(IncompleteShaping):
            font.decode(font.shaper.shape(font.encode(cases[0]), enabled=False))
    with pytest.raises(ResourceLimit, match='max_gates=8000'):
        compile_source(source, tmp_path / 'small-budget.ttf', export='run', limits=Limits(max_gates=8000))
    compiler = NativeCompiler(load(source)[0])
    values, fn, _, _ = compiler.lower('run')
    unpacked = tmp_path / 'unpacked.ttf'
    with pytest.raises(ResourceLimit, match='lookup layout capacity'):
        emit_font(compiler.c, values, compiler.flags, fn.params, fn.results, unpacked,
                  lookup_batch_size=1,lookup_coalescing=False)
    assert not unpacked.exists()


@pytest.mark.parametrize('first,second,combine', [
    ('div_u', 'mul', 'xor'), ('mul', 'mul', 'add'), ('div_u', 'rem_u', None),
])
def test_expensive_operations_compose_with_v8(tmp_path, first, second, combine):
    expression = (f'local.get 0 local.get 1 i64.{first} '
                  f'local.get 2 local.get 3 i64.{second} i64.{combine}' if combine else
                  f'local.get 0 local.get 1 i64.{first} local.get 2 i64.{second}')
    wat = f'(module (func (export "run") (param i64 i64 i64 i64) (result i64) {expression}))'
    differential(tmp_path, wat, [(100, 3, 200, 7), (-1, 3, 7, -1),
                                (1 << 63, -1, (1 << 63) - 1, 1),
                                (1, 0, 2, 1), (1, 1, 0, 0)])


def test_capacity_limits_remain_enforced(tmp_path):
    assert Limits().max_gates == 24000
    for constructor in (Circuit, lambda n: Limits(max_gates=n)):
        with pytest.raises(ValueError):constructor(MAX_GATES + 1)
    circuit = Circuit()
    huge = circuit.argument(0, 22000)
    with pytest.raises(ResourceLimit, match='glyph-count'):
        emit_font(circuit, [huge], {}, ['i22000'], ['i22000'], tmp_path / 'too-many.ttf')
    for size in (0, 65, True):
        c = Circuit()
        with pytest.raises(ValueError, match='batch size'):
            emit_font(c, [c.argument(0, 1)], {}, ['i1'], ['i1'], tmp_path / 'invalid.ttf',
                      lookup_batch_size=size)


@pytest.mark.parametrize('conditional', [False, True])
def test_two_quotients_feed_full_width_multiplier(tmp_path, conditional):
    source = Path(__file__).resolve().parents[1] / 'examples' / 'divmul64.wat'
    wat = source.read_text()
    if conditional:
        wat = '''(module (func (export "run") (param i64 i64 i64 i64 i32) (result i64)
          local.get 4 if (result i64)
            local.get 0 local.get 1 i64.div_u
            local.get 2 local.get 3 i64.div_u i64.mul
          else i64.const 42 end))'''
    mask = (1 << 64) - 1
    cases = [(100, 3, 200, 7), (mask, 3, mask, 7), (mask, 1, mask, 1),
             (1 << 63, 1, 3, 1), (0, 1, mask, 1), (1, mask, mask, 1),
             (1, 0, 2, 1), (1, 1, 2, 0), (0, 0, 0, 0)]
    rng = random.Random(20261018)
    cases += [tuple(rng.getrandbits(64) for _ in range(4)) for _ in range(4)]
    if conditional:cases = [(*args, active) for args in cases for active in (0, 1)]
    manifest, path = differential(tmp_path, wat, cases, binary_input=not conditional)
    assert manifest['metrics']['glyphs'] < 65535
    assert manifest['metrics']['gates'] < 21000
    assert manifest['metrics']['font_bytes'] < 20 * 1024 * 1024
    with NativeFont(path) as font:
        with pytest.raises(IncompleteShaping):
            font.decode(font.shaper.shape(font.encode(cases[0]), enabled=False))


@pytest.mark.parametrize('conditional', [False, True])
def test_four_signed_operations_compose(tmp_path, conditional):
    source = Path(__file__).resolve().parents[1] / 'examples' / 'divmulcount64.wat'
    wat = source.read_text()
    if conditional:
        wat = '''(module (func (export "run") (param i64 i64 i64 i64 i32) (result i64 i64)
          (local $product i64)
          local.get 4 if (result i64)
            local.get 0 local.get 1 i64.div_s
            local.get 2 local.get 3 i64.div_s i64.mul
          else i64.const 42 end
          local.tee $product local.get $product i64.popcnt))'''
    sign = 1 << 63
    cases = [(100, 3, 200, 7), (-17, 3, 17, -3), (-sign, -7, sign - 1, 3),
             (sign - 1, 1, sign - 1, 1), (-sign, 1, 3, 1), (0, 1, 3, 1),
             (1, 0, 2, 1), (1, 1, 2, 0), (-sign, -1, 2, 1), (1, 1, -sign, -1)]
    rng = random.Random(20261019)
    cases += [tuple(rng.getrandbits(64) for _ in range(4)) for _ in range(3)]
    if conditional:cases = [(*args, active) for args in cases for active in (0, 1)]
    manifest, path = differential(tmp_path, wat, cases, binary_input=not conditional)
    metrics = manifest['metrics']
    assert metrics['gates'] < 16000
    assert 32768 < metrics['glyphs'] < 50000
    assert metrics['gate_groups'] > 11000
    assert metrics['font_bytes'] < 20 * 1024 * 1024
    assert metrics['unpacked_gate_groups'] > 0
    with NativeFont(path) as font:
        with pytest.raises(IncompleteShaping):
            font.decode(font.shaper.shape(font.encode(cases[0]), enabled=False))
    with pytest.raises(ResourceLimit, match='max_gates=12000'):
        compile_source(source, tmp_path / 'small-budget.ttf', export='run', limits=Limits(max_gates=12000))
