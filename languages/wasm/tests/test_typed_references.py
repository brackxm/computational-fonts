"""Explicit nullable/non-null function types retain independent V8 validation."""
import pytest

from wasmfont.frontend import load,binary,parse_text,signed_leb
from wasmfont.compiler import compile_source
from wasmfont.ir import parse_binary
from wasmfont.runtime import NativeFont,WasmTrap
from wasmfont.types import ReferenceType,signature_keys
from .test_indirect_calls import compare


@pytest.mark.parametrize('binary_input',[False,True])
@pytest.mark.parametrize('heap',['func','$word'])
def test_explicit_reference_signatures_locals_globals_and_blocks(tmp_path,binary_input,heap):
    wat=f'''(module (type $word (func (param i64) (result i64)))
      (table 1 funcref)
      (global $fallback (ref {heap}) (ref.func $increment))
      (global $selected (mut (ref null {heap})) (ref.null {heap}))
      (func $increment (param i64) (result i64) local.get 0 i64.const 7 i64.add)
      (func $choose (param $strict i32) (result (ref {heap})) (local $ref (ref {heap}))
        local.get $strict if (result (ref {heap}))
          global.get $selected ref.as_non_null
        else global.get $fallback end local.set $ref
        block (result (ref {heap})) local.get $ref end)
      (func (export "run") (param i64 i32 i32) (result i64)
        local.get 2 if global.get $fallback global.set $selected end
        i32.const 0 local.get 1 call $choose table.set
        local.get 0 i32.const 0 call_indirect (type $word)))'''
    _,module,data=compare(tmp_path,wat,[(a,strict,install) for a in [0,-1,1<<63] for strict in [0,1] for install in [0,1]],binary_input=binary_input)
    assert binary(module)==data
    assert isinstance(module.global_types[0],ReferenceType)
    assert module.global_types[0].nullable is False


@pytest.mark.parametrize('nullable',[False,True])
@pytest.mark.parametrize('binary_input',[False,True])
def test_structurally_equal_indexed_reference_types_match_indirect_signatures(tmp_path,nullable,binary_input):
    ref='ref null' if nullable else 'ref'
    wat=f'''(module (type $a (func (param i32) (result i32)))
      (type $alias (func (param i32) (result i32)))
      (table 2 funcref) (elem (i32.const 0) $pass $wrong)
      (func $increment (param i32) (result i32) local.get 0 i32.const 7 i32.add)
      (elem declare func $increment)
      (func $pass (param ({ref} $a)) (result ({ref} $a)) local.get 0)
      (func $wrong (param ({'ref' if nullable else 'ref null'} $a)) (result ({ref} $a))
        local.get 0 {'ref.as_non_null' if not nullable else ''})
      (func (export "run") (param i32 i32) (result i32) (local $result ({ref} $alias))
        ref.func $increment local.get 1 call_indirect (param ({ref} $alias)) (result ({ref} $alias))
        local.set $result
        i32.const 0 local.get $result table.set
        local.get 0 i32.const 0 call_indirect (type $a)))'''
    compare(tmp_path,wat,[(a,slot) for a in [0,7,-1] for slot in [0,1,2]],binary_input=binary_input)


def test_typed_reference_select_and_reference_loop_parameters(tmp_path):
    wat='''(module (type $word (func (param i64) (result i64))) (table 1 funcref)
      (elem declare func $add $xor)
      (func $add (param i64) (result i64) local.get 0 i64.const 7 i64.add)
      (func $xor (param i64) (result i64) local.get 0 i64.const -1 i64.xor)
      (func $choose (param i32 i32) (result (ref $word)) (local $n i32)
        ref.func $add ref.func $xor local.get 0 select (result (ref $word)) local.get 1
        loop $again (param (ref $word) i32) (result (ref $word))
          local.tee $n if (param (ref $word)) (result (ref $word))
            local.get $n i32.const 1 i32.sub br $again end
        end)
      (func (export "run") (param i64 i32 i32) (result i64)
        i32.const 0 local.get 1 local.get 2 call $choose table.set
        local.get 0 i32.const 0 call_indirect (type $word)))'''
    compare(tmp_path,wat,[(a,which,n) for a in [0,7,-1] for which in [0,1] for n in [0,1,7]])


@pytest.mark.parametrize('declaration',['(param (ref func))','(result (ref null func))',
                                     '(param (ref $word))','(result (ref null $word))'])
def test_selected_font_entry_still_requires_integer_abi(tmp_path,declaration):
    path=tmp_path/'abi.wat';path.write_text(f'(module (type $word (func)) (func (export "run") {declaration} unreachable))')
    with pytest.raises(NotImplementedError,match='font entry parameters/results'):compile_source(path,path.with_suffix('.ttf'))


@pytest.mark.parametrize('body',[
    '(local $ref (ref $word)) local.get $ref drop',
    '(local $ref (ref $word)) i32.const 1 if ref.func $f local.set $ref end local.get $ref drop',
])
def test_non_defaultable_locals_must_be_definitely_initialized(tmp_path,body):
    path=tmp_path/'invalid.wat';path.write_text(f'(module (type $word (func)) (func $f) (elem declare func $f) (func (export "run") {body}))')
    with pytest.raises(ValueError,match='V8 rejected'):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


