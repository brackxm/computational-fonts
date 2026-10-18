"""Integer multi-value block types and loop parameters agree with V8 and GSUB."""
from pathlib import Path

import pytest

from wasmfont.compiler import compile_source, Limits
from wasmfont.frontend import load, parse_text, signed_leb, unsigned_leb
from wasmfont.ir import BlockType, parse_binary
from wasmfont.oracle import execute_binary
from wasmfont.runtime import NativeFont, IncompleteShaping, ExecutionBoundExceeded, WasmTrap
from wasmfont.reference.interpreter import WasmTrap as ReferenceTrap


def compare(tmp_path, wat, cases, binary_input=False):
    source = tmp_path / 'program.wat'
    source.write_text(wat)
    module, data = load(source)
    fn = module.functions[module.exports['run'][1]]
    expected = execute_binary(data, 'run', fn.params, cases)
    if binary_input:
        source = source.with_suffix('.wasm')
        source.write_bytes(data)
    font = tmp_path / 'program.ttf'
    manifest = compile_source(source, font, export='run')
    with NativeFont(font) as native:
        for args, reference in zip(cases, expected):
            if 'trap' in reference:
                with pytest.raises(ReferenceTrap):module.invoke('run', args)
                with pytest.raises(WasmTrap):native.invoke(*args)
            else:
                values = tuple(int(v) & ((1 << int(t[1:])) - 1)
                               for v, t in zip(reference['values'], fn.results))
                assert tuple(module.invoke('run', args)) == values
                actual = native.invoke(*args)
                assert ((actual,) if len(values) == 1 else actual) == values
        with pytest.raises(IncompleteShaping):
            native.decode(native.shaper.shape(native.encode(cases[0]), enabled=False))
    return manifest, data


@pytest.mark.parametrize('binary_input', [False, True], ids=['WAT', 'binary'])
@pytest.mark.parametrize('folded', [False, True], ids=['flat', 'folded'])
def test_multi_result_block_branch_discards_temporaries(tmp_path, binary_input, folded):
    body = '(block $done (result i32 i64) i32.const 99 local.get 0 local.get 1 br $done)' if folded else '''
      block $done (result i32) (result i64)
        i32.const 99 local.get 0 local.get 1 br $done
      end $done'''
    wat = f'(module (func (export "run") (param i32 i64) (result i32 i64) {body}))'
    compare(tmp_path, wat, [(0, 0), (7, 11), (-1, -(1 << 63))], binary_input)


@pytest.mark.parametrize('binary_input', [False, True])
def test_block_inputs_preserve_the_stack_below_the_label(tmp_path, binary_input):
    wat = '''(module (type $pair (func (param i32 i64) (result i32 i64)))
      (func (export "run") (param i32 i64) (result i32 i64) (local $a i32) (local $b i64)
        i32.const 7 local.get 0 local.get 1
        block (type $pair) (param i32 i64) (result i32 i64)
          local.set $b local.set $a i32.const 99 local.get $a local.get $b br 0
        end
        local.set $b local.set $a local.get $a i32.add local.get $b))'''
    compare(tmp_path, wat, [(0, 0), (7, 11), (-1, -1)], binary_input)


@pytest.mark.parametrize('folded', [False, True])
def test_if_parameters_are_below_the_condition(tmp_path, folded):
    yes = 'local.set $b i32.const 1 i32.add local.get $b'
    no = 'local.set $b i32.const 2 i32.sub local.get $b i64.const 3 i64.xor'
    body = (f'(if (param i32 i64) (result i32 i64) (local.get 2) (then {yes}) (else {no}))'
            if folded else f'local.get 2 if (param i32 i64) (result i32 i64) {yes} else {no} end')
    wat = f'''(module (func (export "run") (param i32 i64 i32) (result i32 i64) (local $b i64)
      local.get 0 local.get 1 {body}))'''
    compare(tmp_path, wat, [(7, 11, 0), (7, 11, 1), (-1, -1, -1)])


def test_if_without_else_returns_its_inputs_on_false(tmp_path):
    wat = '''(module (func (export "run") (param i32 i64 i32) (result i32 i64)
      local.get 0 local.get 1 local.get 2
      if (param i32 i64) (result i32 i64) i64.const 1 i64.add end))'''
    compare(tmp_path, wat, [(7, 11, 0), (7, 11, 1), (-1, -1, 1)])


@pytest.mark.parametrize('branch', ['br_if $done', 'br_table $done $done'])
def test_conditional_multi_value_branch_preserves_results(tmp_path, branch):
    wat = f'''(module (func (export "run") (param i32) (result i32 i64)
      block $done (result i32 i64)
        i32.const 7 i64.const 11 local.get 0 {branch}
        i64.const 1 i64.add
      end))'''
    compare(tmp_path, wat, [(0,), (1,), (-1,)])


