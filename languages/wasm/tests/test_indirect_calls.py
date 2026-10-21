"""Static function tables and native dynamic dispatch agree with independent V8."""
import pytest

from wasmfont.compiler import compile_source, Limits
from wasmfont.frontend import load, parse_text, binary, unsigned_leb
from wasmfont.ir import BlockType, parse_binary
from wasmfont.module import load_binary
from wasmfont.oracle import execute_binary
from wasmfont.reference.interpreter import WasmTrap as ReferenceTrap
from wasmfont.runtime import NativeFont, WasmTrap, ExecutionBoundExceeded, IncompleteShaping
from wasmfont.state import MemoryTrap
from .test_data_segments import sections, encode_sections
from .test_review_regressions import LEGACY_ADD, insert_section


def compare(tmp_path,wat,cases,*,binary_input=False,limits=None):
    source=tmp_path/'program.wat';source.write_text(wat)
    module,data=load(source);fn=module.functions[module.exports['run'][1]]
    expected=execute_binary(data,'run',fn.params,cases)
    if binary_input:source=source.with_suffix('.wasm');source.write_bytes(data)
    font=tmp_path/'program.ttf';manifest=compile_source(source,font,export='run',limits=limits)
    with NativeFont(font) as native:
        for args,reference in zip(cases,expected):
            if 'trap' in reference:
                with pytest.raises((ReferenceTrap,MemoryTrap)):module.invoke('run',args)
                with pytest.raises(WasmTrap):native.invoke(*args)
            else:
                values=tuple(int(v)&((1<<int(t[1:]))-1) for v,t in zip(reference['values'],fn.results))
                assert tuple(module.invoke('run',args))==values
                result=native.invoke(*args)
                assert ((result,) if len(values)==1 else result)==values,args
        with pytest.raises(IncompleteShaping):
            native.decode(native.shaper.shape(native.encode(cases[0]),enabled=False))
    return manifest,module,data


@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('folded',[False,True])
@pytest.mark.parametrize('binary_input',[False,True])
def test_dynamic_dispatch_and_composed_results(tmp_path,width,folded,binary_input):
    typ=f'i{width}'
    call=('(call_indirect $ops (type $binary) (local.get 0) (local.get 1) (local.get 2))' if folded else
          'local.get 0 local.get 1 local.get 2 call_indirect 0 (type $binary)')
    wat=f'''(module (type $binary (func (param {typ} {typ}) (result {typ})))
      (table $ops (export "dispatch") 6 8 funcref)
      (elem $initial (table $ops) (i32.const 0) func $add $subtract $xor)
      (elem (i32.const 4) $wrong)
      (func $add (param {typ} {typ}) (result {typ}) local.get 0 local.get 1 {typ}.add)
      (func $subtract (param {typ} {typ}) (result {typ}) local.get 0 local.get 1 {typ}.sub)
      (func $xor (param {typ} {typ}) (result {typ}) local.get 0 local.get 1 {typ}.xor)
      (func $wrong (param {typ}) (result {typ}) local.get 0)
      (func (export "run") (param {typ} {typ} i32) (result {typ})
        {call} {typ}.const 7 {typ}.add))'''
    cases=[(a,b,slot) for slot in (0,1,2,3,4,5,6,0xffffffff) for a,b in [(100,7),(-1,1),(1<<(width-1),-1)]]
    _,module,data=compare(tmp_path,wat,cases,binary_input=binary_input)
    assert module.table==[0,1,2,None,3,None] and module.table_maximum==8
    assert module.exports['dispatch']==(1,0)
    assert binary(module)==data
    with NativeFont(tmp_path/'program.ttf') as native:
        for slot,reason in [(3,'uninitialized_element'),(4,'indirect_call_type_mismatch'),(6,'table_out_of_bounds')]:
            with pytest.raises(WasmTrap,match=reason):native.invoke(1,1,slot)


def test_same_signature_different_type_indices_are_compatible(tmp_path):
    wat='''(module (type $a (func (param i32) (result i32)))
      (type $b (func (param i32) (result i32))) (table 1 funcref)
      (elem (i32.const 0) $f)
      (func $f (type $a) local.get 0 i32.const 1 i32.add)
      (func (export "run") (param i32) (result i32)
        local.get 0 i32.const 0 call_indirect (type $b)))'''
    compare(tmp_path,wat,[(0,),(7,),(-1,)])


@pytest.mark.parametrize('signature',['(type $pair)','(param i32 i64) (result i64 i32)'])
def test_multi_value_indirect_results_and_argument_order(tmp_path,signature):
    wat=f'''(module (type $pair (func (param i32 i64) (result i64 i32)))
      (table 1 funcref) (elem (i32.const 0) $f)
      (func $f (param i32 i64) (result i64 i32) local.get 1 local.get 0)
      (func (export "run") (param i32 i64) (result i64 i32)
        local.get 0 local.get 1 i32.const 0 call_indirect {signature}))'''
    compare(tmp_path,wat,[(0,0),(7,0x807f060504030201),(-1,-1)])