def test_references_to_recursive_function_types_fail_explicitly():
    with pytest.raises(NotImplementedError,match='recursive function types'):
        parse_text('(module (type $recursive (func (param (ref $recursive)))))')


@pytest.mark.parametrize('field',[
    '(func (param (ref null 0)))',
    '(func (local (ref 0)))',
    '(global (ref null 0) (ref.null 0))',
    '(table 1 (ref null 0))',
    '(elem (ref null 0) (ref.null 0))',
    '(func ref.null 0 drop)',
    '(func block (result (ref null 0)) unreachable end drop)',
    '(func ref.null func ref.null func i32.const 0 select (result (ref null 0)) drop)',
])
def test_undefined_heap_indices_cannot_bind_to_synthesized_function_types(field):
    with pytest.raises(ValueError,match='heap type index out of range'):parse_text('(module '+field+')')


def test_alias_keys_do_not_expand_higher_order_type_graphs():
    types=[([],['i32'])]
    for at in range(1,500):types.append(([ReferenceType(at-1),ReferenceType(at-1)],[]))
    keys=signature_keys(types)
    assert len(keys)==len(set(keys))==500


def test_inline_signatures_accept_equivalent_reference_spellings_and_aliases(tmp_path):
    wat='''(module (type $word (func)) (type $alias (func))
      (type $pass (func (param (ref $word)) (result funcref)))
      (func $f) (elem declare func $f)
      (func $pass (type $pass) (param (ref $alias)) (result (ref null func))
        local.get 0 block (type $pass) (param (ref $alias)) (result (ref null func)) end)
      (func (export "run") (result i32) ref.func $f call $pass ref.is_null))'''
    compare(tmp_path,wat,[()])


def test_explicit_reference_block_type_binary_decoder(tmp_path):
    # A reference value type is also a legal compact blocktype, independently
    # of the writer's structural type-index encoding for explicit WAT blocks.
    from .test_data_segments import sections,encode_sections
    wat='''(module (func (export "run") (result i32)
      block (result funcref) ref.null func end ref.is_null))'''
    data=binary(parse_text(wat));parts=[]
    for sid,body in sections(data):
        if sid==10:
            body=body.replace(b'\x02\x70',b'\x02\x63\x70')
            body=body[:1]+bytes([body[1]+1])+body[2:]
        parts.append((sid,body))
    path=tmp_path/'compact.wasm';path.write_bytes(encode_sections(parts))
    assert isinstance(parse_binary(path)[0].code[0][1],ReferenceType)
    compile_source(path,path.with_suffix('.ttf'))
    with NativeFont(path.with_suffix('.ttf')) as font:assert font.invoke()==1


@pytest.mark.parametrize('index',[0,63,64,127,128])
@pytest.mark.parametrize('padded',[False,True])
def test_indexed_heap_types_use_signed_leb_and_preserve_declared_indices(tmp_path,index,padded):
    from .test_data_segments import sections,encode_sections
    declarations=' '.join(f'(type $t{i} (func (param i32) (result i32)))' for i in range(index+1))
    module=parse_text(f'''(module {declarations}
      (global $callback (ref $t{index}) (ref.func $f))
      (func $f (type $t0) local.get 0 i32.const 7 i32.add)
      (func (export "run") (param i32 i32) (result i32) (local $ref (ref null $t{index}))
        global.get $callback ref.null $t{index} local.get 1 select (result (ref null $t{index})) local.set $ref
        local.get 0 local.get $ref call_ref $t{index}))''')
    data=binary(module)
    if padded:
        heap=signed_leb(index,33);padding=heap[:-1]+bytes([heap[-1]|128,0])
        data=encode_sections([(sid,body.replace(b'\x64'+heap,b'\x64'+padding,1) if sid==6 else body) for sid,body in sections(data)])
    path=tmp_path/'heaps.wasm';path.write_bytes(data)
    from wasmfont.module import load_binary
    loaded=load_binary(path)
    assert loaded.global_types[0]==ReferenceType(index,False)
    assert loaded.invoke('run',[100,1])==[107]
    compile_source(path,path.with_suffix('.ttf'))
    with NativeFont(path.with_suffix('.ttf')) as font:
        assert font.invoke(100,1)==107
        with pytest.raises(WasmTrap,match='null_reference'):font.invoke(100,0)


def test_heap_index_used_only_in_compact_block_preserves_source_type_space(tmp_path):
    from .test_data_segments import encode_sections
    from wasmfont.module import load_binary
    body=b'\x00\x02\x63\x00\x00\x0b\x1a\x41\x2a\x0b'
    data=encode_sections([(1,b'\x02\x60\x00\x00\x60\x00\x01\x7f'),
                          (3,b'\x01\x01'),(7,b'\x01\x03run\x00\x00'),
                          (10,b'\x01'+bytes([len(body)])+body)])
    path=tmp_path/'compact-only.wasm';path.write_bytes(data)
    assert binary(load_binary(path))==data
