"""Passive data, segment lifetime, binary data counts, and native initialization."""
import pytest

from wasmfont.compiler import compile_source, Limits
from wasmfont.frontend import load, parse_text, binary, unsigned_leb
from wasmfont.ir import parse_binary, uleb
from wasmfont.module import load_binary
from wasmfont.oracle import execute_binary
from wasmfont.runtime import NativeFont, ExecutionBoundExceeded, WasmTrap
from wasmfont.state import MemoryTrap
from .test_bulk_memory import check


def quoted(payload):
    return '"'+''.join(f'\\{b:02x}' for b in payload)+'"'


def program(payload, *, folded=False, drop=False, active=False):
    instruction=('(memory.init $bytes (local.get 0) (local.get 1) (local.get 2))' if folded else
                 'local.get 0 local.get 1 local.get 2 memory.init $bytes')
    before='local.get 3 if data.drop $bytes end' if drop else ''
    return f'''(module (memory 1)
      (data $bytes {'(i32.const 0)' if active else ''} {quoted(payload)})
      (func (export "run") (param i32 i32 i32 {'i32' if drop else ''}) (result i64 i64)
        {before} {instruction} data.drop $bytes data.drop $bytes
        i32.const 0 i64.load i32.const 8 i64.load))'''


@pytest.mark.parametrize('folded',[False,True])
@pytest.mark.parametrize('binary_input',[False,True])
def test_passive_dynamic_ranges_and_text_forms(tmp_path,folded,binary_input):
    payload=b'\x00\x01\x80\xffABC'
    cases=[(destination,source,size) for size in range(len(payload)+1)
           for destination in range(17-size) for source in range(len(payload)-size+1)]
    check(tmp_path,program(payload,folded=folded),cases,binary_input=binary_input)
    module,data=load(tmp_path/'program.wat')
    assert module.segments==[(None,payload)]
    assert binary(module)==data


@pytest.mark.parametrize('size',[0,1,3,17,257])
def test_data_sources_are_independent_of_the_backed_memory_window(tmp_path,size):
    payload=bytes((i*197+51)&255 for i in range(size))
    cases=[(0,0,0),(16,0,0),(65536,size,0),(0,size,0),(0,size+1,0),
           (0,0xffffffff,1),(0,1,0xffffffff),(0,0,0xffffffff),
           (16,0,1),(65536,0,1),(65537,0,0),(0xffffffff,0,1)]
    if size:
        cases += [(0,size-1,1),(15,size-1,1),(0,0,min(size,16)),
                  (0,max(0,size-16),min(size,16)),(1,size-1,1)]
    check(tmp_path,program(payload),cases,ranges=lambda a:[(a[0],a[2])])


@pytest.mark.parametrize('active',[False,True])
def test_dropped_segments_are_empty_and_drop_is_idempotent(tmp_path,active):
    args=[(0,0,0),(0,0,1),(0,1,0),(65536,0,0),(65537,0,0),
          (16,0,1),(0,8,0),(0,0,8),(0,0xffffffff,0)]
    cases=[a+(drop,) for drop in (0,1) for a in args]
    check(tmp_path,program(b'ABCDEFGH',drop=True,active=active),cases,ranges=lambda a:[(a[0],a[2])])


def test_conditional_drop_survives_call_and_return_merges(tmp_path):
    wat='''(module (memory 1) (data $a "ABCDEFGH") (data $b "abcdefgh")
      (func $drop (param i32)
        local.get 0 if data.drop $a return end
        data.drop $b)
      (func (export "run") (param i32 i32 i32) (result i64)
        local.get 0 call $drop
        local.get 1 if
          i32.const 0 i32.const 0 local.get 2 memory.init $a
        else
          i32.const 0 i32.const 0 local.get 2 memory.init $b
        end
        i32.const 0 i64.load))'''
    check(tmp_path,wat,[(drop,which,size) for drop in (0,1) for which in (0,1) for size in (0,1,8)])


