"""Null-reference branches keep different stacks on each successor path."""
import pytest

from wasmfont.compiler import compile_source,Limits
from wasmfont.frontend import binary,load,parse_text
from wasmfont.ir import parse_binary
from wasmfont.module import load_binary
from wasmfont.runtime import NativeFont,WasmTrap,ExecutionBoundExceeded
from wasmfont.validation import validate
from .test_indirect_calls import compare
from .test_data_segments import sections,encode_sections


@pytest.mark.parametrize('binary_input',[False,True])
@pytest.mark.parametrize('folded',[False,True])
def test_br_on_null_passes_other_results_and_retains_non_null_reference(tmp_path,binary_input,folded):
    branch='(br_on_null $missing (local.get 0))' if folded else 'local.get 0 br_on_null $missing'
    wat=f'''(module (table 3 funcref) (elem (i32.const 0) $f) (elem (i32.const 2) $f)
      (func $f)
      (func $probe (param funcref i64) (result i64)
        block $missing (result i64)
          local.get 1 {branch} ref.as_non_null drop i64.const 7 i64.add return
        end)
      (func (export "run") (param i32 i64) (result i64)
        local.get 0 table.get local.get 1 call $probe))'''
    _,module,data=compare(tmp_path,wat,[(slot,v) for slot in [0,1,2,3,-1] for v in [0,7,-1,1<<63]],binary_input=binary_input)
    assert binary(module)==data


@pytest.mark.parametrize('binary_input',[False,True])
@pytest.mark.parametrize('folded',[False,True])
def test_br_on_non_null_passes_reference_on_branch_and_discards_null_on_fallthrough(tmp_path,binary_input,folded):
    branch='(br_on_non_null $found (table.get (local.get 1)))' if folded else 'local.get 1 table.get br_on_non_null $found'
    wat=f'''(module (table 3 funcref) (elem (i32.const 0) $first $second)
      (func $first (param i64) (result i64) local.get 0 i64.const 3 i64.add)
      (func $second (param i64) (result i64) local.get 0 i64.const -1 i64.xor)
      (func (export "run") (param i64 i32) (result i64) (local $ref funcref)
        block $found (result i64 funcref)
          local.get 0 {branch}
          i64.const 7 i64.add ref.func $first
        end
        local.set $ref
        i32.const 2 local.get $ref table.set
        i32.const 2 call_indirect (param i64) (result i64)))'''
    compare(tmp_path,wat,[(v,slot) for v in [0,7,-1,1<<63] for slot in [0,1,2,3,-1]],binary_input=binary_input)


def test_br_on_null_can_target_implicit_function_label(tmp_path):
    wat='''(module (table 2 funcref) (elem (i32.const 0) $f)
      (func $f)
      (func (export "run") (param i32 i64) (result i64)
        local.get 1 local.get 0 table.get br_on_null 0
        drop i64.const 3 i64.mul))'''
    compare(tmp_path,wat,[(slot,v) for slot in [0,1,2] for v in [0,7,-1]])


def test_br_on_non_null_can_return_multiple_values_with_a_reference(tmp_path):
    wat='''(module (table 2 funcref) (elem (i32.const 0) $f)
      (func $f)
      (func $probe (param funcref i64) (result i64 funcref)
        local.get 1 local.get 0 br_on_non_null 0
        i64.const 7 i64.add ref.func $f)
      (func (export "run") (param i32 i64) (result i64 i32)
        local.get 0 table.get local.get 1 call $probe ref.is_null))'''
    compare(tmp_path,wat,[(slot,v) for slot in [0,1,2] for v in [0,7,-1]])


@pytest.mark.parametrize('op',['br_on_null','br_on_non_null'])
def test_reference_branches_can_skip_multiple_nested_blocks(tmp_path,op):
    # br_on_non_null carries a reference to the outer label; br_on_null
    # consumes its reference and carries only the numeric result.
    extra='funcref' if op=='br_on_non_null' else ''
    fallback='ref.null func' if extra else ''
    discard='drop' if extra else ''
    wat=f'''(module (table 2 funcref) (elem (i32.const 0) $f) (func $f)
      (func (export "run") (param i32) (result i64)
        block $outer (result i64 {extra})
          block block
            i64.const 42 local.get 0 table.get {op} $outer
            {'drop' if op=='br_on_null' else ''} drop
          end end
          i64.const 99 {fallback}
        end {discard}))'''
    compare(tmp_path,wat,[(0,),(1,),(2,)])


