"""Independent function tables share references, not storage or growth limits."""
import pytest

from wasmfont.compiler import compile_source
from wasmfont.frontend import binary
from wasmfont.ir import parse_binary
from wasmfont.module import load_binary
from wasmfont.oracle import execute_binary
from wasmfont.runtime import NativeFont,WasmTrap,ExecutionBoundExceeded
from .test_indirect_calls import compare,independent_binary
from .test_data_segments import sections,encode_sections


FUNCTIONS='''(func $a (param i32) (result i32) local.get 0 i32.const 7 i32.add)
 (func $b (param i32) (result i32) local.get 0 i32.const 3 i32.sub)
 (func $wrong (result i64) i64.const 9)'''


@pytest.mark.parametrize('folded',[False,True])
@pytest.mark.parametrize('numeric',[False,True])
def test_nonzero_table_elements_exports_dispatch_and_roundtrip(tmp_path,folded,numeric):
    table='1' if numeric else '$second'
    call=f'(call_indirect {table} (param i32) (result i32) (local.get 1) (local.get 0))' if folded else f'local.get 1 local.get 0 call_indirect {table} (param i32) (result i32)'
    wat=f'''(module (table $first (export "first") 2 funcref)
      (table $second (export "second") 4 6 funcref) (export "alias" (table $second))
      (elem (i32.const 0) $b $a)
      (elem (table {table}) (i32.const 0) funcref (ref.func $a) (ref.null func) (ref.func $b) (ref.func $wrong))
      {FUNCTIONS} (func (export "run") (param i32 i32) (result i32) {call}))'''
    _,module,data=compare(tmp_path,wat,[(s,v) for s in [0,1,2,3,4,-1] for v in [0,10,-1]],binary_input=True)
    assert [t.entries for t in module.tables]==[[1,0],[0,None,1,2]]
    assert module.exports['second']==module.exports['alias']==(1,1)
    assert binary(module)==data


@pytest.mark.parametrize('destination,source',[(0,1),(1,0),(1,1)])
@pytest.mark.parametrize('lengths',[(3,5),(5,3)])
def test_cross_table_copy_checks_both_ranges_and_preserves_source_snapshot(tmp_path,destination,source,lengths):
    left,right=lengths
    refs=['$a','$b','$wrong','$b','$a']
    wat=f'''(module (table $left {left} funcref) (table $right {right} funcref)
      (elem (i32.const 0) {' '.join(refs[:left])})
      (elem (table $right) (i32.const 0) {' '.join(reversed(refs[:right]))}) {FUNCTIONS}
      (func (export "run") (param i32 i32 i32 i32) (result i32 i32)
        local.get 0 local.get 1 local.get 2 table.copy {destination} {source}
        i32.const 100 local.get 3 call_indirect $left (param i32) (result i32)
        i32.const 100 local.get 3 call_indirect $right (param i32) (result i32)))'''
    cases=[(d,s,n,slot) for d,s,n in [(0,0,0),(0,0,3),(1,0,2),(0,1,2),(2,0,2),
        (0,2,2),(3,3,0),(5,5,0),(6,0,0),(0,6,0),(-1,0,0),(0,-1,1),(0,0,-1)] for slot in range(6)]
    compare(tmp_path,wat,cases)


@pytest.mark.parametrize('drop',[False,True])
def test_passive_segment_is_shared_by_tables_and_dropped_once(tmp_path,drop):
    wat=f'''(module (table $left 3 funcref) (table $right 5 funcref)
      (elem (table $right) (i32.const 0) $b $a $b)
      (elem $p funcref (ref.func $a) (ref.null func) (ref.func $b)) {FUNCTIONS}
      (func $init i32.const 0 i32.const 0 i32.const 3 table.init $left $p)
      (start $init)
      (func (export "run") (param i32 i32 i32 i32) (result i32 i32)
        {'elem.drop $p' if drop else ''}
        local.get 0 local.get 1 local.get 2 table.init $right $p
        i32.const 100 i32.const 0 call_indirect $left (param i32) (result i32)
        i32.const 100 local.get 3 call_indirect $right (param i32) (result i32)))'''
    cases=[(d,s,n,slot) for d,s,n in [(0,0,3),(2,0,3),(3,0,3),(5,0,0),(6,0,0),(0,3,0),
             (0,4,0),(0,0,0),(-1,0,1),(0,0,-1)] for slot in range(6)]
    compare(tmp_path,wat,cases)


@pytest.mark.parametrize('expressions',[False,True])
def test_nonzero_active_segments_are_unavailable_to_init_before_start(tmp_path,expressions):
    entries='funcref (ref.func $a)' if expressions else 'func $a'
    wat=f'''(module (table 1 funcref) (table $right 1 funcref)
      (elem $p (table $right) (i32.const 0) {entries}) {FUNCTIONS}
      (func $init i32.const 0 i32.const 0 i32.const 0 table.init $right $p) (start $init)
      (func (export "run") (param i32) (result i32)
        i32.const 0 i32.const 0 local.get 0 table.init $right $p
        i32.const 100 i32.const 0 call_indirect $right (param i32) (result i32)))'''
    compare(tmp_path,wat,[(0,),(1,),(-1,)],binary_input=True)


