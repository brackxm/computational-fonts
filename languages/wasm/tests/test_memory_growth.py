"""Native page counts, growth results, zero bytes, and dynamic memory bounds."""
import pytest

from wasmfont.compiler import compile_source, Limits
from wasmfont.frontend import load, binary, parse_text
from wasmfont.ir import parse_binary
from wasmfont.module import load_binary
from wasmfont.runtime import NativeFont, ExecutionBoundExceeded
from .test_bulk_memory import check
from .test_data_segments import sections, encode_sections


@pytest.mark.parametrize('initial,maximum',[(0,0),(0,1),(0,3),(0,256),(1,1),(1,3),(255,256),(256,256)])
@pytest.mark.parametrize('folded',[False,True])
def test_growth_results_unsigned_deltas_and_page_limit(tmp_path,initial,maximum,folded):
    grow='(memory.grow (local.get 0))' if folded else 'local.get 0 memory.grow'
    wat=f'''(module (memory {initial} {maximum})
      (func (export "run") (param i32) (result i32 i32 i32)
        memory.size {grow} memory.size))'''
    cases=[(v,) for v in sorted({0,1,2,maximum-initial,maximum-initial+1,256,257,0x7fffffff,0x80000000,0xffffffff})]
    check(tmp_path,wat,cases,binary_input=folded)


def test_sequential_growth_failures_keep_the_size_and_can_recover(tmp_path):
    wat='''(module (memory 0 3)
      (func (export "run") (param i32 i32 i32) (result i32 i32 i32 i32)
        local.get 0 memory.grow local.get 1 memory.grow local.get 2 memory.grow memory.size))'''
    cases=[(0,1,1),(1,2,0),(1,3,1),(0xffffffff,2,1),(2,0xffffffff,1),
           (3,0,1),(256,0,1),(0x80000000,0x80000000,1)]
    check(tmp_path,wat,cases)


@pytest.mark.parametrize('window',[0,1,3,16,64,256])
def test_growth_from_zero_exposes_zeroed_backed_bytes(tmp_path,window):
    read=(f'i32.const {window-1} i32.load8_u' if window else 'i32.const 42')
    wat=f'''(module (memory 0 2)
      (func (export "run") (param i32) (result i32 i32 i32)
        local.get 0 memory.grow memory.size {read}))'''
    check(tmp_path,wat,[(0,),(1,),(2,),(3,),(0xffffffff,),(1,)],window=window)


@pytest.mark.parametrize('op',[
    'i32.load','i64.load','i32.load8_s','i32.load8_u','i32.load16_s','i32.load16_u',
    'i64.load8_s','i64.load8_u','i64.load16_s','i64.load16_u','i64.load32_s','i64.load32_u',
])
def test_load_bounds_follow_runtime_growth(tmp_path,op):
    typ=op[:3]
    size=int(op.split('load')[1].split('_')[0] or typ[1:])//8
    wat=f'''(module (memory 0 2)
      (func (export "run") (param i32 i32) (result {typ} i32)
        local.get 0 memory.grow drop local.get 1 {op} memory.size))'''
    cases=[(grow,address) for grow in (0,1,2,3,0xffffffff)
           for address in (0,16-size,17-size,65536-size,65537-size,131072-size,131073-size,0xffffffff)]
    check(tmp_path,wat,cases,ranges=lambda a:[(a[1],size)])


@pytest.mark.parametrize('op',[
    'i32.store','i64.store','i32.store8','i32.store16','i64.store8','i64.store16','i64.store32',
])
def test_store_bounds_and_values_follow_runtime_growth(tmp_path,op):
    typ=op[:3];size=int(op.split('store')[1] or typ[1:])//8
    wat=f'''(module (memory 0 2)
      (func (export "run") (param i32 i32 {typ}) (result i64 i64 i32)
        local.get 0 memory.grow drop local.get 1 local.get 2 {op}
        i32.const 0 i64.load i32.const 8 i64.load memory.size))'''
    cases=[(grow,address,value) for grow in (0,1,2,3)
           for address,value in [(0,-1),(16-size,0x807f0605),(17-size,1),(65536-size,1),(65537-size,1),(0xffffffff,1)]]
    check(tmp_path,wat,cases,ranges=lambda a:[(a[1],size)])