def test_br_on_null_loop_backedge_carries_parameters_and_respects_bound(tmp_path):
    wat='''(module (table 2 funcref) (elem (i32.const 0) $f) (func $f)
      (func (export "run") (param i32) (result i32) (local $count i32)
        block $done (result i32)
          i32.const 0 loop $again (param i32) (result i32)
            i32.const 1 i32.add local.tee $count
            local.get $count i32.const 3 i32.eq br_if $done
            local.get 0 table.get br_on_null $again drop
          end
        end))'''
    compare(tmp_path,wat,[(0,),(1,),(2,)],limits=Limits(loop_iterations=3))
    compile_source(tmp_path/'program.wat',tmp_path/'small.ttf',limits=Limits(loop_iterations=2))
    with NativeFont(tmp_path/'small.ttf') as font:
        assert font.invoke(0)==1
        with pytest.raises(ExecutionBoundExceeded,match='loop'):font.invoke(1)


@pytest.mark.parametrize('folded',[False,True])
def test_null_assertion_traps_only_on_the_executed_path_and_precedes_division(tmp_path,folded):
    expression='(ref.as_non_null (table.get (local.get 0)))' if folded else 'local.get 0 table.get ref.as_non_null'
    wat=f'''(module (table 2 funcref) (elem (i32.const 0) $f) (func $f)
      (func (export "run") (param i32 i32 i64) (result i64)
        local.get 1 if {expression} drop end
        i64.const 100 local.get 2 i64.div_u))'''
    compare(tmp_path,wat,[(slot,enabled,divisor) for slot in [0,1,2] for enabled in [0,1] for divisor in [0,1,7,-1]])
    with NativeFont(tmp_path/'program.ttf') as font:
        with pytest.raises(WasmTrap,match='null_reference'):font.invoke(1,1,0)
        with pytest.raises(WasmTrap,match='integer_divide_by_zero'):font.invoke(1,0,0)
        with pytest.raises(WasmTrap,match='table_out_of_bounds'):font.invoke(2,1,0)


def test_constant_reference_branches_eliminate_unreachable_traps(tmp_path):
    wat='''(module (elem declare func $f) (func $f)
      (func (export "run") (result i32)
        block ref.null func br_on_null 0 drop unreachable end
        block (result funcref) ref.func $f br_on_non_null 0 unreachable end
        ref.as_non_null drop i32.const 42))'''
    compare(tmp_path,wat,[()])


@pytest.mark.parametrize('instruction',['ref.as_non_null','br_on_null 0','br_on_non_null 0'])
def test_reference_instructions_require_reference_operands(tmp_path,instruction):
    path=tmp_path/'bad.wat';path.write_text(f'(module (func (export "run") i32.const 0 {instruction} drop))')
    with pytest.raises(ValueError,match='V8 rejected'):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


@pytest.mark.parametrize('wat',[
    '(module (global (mut (ref null extern)) (ref.null extern)))',
    '(module (func (param (ref extern))))',
    '(module (func (result (ref any)) unreachable))',
    '(module (func ref.null func ref.null func i32.const 0 select (result (ref null struct)) drop))',
])
def test_non_function_reference_declarations_remain_unsupported(wat):
    with pytest.raises((ValueError,NotImplementedError)):parse_text(wat)


def test_reference_branch_depths_decode_padded_leb_operands(tmp_path):
    wat='''(module (func (export "run") (result i32)
      block ref.null func br_on_null 0 drop unreachable end i32.const 42))'''
    data=binary(parse_text(wat))
    parts=[(sid,payload.replace(b'\xd5\x00',b'\xd5\x80\x00')) if sid==10 else (sid,payload) for sid,payload in sections(data)]
    # The extra immediate byte also increases the sole function body's size.
    parts=[(sid,payload[:1]+bytes([payload[1]+1])+payload[2:]) if sid==10 else (sid,payload) for sid,payload in parts]
    data=encode_sections(parts);validate(data)
    path=tmp_path/'padded.wasm';path.write_bytes(data)
    assert ('br_on_null',0) in parse_binary(path)[0].code
    assert load_binary(path).invoke('run',[])==[42]
    compile_source(path,path.with_suffix('.ttf'))
    with NativeFont(path.with_suffix('.ttf')) as font:assert font.invoke()==42
