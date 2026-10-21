"""Extended constant expressions retain typed validation and Wasm wrapping."""
import pytest

from wasmfont.frontend import binary,load,parse_text
from wasmfont.module import load_binary
from wasmfont.compiler import compile_source,Limits
from wasmfont.runtime import NativeFont
from wasmfont.state import MemoryTrap
from wasmfont.validation import validate
from .test_indirect_calls import compare
from .test_data_segments import sections,encode_sections


@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('op',['add','sub','mul'])
@pytest.mark.parametrize('folded',[False,True])
@pytest.mark.parametrize('binary_input',[False,True])
def test_extended_integer_global_initializers(tmp_path,width,op,folded,binary_input):
    typ=f'i{width}'
    left=f'({typ}.const {(1<<width)-1})';right=f'({typ}.const {(1<<(width-1))+3})'
    expression=f'({typ}.{op} {left} {right})' if folded else f'{left} {right} {typ}.{op}'
    wat=f'''(module (global $seed {typ} {expression})
      (global $derived (mut {typ}) (global.get $seed) ({typ}.const 7) {typ}.mul)
      (func (export "run") (param {typ}) (result {typ} {typ})
        global.get $seed global.get $derived local.get 0 {typ}.add global.set $derived global.get $derived))'''
    _,module,data=compare(tmp_path,wat,[(0,),(1,),(-1,),(1<<(width-1),)],binary_input=binary_input)
    assert binary(module)==data
    # Expressions survive WAT writing and binary loading, rather than being
    # folded before the independent validator sees their operand types.
    assert module.constant_expressions['global',0].code[-1]==(f'{typ}.{op}',None)
    assert module.constant_expressions['global',1].code[0]==('global.get',0)


def test_reference_globals_can_alias_previously_defined_immutable_globals(tmp_path):
    wat='''(module (table 1 funcref) (elem declare func $f)
      (global $fref funcref (ref.func $f))
      (global $alias (mut funcref) (global.get $fref))
      (global $null funcref (ref.null func))
      (global $nullalias funcref (global.get $null))
      (func $f (param i64) (result i64) local.get 0 i64.const 3 i64.add)
      (func (export "run") (param i64) (result i64 i32)
        i32.const 0 global.get $alias table.set
        local.get 0 i32.const 0 call_indirect (param i64) (result i64)
        global.get $nullalias ref.is_null))'''
    _,module,data=compare(tmp_path,wat,[(0,),(-1,),(7,)])
    assert module.globals==[0,0,None,None]
    assert binary(module)==data


@pytest.mark.parametrize('body',[
    '(global i32 (i32.const 1) (i64.const 2) i32.add)',
    '(global i64 (i32.const 1))',
    '(global i32 i32.add)',
    '(global i32 (i32.const 1) (i32.const 2))',
    '(global i32)',
    '(global i32 (global.get 0))',
    '(global $a i32 (global.get $b)) (global $b i32 (i32.const 1))',
    '(global $a (mut i32) (i32.const 1)) (global i32 (global.get $a))',
    '(global $a funcref (ref.null func)) (global i32 (global.get $a))',
    '(global i32 (i32.const 4294967296) (i32.const 1) i32.add)',
])
def test_invalid_text_initializers_are_rejected_before_folding(body):
    with pytest.raises(ValueError):parse_text('(module '+body+')')


@pytest.mark.parametrize('op',['i32.div_u','i32.xor','i32.eqz','drop','nop'])
def test_runtime_instructions_cannot_be_used_in_constant_expressions(op):
    with pytest.raises(NotImplementedError,match='constant instruction'):
        parse_text(f'(module (global i32 (i32.const 1) (i32.const 2) {op}))')


def test_independently_constructed_binary_extended_expression_and_padded_operands(tmp_path):
    data=binary(parse_text('(module (global i32 (i32.const 0)) (func (export "run") (result i32) global.get 0))'))
    payload=b'\x01\x7f\x00\x41\xff\xff\xff\xff\x7f\x41\x82\x00\x6a\x41\x03\x6c\x0b'
    data=encode_sections([(sid,payload if sid==6 else body) for sid,body in sections(data)]);validate(data)
    path=tmp_path/'independent.wasm';path.write_bytes(data)
    module=load_binary(path)
    assert module.invoke('run',[])==[3]
    assert module.constant_expressions['global',0].code[-1]==('i32.mul',None)


def test_binary_validation_rejects_malformed_initializer_types(tmp_path):
    data=binary(parse_text('(module (global i32 (i32.const 0)))'))
    payload=b'\x01\x7f\x00\x42\x01\x42\x02\x7c\x0b'
    path=tmp_path/'invalid.wasm'
    path.write_bytes(encode_sections([(sid,payload if sid==6 else body) for sid,body in sections(data)]))
    with pytest.raises(ValueError,match='V8 rejected'):load_binary(path)