@pytest.mark.parametrize('minimum',[0,1,3,256])
def test_empty_slots_and_unsigned_indices(tmp_path,minimum):
    wat=f'''(module (table {minimum} funcref)
      (func (export "run") (param i32) (result i32)
        local.get 0 call_indirect (result i32)))'''
    compare(tmp_path,wat,[(slot,) for slot in (0,1,minimum,0x80000000,0xffffffff)])


def test_void_default_type_preserves_the_caller_stack(tmp_path):
    wat='''(module (table 1 funcref) (elem (i32.const 0) $f)
      (global $g (mut i32) (i32.const 0))
      (func $f i32.const 7 global.set $g)
      (func (export "run") (result i32) i32.const 9 i32.const 0 call_indirect global.get $g i32.add))'''
    compare(tmp_path,wat,[()])


def test_element_overlays_and_canonical_binary_roundtrip(tmp_path):
    wat='''(module (table $t 4 funcref) (export "table" (table $t))
      (elem (i32.const 0) $a $a $a) (elem (i32.const 1) func $b)
      (func $a (result i32) i32.const 7) (func $b (result i32) i32.const 9)
      (func (export "run") (param i32) (result i32) local.get 0 call_indirect (result i32)))'''
    _,module,data=compare(tmp_path,wat,[(0,),(1,),(2,),(3,),(4,)])
    assert module.table==[0,1,0,None]
    assert binary(module)==data and module.exports['table']==(1,0)


def test_dispatch_calls_preserve_memory_globals_pages_and_data_lifetime(tmp_path):
    wat='''(module (type $step (func (param i32))) (table 2 funcref) (elem (i32.const 0) $grow $drop)
      (memory 1 3) (data $p "A") (global $g (mut i32) (i32.const 0))
      (func $grow (param i32)
        local.get 0 memory.grow global.set $g
        i32.const 0 i32.const 42 i32.store8)
      (func $drop (param i32) data.drop $p local.get 0 global.set $g)
      (func (export "run") (param i32 i32 i32) (result i32 i32 i32)
        local.get 1 local.get 0 call_indirect (type $step)
        local.get 2 if i32.const 0 i32.const 0 i32.const 1 memory.init $p end
        global.get $g memory.size i32.const 0 i32.load8_u))'''
    compare(tmp_path,wat,[(0,1,0),(0,1,1),(0,2,0),(0,0,0),(0,3,0),(1,9,1),(1,9,0),(0,1,0)])


def test_indirect_recursion_uses_existing_call_depth_bound(tmp_path):
    wat='''(module (type $sum (func (param i32) (result i32)))
      (table 1 funcref) (elem (i32.const 0) $sum)
      (func $sum (export "run") (param i32) (result i32)
        local.get 0 i32.eqz if (result i32) i32.const 0
        else local.get 0 local.get 0 i32.const 1 i32.sub i32.const 0 call_indirect (type $sum) i32.add end))'''
    compare(tmp_path,wat,[(0,),(1,),(3,),(7,)])
    with NativeFont(tmp_path/'program.ttf') as native:
        with pytest.raises(ExecutionBoundExceeded,match='call'):native.invoke(8)
        with pytest.raises(ExecutionBoundExceeded,match='call'):native.invoke(0xffffffff)
        assert native.invoke(3)==6
    source=tmp_path/'program.wat';font=tmp_path/'shallow.ttf'
    compile_source(source,font,export='run',limits=Limits(call_depth=2))
    with NativeFont(font) as native:
        assert native.invoke(1)==1
        with pytest.raises(ExecutionBoundExceeded,match='call'):native.invoke(2)


def test_wrong_targets_trap_before_call_depth_bound(tmp_path):
    wat='''(module (table 3 funcref) (elem (i32.const 0) $valid $wrong)
      (func $valid (result i32) i32.const 42) (func $wrong (result i64) i64.const 0)
      (func (export "run") (param i32) (result i32) local.get 0 call_indirect (result i32)))'''
    source=tmp_path/'depth.wat';source.write_text(wat);font=tmp_path/'depth.ttf'
    compile_source(source,font,export='run',limits=Limits(call_depth=1))
    with NativeFont(font) as native:
        with pytest.raises(ExecutionBoundExceeded,match='call'):native.invoke(0)
        for slot,reason in [(1,'indirect_call_type_mismatch'),(2,'uninitialized_element'),(3,'table_out_of_bounds')]:
            with pytest.raises(WasmTrap,match=reason):native.invoke(slot)