@pytest.mark.parametrize('offset',[1,65535,65536,0xfffffff8,0xffffffff])
def test_load_store_offset_addition_never_wraps_after_growth(tmp_path,offset):
    wat=f'''(module (memory 0 2)
      (func (export "run") (param i32 i32) (result i32)
        local.get 0 memory.grow drop
        local.get 1 i32.const 42 i32.store offset={offset}
        local.get 1 i32.load offset={offset}))'''
    cases=[(g,a) for g in (0,1,2) for a in (0,1,0x7fffffff,0xffffffff)]
    check(tmp_path,wat,cases,ranges=lambda a:[(a[1]+offset,4)])


@pytest.mark.parametrize('op',['memory.copy','memory.fill','memory.init $data'])
def test_bulk_ranges_use_current_size_and_keep_trap_precedence(tmp_path,op):
    wat=f'''(module (memory 0 2) (data $data "ABCDEFGHIJKLMNOP")
      (func (export "run") (param i32 i32 i32 i32) (result i32 i32)
        local.get 0 memory.grow
        local.get 1 local.get 2 local.get 3 {op} memory.size))'''
    ranges=[(0,0,0),(65536,0,0),(131072,0,0),(65536,65536,0),
            (16,0,1),(0,16,1),(65536,0,1),(65535,0,2),(131072,0,1),
            (0,65536,1),(0,0,16),(0xffffffff,0,1)]
    cases=[(grow,)+args for grow in (0,1,2,3) for args in ranges]
    def backed(args):
        _,destination,source,size=args
        return [(destination,size)]+([(source,size)] if op=='memory.copy' else [])
    check(tmp_path,wat,cases,ranges=backed)


def test_growth_preserves_existing_memory_and_passive_segment_state(tmp_path):
    wat='''(module (memory 1 3) (data (i32.const 0) "ABCDEFGH") (data $p "abcdefgh")
      (func (export "run") (param i32 i64 i32) (result i32 i32 i64 i64)
        i32.const 8 local.get 1 i64.store
        i32.const 0 i32.const 0 i32.const 8 memory.init $p data.drop $p
        local.get 0 memory.grow memory.size
        local.get 2 if i32.const 0 i32.const 0 i32.const 1 memory.init $p end
        i32.const 0 i64.load i32.const 8 i64.load))'''
    check(tmp_path,wat,[(g,v,p) for g in (0,1,2,3,0xffffffff) for v in (0,-1,0x807f060504030201) for p in (0,1)])


def test_conditional_and_internal_call_growth_propagates_to_caller(tmp_path):
    wat='''(module (memory 0 3)
      (func $grow (param i32 i32) (result i32)
        local.get 0 if (result i32) local.get 1 memory.grow return
        else memory.size end)
      (func (export "run") (param i32 i32 i32) (result i32 i32 i32 i32)
        local.get 0 local.get 1 call $grow memory.size
        local.get 2 memory.grow memory.size))'''
    check(tmp_path,wat,[(flag,a,b) for flag in (0,1,0x80000000) for a,b in [(0,1),(1,1),(3,1),(4,2),(0xffffffff,1)]])


def test_growth_merges_on_loop_backedges_and_exits(tmp_path):
    wat='''(module (memory 0 3)
      (func (export "run") (param i32 i32) (result i32 i32) (local $n i32) (local $last i32)
        local.get 0 local.set $n
        block $done loop $again
          local.get $n i32.eqz br_if $done
          local.get 1 memory.grow local.set $last
          local.get $n i32.const 1 i32.sub local.set $n br $again
        end end local.get $last memory.size))'''
    check(tmp_path,wat,[(n,delta) for n in (0,1,2,3,7) for delta in (0,1,2,0xffffffff)])
    with NativeFont(tmp_path/'program.ttf') as native:
        with pytest.raises(ExecutionBoundExceeded,match='loop'):native.invoke(8,1)
        assert native.invoke(1,1)==(0,1)