def test_growth_mutation_and_sizes_survive_calls_branches_and_loop_merges(tmp_path):
    wat=f'''(module (table $left 1 2 funcref) (table $right 1 4 funcref)
      (elem (i32.const 0) $a) (elem (table $right) (i32.const 0) $b) {FUNCTIONS}
      (func $grow (param i32 i32)
        local.get 1 if ref.func $a local.get 0 table.grow $left drop
        else ref.func $b local.get 0 table.grow $right drop end)
      (func (export "run") (param i32 i32 i32) (result i32 i32 i32 i32) (local $n i32)
        local.get 2 local.set $n
        block $done loop $again local.get $n i32.eqz br_if $done
          local.get 0 local.get 1 call $grow
          local.get $n i32.const 1 i32.sub local.set $n br $again end end
        table.size $left table.size $right
        i32.const 100 i32.const 0 call_indirect $left (param i32) (result i32)
        i32.const 100 i32.const 0 call_indirect $right (param i32) (result i32)))'''
    _,module,_=compare(tmp_path,wat,[(delta,branch,n) for delta in [0,1,2,4,-1] for branch in [0,1] for n in [0,1,3,7]])
    with NativeFont(tmp_path/'program.ttf') as font:
        with pytest.raises(ExecutionBoundExceeded,match='loop'):font.invoke(1,0,8)
        assert font.invoke(1,0,3)==(1,4,107,97)
        assert font.invoke(1,0,1)==(1,2,107,97)
        assert font.invoke(1,1,3)==(2,1,107,97)
    state=module.instantiate()
    assert module.invoke('run',[1,0,1],state=state)==[1,2,107,97]
    assert module.invoke('run',[1,0,1],state=state)==[1,3,107,97]
    assert state.table==[0] and state.extra_tables==[[1,1,1]]


@pytest.mark.parametrize('initial',[0,1,3])
def test_get_set_fill_and_grow_target_only_the_selected_table(tmp_path,initial):
    wat=f'''(module (table $left 2 funcref) (table $right {initial} 5 funcref)
      (elem (i32.const 0) $a $b) {FUNCTIONS}
      (func $get (param i32) (result funcref) local.get 0 table.get $left)
      (func (export "run") (param i32 i32 i32 i32) (result i32 i32 i32 i32 i32)
        local.get 0 call $get local.get 1 table.grow $right
        i32.const 0 ref.null func local.get 2 table.fill $right
        local.get 3 local.get 0 table.get $left table.set $right
        table.size $left table.size $right
        i32.const 100 local.get 0 call_indirect $left (param i32) (result i32)
        i32.const 100 local.get 3 call_indirect $right (param i32) (result i32)))'''
    compare(tmp_path,wat,[(ref,grow,fill,slot) for ref in [0,1,2] for grow in [0,1,3,5,-1]
                         for fill,slot in [(0,0),(1,0),(0,4),(5,1),(0,-1)]])


@pytest.mark.parametrize('flag',[2,6])
def test_independent_binary_nonzero_table_elements_and_padded_indices(tmp_path,flag):
    data=independent_binary(table_count=2)
    element=b'\x01'+bytes([flag])+b'\x81\x00\x41\x00\x0b'+(b'\x70' if flag==6 else b'\x00')
    element+=b'\x01'+(b'\xd2\x00\x0b' if flag==6 else b'\x00')
    body=(b'\x00\x41\x01\x41\x00\x25\x81\x00\x26\x81\x00'
          b'\x20\x00\x20\x01\x11\x00\x81\x00\x0b')
    target=b'\x00\x20\x00\x41\x01\x6a\x0b'
    code=b'\x02'+bytes([len(target)])+target+bytes([len(body)])+body
    data=encode_sections([(tag,element if tag==9 else code if tag==10 else payload) for tag,payload in sections(data)])
    path=tmp_path/'independent.wasm';path.write_bytes(data);module=load_binary(path)
    assert module.table==[None,None] and module.extra_tables[0].entries==[0,None]
    assert module.elements[0].table==1 and parse_binary(path)[1].code[-1][1].table==1
    assert execute_binary(data,'run',['i32','i32'],[(7,0),(9,1),(1,2)])[:2]==[{'values':['8']},{'values':['10']}]
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as font:
        assert font.invoke(7,0)==8 and font.invoke(9,1)==10
        with pytest.raises(WasmTrap,match='table_out_of_bounds'):font.invoke(1,2)


