"""Bulk memory agrees with V8, the reference VM, and actual GSUB execution."""
import random

import pytest

from wasmfont.compiler import compile_source, Limits
from wasmfont.frontend import load, binary, unsigned_leb
from wasmfont.ir import parse_binary
from wasmfont.module import load_binary
from wasmfont.oracle import execute_binary
from wasmfont.runtime import NativeFont, WasmTrap, ExecutionBoundExceeded, IncompleteShaping
from wasmfont.state import MemoryTrap, MachineState
from wasmfont.reference.interpreter import run
from wasmfont.ir import Function


def check(tmp_path, wat, cases, *, window=16, binary_input=False, ranges=None):
    source=tmp_path/'program.wat';source.write_text(wat)
    module,data=load(source)
    fn=module.functions[module.exports['run'][1]]
    expected=execute_binary(data,'run',fn.params,cases)
    if binary_input:
        source=source.with_suffix('.wasm');source.write_bytes(data)
    font=tmp_path/'program.ttf'
    manifest=compile_source(source,font,export='run',limits=Limits(memory_bytes=window))
    with NativeFont(font) as native:
        for args,result in zip(cases,expected):
            if 'trap' in result:
                with pytest.raises(MemoryTrap):module.invoke('run',args)
                with pytest.raises(WasmTrap,match='memory_out_of_bounds'):native.invoke(*args)
            else:
                values=tuple(int(v)&((1<<int(t[1:]))-1) for v,t in zip(result['values'],fn.results))
                assert tuple(module.invoke('run',args))==values
                if ranges is not None and any(size and address+size>window for address,size in ranges(args)):
                    with pytest.raises(ExecutionBoundExceeded,match='memory'):native.invoke(*args)
                else:
                    actual=native.invoke(*args)
                    assert ((actual,) if len(values)==1 else actual)==values, args
        with pytest.raises(IncompleteShaping):
            native.decode(native.shaper.shape(native.encode(cases[0]),enabled=False))
    return manifest,data


def dynamic_program(op,folded=False):
    instruction=(f'({op} (local.get 0) (local.get 1) (local.get 2))' if folded else
                 f'local.get 0 local.get 1 local.get 2 {op}')
    return f'''(module (memory 1)
      (func (export "run") (param i32 i32 i32 i64 i64) (result i64 i64)
        i32.const 0 local.get 3 i64.store
        i32.const 8 local.get 4 i64.store
        {instruction}
        i32.const 0 i64.load i32.const 8 i64.load))'''


PATTERN=(0x807f060504030201,0xfedcba9876543210)


@pytest.mark.parametrize('op',['memory.copy','memory.fill'])
def test_dynamic_bulk_memory_all_small_ranges(tmp_path,op):
    rng=random.Random(179)
    cases=[]
    for size in range(17):
        for destination in range(17-size):
            sources=range(17-size) if op=='memory.copy' else (0,255,0x12345678,-1)
            for source in sources:
                cases.append((destination,source,size,rng.getrandbits(64),rng.getrandbits(64)))
    manifest,_=check(tmp_path,dynamic_program(op),cases)
    # Copy alignment uses a barrel network, keeping the default window compact.
    assert manifest['metrics']['gates']<2300


@pytest.mark.parametrize('binary_input',[False,True])
@pytest.mark.parametrize('folded',[False,True])
@pytest.mark.parametrize('op',['memory.copy','memory.fill'])
def test_bulk_text_forms_and_binary_input(tmp_path,op,folded,binary_input):
    cases=[(d,s,n)+PATTERN for d,s,n in [(0,1,8),(1,0,8),(0,0,16),(16,16,0),(0,0,0)]]
    check(tmp_path,dynamic_program(op,folded),cases,binary_input=binary_input)


@pytest.mark.parametrize('op',['memory.copy','memory.fill'])
def test_bounds_overflow_zero_length_and_recovery(tmp_path,op):
    addresses=[(0,0,0),(16,16,0),(65536,65536,0),(65537,0,0),
               (0,65537,0),(16,0,1),(0,16,1),(15,0,2),(0,15,2),
               (65535,0,2),(0,65535,2),(0xffffffff,0,1),(0,0xffffffff,1),
               (1,0,0xffffffff),(0,1,0xffffffff),(65536,0,0),
               (0,65536,0),(0,0xffffffff,0),(0,0,16),(16,65535,2),(65535,16,2),(0,0,1)]
    cases=[args+PATTERN for args in addresses]
    def ranges(args):
        d,s,n=tuple(v&0xffffffff for v in args[:3])
        return [(d,n)]+([(s,n)] if op=='memory.copy' else [])
    check(tmp_path,dynamic_program(op),cases,ranges=ranges)


