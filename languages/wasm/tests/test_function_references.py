"""Nullable funcref values compose through internal interfaces and control flow."""
import pytest

from wasmfont.compiler import compile_source
from wasmfont.frontend import binary
from wasmfont.module import load_binary
from wasmfont.oracle import execute_binary
from wasmfont.runtime import NativeFont,ExecutionBoundExceeded
from .test_indirect_calls import compare,independent_binary
from .test_data_segments import sections,encode_sections

FUNCS='''(func $a (param i32) (result i32) local.get 0 i32.const 7 i32.add)
 (func $b (param i32) (result i32) local.get 0 i32.const 3 i32.sub)'''


@pytest.mark.parametrize('binary_input',[False,True])
@pytest.mark.parametrize('folded',[False,True])
def test_typed_reference_select_internal_calls_and_globals(tmp_path,binary_input,folded):
    select='(select (result funcref) (local.get 0) (local.get 1) (local.get 2))' if folded else 'local.get 0 local.get 1 local.get 2 select (result funcref)'
    wat=f'''(module (table 3 funcref)
      (elem (i32.const 0) funcref (ref.func $a) (ref.null func) (ref.func $b))
      (global $g (mut funcref) (ref.func $a)) {FUNCS}
      (func $choose (param funcref funcref i32) (result funcref) {select})
      (func (export "run") (param i32 i32) (result i32 i32)
        global.get $g ref.func $b local.get 0 call $choose global.set $g
        i32.const 1 global.get $g table.set
        local.get 1 i32.const 1 call_indirect (param i32) (result i32)
        global.get $g ref.is_null))'''
    compare(tmp_path,wat,[(s,v) for s in [0,1,-1] for v in [0,10,-1,0x80000000]],binary_input=binary_input)


@pytest.mark.parametrize('typ',['i32','i64'])
def test_typed_integer_select_preserves_width(tmp_path,typ):
    wat=f'''(module (func (export "run") (param {typ} {typ} i32) (result {typ})
      local.get 0 local.get 1 local.get 2 select (result {typ})))'''
    compare(tmp_path,wat,[(1,-1,0),(1,-1,1),(1,-1,0x80000000)])


@pytest.mark.parametrize('form',['block','if','br','br_if','br_table'])
def test_reference_block_parameters_results_and_branches(tmp_path,form):
    bodies={
      'block':'ref.func $a block (param funcref) (result funcref) end',
      'if':'local.get 0 if (result funcref) ref.func $a else ref.null func end',
      'br':'block $out (result funcref) ref.func $a br $out end',
      'br_if':'block $out (result funcref) ref.func $a local.get 0 br_if $out drop ref.null func end',
      'br_table':'block $outer (result funcref) block $inner (result funcref) ref.func $a local.get 0 br_table $inner $outer end end',
    }
    wat=f'''(module (elem declare func $a) {FUNCS}
      (func (export "run") (param i32) (result i32) {bodies[form]} ref.is_null))'''
    compare(tmp_path,wat,[(0,),(1,),(2,),(0xffffffff,)])


def test_mixed_reference_loop_parameters_and_backedge_values(tmp_path):
    wat=f'''(module (table 1 funcref) (elem declare func $a $b) {FUNCS}
      (func (export "run") (param i32 i32) (result i32) (local $n i32) (local $r funcref)
        ref.func $a local.get 0
        loop $again (param funcref i32) (result funcref)
          local.set $n local.set $r
          local.get $n if (result funcref)
            ref.func $a ref.func $b local.get $r ref.is_null select (result funcref)
            local.get $n i32.const 1 i32.sub br $again
          else local.get $r end
        end
        local.set $r i32.const 0 local.get $r table.set
        local.get 1 i32.const 0 call_indirect (param i32) (result i32)))'''
    compare(tmp_path,wat,[(n,v) for n in [0,1,3,7] for v in [0,100,-1]])
    with NativeFont(tmp_path/'program.ttf') as font:
        with pytest.raises(ExecutionBoundExceeded,match='loop'):font.invoke(8,100)


