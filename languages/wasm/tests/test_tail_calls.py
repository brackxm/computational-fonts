"""Direct and indirect tail calls replace frames and retain Wasm state."""
from pathlib import Path
import subprocess
import sys

import pytest

from wasmfont.compiler import compile_source,Limits
from wasmfont.frontend import load
from wasmfont.ir import parse_binary
from wasmfont.oracle import execute_binary
from wasmfont.reference.interpreter import WasmTrap as ReferenceTrap
from wasmfont.runtime import NativeFont,WasmTrap,ExecutionBoundExceeded,IncompleteShaping
from .test_indirect_calls import compare,independent_binary
from .test_data_segments import sections,encode_sections


@pytest.mark.parametrize('binary_input',[False,True])
@pytest.mark.parametrize('folded',[False,True])
def test_direct_tail_recursion_uses_one_frame_and_discards_old_locals(tmp_path,binary_input,folded):
    tail='(return_call $walk (i32.sub (local.get 0) (i32.const 1)) (i64.add (local.get 1) (i64.const 1)))' if folded else 'local.get 0 i32.const 1 i32.sub local.get 1 i64.const 1 i64.add return_call $walk'
    wat=f'''(module (func $walk (export "run") (param i32 i64) (result i64 i32) (local $zero i32)
      local.get 0 i32.eqz if (result i64 i32) local.get 1 local.get $zero
      else i32.const 99 local.set $zero {tail} end))'''
    compare(tmp_path,wat,[(n,v) for n in [0,1,3,8] for v in [0,-1,0x807f060504030201]],
            binary_input=binary_input,limits=Limits(call_depth=1))
    with NativeFont(tmp_path/'program.ttf') as font:
        with pytest.raises(ExecutionBoundExceeded,match='tail_call'):font.invoke(9,100)
        with pytest.raises(IncompleteShaping):font.decode(font.shaper.shape(font.encode([3,100]),enabled=False))


@pytest.mark.parametrize('form',['plain','block','loop','if'])
def test_tail_exit_discards_stack_prefix_and_merges_different_callee_locals(tmp_path,form):
    first='i32.const 999 local.get 0 local.get 1 return_call $a'
    second='i64.const 888 local.get 0 local.get 1 return_call $b'
    body={'plain':first,'block':f'block {first} end unreachable',
          'loop':f'loop {first} end unreachable',
          'if':f'local.get 2 if (result i32 i64) {first} else {second} end'}[form]
    wat=f'''(module
      (func $a (param i64 i32) (result i32 i64) (local i32) local.get 1 local.get 0)
      (func $b (param i64 i32) (result i32 i64) (local i64 i64 funcref)
        local.get 1 i32.const 3 i32.add local.get 0 i64.const -1 i64.xor)
      (func (export "run") (param i64 i32 i32) (result i32 i64) {body}))'''
    compare(tmp_path,wat,[(v,x,b) for v in [0,-1,0x807f060504030201] for x in [0,-1] for b in [0,1]],limits=Limits(call_depth=1))


@pytest.mark.parametrize('table',[0,1])
@pytest.mark.parametrize('folded',[False,True])
def test_indirect_tail_call_uses_selected_table_and_structural_types(tmp_path,table,folded):
    call=f'(return_call_indirect {table} (param i64 i64) (result i64) (local.get 0) (local.get 1) (local.get 2))' if folded else f'local.get 0 local.get 1 local.get 2 return_call_indirect {table} (param i64 i64) (result i64)'
    wat=f'''(module (table 4 funcref) (table 4 funcref)
      (elem (table 0) (i32.const 0) $add $divide $wrong)
      (elem (table 1) (i32.const 0) $divide $add $wrong)
      (func $add (param i64 i64) (result i64) local.get 0 local.get 1 i64.add)
      (func $divide (param i64 i64) (result i64) local.get 0 local.get 1 i64.div_u)
      (func $wrong (result i32) i32.const 7)
      (func (export "run") (param i64 i64 i32) (result i64) {call}))'''
    compare(tmp_path,wat,[(a,b,slot) for a,b in [(100,7),(-1,1),(1,0)] for slot in [0,1,2,3,4,-1]],limits=Limits(call_depth=1))


def test_invalid_indirect_target_traps_before_tail_bound(tmp_path):
    path=tmp_path/'bounds.wat';path.write_text('''(module (table 3 funcref)
      (elem (i32.const 0) $valid $wrong)
      (func $valid (result i32) i32.const 42) (func $wrong (result i64) i64.const 7)
      (func (export "run") (param i32) (result i32) local.get 0 return_call_indirect (result i32)))''')
    compile_source(path,path.with_suffix('.ttf'),limits=Limits(call_depth=1,tail_calls=0))
    with NativeFont(path.with_suffix('.ttf')) as font:
        with pytest.raises(ExecutionBoundExceeded,match='tail_call'):font.invoke(0)
        for slot,reason in [(1,'indirect_call_type_mismatch'),(2,'uninitialized_element'),(3,'table_out_of_bounds'),(-1,'table_out_of_bounds')]:
            with pytest.raises(WasmTrap,match=reason):font.invoke(slot)


