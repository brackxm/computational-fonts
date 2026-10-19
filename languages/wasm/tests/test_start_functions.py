"""Start initialization precedes exports without host execution during compilation."""
import pytest

from wasmfont.compiler import compile_source, Limits
from wasmfont.frontend import load, parse_text, binary, unsigned_leb
from wasmfont.module import load_binary
from wasmfont.oracle import execute_binary
from wasmfont.reference import interpreter
from wasmfont.reference.interpreter import WasmTrap as ReferenceTrap
from wasmfont.reference.lowering import compile_module
from wasmfont.runtime import NativeFont, WasmTrap, ExecutionBoundExceeded
from wasmfont.state import MemoryTrap
from .test_data_segments import encode_sections, sections
from .test_indirect_calls import compare
from .test_review_regressions import LEGACY_ADD


@pytest.mark.parametrize('binary_input',[False,True])
@pytest.mark.parametrize('target',['$init','0'])
def test_start_observes_active_data_and_table_then_initializes_export_state(tmp_path,binary_input,target):
    wat=f'''(module (start {target}) (memory 1 2)
      (global $g (mut i32) (i32.const 0))
      (data (i32.const 0) "\\01\\00\\00\\00") (data $p "ABCDEFGH")
      (table 1 funcref) (elem (i32.const 0) $step)
      (func $init
        i32.const 0 i32.load global.set $g
        i32.const 8 i32.const 0 i32.const 8 memory.init $p data.drop $p
        i32.const 1 memory.grow drop
        i32.const 0 call_indirect)
      (func $step global.get $g i32.const 7 i32.add global.set $g)
      (func (export "run") (param i32 i32) (result i32 i32 i64)
        local.get 1 if i32.const 0 i32.const 0 i32.const 1 memory.init $p end
        global.get $g local.get 0 i32.add memory.size i32.const 8 i64.load))'''
    _,module,data=compare(tmp_path,wat,[(0,0),(10,0),(-1,0),(0,1)],binary_input=binary_input)
    assert module.start==0 and binary(module)==data
    with NativeFont(tmp_path/'program.ttf') as native:
        assert native.invoke(10,0)==(18,2,0x4847464544434241)


TRAPS=[
    ('unreachable','unreachable'),
    ('i32.const 1 i32.const 0 i32.div_u drop','integer_divide_by_zero'),
    ('i32.const 65536 i32.load8_u drop','memory_out_of_bounds'),
    ('data.drop 0 i32.const 0 i32.const 0 i32.const 1 memory.init 0','memory_out_of_bounds'),
    ('i32.const 0 call_indirect','indirect_call_type_mismatch'),
    ('i32.const 1 call_indirect','uninitialized_element'),
    ('i32.const 2 call_indirect','table_out_of_bounds'),
]


@pytest.mark.parametrize('body,reason',TRAPS)
@pytest.mark.parametrize('binary_input',[False,True])
def test_start_traps_before_export_even_when_loading_and_compilation_succeed(tmp_path,body,reason,binary_input):
    wat=f'''(module (memory 1) (data "A") (table 2 funcref)
      (elem (i32.const 0) $wrong)
      (func $wrong (result i64) i64.const 0)
      (func $init {body}) (start $init)
      (func (export "run") (param i32) (result i32) i32.const 1 local.get 0 i32.div_u))'''
    _,module,_=compare(tmp_path,wat,[(0,),(1,)],binary_input=binary_input)
    with pytest.raises((ReferenceTrap,MemoryTrap)):
        module.instantiate()
    with NativeFont(tmp_path/'program.ttf') as native:
        for value in [0,1]:
            with pytest.raises(WasmTrap,match=f'^{reason}$'):native.invoke(value)


@pytest.mark.parametrize('body,kind',[
    ('loop br 0 end','loop'),('call $init','call'),
])
def test_start_loops_and_recursion_report_bounds_without_host_initialization(tmp_path,monkeypatch,body,kind):
    path=tmp_path/'bounded.wat'
    path.write_text(f'''(module (func $init {body}) (start $init)
      (func (export "run") (result i32) i32.const 1 i32.const 0 i32.div_u))''')
    module,_=load(path)
    with pytest.raises(ReferenceTrap,match='fuel'):module.instantiate(fuel=10)
    with pytest.raises(ReferenceTrap,match='fuel'):module.invoke('run',[],fuel=10)
    def forbidden(*args,**kwargs):raise AssertionError('compiler executed the reference VM')
    with monkeypatch.context() as patch:
        patch.setattr(interpreter,'run',forbidden)
        load(path)
        compile_source(path,path.with_suffix('.ttf'),export='run',limits=Limits(loop_iterations=2,call_depth=2))
    with NativeFont(path.with_suffix('.ttf')) as native:
        with pytest.raises(ExecutionBoundExceeded,match=f'^{kind}$'):native.invoke()