@pytest.mark.parametrize('op',['memory.copy','memory.fill'])
@pytest.mark.parametrize('window',[0,1,3,17,64,256])
def test_configured_windows_and_non_power_of_two_copy_alignment(tmp_path,op,window):
    rng=random.Random(window)
    payload=bytes(rng.getrandbits(8) for _ in range(window))
    data=''.join(f'\\{b:02x}' for b in payload)
    readout=[];types=[]
    for i in range(0,window,8):
        if i+8<=window:readout.append(f'i32.const {i} i64.load');types.append('i64')
        else:
            for j in range(i,window):readout.append(f'i32.const {j} i32.load8_u');types.append('i32')
    # No loads are needed to observe a zero-byte window; retain a result cell.
    if not types:types=['i32'];readout=['i32.const 42']
    wat=f'''(module (memory 1) (data (i32.const 0) "{data}")
      (func (export "run") (param i32 i32 i32) (result {' '.join(types)})
        local.get 0 local.get 1 local.get 2 {op} {' '.join(readout)}))'''
    cases=[(0,0,0),(65536,65536,0),(window,0,1),(0,0,window)]
    if window:
        cases += [(window-1,0,1),(0,window-1,1),(1,0,window-1),(0,1,window-1)]
        if window<256:
            cases += [(d,s,rng.randrange(window-max(d,s)+1))
                      for d,s in ((rng.randrange(window),rng.randrange(window)) for _ in range(20))]
    def ranges(args):
        d,s,n=args
        return [(d,n)]+([(s,n)] if op=='memory.copy' else [])
    check(tmp_path,wat,cases,window=window,ranges=ranges)


@pytest.mark.parametrize('op',['memory.copy','memory.fill'])
def test_zero_page_memory_checks_endpoints_even_for_zero_length(tmp_path,op):
    wat=f'''(module (memory 0) (func (export "run") (param i32 i32 i32) (result i32)
      local.get 0 local.get 1 local.get 2 {op} i32.const 42))'''
    check(tmp_path,wat,[(0,0,0),(1,0,0),(0,1,0),(0,0,1),(0,0,-1)],window=0)


def test_bulk_memory_composes_with_calls_loops_and_conditional_traps(tmp_path):
    wat='''(module (memory 1) (global $count (mut i32) (i32.const 0))
      (func $copy (param i32 i32 i32)
        local.get 0 local.get 1 local.get 2 memory.copy
        global.get $count i32.const 1 i32.add global.set $count)
      (func (export "run") (param $n i32) (param $byte i32) (param $bad i32)
        (result i64 i64 i32) (local $left i32)
        i32.const 0 local.get $byte i32.const 4 memory.fill
        local.get $n local.set $left
        block $done loop $again
          local.get $left i32.eqz br_if $done
          i32.const 1 i32.const 0 i32.const 15 call $copy
          local.get $left i32.const 1 i32.sub local.set $left br $again
        end end
        local.get $bad if
          i32.const 0 i32.const 65535 i32.const 2 memory.copy
        end
        i32.const 0 i64.load i32.const 8 i64.load global.get $count))'''
    cases=[(0,0x1234,0),(1,255,0),(3,128,0),(7,-1,0),(0,1,1),(7,0,1),(1,7,0)]
    check(tmp_path,wat,cases)
    with NativeFont(tmp_path/'program.ttf') as native:
        with pytest.raises(ExecutionBoundExceeded,match='loop'):native.invoke(8,42,0)
        assert native.invoke(0,0,0)==(0,0,0)


@pytest.mark.parametrize('op',['memory.copy','memory.fill'])
@pytest.mark.parametrize('size',[0,1,16])
def test_constant_lengths_keep_dynamic_address_and_value_semantics(tmp_path,op,size):
    wat=dynamic_program(op).replace('local.get 0 local.get 1 local.get 2 '+op,
                                   f'local.get 0 local.get 1 i32.const {size} {op}')
    args=[(0,0,0)+PATTERN,(0,1,0)+PATTERN,(65536,65536,0)+PATTERN]
    def ranges(args):return [(args[0],size)]+([(args[1],size)] if op=='memory.copy' else [])
    check(tmp_path,wat,args,ranges=ranges)


