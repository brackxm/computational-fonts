"""Mutable references and element lifetimes match V8 and native HarfBuzz."""
import random
import pytest

from wasmfont.compiler import compile_source,Limits
from wasmfont.frontend import load
from wasmfont.module import load_binary
from wasmfont.oracle import execute_binary
from wasmfont.runtime import NativeFont,WasmTrap,ExecutionBoundExceeded
from .test_indirect_calls import compare,independent_binary
from .test_data_segments import sections,encode_sections

FUNCTIONS='''(func $a (param i32) (result i32) local.get 0 i32.const 7 i32.add)
 (func $b (param i32) (result i32) local.get 0 i32.const 3 i32.sub)
 (func $wrong (result i64) i64.const 9)'''


@pytest.mark.parametrize('binary_input',[False,True])
def test_dynamic_references_locals_nulls_and_type_checks(tmp_path,binary_input):
    wat=f'''(module (table $t 4 funcref) (elem (i32.const 0) $a $b $wrong)
      {FUNCTIONS}
      (func (export "run") (param i32 i32 i32) (result i32 i32) (local $r funcref)
        local.get 0 table.get $t local.tee $r ref.is_null
        local.get 1 local.get $r table.set $t
        local.get 2 local.get 1 call_indirect (param i32) (result i32)))'''
    cases=[(s,d,v) for s in [0,1,2,3,4,0xffffffff] for d in [0,3,4] for v in [0,10,-1]]
    compare(tmp_path,wat,cases,binary_input=binary_input)


def test_reference_locals_merge_across_branches_and_default_to_null(tmp_path):
    wat=f'''(module (table 1 funcref) (elem declare func $a $b) {FUNCTIONS}
      (func (export "run") (param i32 i32) (result i32 i32) (local $r funcref)
        local.get $r ref.is_null
        local.get 0 if ref.func $a local.set $r else ref.func $b local.set $r end
        i32.const 0 local.get $r table.set
        local.get 1 i32.const 0 call_indirect (param i32) (result i32)))'''
    compare(tmp_path,wat,[(b,v) for b in [0,1,0xffffffff] for v in [0,9,-1]])


@pytest.mark.parametrize('operation',['table.copy','table.init $p','table.fill'])
@pytest.mark.parametrize('length',[3,4,5])
def test_bulk_table_ranges_overlap_and_snapshot_alignment(tmp_path,operation,length):
    references=' '.join(['$a','$b','$wrong','$a','$b'][:length])
    source='ref.func $b' if operation=='table.fill' else 'local.get 1'
    wat=f'''(module (table {length} funcref) (elem (i32.const 0) {references})
      (elem $p func {references}) {FUNCTIONS}
      (func (export "run") (param i32 i32 i32 i32) (result i32)
        local.get 0 {source} local.get 2 {operation}
        i32.const 100 local.get 3 call_indirect (param i32) (result i32)))'''
    rng=random.Random(length)
    cases=[(d,s,n,slot) for d,s,n in [(0,1,length-1),(1,0,length-1),(0,0,length),
      (length,length,0),(length+1,0,0),(0,length+1,0),(0,0,length+1),(0xffffffff,0,1),
      (0,0xffffffff,1),(0,0,0xffffffff)] for slot in range(length+1)]
    cases += [(rng.randrange(length+2),rng.randrange(length+2),rng.randrange(length+2),rng.randrange(length+1)) for _ in range(30)]
    compare(tmp_path,wat,cases)


@pytest.mark.parametrize('mode',['passive','active','declarative'])
@pytest.mark.parametrize('drop',[False,True])
def test_element_modes_drop_lifetime_and_zero_length_endpoints(tmp_path,mode,drop):
    segment={'passive':'func','active':'(i32.const 0)','declarative':'declare func'}[mode]
    wat=f'''(module (table 3 funcref) (elem $p {segment} $a $b) {FUNCTIONS}
      (func (export "run") (param i32 i32 i32) (result i32)
        {'elem.drop $p elem.drop $p' if drop else ''}
        local.get 0 local.get 1 local.get 2 table.init $p
        i32.const 0 table.get ref.is_null))'''
    compare(tmp_path,wat,[(d,s,n) for d in [0,2,3,4,0xffffffff] for s,n in [(0,0),(0,1),(1,0),(1,1),(2,0),(2,1),(0xffffffff,1)]])