def test_indirect_calls_accept_and_return_references_with_structural_type_checks(tmp_path):
    wat=f'''(module (table 4 funcref) (elem (i32.const 0) $identity $null $a)
      (elem declare func $b) {FUNCS}
      (func $identity (param funcref) (result funcref) local.get 0)
      (func $null (param funcref) (result funcref) ref.null func)
      (func (export "run") (param i32 i32) (result i32)
        i32.const 3 ref.func $b local.get 0 call_indirect (param funcref) (result funcref) table.set
        local.get 1 i32.const 3 call_indirect (param i32) (result i32)))'''
    compare(tmp_path,wat,[(slot,v) for slot in [0,1,2,3,4,0xffffffff] for v in [0,10,-1]])


@pytest.mark.parametrize('mode',['active','passive','declarative'])
@pytest.mark.parametrize('wrappers',[False,True])
def test_nullable_element_expression_lifetimes_and_roundtrip(tmp_path,mode,wrappers):
    expressions=['(ref.func $a)','(ref.null func)','(ref.func $b)']
    if wrappers:expressions=[f'(item {e})' for e in expressions]
    head={'active':'(i32.const 0)','passive':'','declarative':'declare'}[mode]
    init='local.get 1 i32.const 0 i32.const 3 table.init $p' if mode!='active' else ''
    wat=f'''(module (table 6 funcref) (elem $p {head} funcref {' '.join(expressions)}) {FUNCS}
      (func (export "run") (param i32 i32 i32) (result i32)
        local.get 2 if elem.drop $p end {init}
        i32.const 10 local.get 0 call_indirect (param i32) (result i32)))'''
    _,module,data=compare(tmp_path,wat,[(slot,d,drop) for slot in [0,1,2,3,5,6] for d in [0,3,4] for drop in [0,1]])
    assert binary(module)==data


def test_reference_globals_initialized_before_start_and_fresh_invocations(tmp_path):
    wat=f'''(module (table 1 funcref) (elem declare funcref (ref.func $a) (ref.func $b)) {FUNCS}
      (global $constant funcref (ref.func $a)) (global $chosen (mut funcref) (ref.null func))
      (func $start global.get $constant global.set $chosen) (start $start)
      (func (export "run") (param i32 i32) (result i32)
        local.get 0 if ref.func $b global.set $chosen end
        i32.const 0 global.get $chosen table.set
        local.get 1 i32.const 0 call_indirect (param i32) (result i32)))'''
    _,module,_=compare(tmp_path,wat,[(0,10),(1,10),(0,10)])
    state=module.instantiate()
    assert module.invoke('run',[1,10],state=state)==[7]
    assert module.invoke('run',[0,10],state=state)==[7]
    assert module.invoke('run',[0,10])==[17]


@pytest.mark.parametrize('flag',[4,5,6,7])
def test_independent_binary_reference_elements_and_padded_typed_select(tmp_path,flag):
    data=independent_binary()
    # Independently encode reference expressions, including a null middle slot.
    header=bytes([flag])+(b'\x80\x00' if flag==6 else b'')
    if flag in (4,6):header+=b'\x41\x00\x0b'
    if flag!=4:header+=b'\x70'
    element=b'\x01'+header+b'\x03\xd2\x00\x0b\xd0\xf0\x7f\x0b\xd2\x00\x0b'
    table=b'\x01\x70\x00\x03'
    target=b'\x00\x20\x00\x41\x01\x6a\x0b'
    # Select null vs ref.func 0 and test for null. The public parameters remain i32.
    body=b'\x00\xd0\x70\xd2\x00\x20\x01\x1c\x81\x00\x70\xd1\x0b'
    code=b'\x02'+bytes([len(target)])+target+bytes([len(body)])+body
    data=encode_sections([(tag,element if tag==9 else table if tag==4 else code if tag==10 else payload) for tag,payload in sections(data)])
    path=tmp_path/'independent.wasm';path.write_bytes(data);module=load_binary(path)
    assert module.elements[0].functions==[0,None,0]
    assert execute_binary(data,'run',['i32','i32'],[(7,0),(7,1)])==[{'values':['0']},{'values':['1']}]
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as font:
        assert font.invoke(7,0)==0 and font.invoke(7,1)==1


