"""Calls through typed function values share normal bounds and runtime state."""
import pytest

from wasmfont.compiler import compile_source,Limits
from wasmfont.frontend import binary,parse_text,unsigned_leb
from wasmfont.ir import parse_binary
from wasmfont.module import load_binary
from wasmfont.oracle import execute_binary
from wasmfont.runtime import NativeFont,WasmTrap,ExecutionBoundExceeded
from .test_indirect_calls import compare
from .test_data_segments import sections,encode_sections


@pytest.mark.parametrize('binary_input',[False,True])
@pytest.mark.parametrize('folded',[False,True])
def test_callbacks_are_called_without_any_table(tmp_path,binary_input,folded):
    call='(call_ref $binary (local.get 1) (local.get 2) (local.get 0))' if folded else 'local.get 1 local.get 2 local.get 0 call_ref $binary'
    wat=f'''(module (type $binary (func (param i64 i64) (result i64)))
      (elem declare func $add $divide)
      (func $add (type $binary) local.get 0 local.get 1 i64.add)
      (func $divide (type $binary) local.get 0 local.get 1 i64.div_u)
      (func $apply (param (ref null $binary) i64 i64) (result i64)
        i64.const 7 {call} i64.add)
      (func (export "run") (param i64 i64 i32) (result i64)
        local.get 2 if (result (ref null $binary)) ref.func $divide else ref.func $add end
        local.get 0 local.get 1 call $apply))'''
    _,module,data=compare(tmp_path,wat,[(a,b,which) for a,b in [(100,7),(-1,1),(1,0),(1<<63,-1)] for which in [0,1]],binary_input=binary_input)
    assert not module.tables and binary(module)==data


@pytest.mark.parametrize('source',['global','local','direct'])
def test_null_reference_traps_before_call_depth_bound(tmp_path,source):
    reference={'global':'global.get $empty','local':'local.get $empty','direct':'ref.null $word'}[source]
    local='(local $empty (ref null $word))' if source=='local' else ''
    path=tmp_path/'null.wat';path.write_text(f'''(module (type $word (func (result i32)))
      (global $empty (ref null $word) (ref.null $word))
      (func (export "run") (result i32) {local} {reference} call_ref $word))''')
    compile_source(path,path.with_suffix('.ttf'),limits=Limits(call_depth=1))
    with NativeFont(path.with_suffix('.ttf')) as font:
        with pytest.raises(WasmTrap,match='null_reference'):font.invoke()


def test_reference_call_arguments_results_globals_memory_and_start_are_shared(tmp_path):
    wat='''(module (type $binary (func (param i64 i32) (result i32 i64)))
      (type $alias (func (param i64 i32) (result i32 i64)))
      (memory 1) (global $count (mut i32) (i32.const 0))
      (global $chosen (mut (ref null $binary)) (ref.null $binary))
      (func $swap (type $binary)
        global.get $count i32.const 1 i32.add global.set $count
        i32.const 0 local.get 1 i32.store
        local.get 1 local.get 0)
      (elem declare func $swap)
      (func $start ref.func $swap global.set $chosen) (start $start)
      (func $apply (param (ref null $alias) i64 i32) (result i32 i64)
        local.get 1 local.get 2 local.get 0 call_ref $alias)
      (func (export "run") (param i64 i32) (result i32 i64 i32 i32)
        global.get $chosen local.get 0 local.get 1 call $apply
        global.get $count i32.const 0 i32.load))'''
    compare(tmp_path,wat,[(a,b) for a in [0,-1,1<<63] for b in [0,7,-1]])


def test_higher_order_reference_calls_return_typed_function_values(tmp_path):
    wat='''(module (type $word (func (param i32) (result i32)))
      (type $factory (func (param (ref $word)) (result (ref $word))))
      (func $increment (type $word) local.get 0 i32.const 7 i32.add)
      (func $identity (type $factory) local.get 0)
      (elem declare func $increment $identity)
      (func (export "run") (param i32) (result i32)
        local.get 0 ref.func $increment ref.func $identity call_ref $factory call_ref $word))'''
    compare(tmp_path,wat,[(0,),(7,),(-1,)])


def test_conditional_reference_call_does_not_trap_on_inactive_null(tmp_path):
    wat='''(module (type $word (func (param i64) (result i64)))
      (func (export "run") (param i64 i32) (result i64)
        local.get 1 if (result i64)
          local.get 0 ref.null $word call_ref $word
        else local.get 0 end))'''
    compare(tmp_path,wat,[(a,b) for a in [0,7,-1] for b in [0,1]])


def test_reference_recursion_consumes_ordinary_call_depth(tmp_path):
    wat='''(module (type $sum (func (param i32) (result i32)))
      (elem declare func $sum)
      (func $sum (export "run") (type $sum)
        local.get 0 if (result i32)
          local.get 0 local.get 0 i32.const 1 i32.sub ref.func $sum call_ref $sum i32.add
        else i32.const 0 end))'''
    compare(tmp_path,wat,[(0,),(1,),(3,),(7,)])
    with NativeFont(tmp_path/'program.ttf') as font:
        with pytest.raises(ExecutionBoundExceeded,match='call'):font.invoke(8)


