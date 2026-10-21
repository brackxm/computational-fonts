"""Typed tables and segments preserve types through mutation and direct calls."""
import pytest

from wasmfont.compiler import compile_source
from wasmfont.frontend import binary,parse_text
from wasmfont.module import load_binary
from wasmfont.runtime import NativeFont,WasmTrap
from wasmfont.types import ReferenceType
from .test_indirect_calls import compare


@pytest.mark.parametrize('nullable',[False,True])
@pytest.mark.parametrize('table',[0,1])
@pytest.mark.parametrize('binary_input',[False,True])
def test_typed_table_values_are_directly_callable(tmp_path,nullable,table,binary_input):
    typ=f'(ref {"null " if nullable else ""}$binary)'
    initial='' if nullable else '(ref.func $add)'
    wat=f'''(module (type $binary (func (param i64 i64) (result i64)))
      (table 3 5 {typ} {initial}) (table 3 5 {typ} {initial})
      (elem (table {table}) (i32.const 0) (ref $binary) (ref.func $add) (ref.func $divide))
      (func $add (type $binary) local.get 0 local.get 1 i64.add)
      (func $divide (type $binary) local.get 0 local.get 1 i64.div_u)
      (func (export "run") (param i64 i64 i32) (result i64)
        local.get 0 local.get 1 local.get 2 table.get {table} call_ref $binary))'''
    _,module,data=compare(tmp_path,wat,[(a,b,slot) for a,b in [(100,7),(-1,1),(1,0)] for slot in [0,1,2,3,-1]],binary_input=binary_input)
    assert module.tables[table].element_type==ReferenceType(0,nullable)
    assert module.elements[0].element_type==ReferenceType(0,False)
    assert binary(module)==data


@pytest.mark.parametrize('nullable',[False,True])
def test_typed_bulk_segments_grow_copy_fill_and_drop(tmp_path,nullable):
    typ=f'(ref {"null " if nullable else ""}$binary)'
    initial='' if nullable else '(ref.func $add)'
    wat=f'''(module (type $binary (func (param i32 i32) (result i32)))
      (type $alias (func (param i32 i32) (result i32)))
      (table $source 3 {typ} {initial}) (table $dispatch 1 4 (ref {"null " if nullable else ""}$alias) {initial})
      (elem $library {typ} (ref.func $add) (ref.func $subtract) (ref.func $multiply))
      (func $add (type $binary) local.get 0 local.get 1 i32.add)
      (func $subtract (type $binary) local.get 0 local.get 1 i32.sub)
      (func $multiply (type $binary) local.get 0 local.get 1 i32.mul)
      (func (export "run") (param i32 i32 i32 i32) (result i32 i32)
        i32.const 0 i32.const 0 i32.const 3 table.init $source $library elem.drop $library
        i32.const 0 i32.const 0 i32.const 1 table.copy $dispatch $source
        local.get 2 table.get $source i32.const 3 table.grow $dispatch drop
        local.get 3 if i32.const 0 i32.const 1 table.get $source i32.const 1 table.fill $dispatch end
        local.get 0 local.get 1 i32.const 3 table.get $dispatch call_ref $alias
        table.size $dispatch))'''
    compare(tmp_path,wat,[(a,b,operation,fill) for a,b in [(100,7),(-1,2)] for operation in [0,1,2,3] for fill in [0,1]])


@pytest.mark.parametrize('mode',['active','passive','declarative'])
def test_typed_element_forms_allow_nullable_entries(tmp_path,mode):
    prefix={'active':'(i32.const 0)','passive':'','declarative':'declare'}[mode]
    wat=f'''(module (type $word (func (result i32))) (table 2 (ref null $word))
      (elem $callbacks {prefix} (ref null $word) (ref.func $f) (ref.null $word))
      (func $f (type $word) i32.const 42)
      (func (export "run") (param i32) (result i32)
        {'i32.const 0 i32.const 0 i32.const 2 table.init $callbacks' if mode!='active' else ''}
        local.get 0 table.get call_ref $word))'''
    _,module,data=compare(tmp_path,wat,[(0,),(1,),(2,)])
    assert binary(module)==data


def test_typed_table_indirect_signature_mismatch_still_traps(tmp_path):
    wat='''(module (type $word (func (param i32) (result i32)))
      (table 1 (ref $word) (ref.func $f))
      (func $f (type $word) local.get 0)
      (func (export "run") (param i64) (result i64)
        local.get 0 i32.const 0 call_indirect (param i64) (result i64)))'''
    compare(tmp_path,wat,[(0,),(7,),(-1,)])


def test_typed_table_initialization_precedes_start(tmp_path):
    wat='''(module (type $word (func (result i32)))
      (table 1 (ref $word) (ref.func $f)) (global $answer (mut i32) (i32.const 0))
      (func $f (type $word) i32.const 42)
      (func $start i32.const 0 table.get call_ref $word global.set $answer) (start $start)
      (func (export "run") (result i32) global.get $answer))'''
    compare(tmp_path,wat,[()])


@pytest.mark.parametrize('field',[
    '(table 1 (ref $word))',
    '(table 0 (ref $word))',
    '(table 1 (ref $word) (ref.null $word))',
    '(table 1 (ref null $word)) (elem (i32.const 0) funcref (ref.func $f))',
    '(table 1 (ref null $word)) (elem (i32.const 0) (ref $word) (ref.null $word))',
    '(table 1 (ref null $word)) (elem (i32.const 0) (ref null $other) (ref.func $wrong))',
])
def test_invalid_typed_table_or_element_initialization_fails_before_output(tmp_path,field):
    path=tmp_path/'invalid.wat';path.write_text(f'''(module (type $word (func))
      (type $other (func (result i32))) {field}
      (func $f) (func $wrong (result i32) i32.const 7) (elem declare func $f $wrong)
      (func (export "run")))''')
    with pytest.raises(ValueError):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


def test_programmatic_typed_table_overlay_preserves_reference_type(tmp_path):
    module=parse_text('''(module (type $word (func (result i32)))
      (table 3 (ref null $word) (ref.func $f))
      (func $f (type $word) i32.const 42)
      (func (export "run") (param i32) (result i32) local.get 0 table.get call_ref $word))''')
    module.table[1]=None
    data=binary(module);path=tmp_path/'overlay.wasm';path.write_bytes(data)
    reloaded=load_binary(path)
    assert reloaded.elements[0].element_type==ReferenceType(0,True)
    compile_source(path,path.with_suffix('.ttf'))
    with NativeFont(path.with_suffix('.ttf')) as font:
        assert font.invoke(0)==font.invoke(2)==42
        with pytest.raises(WasmTrap,match='null_reference'):font.invoke(1)