def test_start_and_export_have_separate_call_stacks(tmp_path):
    wat='''(module (global $g (mut i32) (i32.const 0))
      (func $step global.get $g i32.const 1 i32.add global.set $g)
      (func $init call $step) (start $init)
      (func (export "run") (result i32) call $step global.get $g))'''
    compare(tmp_path,wat,[()],limits=Limits(call_depth=2))
    assert load(tmp_path/'program.wat')[0].invoke('run',[])==[2]
    compile_source(tmp_path/'program.wat',tmp_path/'shallow.ttf',export='run',limits=Limits(call_depth=1))
    with NativeFont(tmp_path/'shallow.ttf') as native:
        with pytest.raises(ExecutionBoundExceeded,match='call'):native.invoke()


def test_start_and_export_share_reference_fuel(tmp_path):
    path=tmp_path/'fuel.wat'
    path.write_text('''(module (func $init nop nop) (start $init)
      (func (export "run") (result i32) nop nop nop i32.const 42))''')
    module,_=load(path)
    with pytest.raises(ReferenceTrap,match='fuel'):module.invoke('run',[],fuel=5)
    assert module.invoke('run',[],fuel=6)==[42]
    state=module.instantiate(fuel=2)
    assert module.invoke('run',[],state=state,fuel=4)==[42]


def test_initialization_occurs_once_per_instance_and_fresh_for_each_shaping(tmp_path):
    wat='''(module (memory 1 3) (global $g (mut i32) (i32.const 0))
      (func $init i32.const 1 memory.grow drop
        global.get $g i32.const 1 i32.add global.set $g) (start $init)
      (func (export "run") (param i32) (result i32 i32)
        global.get $g local.get 0 i32.add global.set $g global.get $g memory.size))'''
    _,module,_=compare(tmp_path,wat,[(4,),(4,),(0,)])
    state=module.instantiate()
    assert state.globals==[1] and state.pages==2
    assert module.invoke('run',[4],state=state)==[5,2]
    assert module.invoke('run',[4],state=state)==[9,2]
    assert module.invoke('run',[4])==[5,2]


def test_exporting_the_start_function_does_not_suppress_explicit_calls(tmp_path):
    wat='''(module (global $g (mut i32) (i32.const 0))
      (func $init (export "init") global.get $g i32.const 1 i32.add global.set $g)
      (start $init)
      (func (export "run") (result i32) call $init global.get $g))'''
    _,module,_=compare(tmp_path,wat,[()])
    state=module.instantiate()
    assert state.globals==[1]
    assert module.invoke('init',[],state=state)==[] and state.globals==[2]
    compile_source(tmp_path/'program.wat',tmp_path/'init.ttf',export='init')
    with NativeFont(tmp_path/'init.ttf') as native:assert native.invoke()==()


@pytest.mark.parametrize('base',[0,65536])
def test_start_writes_backed_memory_before_runtime_arguments(tmp_path,base):
    wat=f'''(module (memory 2)
      (func $init i32.const {base} i64.const 0x807f060504030201 i64.store) (start $init)
      (func (export "run") (param i64) (result i64) i32.const {base} i64.load local.get 0 i64.xor))'''
    compare(tmp_path,wat,[(0,),(-1,),(0x807f060504030201,)],limits=Limits(memory_base=base))


def test_start_outside_backed_memory_reports_resource_bound(tmp_path):
    path=tmp_path/'outside.wat'
    path.write_text('''(module (memory 1) (func $init i32.const 16 i32.const 7 i32.store8)
      (start $init) (func (export "run") (result i32) i32.const 42))''')
    module,data=load(path)
    assert execute_binary(data,'run',[],[()])==[{'values':['42']}]
    assert module.invoke('run',[])==[42]
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as native:
        with pytest.raises(ExecutionBoundExceeded,match='memory'):native.invoke()