def test_branch_table_targets_nested_multi_value_labels(tmp_path):
    wat = '''(module (func (export "run") (param i32) (result i32 i64)
      block $outer (result i32 i64)
        block $inner (result i32 i64)
          i32.const 99 i32.const 7 i64.const 9 local.get 0 br_table $inner $outer $outer
        end
        i64.const 1 i64.add
      end))'''
    compare(tmp_path, wat, [(0,), (1,), (2,), (-1,)])


SUM_LOOP = '''(module (type $carry (func (param i32 i64) (result i64)))
  (func (export "run") (param i32) (result i64) (local $n i32) (local $sum i64)
    local.get 0 i64.const 0
    loop $again (type $carry)
      local.set $sum local.tee $n i32.eqz
      if (result i64)
        local.get $sum
      else
        i32.const 99 local.get $n i32.const 1 i32.sub
        local.get $sum local.get $n i64.extend_i32_u i64.add br $again
      end
    end))'''


@pytest.mark.parametrize('binary_input', [False, True])
def test_loop_backedges_carry_inputs_not_results(tmp_path, binary_input):
    compare(tmp_path, SUM_LOOP, [(0,), (1,), (3,), (7,)], binary_input)
    with NativeFont(tmp_path / 'program.ttf') as native:
        assert native.invoke(7) == 28
        with pytest.raises(ExecutionBoundExceeded, match='loop'):native.invoke(8)
        with pytest.raises(ExecutionBoundExceeded, match='loop'):native.invoke(-1)
        assert native.invoke(3) == 6


def test_loop_parameter_merges_from_different_backedges(tmp_path):
    wat = '''(module (func (export "run") (param i32) (result i64)
      (local $n i32) (local $sum i64)
      local.get 0 i64.const 0
      loop $again (param i32 i64) (result i64)
        local.set $sum local.tee $n i32.eqz
        if (result i64) local.get $sum
        else
          local.get $n i32.const 1 i32.and
          if
            local.get $n i32.const 1 i32.sub local.get $sum i64.const 3 i64.add br $again
          else
            local.get $n i32.const 1 i32.sub local.get $sum i64.const 5 i64.add br $again
          end
          unreachable
        end
      end))'''
    compare(tmp_path, wat, [(0,), (1,), (2,), (5,), (7,)])


def test_multi_value_results_compose_across_calls_and_traps(tmp_path):
    wat = '''(module
      (func $pair (param i64 i64) (result i64 i64)
        block (result i64 i64)
          local.get 0 local.get 1 i64.div_u local.get 0 local.get 1 i64.rem_u
        end)
      (func (export "run") (param i64 i64 i32) (result i64 i64)
        local.get 0 local.get 1 call $pair local.get 2
        if (param i64 i64) (result i64 i64) unreachable end))'''
    compare(tmp_path, wat, [(17, 3, 0), (-1, 4294967297, 0), (17, 0, 0), (17, 3, 1)])


def section(tag, payload):
    return bytes([tag]) + unsigned_leb(len(payload)) + payload


@pytest.mark.parametrize('type_index', [0, 63, 64, 127, 128])
def test_binary_block_type_uses_signed_33_bit_index(tmp_path, type_index):
    # Build independently of the WAT type interner, including indices that need
    # sign padding and multiple bytes. Each block returns (i32, i64).
    types = b'\x60\0\0' * type_index + b'\x60\0\2\x7f\x7e'
    body = b'\0\x02' + signed_leb(type_index, 33) + b'\x41\x07\x42\x09\x0b\x0b'
    data = (b'\0asm\1\0\0\0' + section(1, unsigned_leb(type_index + 1) + types) +
            section(3, b'\1' + unsigned_leb(type_index)) + section(7, b'\1\3run\0\0') +
            section(10, b'\1' + unsigned_leb(len(body)) + body))
    assert execute_binary(data, 'run', [], [()]) == [{'values': ['7', '9']}]
    source = tmp_path / 'indexed.wasm'
    source.write_bytes(data)
    assert parse_binary(source)[0].code[0] == ('block', BlockType(results=('i32', 'i64')))
    module, _ = load(source)
    assert module.invoke('run', []) == [7, 9]
    font = source.with_suffix('.ttf')
    compile_source(source, font)
    with NativeFont(font) as native:assert native.invoke() == (7, 9)