@pytest.mark.parametrize('index',[0,127,128])
@pytest.mark.parametrize('padded',[False,True])
def test_reference_call_binary_unsigned_type_index(tmp_path,index,padded):
    data=binary(parse_text('''(module (type $word (func (param i32) (result i32)))
      (func $f (type $word) local.get 0 i32.const 7 i32.add) (elem declare func $f)
      (func (export "run") (type $word) local.get 0 ref.func $f call_ref $word))'''))
    def encoded(n):
        value=unsigned_leb(n)
        return value[:-1]+bytes([value[-1]|128,0]) if padded else value
    parts=[]
    for sid,body in sections(data):
        if sid==1:body=unsigned_leb(index+1)+b'\x60\x01\x7f\x01\x7f'*(index+1)
        if sid==10:
            from wasmfont.ir import uleb
            count,pos=uleb(body,0);bodies=[]
            for _ in range(count):
                size,pos=uleb(body,pos);code=body[pos:pos+size];pos+=size
                code=code.replace(b'\x14\x00',b'\x14'+encoded(index))
                bodies.append(unsigned_leb(len(code))+code)
            body=unsigned_leb(count)+b''.join(bodies)
        parts.append((sid,body))
    data=encode_sections(parts);path=tmp_path/'independent.wasm';path.write_bytes(data)
    assert parse_binary(path)[1].code[-1][0]=='call_ref'
    assert execute_binary(data,'run',['i32'],[(100,)])==[{'values':['107']}]
    assert load_binary(path).invoke('run',[100])==[107]
    compile_source(path,path.with_suffix('.ttf'))
    with NativeFont(path.with_suffix('.ttf')) as font:assert font.invoke(100)==107


@pytest.mark.parametrize('body',[
    'i32.const 1 ref.null func call_ref $word',
    'i32.const 1 ref.func $wrong call_ref $word',
    'i32.const 1 i32.const 0 call_ref $word',
    'i32.const 1 ref.null $word call_ref 999',
    'i32.const 1 ref.null $word call_ref',
])
def test_invalid_reference_calls_fail_before_font_output(tmp_path,body):
    path=tmp_path/'bad.wat';path.write_text(f'''(module
      (type $word (func (param i32) (result i32)))
      (func $wrong (param i64) (result i64) local.get 0) (elem declare func $wrong)
      (func (export "run") (result i32) {body}))''')
    with pytest.raises((ValueError,NotImplementedError)):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


@pytest.mark.parametrize('binary_input',[False,True])
@pytest.mark.parametrize('folded',[False,True])
def test_tail_reference_recursion_replaces_frame_and_discards_locals(tmp_path,binary_input,folded):
    tail='(return_call_ref $walk (i32.sub (local.get 0) (i32.const 1)) (i64.add (local.get 1) (i64.const 3)) (ref.func $walk))' if folded else 'local.get 0 i32.const 1 i32.sub local.get 1 i64.const 3 i64.add ref.func $walk return_call_ref $walk'
    wat=f'''(module (type $walk (func (param i32 i64) (result i64 i32)))
      (elem declare func $walk)
      (func $walk (export "run") (type $walk) (local $fresh i32)
        local.get 0 if (result i64 i32)
          i32.const 99 local.set $fresh i32.const 100 {tail}
        else local.get 1 local.get $fresh end))'''
    compare(tmp_path,wat,[(n,a) for n in [0,1,3,8] for a in [0,-1,1<<63]],binary_input=binary_input,limits=Limits(call_depth=1))
    with NativeFont(tmp_path/'program.ttf') as font:
        with pytest.raises(ExecutionBoundExceeded,match='tail_call'):font.invoke(9,100)


def test_null_reference_traps_before_exhausted_tail_budget(tmp_path):
    path=tmp_path/'null-tail.wat';path.write_text('''(module (type $word (func (result i32)))
      (elem declare func $f) (func $f (type $word) i32.const 42)
      (func (export "run") (param i32) (result i32)
        ref.func $f ref.null $word local.get 0 select (result (ref null $word)) return_call_ref $word))''')
    compile_source(path,path.with_suffix('.ttf'),limits=Limits(call_depth=1,tail_calls=0))
    with NativeFont(path.with_suffix('.ttf')) as font:
        with pytest.raises(WasmTrap,match='null_reference'):font.invoke(0)
        with pytest.raises(ExecutionBoundExceeded,match='tail_call'):font.invoke(1)


def test_tail_reference_calls_preserve_references_and_shared_mutable_state(tmp_path):
    wat='''(module (type $word (func (param i64) (result i64)))
      (type $step (func (param (ref $word) i64) (result i64)))
      (memory 1) (global $count (mut i32) (i32.const 0))
      (elem declare func $leaf $step)
      (func $leaf (type $word) i32.const 0 local.get 0 i64.store
        global.get $count i32.const 1 i32.add global.set $count local.get 0 i64.const 7 i64.add)
      (func $step (type $step)
        global.get $count i32.const 1 i32.add global.set $count
        local.get 1 local.get 0 return_call_ref $word)
      (func (export "run") (param i64) (result i64 i64 i32)
        ref.func $leaf local.get 0 ref.func $step call_ref $step
        i32.const 0 i64.load global.get $count))'''
    compare(tmp_path,wat,[(0,),(100,),(-1,)],limits=Limits(call_depth=2,tail_calls=1))


@pytest.mark.parametrize('call',['call_ref','return_call_ref'])
def test_reference_returns_keep_declared_result_types(tmp_path,call):
    wat=f'''(module (type $word (func))
      (type $factory (func (result (ref $word))))
      (func $f) (elem declare func $f $factory)
      (func $factory (type $factory) ref.func $f)
      (func $helper (result (ref $word)) ref.func $factory {call} $factory)
      (func (export "run") (result i32) call $helper ref.is_null))'''
    compare(tmp_path,wat,[()],limits=Limits(call_depth=3))