def test_segment_lifetime_crosses_loop_backedges(tmp_path):
    wat='''(module (memory 1) (data $a "A")
      (func (export "run") (param i32) (result i32) (local $n i32)
        local.get 0 local.set $n
        block $done loop $again
          local.get $n i32.eqz br_if $done
          i32.const 0 i32.const 0 i32.const 1 memory.init $a data.drop $a
          local.get $n i32.const 1 i32.sub local.set $n br $again
        end end
        i32.const 0 i32.load8_u))'''
    check(tmp_path,wat,[(0,),(1,),(2,),(7,),(-1,),(1,),(0,)])


def test_segment_lifetime_merges_at_loop_exit(tmp_path):
    wat='''(module (memory 1) (data $p "A")
      (func (export "run") (param i32) (result i32) (local $n i32)
        local.get 0 local.set $n
        block $done loop $again
          local.get $n i32.eqz br_if $done
          data.drop $p local.get $n i32.const 1 i32.sub local.set $n br $again
        end end
        i32.const 0 i32.const 0 i32.const 1 memory.init $p
        i32.const 0 i32.load8_u))'''
    check(tmp_path,wat,[(0,),(1,),(3,),(7,),(0,)])
    with NativeFont(tmp_path/'program.ttf') as native:
        with pytest.raises(ExecutionBoundExceeded,match='loop'):native.invoke(8)


def test_repeated_initialization_composes_with_copy_fill_and_typed_loop(tmp_path):
    wat='''(module (memory 1) (data $p "ABCDEFGH")
      (func (export "run") (param i32 i32) (result i64 i64) (local $n i32)
        i32.const 0 local.get 1 i32.const 16 memory.fill
        local.get 0
        loop $again (param i32)
          local.tee $n
          if
            i32.const 0 i32.const 0 i32.const 8 memory.init $p
            i32.const 4 i32.const 0 i32.const 8 memory.copy
            local.get $n i32.const 1 i32.sub br $again
          end
        end
        data.drop $p i32.const 0 i64.load i32.const 8 i64.load))'''
    check(tmp_path,wat,[(0,0),(1,0),(3,255),(7,128)])
    with NativeFont(tmp_path/'program.ttf') as native:
        with pytest.raises(ExecutionBoundExceeded,match='loop'):native.invoke(8,0)
        assert native.invoke(0,0)==(0,0)


@pytest.mark.parametrize('window',[0,1,3,17,64,256])
def test_initialization_with_configurable_windows(tmp_path,window):
    payload=bytes(range(256))+b'!'
    wat=f'''(module (memory 1) (data $p {quoted(payload)})
      (func (export "run") (param i32 i32 i32) (result i32)
        local.get 0 local.get 1 local.get 2 memory.init $p
        {'i32.const '+str(max(0,window-1))+' i32.load8_u' if window else 'i32.const 42'}))'''
    cases=[(0,0,0),(65536,257,0),(0,0,window),(window,0,1)]
    if window:cases += [(window-1,256,1),(0,256,1)]
    check(tmp_path,wat,cases,window=window,ranges=lambda a:[(a[0],a[2])])


@pytest.mark.parametrize('payload',['', 'ABC'])
def test_passive_data_and_drop_without_memory(tmp_path,payload):
    wat=f'''(module (data $p "{payload}")
      (func (export "run") (result i32) data.drop $p data.drop $p i32.const 42))'''
    check(tmp_path,wat,[()])
    module,data=load(tmp_path/'program.wat')
    assert not module.has_memory and module.initial_pages==0
    assert module.segments==[(None,payload.encode())]
    assert binary(module)==data


def test_fresh_instances_restore_segments_but_reused_reference_state_keeps_drops(tmp_path):
    wat=program(b'ABCDEFGH',drop=True)
    path=tmp_path/'program.wat';path.write_text(wat)
    module,_=load(path);state=module.instantiate()
    assert module.invoke('run',[0,0,8,0],state=state)==[0x4847464544434241,0]
    with pytest.raises(MemoryTrap):module.invoke('run',[0,0,1,0],state=state)
    assert module.invoke('run',[0,0,8,0])==[0x4847464544434241,0]
    assert module.instantiate().data_segments==[b'ABCDEFGH']
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as native:
        with pytest.raises(WasmTrap):native.invoke(0,0,1,1)
        assert native.invoke(0,0,8,0)==(0x4847464544434241,0)