@pytest.mark.parametrize('body',[
    'memory.copy','memory.fill',
    'i32.const 0 i32.const 0 i64.const 1 memory.copy',
    'i64.const 0 i32.const 0 i32.const 1 memory.fill',
    'i32.const 0 i64.const 0 i32.const 1 memory.copy',
])
def test_ill_typed_bulk_memory_is_rejected_before_writing_font(tmp_path,body):
    source=tmp_path/'bad.wat';source.write_text(f'(module (memory 1) (func {body}))')
    output=tmp_path/'bad.ttf'
    with pytest.raises(ValueError,match='V8 rejected'):compile_source(source,output)
    assert not output.exists() and not output.with_suffix('.json').exists()


@pytest.mark.parametrize('op',['memory.copy','memory.fill'])
def test_bulk_memory_requires_a_memory(tmp_path,op):
    source=tmp_path/'bad.wat'
    source.write_text(f'(module (func i32.const 0 i32.const 0 i32.const 0 {op}))')
    with pytest.raises(ValueError,match='V8 rejected'):load(source)


def instruction_binary(instruction,*,memories=1):
    def section(i,payload):return bytes([i])+unsigned_leb(len(payload))+payload
    body=b'\x00\x41\x00\x41\x00\x41\x00'+instruction+b'\x0b'
    return (b'\0asm\x01\0\0\0'+section(1,b'\x01\x60\x00\x00')+
            section(3,b'\x01\x00')+section(5,unsigned_leb(memories)+b'\x00\x01'*memories)+
            section(10,b'\x01'+unsigned_leb(len(body))+body))


@pytest.mark.parametrize('instruction,op',[
    (b'\xfc\x0a\x00\x00','memory.copy'),(b'\xfc\x0b\x00','memory.fill'),
    (b'\xfc\x8a\x00\x80\x00\x80\x00','memory.copy'),
    (b'\xfc\x8b\x00\x80\x00','memory.fill'),
])
def test_independent_binary_bulk_encodings_and_padded_lebs(tmp_path,instruction,op):
    source=tmp_path/'program.wasm';source.write_bytes(instruction_binary(instruction))
    module=load_binary(source)
    assert module.functions[0].code[-1]==(op,None)
    assert parse_binary(source)[0].code[-1]==(op,None)
    assert module.functions[0].code==load_binary_bytes(tmp_path,binary(module)).functions[0].code


def load_binary_bytes(tmp_path,data):
    path=tmp_path/'roundtrip.wasm';path.write_bytes(data)
    return load_binary(path)


@pytest.mark.parametrize('instruction',[b'\xfc\x0a\x01\x00',b'\xfc\x0a\x00\x01',b'\xfc\x0b\x01'])
def test_multiple_memory_indices_fail_closed(tmp_path,instruction):
    path=tmp_path/'multiple.wasm';path.write_bytes(instruction_binary(instruction,memories=2))
    with pytest.raises(NotImplementedError,match='multiple memories'):load_binary(path)
    with pytest.raises(NotImplementedError,match='multiple memories'):parse_binary(path)


def test_other_prefixed_instructions_still_fail_closed(tmp_path):
    # Saturating float conversion subopcodes remain outside the integer subset.
    data=instruction_binary(b'\xfc\x00')
    path=tmp_path/'unsupported.wasm';path.write_bytes(data)
    with pytest.raises(NotImplementedError,match='unsupported Wasm opcode'):parse_binary(path)


@pytest.mark.parametrize('op,destination,source',[
    ('memory.copy',65535,0),('memory.copy',0,65535),('memory.fill',65535,42),
])
def test_reference_bounds_traps_do_not_partially_write(op,destination,source):
    state=MachineState();state.memory[:16]=bytes(range(16))
    before=bytes(state.memory)
    fn=Function([],[],[],[('i32.const',destination),('i32.const',source),
                         ('i32.const',2),(op,None)])
    with pytest.raises(MemoryTrap):run([fn],0,[],state=state)
    assert state.memory==before


@pytest.mark.parametrize('instruction',[
    b'\xfc',b'\xfc\x0a',b'\xfc\x0a\x00',b'\xfc\x0b',b'\xfc\x0b\x01',
])
def test_malformed_bulk_binary_is_validated_before_compiling(tmp_path,instruction):
    source=tmp_path/'bad.wasm';source.write_bytes(instruction_binary(instruction))
    output=tmp_path/'bad.ttf'
    with pytest.raises(ValueError,match='V8 rejected'):compile_source(source,output)
    assert not output.exists() and not output.with_suffix('.json').exists()