@pytest.mark.parametrize('maximum',[None,0,1,4,256])
def test_grow_success_failure_null_initialization_and_current_size(tmp_path,maximum):
    initial=0 if maximum==0 else 1
    wat=f'''(module (table {initial} {'' if maximum is None else maximum} funcref)
      (elem declare func $a) {FUNCTIONS}
      (func (export "run") (param i32 i32 i32) (result i32 i32 i32) (local $r funcref)
        local.get 1 if ref.null func local.set $r else ref.func $a local.set $r end
        local.get $r local.get 0 table.grow table.size
        local.get 2 table.get ref.is_null))'''
    cases=[(delta,null,slot) for delta in [0,1,3,4,255,0xffffffff] for null in [0,1] for slot in [0,1,3,255,256]]
    compare(tmp_path,wat,cases)


def test_mutations_and_drops_survive_start_calls_loops_and_branches(tmp_path):
    wat=f'''(module (table 2 4 funcref) (elem $p func $a $b) {FUNCTIONS}
      (func $init i32.const 0 i32.const 0 i32.const 2 table.init $p elem.drop $p)
      (start $init)
      (func $step (param i32)
        i32.const 0 local.get 0 table.get table.set
        ref.func $b i32.const 1 table.grow drop)
      (func (export "run") (param i32 i32) (result i32 i32) (local $n i32)
        local.get 0 local.set $n
        block $done loop $again
          local.get $n i32.eqz br_if $done
          i32.const 1 call $step
          local.get $n i32.const 1 i32.sub local.set $n br $again
        end end
        local.get 1 if i32.const 0 i32.const 0 i32.const 1 table.init $p end
        i32.const 100 i32.const 0 call_indirect (param i32) (result i32) table.size))'''
    compare(tmp_path,wat,[(n,drop) for n in [0,1,3,7] for drop in [0,1]])
    with NativeFont(tmp_path/'program.ttf') as font:
        with pytest.raises(ExecutionBoundExceeded,match='loop'):font.invoke(8,0)
        assert font.invoke(1,0)==(97,3)
        assert font.invoke(0,0)==(107,2)


def test_dynamic_invalid_targets_trap_before_depth_bound(tmp_path):
    wat=f'''(module (table 4 funcref) (elem (i32.const 0) $a $b $wrong) {FUNCTIONS}
      (func (export "run") (param i32) (result i32)
        i32.const 0 local.get 0 table.get table.set
        i32.const 1 i32.const 0 call_indirect (param i32) (result i32)))'''
    source=tmp_path/'depth.wat';source.write_text(wat)
    compile_source(source,source.with_suffix('.ttf'),export='run',limits=Limits(call_depth=1))
    with NativeFont(source.with_suffix('.ttf')) as font:
        with pytest.raises(ExecutionBoundExceeded,match='call'):font.invoke(0)
        for slot,reason in [(2,'indirect_call_type_mismatch'),(3,'uninitialized_element'),(4,'table_out_of_bounds')]:
            with pytest.raises(WasmTrap,match=reason):font.invoke(slot)


@pytest.mark.parametrize('mode',[1,3])
def test_independent_passive_and_declarative_binary_elements(tmp_path,mode):
    data=independent_binary()
    # Declare target 0 using a passive/declarative element; the dispatcher installs ref.func 0.
    bodies=[b'\x00\x20\x00\x41\x01\x6a\x0b',
      b'\x00\x41\x00\xd2\x00\x26\x80\x00\x20\x00\x20\x01\x11\x00\x00\x0b']
    code=b'\x02'+b''.join(bytes([len(b)])+b for b in bodies)
    data=encode_sections([(tag,bytes([1,mode,0,1,0]) if tag==9 else code if tag==10 else payload) for tag,payload in sections(data)])
    path=tmp_path/'independent.wasm';path.write_bytes(data);module=load_binary(path)
    assert module.elements[0].mode==('passive' if mode==1 else 'declarative')
    expected=execute_binary(data,'run',['i32','i32'],[(7,0),(7,1)])
    assert expected[0]=={'values':['8']} and 'trap' in expected[1]
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as font:
        assert font.invoke(7,0)==8
        with pytest.raises(WasmTrap,match='uninitialized_element'):font.invoke(7,1)