def test_source_and_destination_traps_precede_window_bounds_and_do_not_write(tmp_path):
    path=tmp_path/'program.wat';path.write_text(program(b'ABC'))
    module,_=load(path);state=module.instantiate();state.memory[:16]=bytes(range(16))
    before=bytes(state.memory)
    with pytest.raises(MemoryTrap):module.invoke('run',[16,2,2],state=state)
    assert state.memory==before and state.data_segments==[b'ABC']
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as native:
        with pytest.raises(WasmTrap,match='memory_out_of_bounds'):native.invoke(16,2,2)
        with pytest.raises(ExecutionBoundExceeded,match='memory'):native.invoke(16,0,1)


def sections(data):
    out=[];p=8
    while p<len(data):
        sid=data[p];size,p=uleb(data,p+1);out.append((sid,data[p:p+size]));p+=size
    return out


def encode_sections(items):
    return b'\0asm\x01\0\0\0'+b''.join(bytes([sid])+unsigned_leb(len(payload))+payload for sid,payload in items)


def independent_binary(index=0,*,active=False,padded=False):
    # Independently encode a (i32, i32, i32) -> i64 function and data-count section.
    types=b'\x01\x60\x03\x7f\x7f\x7f\x01\x7e'
    idx=unsigned_leb(index)
    body=(b'\x00\x20\x00\x20\x01\x20\x02\xfc'+(b'\x88\x00' if padded else b'\x08')+
          idx+(b'\x80\x00' if padded else b'\x00')+b'\xfc\x09'+idx+b'\x41\x00\x29\x03\x00\x0b')
    segment=(b'\x02\x00\x41\x00\x0b' if active else b'\x01')+b'\x08ABCDEFGH'
    return encode_sections([(1,types),(3,b'\x01\x00'),(5,b'\x01\x00\x01'),
                            (7,b'\x01\x03run\x00\x00'),(12,unsigned_leb(index+1)),
                            (10,b'\x01'+unsigned_leb(len(body))+body),
                            (11,unsigned_leb(index+1)+b'\x01\x00'*index+segment)])


@pytest.mark.parametrize('index',[0,1,127,128])
@pytest.mark.parametrize('padded',[False,True])
def test_independent_binary_encoding_and_data_index_leb(tmp_path,index,padded):
    data=independent_binary(index,padded=padded)
    path=tmp_path/'independent.wasm';path.write_bytes(data)
    module=load_binary(path)
    assert parse_binary(path)[0].code[3:5]==[('memory.init',index),('data.drop',index)]
    assert [sid for sid,_ in sections(data)]==[1,3,5,7,12,10,11]
    assert module.segments[index]==(None,b'ABCDEFGH')
    assert execute_binary(data,'run',['i32']*3,[(0,0,8)])==[{'values':['5208208757389214273']}]
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as native:
        assert native.invoke(0,0,8)==0x4847464544434241


def test_explicit_memory_zero_active_binary_segment_is_already_dropped(tmp_path):
    path=tmp_path/'active.wasm';path.write_bytes(independent_binary(active=True))
    module=load_binary(path)
    assert module.segments==[(0,b'ABCDEFGH')]
    assert module.invoke('run',[0,0,0])==[0x4847464544434241]
    with pytest.raises(MemoryTrap):module.invoke('run',[0,0,1])
    compile_source(path,path.with_suffix('.ttf'),export='run')
    with NativeFont(path.with_suffix('.ttf')) as native:
        assert native.invoke(0,0,0)==0x4847464544434241
        with pytest.raises(WasmTrap):native.invoke(0,0,1)


@pytest.mark.parametrize('case',['missing','mismatch','trailing','duplicate','after-code','before-memory'])
def test_bad_data_counts_rejected_before_writing_font(tmp_path,case):
    items=sections(independent_binary())
    if case=='missing':items=[(sid,p) for sid,p in items if sid!=12]
    elif case in ('mismatch','trailing'):
        items=[(sid,(b'\x02' if case=='mismatch' else b'\x01\x00') if sid==12 else p) for sid,p in items]
    elif case=='duplicate':items.insert(5,(12,b'\x01'))
    else:
        entry=items.pop(4);items.insert(5 if case=='after-code' else 2,entry)
    path=tmp_path/'invalid.wasm';path.write_bytes(encode_sections(items))
    with pytest.raises(ValueError,match='V8 rejected'):compile_source(path,path.with_suffix('.ttf'),export='run')
    assert not path.with_suffix('.ttf').exists() and not path.with_suffix('.json').exists()


