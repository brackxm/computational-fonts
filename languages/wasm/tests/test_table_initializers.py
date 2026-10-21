"""Table initializer expressions seed every initial slot before active elements."""
import pytest

from wasmfont.compiler import compile_source
from wasmfont.frontend import parse_text,binary,load
from wasmfont.module import load_binary
from wasmfont.oracle import execute_binary
from wasmfont.runtime import NativeFont
from wasmfont.validation import validate
from .test_indirect_calls import compare
from .test_data_segments import sections,encode_sections


@pytest.mark.parametrize('binary_input',[False,True])
@pytest.mark.parametrize('folded',[False,True])
@pytest.mark.parametrize('minimum',[0,1,3,256])
@pytest.mark.parametrize('initial',['ref.null func','ref.func $f'])
def test_explicit_initializers_seed_only_initial_slots(tmp_path,binary_input,folded,minimum,initial):
    wat=f'''(module (table $callbacks (export "callbacks") {minimum} 256 funcref {'('+initial+')' if folded else initial})
      (func $f (param i64) (result i64) local.get 0 i64.const 7 i64.add)
      (func (export "run") (param i64 i32) (result i64 i32)
        local.get 0 local.get 1 call_indirect (param i64) (result i64) table.size))'''
    _,module,data=compare(tmp_path,wat,[(value,slot) for value in [0,-1,1<<63] for slot in sorted({0,minimum-1,minimum,255,256,-1})],binary_input=binary_input)
    assert module.table==([0] if 'ref.func' in initial else [None])*minimum
    assert binary(module)==data
    assert not module.elements


@pytest.mark.parametrize('table',[0,1])
def test_active_elements_override_seed_in_declaration_order(tmp_path,table):
    wat=f'''(module (table $first 4 funcref (ref.func $add))
      (table $second 4 funcref (ref.func $subtract))
      (elem (table {table}) (i32.const 1) funcref (ref.null func) (ref.func $subtract))
      (elem (table {table}) (i32.const 2) func $multiply)
      (func $add (param i32 i32) (result i32) local.get 0 local.get 1 i32.add)
      (func $subtract (param i32 i32) (result i32) local.get 0 local.get 1 i32.sub)
      (func $multiply (param i32 i32) (result i32) local.get 0 local.get 1 i32.mul)
      (func (export "run") (param i32 i32 i32) (result i32)
        local.get 0 local.get 1 local.get 2 call_indirect {table} (param i32 i32) (result i32)))'''
    _,module,data=compare(tmp_path,wat,[(a,b,slot) for a,b in [(0,7),(-1,2),(100,7)] for slot in [0,1,2,3,4,-1]])
    seed=table
    assert module.tables[table].entries==[seed,None,2,seed]
    assert binary(module)==data


def test_grown_slots_use_grow_operand_instead_of_declaration_initializer(tmp_path):
    wat='''(module (table 2 4 funcref (ref.func $add))
      (table $source 3 funcref (ref.func $subtract))
      (func $add (param i32 i32) (result i32) local.get 0 local.get 1 i32.add)
      (func $subtract (param i32 i32) (result i32) local.get 0 local.get 1 i32.sub)
      (func (export "run") (param i32 i32 i32 i32) (result i32 i32)
        local.get 3 if (result funcref) i32.const 0 table.get $source else ref.null func end
        i32.const 2 table.grow drop
        local.get 0 local.get 1 local.get 2 call_indirect (param i32 i32) (result i32)
        table.size))'''
    compare(tmp_path,wat,[(a,b,slot,filled) for a,b in [(100,7),(-1,1)] for slot in [0,1,2,3,4] for filled in [0,1]])


def test_seed_is_visible_to_start_function_and_instances_remain_independent(tmp_path):
    wat='''(module (table 2 funcref (ref.func $add))
      (func $add (param i32 i32) (result i32) local.get 0 local.get 1 i32.add)
      (func $subtract (param i32 i32) (result i32) local.get 0 local.get 1 i32.sub)
      (elem declare func $subtract)
      (func $init i32.const 1 ref.func $subtract table.set) (start $init)
      (func (export "run") (param i32 i32 i32) (result i32)
        local.get 0 local.get 1 local.get 2 call_indirect (param i32 i32) (result i32)))'''
    _,module,_=compare(tmp_path,wat,[(100,7,0),(100,7,1),(100,7,0),(100,7,1)])
    first=module.instantiate();first.table[0]=None
    assert module.instantiate().table==[0,1]
    assert module.table==[0,0]


def test_independent_binary_table_prefix_and_padded_function_index(tmp_path):
    original=binary(parse_text('''(module (table 3 4 funcref)
      (func $f (result i32) i32.const 42)
      (func (export "run") (param i32) (result i32) local.get 0 call_indirect (result i32)))'''))
    data=encode_sections([(sid,b'\x01\x40\x00\x70\x01\x03\x04\xd2\x80\x00\x0b' if sid==4 else body)
                          for sid,body in sections(original)])
    validate(data);path=tmp_path/'independent.wasm';path.write_bytes(data)
    module=load_binary(path)
    assert module.table==[0,0,0]
    expected=execute_binary(data,'run',['i32'],[(0,),(2,),(3,)])
    assert expected[:2]==[{'values':['42']},{'values':['42']}]
    assert 'trap' in expected[2]
    compile_source(path,path.with_suffix('.ttf'))
    with NativeFont(path.with_suffix('.ttf')) as font:assert font.invoke(2)==42


@pytest.mark.parametrize('initial',['(i32.const 0)','(ref.null func) (ref.null func)',
                                    '(global.get $ref)','(item (ref.null func))'])
def test_invalid_table_initializers_cannot_be_folded_away(tmp_path,initial):
    path=tmp_path/'invalid.wat'
    path.write_text(f'(module (global $ref funcref (ref.null func)) (table 2 funcref {initial}))')
    with pytest.raises((ValueError,NotImplementedError)):load(path)


def test_empty_table_still_validates_initializer_function_index(tmp_path):
    path=tmp_path/'invalid.wat'
    path.write_text('(module (table 0 funcref (ref.func 999)) (func (export "run")))')
    with pytest.raises(ValueError,match='V8 rejected'):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


@pytest.mark.parametrize('table',[0,1])
def test_writing_modified_seeded_table_can_clear_a_slot(tmp_path,table):
    # Programmatically constructed entries still serialize correctly when the
    # declaration's initializer is non-null and the overlay contains null.
    module=parse_text(f'''(module (table 3 funcref (ref.func $f))
      (table 3 funcref (ref.func $f)) (func $f (result i32) i32.const 42)
      (func (export "run") (param i32) (result i32) local.get 0 call_indirect {table} (result i32)))''')
    module.tables[table].entries[1]=None
    data=binary(module);validate(data)
    path=tmp_path/'modified.wasm';path.write_bytes(data)
    assert load_binary(path).tables[table].entries==[0,None,0]
    expected=execute_binary(data,'run',['i32'],[(0,),(1,),(2,)])
    assert expected[0]==expected[2]=={'values':['42']}
    assert 'trap' in expected[1]