@pytest.mark.parametrize('signature,body',[
 ('(param funcref)',''),('(result funcref)','ref.null func'),
])
def test_font_entry_reference_abi_is_rejected_explicitly(tmp_path,signature,body):
    path=tmp_path/'abi.wat';path.write_text(f'(module (func (export "run") {signature} {body}))')
    with pytest.raises(NotImplementedError,match='font entry parameters/results'):compile_source(path,path.with_suffix('.ttf'),export='run')
    assert not path.with_suffix('.ttf').exists()


@pytest.mark.parametrize('field,body',[
 ('','ref.null func i32.const 0 i32.const 1 select (result funcref) drop'),
 ('','ref.null func ref.null func i32.const 1 select drop'),
 ('','ref.null func ref.null func i32.const 1 select (result i32) drop'),
 ('','ref.null func ref.null func i32.const 1 select (result funcref i32) drop'),
 ('','ref.null func ref.null func i32.const 1 select (result externref) drop'),
 ('(global $g funcref (ref.null func))','ref.null func global.set $g'),
 ('(global $g (mut funcref) (ref.null func))','i32.const 0 global.set $g'),
 ('(elem funcref (i32.const 0))',''),
 ('(global $g funcref (ref.null extern))',''),
 ('(global $g funcref (item (ref.null func)))',''),
])
def test_reference_type_errors_fail_before_font_output(tmp_path,field,body):
    path=tmp_path/'bad.wat';path.write_text(f'(module {field} (func (export "run") {body}))')
    with pytest.raises((ValueError,NotImplementedError)):compile_source(path,path.with_suffix('.ttf'),export='run')
    assert not path.with_suffix('.ttf').exists()


@pytest.mark.parametrize('indirect',[False,True])
def test_mixed_multi_value_internal_reference_results(tmp_path,indirect):
    call='i32.const 0 call_indirect (param funcref i64 i32) (result i32 funcref i64)' if indirect else 'call $swap'
    wat=f'''(module (table 2 funcref) (elem (i32.const 0) $swap) (elem declare func $a) {FUNCS}
      (func $swap (param funcref i64 i32) (result i32 funcref i64)
        local.get 2 local.get 0 local.get 1)
      (func (export "run") (param i64 i32) (result i32 i64 i32) (local $r funcref) (local $value i64)
        ref.func $a local.get 0 local.get 1 {call} local.set $value local.set $r
        local.get $value i32.const 1 local.get $r table.set
        local.get 1 i32.const 1 call_indirect (param i32) (result i32)))'''
    compare(tmp_path,wat,[(a,b) for a in [0,0x807f060504030201,-1] for b in [0,7,-1]])


def test_global_reference_initializer_is_a_dynamic_dispatch_target_without_elements(tmp_path):
    wat=f'''(module (table 1 funcref) (global $g funcref (ref.func $a)) {FUNCS}
      (func (export "run") (param i32 i32) (result i32)
        i32.const 0 global.get $g ref.null func local.get 0 select (result funcref) table.set
        local.get 1 i32.const 0 call_indirect (param i32) (result i32)))'''
    compare(tmp_path,wat,[(s,v) for s in [0,1,-1] for v in [0,10,-1]])


def test_recursive_reference_results_preserve_call_bounds(tmp_path):
    wat=f'''(module (table 1 funcref) (elem declare func $a) {FUNCS}
      (func $recursive (param funcref i32) (result funcref)
        local.get 1 if (result funcref)
          local.get 0 local.get 1 i32.const 1 i32.sub call $recursive
        else local.get 0 end)
      (func (export "run") (param i32) (result i32)
        ref.func $a local.get 0 call $recursive ref.is_null))'''
    compare(tmp_path,wat,[(0,),(1,),(5,),(6,)])
    with NativeFont(tmp_path/'program.ttf') as font:
        with pytest.raises(ExecutionBoundExceeded,match='call'):font.invoke(7)