@pytest.mark.parametrize('op',['memory.init','data.drop'])
@pytest.mark.parametrize('index',['-1','4294967296','"0"','$missing','1','0xffffffff'])
def test_invalid_data_indices_rejected(tmp_path,op,index):
    body=f'i32.const 0 i32.const 0 i32.const 0 {op} {index}' if op=='memory.init' else f'{op} {index}'
    path=tmp_path/'bad.wat';path.write_text(f'(module (memory 1) (data "A") (func {body}))')
    with pytest.raises(ValueError):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


@pytest.mark.parametrize('body',[
    'memory.init 0','data.drop','memory.init',
    'i64.const 0 i32.const 0 i32.const 0 memory.init 0',
    'i32.const 0 i64.const 0 i32.const 0 memory.init 0',
    'i32.const 0 i32.const 0 i64.const 0 memory.init 0',
])
def test_malformed_or_ill_typed_data_instructions_rejected(tmp_path,body):
    path=tmp_path/'bad.wat';path.write_text(f'(module (memory 1) (data "A") (func {body}))')
    with pytest.raises(ValueError):compile_source(path,path.with_suffix('.ttf'))
    assert not path.with_suffix('.ttf').exists()


def test_init_requires_memory_even_for_zero_bytes(tmp_path):
    path=tmp_path/'bad.wat'
    path.write_text('(module (data "") (func i32.const 0 i32.const 0 i32.const 0 memory.init 0))')
    with pytest.raises(ValueError,match='V8 rejected'):load(path)


@pytest.mark.parametrize('active',[False,True])
def test_large_segments_with_constant_addresses_keep_small_circuits(tmp_path,active):
    payload=bytes(range(256))*32
    wat=f'''(module (memory 1) (data $p {'(i32.const 0)' if active else ''} {quoted(payload)})
      (func (export "run") (param i32) (result i64)
        i32.const 0 i32.const 4096 local.get 0 memory.init $p
        i32.const 0 i64.load))'''
    if active:
        wat=wat.replace('i32.const 4096 local.get 0','i32.const 0 local.get 0')
    path=tmp_path/'large.wat';path.write_text(wat)
    compile_source(path,path.with_suffix('.ttf'),export='run',limits=Limits(max_gates=500))
    with NativeFont(path.with_suffix('.ttf')) as native:
        if active:
            assert native.invoke(0)==0x0706050403020100
            with pytest.raises(WasmTrap):native.invoke(1)
        else:
            assert native.invoke(8)==0x0706050403020100
            assert native.invoke(0)==0


def test_zero_byte_window_checks_ranges_without_materializing_data(tmp_path):
    payload=bytes((i*i+17*i+53)&255 for i in range(8192))
    path=tmp_path/'zero-window.wat'
    path.write_text(f'''(module (memory 1) (data $p {quoted(payload)})
      (func (export "run") (param i32 i32 i32) (result i32)
        local.get 0 local.get 1 local.get 2 memory.init $p i32.const 42))''')
    compile_source(path,path.with_suffix('.ttf'),export='run',limits=Limits(memory_bytes=0,max_gates=500))
    with NativeFont(path.with_suffix('.ttf')) as native:
        for args in [(0,0,0),(0,100,0),(65536,8192,0)]:assert native.invoke(*args)==42
        with pytest.raises(ExecutionBoundExceeded,match='memory'):native.invoke(1,0,1)
        with pytest.raises(WasmTrap,match='memory_out_of_bounds'):native.invoke(1,8192,1)


@pytest.mark.parametrize('field',['(data $p "A") (data $p "B")','(data 0 "A")',
                                  '(data (i64.const 0) "A")','(data "A" (i32.const 0))'])
def test_invalid_data_declarations_fail_closed(field):
    with pytest.raises((ValueError,NotImplementedError)):parse_text(f'(module (memory 1) {field})')