@pytest.mark.parametrize('outer,inner,required',[
    ('call','return_call',2),('return_call','return_call',1),('return_call','call',2),
])
def test_ordinary_calls_still_consume_depth_and_preserve_caller_stack(tmp_path,outer,inner,required):
    prefix='i32.const 100' if outer=='call' else 'i64.const 999'
    suffix='i32.add' if outer=='call' else ''
    wat=f'''(module (func $leaf (result i32) i32.const 7)
      (func $middle (result i32) {inner} $leaf)
      (func (export "run") (result i32) {prefix} {outer} $middle {suffix}))'''
    compare(tmp_path,wat,[()],limits=Limits(call_depth=required))
    if required>1:
        compile_source(tmp_path/'program.wat',tmp_path/'small.ttf',export='run',limits=Limits(call_depth=required-1))
        with NativeFont(tmp_path/'small.ttf') as font:
            with pytest.raises(ExecutionBoundExceeded,match='call'):font.invoke()


def test_start_and_recursive_indirect_tails_preserve_all_state_and_have_separate_budgets(tmp_path):
    wat='''(module (memory 0 1) (data $p "ABCD")
      (global $count (mut i32) (i32.const 0))
      (table 1 funcref) (table $ops 1 2 funcref) (elem (table $ops) (i32.const 0) $step)
      (func $start return_call $init) (start $start)
      (func $init i32.const 1 memory.grow drop
        i32.const 0 i32.const 0 i32.const 4 memory.init $p data.drop $p
        ref.func $step i32.const 1 table.grow $ops drop
        i32.const 1 global.set $count)
      (func $step (param i32) (result i32 i32 i32 i32)
        local.get 0 if (result i32 i32 i32 i32)
          global.get $count i32.const 1 i32.add global.set $count
          i32.const 0 global.get $count i32.store8
          local.get 0 i32.const 1 i32.sub i32.const 1
          return_call_indirect $ops (param i32) (result i32 i32 i32 i32)
        else i32.const 0 i32.load global.get $count memory.size table.size $ops end)
      (func (export "run") (param i32) (result i32 i32 i32 i32) local.get 0 return_call $step))'''
    _,module,_=compare(tmp_path,wat,[(n,) for n in [0,1,2,7]],limits=Limits(call_depth=1))
    with NativeFont(tmp_path/'program.ttf') as font:
        with pytest.raises(ExecutionBoundExceeded,match='tail_call'):font.invoke(8)
        assert font.invoke(2)==(0x44434203,3,1,2)
        assert font.invoke(0)==(0x44434241,1,1,2)
    state=module.instantiate()
    assert module.invoke('run',[2],state=state)==[0x44434203,3,1,2]
    assert module.invoke('run',[2],state=state)==[0x44434205,5,1,2]


def test_reference_valued_tail_arguments_and_results_keep_their_types(tmp_path):
    wat='''(module (table 1 funcref) (elem declare func $target)
      (func $target (param i32) (result i32) local.get 0 i32.const 7 i32.add)
      (func $walk (param funcref i32) (result funcref)
        local.get 1 if (result funcref)
          local.get 0 local.get 1 i32.const 1 i32.sub return_call $walk
        else local.get 0 end)
      (func (export "run") (param i32 i32 i32) (result i32)
        i32.const 0 ref.func $target ref.null func local.get 0 select (result funcref)
        local.get 1 call $walk table.set
        local.get 2 i32.const 0 return_call_indirect (param i32) (result i32)))'''
    compare(tmp_path,wat,[(selected,n,v) for selected in [0,1] for n in [0,1,8] for v in [0,-1]],limits=Limits(call_depth=2))


@pytest.mark.parametrize('indirect',[False,True])
def test_independent_binary_padded_tail_operands(tmp_path,indirect):
    data=independent_binary(table_count=2)
    # Install target 0 in table 1 and tail-call it with padded immediates.
    element=b'\x01\x02\x81\x00\x41\x00\x0b\x00\x01\x00'
    body=b'\x00\x20\x00'+(b'\x20\x01\x13\x80\x00\x81\x00' if indirect else b'\x12\x80\x00')+b'\x0b'
    target=b'\x00\x20\x00\x41\x01\x6a\x0b'
    code=b'\x02'+bytes([len(target)])+target+bytes([len(body)])+body
    data=encode_sections([(tag,element if tag==9 else code if tag==10 else payload) for tag,payload in sections(data)])
    path=tmp_path/'tail.wasm';path.write_bytes(data)
    assert parse_binary(path)[1].code[-1][0]==('return_call_indirect' if indirect else 'return_call')
    assert execute_binary(data,'run',['i32','i32'],[(7,0),(9,1)])[0]=={'values':['8']}
    compile_source(path,path.with_suffix('.ttf'),export='run',limits=Limits(call_depth=1))
    with NativeFont(path.with_suffix('.ttf')) as font:
        assert font.invoke(7,0)==8
        if indirect:
            with pytest.raises(WasmTrap,match='uninitialized_element'):font.invoke(9,1)
        else:assert font.invoke(9,1)==10