def test_duplicate_table_targets_share_one_expensive_callee(tmp_path):
    wat=f'''(module (type $div (func (param i64 i64) (result i64)))
      (table 256 funcref) (elem (i32.const 0) {' '.join(['$divide']*256)})
      (func $divide (type $div) local.get 0 local.get 1 i64.div_u)
      (func (export "run") (param i64 i64 i32) (result i64)
        local.get 0 local.get 1 local.get 2 call_indirect (type $div)))'''
    cases=[(0xffffffffffffffff,7,slot) for slot in (0,1,127,255,256,0xffffffff)]+[(1,0,0)]
    manifest,_,_=compare(tmp_path,wat,cases,limits=Limits(max_gates=4500))
    assert manifest['lowered_instructions']<=10
    assert manifest['metrics']['gates']<4400
    assert manifest['metrics']['font_bytes']<1_600_000


def independent_binary(*,index=0,padded=False,explicit_element=False,element_offset=0,table_count=1):
    # (i32)->i32 target; (i32,i32)->i32 dispatcher. Encode these without the WAT writer.
    def u(n):return unsigned_leb(n)
    types=[b'\x60\x01\x7f\x01\x7f']*(index+1)+[b'\x60\x02\x7f\x7f\x01\x7f']
    bodies=[b'\x00\x20\x00\x41\x01\x6a\x0b',
            b'\x00\x20\x00\x20\x01\x11'+u(index)+(b'\x80\x00' if padded else b'\x00')+b'\x0b']
    elem=(b'\x02\x00' if explicit_element else b'\x00')+b'\x41'+bytes([element_offset])+b'\x0b'
    if explicit_element:elem+=b'\x00'
    return encode_sections([(1,u(len(types))+b''.join(types)),(3,b'\x02\x00'+u(index+1)),
                            (4,u(table_count)+b'\x70\x00\x02'*table_count),(7,b'\x01\x03run\x00\x01'),
                            (9,b'\x01'+elem+b'\x01\x00'),(10,u(2)+b''.join(u(len(b))+b for b in bodies))])


@pytest.mark.parametrize('index',[0,63,64,127,128])
@pytest.mark.parametrize('explicit_element',[False,True])
def test_independent_binary_type_indices_and_element_encodings(tmp_path,index,explicit_element):
    data=independent_binary(index=index,padded=True,explicit_element=explicit_element)
    path=tmp_path/'independent.wasm';path.write_bytes(data);module=load_binary(path)
    assert module.table==[0,None]
    assert parse_binary(path)[1].code[-1]==('call_indirect',BlockType(('i32',),('i32',)))
    assert execute_binary(data,'run',['i32','i32'],[(7,0)])==[{'values':['8']}]
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as native:
        assert native.invoke(7,0)==8
        with pytest.raises(WasmTrap,match='uninitialized_element'):native.invoke(7,1)


@pytest.mark.parametrize('tag',[4,9])
def test_empty_table_and_element_sections_are_accepted_by_both_compilers(tmp_path,tag):
    from wasmfont.reference.lowering import compile_module
    from wasmfont.harfbuzz import run
    data=insert_section(binary(parse_text(LEGACY_ADD)),tag,b'\x00')
    path=tmp_path/'empty.wasm';path.write_bytes(data)
    assert load_binary(path).invoke('run',[7,9])==[16]
    font=tmp_path/'legacy.ttf';lowered=compile_module(path,font)
    assert lowered.decode(run(font,lowered.encode(7,9)))==16


@pytest.mark.parametrize('offset',[2,3])
def test_out_of_bounds_elements_fail_before_native_or_legacy_output(tmp_path,offset):
    from wasmfont.reference.lowering import compile_module
    data=independent_binary(element_offset=offset)
    assert 'trap' in execute_binary(data,'run',['i32','i32'],[(7,0)])[0]
    path=tmp_path/'invalid.wasm';path.write_bytes(data)
    for name,compiler in [('native',compile_source),('legacy',compile_module)]:
        font=tmp_path/(name+'.ttf')
        with pytest.raises(ValueError,match='element segment out of table bounds'):compiler(path,font)
        assert not font.exists()


@pytest.mark.parametrize('field',[
    '(table 1 externref)',
    '(table 257 funcref)','(table 2 1 funcref)','(table -1 funcref)',
    '(table 1 257 funcref)','(table funcref)',
    '(table 1 funcref (export "t"))','(table (export) 1 funcref)',
    '(table 1 funcref) (elem (i32.const 1) $f)',
    '(table 1 funcref) (elem (i32.const -1) $f)',
    '(elem (i32.const 0) $f)',
    '(table 1 funcref) (elem (i32.const 0 1) $f)',
    '(table 1 funcref) (elem (i32.const 0) $missing)',
    '(table 1 funcref) (elem (i32.const 0) 9)',
    '(table 1 funcref) (elem $a (i32.const 0) $f) (elem $a (i32.const 0) $f)',
])
def test_invalid_or_unsupported_table_declarations_fail_closed(tmp_path,field):
    path=tmp_path/'bad.wat';path.write_text(f'(module {field} (func $f))')
    with pytest.raises((ValueError,NotImplementedError)):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