@pytest.mark.parametrize('binary_input',[False,True])
@pytest.mark.parametrize('table',[0,1])
@pytest.mark.parametrize('form',['folded','offset-folded','offset-flat'])
def test_computed_data_and_element_offsets_and_reference_aliases(tmp_path,binary_input,table,form):
    def offset(op,left,right):
        folded=f'(i32.{op} {left} {right})'
        return folded if form=='folded' else f'(offset {folded})' if form=='offset-folded' else f'(offset {left} {right} i32.{op})'
    data_offset=offset('mul','(global.get $base)','(i32.const 2)')
    elem_offset=offset('sub','(global.get $base)','(i32.const 1)')
    wat=f'''(module (memory 1) (table 4 funcref) (table 4 funcref)
      (global $base i32 (i32.add (i32.const 1) (i32.const 1)))
      (global $operation funcref (ref.func $add))
      (global $null funcref (ref.null func))
      (data {data_offset} "ABCD")
      (elem (table {table}) {elem_offset} funcref (item (global.get $operation)) (global.get $null))
      (func $add (param i32) (result i32) local.get 0 i32.const 4 i32.load i32.add)
      (func (export "run") (param i32 i32) (result i32)
        local.get 0 local.get 1 call_indirect {table} (param i32) (result i32)))'''
    _,module,data=compare(tmp_path,wat,[(a,slot) for a in [0,7,-1] for slot in [0,1,2,3,4,-1]],binary_input=binary_input)
    assert module.segments==[(4,b'ABCD')]
    assert module.tables[table].entries==[None,0,None,None]
    assert binary(module)==data
    assert module.constant_expressions['data',0].code[-1]==('i32.mul',None)
    assert module.constant_expressions['elem',0].code[-1]==('i32.sub',None)
    assert module.constant_expressions['element',0,0].code==(('global.get',1),)


@pytest.mark.parametrize('mode',['active','passive','declarative'])
def test_reference_element_initializers_can_read_immutable_globals(tmp_path,mode):
    prefix={'active':'(offset i32.const 0 i32.const 0 i32.add)','passive':'','declarative':'declare'}[mode]
    wat=f'''(module (table 2 funcref)
      (global $callback funcref (ref.func $f)) (global $empty funcref (ref.null func))
      (elem $refs {prefix} funcref (global.get $callback) (item (global.get $empty)))
      (func $f (result i32) i32.const 42)
      (func (export "run") (param i32) (result i32)
        {'i32.const 0 i32.const 0 i32.const 2 table.init $refs' if mode!='active' else ''}
        local.get 0 call_indirect (result i32)))'''
    _,module,data=compare(tmp_path,wat,[(0,),(1,),(2,)])
    assert binary(module)==data


def test_expression_offsets_wrap_before_instantiation_bounds_checks(tmp_path):
    wat='''(module (memory 1) (table 1 funcref)
      (data (i32.add (i32.const -1) (i32.const 1)) "A")
      (elem (i32.mul (i32.const -2147483648) (i32.const 2)) func $f)
      (func $f (result i32) i32.const 0 i32.load8_u)
      (func (export "run") (result i32) i32.const 0 call_indirect (result i32)))'''
    _,module,_=compare(tmp_path,wat,[()])
    assert module.segments==[(0,b'A')]


@pytest.mark.parametrize('payload',['','A'])
def test_data_offset_out_of_bounds_is_an_instantiation_error(tmp_path,payload):
    path=tmp_path/'bounds.wat'
    path.write_text(f'(module (memory 1) (data (i32.sub (i32.const 0) (i32.const 1)) "{payload}"))')
    with pytest.raises(MemoryTrap):load(path)


@pytest.mark.parametrize('field',[
    '(data (global.get $mutable) "A")',
    '(elem (global.get $mutable) func $f)',
    '(elem funcref (global.get $mutable_ref))',
    '(data (offset i64.const 1) "A")',
    '(elem (offset i32.const 0 i32.const 0) func $f)',
    '(elem funcref (item (ref.null func) (ref.null func)))',
])
def test_invalid_offset_and_reference_expressions_are_not_folded_away(field):
    wat=f'''(module (memory 1) (table 2 funcref)
      (global $mutable (mut i32) (i32.const 0))
      (global $mutable_ref (mut funcref) (ref.null func))
      (func $f) {field})'''
    with pytest.raises(ValueError):parse_text(wat)


def test_loading_and_compiling_constant_expressions_never_runs_wasm(tmp_path,monkeypatch):
    import wasmfont.reference.interpreter as interpreter
    def forbidden(*args,**kwargs):raise AssertionError('initializer called the reference VM')
    monkeypatch.setattr(interpreter,'run',forbidden)
    source=tmp_path/'declarations.wat'
    source.write_text('''(module (memory 1)
      (global $base i32 (i32.mul (i32.const 2) (i32.const 2)))
      (data (global.get $base) "A")
      (func (export "run") (result i32) global.get $base i32.load8_u))''')
    compile_source(source,source.with_suffix('.ttf'),limits=Limits(memory_bytes=8))
    with NativeFont(source.with_suffix('.ttf')) as font:assert font.invoke()==65


def test_programmatic_value_edits_are_not_overwritten_by_retained_expressions(tmp_path):
    module=parse_text('''(module (memory 1) (table 1 funcref)
      (global $seed i32 (i32.add (i32.const 2) (i32.const 2)))
      (global $alias i32 (global.get $seed))
      (global $callback funcref (ref.func $first))
      (data (global.get $seed) "A")
      (elem (i32.const 0) funcref (global.get $callback))
      (func $first (result i32) i32.const 1)
      (func $second (result i32) i32.const 2)
      (func (export "run") (result i32 i32 i32 i32)
        global.get $seed global.get $alias i32.const 4 i32.load8_u
        i32.const 0 call_indirect (result i32)))''')
    module.globals[0]=8
    module.globals[2]=1
    module.elements[0].functions[0]=1
    path=tmp_path/'edited.wasm';path.write_bytes(binary(module))
    reloaded=load_binary(path)
    assert reloaded.globals==[8,4,1]
    assert reloaded.segments==[(4,b'A')]
    assert reloaded.table==[1]
    assert reloaded.invoke('run',[])==[8,4,65,2]