def test_reference_tail_calls_use_fuel_without_growing_python_stack(tmp_path):
    path=tmp_path/'fuel.wat';path.write_text('''(module
      (func $walk (export "run") (param i32 i32) (result i32)
        local.get 0 if (result i32)
          local.get 0 i32.const 1 i32.sub local.get 1 i32.const 1 i32.add return_call $walk
        else local.get 1 end))''')
    module,data=load(path)
    assert execute_binary(data,'run',['i32','i32'],[(2000,7)])==[{'values':['2007']}]
    assert module.invoke('run',[2000,7])==[2007]
    with pytest.raises(ReferenceTrap,match='fuel'):module.invoke('run',[2000,7],fuel=50)


def test_tail_exits_from_loops_keep_loop_and_tail_bounds_distinct(tmp_path):
    wat='''(module (func $finish (result i32) i32.const 42)
      (func $walk (export "run") (param i32 i32) (result i32)
        local.get 0 if (result i32)
          loop $again (result i32)
            local.get 0 i32.const 1 i32.sub local.tee 0 i32.eqz
            if return_call $finish end
            local.get 1 if local.get 0 local.get 1 return_call $walk end
            br $again
          end
        else i32.const 42 end))'''
    compare(tmp_path,wat,[(n,mode) for n in [0,1,3,8] for mode in [0,1]],limits=Limits(call_depth=1))
    with NativeFont(tmp_path/'program.ttf') as font:
        with pytest.raises(ExecutionBoundExceeded,match='^loop$'):font.invoke(9,0)
        with pytest.raises(ExecutionBoundExceeded,match='tail_call'):font.invoke(9,1)


def test_normal_child_calls_receive_independent_tail_budgets(tmp_path):
    wat='''(module (func $walk (param i32) (result i32)
        local.get 0 if (result i32) local.get 0 i32.const 1 i32.sub return_call $walk
        else i32.const 1 end)
      (func (export "run") (param i32) (result i32)
        local.get 0 call $walk local.get 0 call $walk i32.add))'''
    compare(tmp_path,wat,[(0,),(1,),(8,)],limits=Limits(call_depth=2))


def test_maximum_tail_and_normal_depth_bounds_do_not_overflow_python_stack(tmp_path):
    wat='''(module (func $walk (param i32 i32) (result i32)
      local.get 0 if (result i32)
        local.get 0 i32.const 1 i32.sub local.get 1 return_call $walk
      else local.get 1 if (result i32)
        i32.const 64 local.get 1 i32.const 1 i32.sub call $walk
      else i32.const 42 end end)
      (func (export "run") (result i32) i32.const 64 i32.const 30 call $walk))'''
    compare(tmp_path,wat,[()],limits=Limits(call_depth=32,tail_calls=64))


def test_tail_cycles_report_a_bound_without_a_result(tmp_path):
    path=tmp_path/'cycle.wat';path.write_text('''(module
      (func $a (export "run") (result i32) return_call $b)
      (func $b (result i32) return_call $a))''')
    module,_=load(path);compile_source(path,path.with_suffix('.ttf'),limits=Limits(call_depth=1))
    with NativeFont(path.with_suffix('.ttf')) as font:
        with pytest.raises(ExecutionBoundExceeded,match='tail_call'):font.invoke()
    with pytest.raises(ReferenceTrap,match='fuel'):module.invoke('run',[],fuel=30)


@pytest.mark.parametrize('body',[
    'return_call 99','return_call 0','i64.const 0 return_call 0','return_call $wrong',
    'i32.const 0 return_call_indirect 1 (result i32)',
    'i64.const 0 return_call_indirect (result i32)',
    'i32.const 0 return_call_indirect (result i64)',
])
def test_invalid_tail_indices_operands_and_result_types_fail_before_output(tmp_path,body):
    path=tmp_path/'invalid.wat';path.write_text(f'''(module (table 1 funcref)
      (func (param i32) (result i32) local.get 0) (func $wrong (result i64) i64.const 0)
      (func (export "run") (result i32) {body}))''')
    with pytest.raises(ValueError):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


def test_cli_tail_budget_and_invalid_limits(tmp_path):
    path=tmp_path/'cli.wat';path.write_text('''(module
      (func $walk (export "run") (param i32) (result i32)
        local.get 0 if (result i32) local.get 0 i32.const 1 i32.sub return_call $walk
        else i32.const 42 end))''')
    root=Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable,str(root/'build.py'),str(path),'-o',str(path.with_suffix('.ttf')),
                    '--call-depth','1','--tail-calls','12'],check=True,capture_output=True,timeout=30)
    with NativeFont(path.with_suffix('.ttf')) as font:
        assert font.invoke(12)==42
        with pytest.raises(ExecutionBoundExceeded,match='tail_call'):font.invoke(13)
    for invalid in [-1,65,1.5,True,None]:
        with pytest.raises(ValueError,match='tail_calls'):Limits(tail_calls=invalid)