@pytest.mark.parametrize('signature',[
    '(type -1)','(type 99)','(type "0")','(type $missing)',
    '(type 0) (type 0)','(type 0) (param i64)',
])
def test_invalid_indirect_signatures_fail_before_output(tmp_path,signature):
    path=tmp_path/'bad.wat'
    path.write_text(f'''(module (type (func (param i32) (result i32))) (table 1 funcref)
      (func (param i32) (result i32) local.get 0 i32.const 0 call_indirect {signature}))''')
    with pytest.raises(ValueError):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


@pytest.mark.parametrize('body',[
    'i32.const 0 call_indirect (result i32)',
    'i64.const 0 call_indirect (result i32)',
    'i64.const 0 i32.const 0 call_indirect (param i32) (result i32)',
    'i32.const 0 call_indirect 1 (result i32)',
])
def test_missing_table_and_ill_typed_calls_rejected(tmp_path,body):
    path=tmp_path/'bad.wat';path.write_text(f'(module (func (result i32) {body}))')
    with pytest.raises((ValueError,NotImplementedError)):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


def test_multiple_binary_tables_preserve_the_default_table(tmp_path):
    data=independent_binary(table_count=2)
    path=tmp_path/'unsupported.wasm';path.write_bytes(data)
    module=load_binary(path)
    assert [table.entries for table in module.tables]==[[0,None],[None,None]]
    assert execute_binary(data,'run',['i32','i32'],[(7,0)])==[{'values':['8']}]


@pytest.mark.parametrize('body',[
    'i32.const 0 call_indirect (type $sig)',
    'i32.const 1 i64.const 0 call_indirect (type $sig)',
    'i64.const 1 i32.const 0 call_indirect (type $sig)',
    'i32.const 1 i32.const 0 call_indirect 0 $unexpected (type $sig)',
])
def test_call_operands_are_validated_with_a_declared_table(tmp_path,body):
    path=tmp_path/'bad-operands.wat'
    path.write_text(f'''(module (type $sig (func (param i32) (result i32)))
      (table 1 funcref) (func (result i32) {body}))''')
    with pytest.raises(ValueError):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


def test_nonzero_binary_table_operand_is_never_ignored(tmp_path):
    data=independent_binary(table_count=2)
    data=encode_sections([(sid,p.replace(b'\x11\x00\x00',b'\x11\x00\x01') if sid==10 else p)
                          for sid,p in sections(data)])
    path=tmp_path/'second-table.wasm';path.write_bytes(data)
    module=load_binary(path)
    assert parse_binary(path)[1].code[-1][1].table==1
    assert 'trap' in execute_binary(data,'run',['i32','i32'],[(7,0)])[0]
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as font:
        with pytest.raises(WasmTrap,match='uninitialized_element'):font.invoke(7,0)


def test_inactive_indirect_calls_do_not_leak_table_or_callee_traps(tmp_path):
    wat='''(module (table 3 funcref) (elem (i32.const 0) $divide $wrong)
      (func $divide (param i32 i32) (result i32) local.get 0 local.get 1 i32.div_u)
      (func $wrong (result i32) i32.const 7)
      (func (export "run") (param i32 i32) (result i32)
        local.get 1 if (result i32)
          i32.const 100 i32.const 0 local.get 0 call_indirect (param i32 i32) (result i32)
        else i32.const 42 end))'''
    compare(tmp_path,wat,[(slot,enabled) for slot in (0,1,2,3,0xffffffff) for enabled in (0,1)])


def test_indirect_results_feed_loop_carried_state(tmp_path):
    wat='''(module (table 3 funcref) (elem (i32.const 0) $add $subtract)
      (func $add (param i32) (result i32) local.get 0 i32.const 3 i32.add)
      (func $subtract (param i32) (result i32) local.get 0 i32.const 1 i32.sub)
      (func (export "run") (param i32 i32) (result i32) (local $n i32) (local $sum i32)
        local.get 0 local.set $n
        block $done loop $again
          local.get $n i32.eqz br_if $done
          local.get $sum local.get 1 call_indirect (param i32) (result i32) local.set $sum
          local.get $n i32.const 1 i32.sub local.set $n br $again
        end end local.get $sum))'''
    compare(tmp_path,wat,[(n,slot) for n in (0,1,3,7) for slot in (0,1,2,3)])
    with NativeFont(tmp_path/'program.ttf') as native:
        with pytest.raises(ExecutionBoundExceeded,match='loop'):native.invoke(8,0)