@pytest.mark.parametrize('index',[0,1,127,128])
@pytest.mark.parametrize('padded',[False,True])
def test_independent_binary_start_indices_and_unsigned_leb(tmp_path,index,padded):
    u=unsigned_leb;start=u(index)
    if padded:start=start[:-1]+bytes([start[-1]|128,0])
    bodies=[b'\x00\x0b']*index+[b'\x00\x41\x2a\x24\x00\x0b',b'\x00\x23\x00\x0b']
    data=encode_sections([
        (1,b'\x02\x60\x00\x00\x60\x00\x01\x7f'),
        (3,u(index+2)+b'\x00'*(index+1)+b'\x01'),
        (6,b'\x01\x7f\x01\x41\x00\x0b'),(7,b'\x01\x03run\x00'+u(index+1)),
        (8,start),(10,u(len(bodies))+b''.join(u(len(body))+body for body in bodies))])
    path=tmp_path/'independent.wasm';path.write_bytes(data)
    module=load_binary(path)
    assert module.start==index and module.globals==[0]
    assert module.invoke('run',[])==[42]
    assert execute_binary(data,'run',[],[()])==[{'values':['42']}]
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as native:assert native.invoke()==42


@pytest.mark.parametrize('field',[
    '(start)','(start 0 1)','(start "0")','(start -1)','(start 4294967296)',
    '(start $missing)','(start 99)','(start 0) (start 0)',
])
def test_invalid_wat_start_fields_fail_before_output(tmp_path,field):
    path=tmp_path/'bad.wat';path.write_text(f'(module (func $init) {field})')
    with pytest.raises(ValueError):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


@pytest.mark.parametrize('function',['(func (param i32))','(func (result i32) i32.const 0)'])
def test_start_requires_a_void_signature(tmp_path,function):
    path=tmp_path/'bad.wat';path.write_text(f'(module {function} (start 0))')
    with pytest.raises(ValueError,match='no parameters or results'):compile_source(path,path.with_suffix('.ttf'))


@pytest.mark.parametrize('function',['(func (param i32))','(func (result i32) i32.const 0)'])
def test_invalid_binary_start_signatures_are_rejected_by_v8(tmp_path,function):
    module=parse_text(f'(module {function})');module.start=0
    path=tmp_path/'bad-signature.wasm';path.write_bytes(binary(module))
    with pytest.raises(ValueError,match='V8 rejected'):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


def test_start_growth_cannot_repair_an_invalid_active_data_segment(tmp_path):
    path=tmp_path/'invalid-data.wat'
    path.write_text('''(module (memory 0 1) (data (i32.const 0) "A")
      (func $init i32.const 1 memory.grow drop) (start $init)
      (func (export "run") (result i32) i32.const 42))''')
    data=binary(parse_text(path.read_text()))
    assert 'trap' in execute_binary(data,'run',[],[()])[0]
    for compiler in [compile_source,compile_module]:
        with pytest.raises(MemoryTrap):compiler(path,path.with_suffix('.ttf'))
        assert not path.with_suffix('.ttf').exists()


@pytest.mark.parametrize('payload',[b'',b'\x02',b'\x00\x00',b'\x80',b'\x80\x80\x80\x80\x10'])
def test_invalid_binary_start_sections_are_validated_before_output(tmp_path,payload):
    valid=binary(parse_text('(module (func) (start 0))'))
    path=tmp_path/'bad.wasm'
    path.write_bytes(encode_sections([(sid,payload if sid==8 else p) for sid,p in sections(valid)]))
    for compiler in [compile_source,compile_module]:
        with pytest.raises(ValueError,match='V8 rejected'):compiler(path,path.with_suffix('.ttf'))
        assert not path.with_suffix('.ttf').exists()


@pytest.mark.parametrize('body',['nop','unreachable'])
@pytest.mark.parametrize('binary_input',[False,True])
def test_legacy_lowerer_never_ignores_start(tmp_path,body,binary_input):
    wat=LEGACY_ADD.replace('(func unreachable)',f'(func {body})')[:-1]+'(start 1))'
    path=tmp_path/'legacy.wat';path.write_text(wat)
    if binary_input:path=path.with_suffix('.wasm');path.write_bytes(binary(parse_text(wat)))
    with pytest.raises(NotImplementedError,match='start section'):compile_module(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()