@pytest.mark.parametrize('header', [
    '(type)', '(type 0 0)', '(type "0")', '(type -1)', '(type 1)',
    '(type 0) (type 0)', '(type $unknown)', '(result i32) (param i32)',
    '(param i32) (type 0)', '(param $named i32)', '(result "i32")', '(param f32)',
    '(type 0) (param i64) (result i32 i64)',
])
def test_invalid_block_signature_rejected_before_encoding(tmp_path, header):
    wat = f'''(module (type (func (param i32) (result i32 i64)))
      (func (export "run") block {header} end))'''
    with pytest.raises((ValueError, NotImplementedError)):parse_text(wat)
    source = tmp_path / 'invalid.wat'
    source.write_text(wat)
    with pytest.raises((ValueError, NotImplementedError)):compile_source(source, source.with_suffix('.ttf'))
    assert not source.with_suffix('.ttf').exists()


@pytest.mark.parametrize('body', [
    'block (param i32) (result i32) end',
    'i64.const 0 block (param i32) (result i32) end',
    'block (result i32 i64) i32.const 1 br 0 end',
    'i32.const 1 loop (param i32) (result i64) i64.const 1 br 0 end',
    'i32.const 1 if (result i32 i64) i32.const 1 i64.const 2 end',
])
def test_ill_typed_multi_value_control_flow_is_rejected_by_v8(tmp_path, body):
    source = tmp_path / 'invalid.wat'
    source.write_text(f'(module (func (export "run") {body}))')
    with pytest.raises(ValueError, match='V8 rejected'):compile_source(source, source.with_suffix('.ttf'))
    assert not source.with_suffix('.ttf').exists()
    assert not source.with_suffix('.json').exists()


@pytest.mark.parametrize('kind', ['block', 'loop', 'if'])
def test_block_parameters_can_be_consumed_without_results(tmp_path, kind):
    condition = 'local.get 2' if kind == 'if' else ''
    alternative = 'else drop drop' if kind == 'if' else ''
    wat = f'''(module (func (export "run") (param i32 i64 i32) (result i32)
      i32.const 42 local.get 0 local.get 1 {condition}
      {kind} (param i32 i64) drop drop {alternative} end))'''
    compare(tmp_path, wat, [(7, 11, 0), (-1, -1, 1)])


def test_loop_branch_table_uses_parameter_arity(tmp_path):
    wat = '''(module (func (export "run") (param i32) (result i64)
      (local $n i32) (local $sum i64)
      block $exit (result i32 i64)
        local.get 0 i64.const 0
        loop $again (param i32 i64) (result i64)
          local.set $sum local.set $n
          local.get $n i32.const 1 i32.sub
          local.get $sum local.get $n i64.extend_i32_u i64.add
          local.get $n i32.const 1 i32.le_u br_table $again $exit $exit
        end
        i32.const 0 unreachable
      end
      local.set $sum drop local.get $sum))'''
    compare(tmp_path, wat, [(1,), (2,), (3,), (7,)])


def test_typed_loop_respects_configured_iteration_bound(tmp_path):
    source = tmp_path / 'bounded.wat'
    source.write_text(SUM_LOOP)
    font = source.with_suffix('.ttf')
    compile_source(source, font, limits=Limits(loop_iterations=3))
    with NativeFont(font) as native:
        assert native.invoke(2) == 3
        with pytest.raises(ExecutionBoundExceeded, match='loop'):native.invoke(3)


def test_division_results_compose_through_loop_parameters(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'examples' / 'division_loop64.wat'
    cases = [(100, 7, 0), (100, 7, 3), (-1, 4294967297, 3), (-1, 7, 7),
             (-1, 1, 7), (1, 0, 0), (1, 0, 7)]
    compare(tmp_path, source.read_text(), cases, binary_input=True)
    with NativeFont(tmp_path / 'program.ttf') as native:
        assert native.invoke(100, 7, 3) == (23, 5)
        with pytest.raises(ExecutionBoundExceeded, match='loop'):native.invoke(100, 7, 8)
        assert native.invoke(100, 7, 0) == (14, 2)


def test_untaken_loop_branch_keeps_parameter_values_for_fallthrough(tmp_path):
    wat = '''(module (func (export "run") (param i32) (result i32 i64)
      (local $n i32) (local $sum i64)
      i32.const 7 local.get 0 i64.const 0
      loop $again (param i32 i64) (result i64)
        local.set $sum local.set $n
        local.get $n i32.const 1 i32.sub local.get $sum i64.const 1 i64.add
        local.get $n i32.const 1 i32.gt_u br_if $again
        local.set $sum drop local.get $sum
      end))'''
    compare(tmp_path, wat, [(1,), (2,), (7,), (8,)])