def test_growth_state_is_fresh_per_shape_but_persists_in_reference_instance(tmp_path):
    wat='''(module (memory 0 2) (func (export "run") (param i32) (result i32 i32)
      local.get 0 memory.grow memory.size))'''
    path=tmp_path/'fresh.wat';path.write_text(wat);module,_=load(path)
    state=module.instantiate()
    assert module.invoke('run',[1],state=state)==[0,1]
    assert module.invoke('run',[1],state=state)==[1,2]
    assert module.invoke('run',[1],state=state)==[0xffffffff,2]
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as native:
        assert native.invoke(1)==(0,1)
        assert native.invoke(3)==(0xffffffff,0)
        assert native.invoke(1)==(0,1)


def test_unbounded_binary_uses_the_existing_embedder_growth_cap(tmp_path):
    wat='''(module (memory 0 16) (func (export "run") (param i32) (result i32 i32)
      local.get 0 memory.grow memory.size))'''
    data=binary(parse_text(wat))
    data=encode_sections([(sid,b'\x01\x00\x00' if sid==5 else payload) for sid,payload in sections(data)])
    path=tmp_path/'unbounded.wasm';path.write_bytes(data)
    module=load_binary(path);assert module.maximum_pages==16
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as native:
        for delta in (0,1,16,17,0xffffffff):
            actual=native.invoke(delta)
            assert actual==tuple(module.invoke('run',[delta]))
            assert actual==((0,delta) if delta<=16 else (0xffffffff,0))


@pytest.mark.parametrize('opcode',[0x3f,0x40])
def test_binary_padded_zero_memory_indices(tmp_path,opcode):
    wat='(module (memory 0 2) (func (export "run") (result i32) i32.const 1 memory.grow drop memory.size))'
    data=binary(parse_text(wat))
    data=encode_sections([(sid,payload.replace(bytes([opcode,0]),bytes([opcode,0x80,0])) if sid==10 else payload)
                          for sid,payload in sections(data)])
    # Adjust the function-body size after expanding its memory index.
    items=sections(data)
    items=[(sid,payload[:1]+bytes([payload[1]+1])+payload[2:] if sid==10 else payload) for sid,payload in items]
    path=tmp_path/'padded.wasm';path.write_bytes(encode_sections(items))
    assert load_binary(path).invoke('run',[])==[1]
    assert any(op=='memory.grow' for op,_ in parse_binary(path)[0].code)
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as native:assert native.invoke()==1


@pytest.mark.parametrize('body',['memory.grow','i64.const 1 memory.grow','i32.const 1 memory.grow'])
def test_growth_requires_valid_i32_operand_and_a_memory(tmp_path,body):
    memory='' if body=='i32.const 1 memory.grow' else '(memory 0 2)'
    path=tmp_path/'bad.wat';path.write_text(f'(module {memory} (func (result i32) {body}))')
    with pytest.raises(ValueError,match='V8 rejected'):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


def test_conditional_growth_controls_later_access(tmp_path):
    wat='''(module (memory 0 1) (func (export "run") (param i32 i32) (result i32)
      local.get 0 if local.get 1 memory.grow drop end i32.const 0 i32.load))'''
    check(tmp_path,wat,[(flag,delta) for flag in (0,1,0x80000000) for delta in (0,1,2,0xffffffff)])


def test_future_growth_does_not_make_an_earlier_access_valid(tmp_path):
    wat='''(module (memory 0 1) (func (export "run") (result i32)
      i32.const 0 i32.load drop i32.const 1 memory.grow))'''
    check(tmp_path,wat,[()])