def test_independent_binary_bulk_operations_use_both_table_indices(tmp_path):
    data=independent_binary(table_count=2)
    target=b'\x00\x20\x00\x41\x01\x6a\x0b'
    body=(b'\x00'
          # Initialize table 1 from passive element 0, then drop the segment.
          b'\x41\x00\x41\x00\x41\x01\xfc\x8c\x00\x80\x00\x81\x00'
          b'\xfc\x8d\x00\x80\x00'
          # Copy slot 0 in table 1 to slot 1 in table 0.
          b'\x41\x01\x41\x00\x41\x01\xfc\x8e\x00\x80\x00\x81\x00'
          # Fill slot 0 in table 1 with null and set its slot 1 to target 0.
          b'\x41\x00\xd0\x70\x41\x01\xfc\x91\x00\x81\x00'
          b'\x41\x01\xd2\x00\x26\x81\x00'
          # Assert table 1 has null then non-null; a zero grow keeps size 2.
          b'\x41\x00\x25\x81\x00\xd1\x45\x04\x40\x00\x0b'
          b'\x41\x01\x25\x81\x00\xd1\x04\x40\x00\x0b'
          b'\xd0\x70\x41\x00\xfc\x8f\x00\x81\x00\x1a'
          b'\xfc\x90\x00\x81\x00\x41\x02\x47\x04\x40\x00\x0b'
          b'\x20\x00\x20\x01\x11\x00\x80\x00\x0b')
    code=b'\x02'+bytes([len(target)])+target+bytes([len(body)])+body
    data=encode_sections([(tag,b'\x01\x01\x00\x01\x00' if tag==9 else code if tag==10 else payload)
                          for tag,payload in sections(data)])
    path=tmp_path/'bulk.wasm';path.write_bytes(data);module=load_binary(path)
    assert execute_binary(data,'run',['i32','i32'],[(7,1),(7,0)])[0]=={'values':['8']}
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as font:
        assert font.invoke(7,1)==8 and module.invoke('run',[7,1])==[8]
        with pytest.raises(WasmTrap,match='uninitialized_element'):font.invoke(7,0)


def test_nonzero_indirect_table_can_accept_and_return_function_references(tmp_path):
    wat=f'''(module (table $ops 1 funcref) (table $helpers 1 funcref)
      (elem (table $helpers) (i32.const 0) $choose) (elem declare func $a $b) {FUNCTIONS}
      (func $choose (param funcref funcref i32) (result funcref)
        local.get 0 local.get 1 local.get 2 select (result funcref))
      (func (export "run") (param i32 i32) (result i32)
        i32.const 0 ref.func $a ref.func $b local.get 0
        i32.const 0 call_indirect $helpers (param funcref funcref i32) (result funcref) table.set $ops
        local.get 1 i32.const 0 call_indirect $ops (param i32) (result i32)))'''
    compare(tmp_path,wat,[(enabled,value) for enabled in [0,1,-1] for value in [0,10,-1]])


def test_sixteen_tables_and_the_last_table_grows_independently(tmp_path):
    declarations=' '.join(f'(table $t{i} 0 1 funcref)' for i in range(16))
    wat=f'''(module {declarations} (elem declare func $a) {FUNCTIONS}
      (func (export "run") (result i32 i32)
        ref.func $a i32.const 1 table.grow $t15 drop
        table.size $t0 i32.const 100 i32.const 0 call_indirect $t15 (param i32) (result i32)))'''
    compare(tmp_path,wat,[()])
    path=tmp_path/'excess.wat';path.write_text(wat.replace('(module','(module (table 0 funcref)',1))
    with pytest.raises(ValueError,match='at most 16'):compile_source(path,path.with_suffix('.ttf'),export='run')
    assert not path.with_suffix('.ttf').exists()


def test_unspecified_maximum_applies_to_each_table_independently(tmp_path):
    wat=f'''(module (table $left 1 funcref) (table $right 1 funcref)
      (elem declare func $a $b) {FUNCTIONS}
      (func (export "run") (param i32 i32) (result i32 i32 i32 i32)
        ref.func $a local.get 0 table.grow $left
        ref.func $b local.get 1 table.grow $right
        table.size $left table.size $right))'''
    compare(tmp_path,wat,[(a,b) for a in [0,1,254,255,-1] for b in [0,1,254,255,-1]])
    # Allocation beyond the implementation's cap may fail even without a
    # declared maximum; such failures are allowed by Wasm.
    with NativeFont(tmp_path/'program.ttf') as font:
        assert font.invoke(256,1)==(0xffffffff,1,1,2)
        assert font.invoke(1,256)==(1,0xffffffff,2,1)


@pytest.mark.parametrize('body',[
    'i32.const 0 table.get 2 drop','i32.const 0 ref.null func table.set 2',
    'table.size 2 drop','ref.null func i32.const 1 table.grow 2 drop',
    'i32.const 0 ref.null func i32.const 0 table.fill 2',
    'i32.const 0 i32.const 0 i32.const 0 table.copy 0 2',
    'i32.const 0 i32.const 0 i32.const 0 table.copy 2 0',
    'i32.const 0 i32.const 0 i32.const 0 table.init 2 $p',
    'i32.const 0 call_indirect 2',
])
def test_invalid_table_indices_fail_before_font_output(tmp_path,body):
    path=tmp_path/'bad.wat';path.write_text(f'''(module (table 1 funcref) (table 1 funcref)
        (elem $p func $f) (func $f) (func (export "run") {body}))''')
    with pytest.raises(ValueError):compile_source(path,path.with_suffix('.ttf'),export='run')
    assert not path.with_suffix('.ttf').exists()