@pytest.mark.parametrize('body',[
 'i32.const 0 table.get 1 drop','i32.const 0 ref.null func table.set 1',
 'table.size 1 drop','ref.null func i32.const 0 table.grow 1 drop',
 'i32.const 0 ref.null func i32.const 0 table.fill 1',
 'i32.const 0 i32.const 0 i32.const 0 table.copy 0 1',
 'i32.const 0 i32.const 0 i32.const 0 table.init 1 $p',
 'ref.null extern drop','ref.func 99 drop','elem.drop 99',
 'i32.const 0 table.get i32.eqz drop', 'i32.const 0 i32.const 0 table.set',
])
def test_invalid_reference_and_table_operands_fail_before_output(tmp_path,body):
    path=tmp_path/'bad.wat';path.write_text(f'(module (table 1 funcref) (elem $p func $f) (func $f) (func (export "run") {body}))')
    with pytest.raises((ValueError,NotImplementedError)):compile_source(path,path.with_suffix('.ttf'),export='run')
    assert not path.with_suffix('.ttf').exists()


def test_unspecified_table_maximum_uses_bounded_allocation_policy(tmp_path):
    path=tmp_path/'bounded.wat';path.write_text('''(module (table 1 funcref)
      (func (export "run") (param i32) (result i32 i32)
        ref.null func local.get 0 table.grow table.size))''')
    module,_=load(path);compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as font:
        assert font.invoke(255)==(1,256)
        assert font.invoke(256)==(0xffffffff,1)
        assert module.invoke('run',[256])==[0xffffffff,1]


def test_independent_bulk_table_binary_operands_and_padded_indices(tmp_path):
    data=independent_binary()
    target=b'\x00\x20\x00\x41\x01\x6a\x0b'
    # Initialize table 0 from element 0, grow with a null, and copy target 0 to 1.
    # All FC subopcodes and zero table/element indices use padded unsigned LEB.
    body=(b'\x00\x41\x00\x41\x00\x41\x01\xfc\x8c\x00\x80\x00\x80\x00'
          b'\xfc\x8d\x00\x80\x00\xd0\x70\x41\x00\xfc\x8f\x00\x80\x00\x1a'
          b'\x41\x01\x41\x00\x41\x01\xfc\x8e\x00\x80\x00\x80\x00'
          b'\x20\x00\x20\x01\x11\x00\x00\x0b')
    code=b'\x02'+bytes([len(target)])+target+bytes([len(body)])+body
    data=encode_sections([(tag,b'\x01\x01\x00\x01\x00' if tag==9 else code if tag==10 else payload) for tag,payload in sections(data)])
    path=tmp_path/'bulk.wasm';path.write_bytes(data);module=load_binary(path)
    assert execute_binary(data,'run',['i32','i32'],[(7,0),(9,1)])==[{'values':['8']},{'values':['10']}]
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as font:
        for value,slot in [(7,0),(9,1)]:
            assert module.invoke('run',[value,slot])==[value+1]
            assert font.invoke(value,slot)==value+1


def test_passive_elements_without_table_and_active_segments_dropped_before_start(tmp_path):
    wat='''(module (elem $declared declare func $f) (elem $p func $f)
      (func $f) (func (export "run") (result i32)
        elem.drop $p elem.drop $declared ref.func $f ref.is_null))'''
    compare(tmp_path,wat,[()])
    wat='''(module (table 1 funcref) (elem $active (i32.const 0) $f)
      (func $f) (func $start i32.const 0 i32.const 0 i32.const 1 table.init $active)
      (start $start) (func (export "run") (result i32) i32.const 42))'''
    compare(tmp_path,wat,[()])
