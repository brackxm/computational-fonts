"""Nonzero backed-memory windows preserve absolute Wasm addresses and traps."""
from pathlib import Path
import random
import subprocess
import sys

import pytest

from wasmfont.compiler import compile_source, Limits
from wasmfont.frontend import load
from wasmfont.oracle import execute_binary
from wasmfont.reference.interpreter import WasmTrap as ReferenceTrap
from wasmfont.runtime import NativeFont, WasmTrap, ExecutionBoundExceeded, IncompleteShaping
from wasmfont.state import MemoryTrap


ROOT=Path(__file__).resolve().parents[1]


def quoted(data):
    return '"'+''.join(f'\\{byte:02x}' for byte in data)+'"'


def check(tmp_path,wat,cases,*,base,window=16,ranges=lambda args:[],binary_input=False):
    source=tmp_path/'window.wat';source.write_text(wat)
    module,data=load(source)
    fn=module.functions[module.exports['run'][1]]
    expected=execute_binary(data,'run',fn.params,cases)
    if binary_input:source=source.with_suffix('.wasm');source.write_bytes(data)
    font=tmp_path/'window.ttf'
    manifest=compile_source(source,font,export='run',limits=Limits(memory_base=base,memory_bytes=window))
    with NativeFont(font) as native:
        for args,result in zip(cases,expected):
            if 'trap' in result:
                with pytest.raises((ReferenceTrap,MemoryTrap)):module.invoke('run',args)
                with pytest.raises(WasmTrap):native.invoke(*args)
            else:
                values=tuple(int(v)&((1<<int(t[1:]))-1) for v,t in zip(result['values'],fn.results))
                assert tuple(module.invoke('run',args))==values,args
                if any(size and not base<=address<=base+window-size for address,size in ranges(args)):
                    with pytest.raises(ExecutionBoundExceeded,match='memory'):native.invoke(*args)
                else:
                    actual=native.invoke(*args)
                    assert ((actual,) if len(values)==1 else actual)==values,args
        with pytest.raises(IncompleteShaping):
            native.decode(native.shaper.shape(native.encode(cases[0]),enabled=False))
    assert manifest['limits']['memory_base']==base
    return manifest


LOADS=['i32.load','i64.load','i32.load8_s','i32.load8_u','i32.load16_s','i32.load16_u',
       'i64.load8_s','i64.load8_u','i64.load16_s','i64.load16_u','i64.load32_s','i64.load32_u']


@pytest.mark.parametrize('base',[1,1024,65533,65536])
@pytest.mark.parametrize('op',LOADS)
def test_absolute_loads_with_unaligned_and_page_crossing_windows(tmp_path,base,op):
    size=int(op.split('load')[1].split('_')[0] or op[1:3])//8
    payload=bytes([0x80,0xff,0x01,0xfe,0x7f]*4)
    wat=f'''(module (memory 2) (data (i32.const {base-1}) {quoted(payload)})
      (func (export "run") (param i32) (result {op[:3]}) local.get 0 {op}))'''
    addresses=sorted({0,base-1,base,base+1,base+17-size,base+18-size,131072-size,131073-size,0xffffffff})
    check(tmp_path,wat,[(a,) for a in addresses],base=base,window=17,ranges=lambda a:[(a[0],size)])


@pytest.mark.parametrize('op',['i32.store','i64.store','i32.store8','i32.store16','i64.store8','i64.store16','i64.store32'])
@pytest.mark.parametrize('base',[1,65536])
def test_absolute_stores_and_caller_memory(tmp_path,base,op):
    size=int(op.split('store')[1] or op[1:3])//8
    wat=f'''(module (memory 2)
      (func $write (param i32 {op[:3]}) local.get 0 local.get 1 {op})
      (func (export "run") (param i32 {op[:3]}) (result i64 i64)
        local.get 0 local.get 1 call $write
        i32.const {base} i64.load i32.const {base+8} i64.load))'''
    cases=[(a,v) for a in [0,base-1,base,base+1,base+16-size,base+17-size,0xffffffff]
           for v in (0,-1,0x807f060504030201)]
    check(tmp_path,wat,cases,base=base,ranges=lambda a:[(a[0],size)])


@pytest.mark.parametrize('offset',[1023,1024,1025,0xffffffff])
def test_effective_offsets_are_absolute_and_never_wrap(tmp_path,offset):
    wat=f'''(module (memory 0 2)
      (func (export "run") (param i32 i32) (result i32)
        local.get 0 memory.grow drop
        local.get 1 i32.const 0x807f0605 i32.store offset={offset}
        local.get 1 i32.load offset={offset}))'''
    cases=[(grow,a) for grow in [0,1,2,3,0xffffffff] for a in [0,1,2,13,14,1024,0xffffffff]]
    check(tmp_path,wat,cases,base=1024,ranges=lambda a:[(a[1]+offset,4)])


def readout(base,window):
    types=[];code=[]
    for at in range(0,window,8):
        if at+8<=window:types.append('i64');code.append(f'i32.const {base+at} i64.load')
        else:
            for byte in range(at,window):types.append('i32');code.append(f'i32.const {base+byte} i32.load8_u')
    return (' '.join(types),' '.join(code)) if types else ('i32','i32.const 42')


@pytest.mark.parametrize('base',[1,1025,65533,65536])
@pytest.mark.parametrize('op',['memory.copy','memory.fill','memory.init $p'])
def test_bulk_ranges_alignment_and_overlap_at_nonzero_bases(tmp_path,base,op):
    window=17;payload=bytes((i*37+0x80)&255 for i in range(23))
    types,reads=readout(base,window)
    wat=f'''(module (memory 2) (data (i32.const {base}) {quoted(payload[:window])})
      (data $p {quoted(payload)})
      (func (export "run") (param i32 i32 i32) (result {types})
        local.get 0 local.get 1 local.get 2 {op} {reads}))'''
    def source(at):return at if op.startswith('memory.init') else base+at
    cases=[(base,source(0),17),(base+1,source(0),16),(base,source(1),16),
           (base+16,source(0),1),(base,source(16),1),(base-1,source(0),1),
           (base+17,source(0),1),(base,source(17),1),(131072,source(0),0),
           (0,source(0),0),(base,0xffffffff,0),(base,source(0),0xffffffff),
           (0xffffffff,source(0),1),(base,0xffffffff,1),(base,source(0),0)]
    rng=random.Random(base)
    for _ in range(20):
        d=rng.randrange(18);s=rng.randrange(18)
        cases.append((base+d,source(s),rng.randrange(18-max(d,s))))
    def ranges(a):
        return [(a[0],a[2])]+([(a[1],a[2])] if op=='memory.copy' else [])
    check(tmp_path,wat,cases,base=base,window=window,ranges=ranges,binary_input=True)


@pytest.mark.parametrize('window',[0,1,3])
@pytest.mark.parametrize('op',['memory.copy','memory.fill','memory.init $p'])
def test_small_windows_zero_length_ranges_and_dropped_segments(tmp_path,window,op):
    base=65535;types,reads=readout(base,window)
    wat=f'''(module (memory 2) (data $p "ABCD")
      (func (export "run") (param i32 i32 i32 i32) (result {types})
        local.get 3 if data.drop $p end
        local.get 0 local.get 1 local.get 2 {op} {reads}))'''
    src=base if op=='memory.copy' else 0
    cases=[(d,s,n,drop) for d,s,n in [(base,src,window),(base,src,0),(0,0,0),
           (131072,131072 if op=='memory.copy' else 0,0),(base-1,src,1),
           (base+window,src,1),(131073,0,0),(base,1,0)] for drop in [0,1]]
    def ranges(a):return [(a[0],a[2])]+([(a[1],a[2])] if op=='memory.copy' else [])
    check(tmp_path,wat,cases,base=base,window=window,ranges=ranges)


def test_active_segment_intersections_and_overlays(tmp_path):
    base=1024
    wat=f'''(module (memory 1)
      (data (i32.const {base-2}) "abcdefghijkl")
      (data (i32.const {base+5}) "XYZ") (data (i32.const {base+15}) "TAIL")
      (func (export "run") (result i64 i64) i32.const {base} i64.load i32.const {base+8} i64.load))'''
    check(tmp_path,wat,[()],base=base)


def test_growth_exposes_zeroed_window_across_page_boundary(tmp_path):
    base=65533
    wat=f'''(module (memory 1 2) (data (i32.const {base-1}) "ABCD")
      (func (export "run") (param i32 i32) (result i32 i32 i64)
        local.get 0 memory.grow memory.size local.get 1 i64.load))'''
    cases=[(g,a) for g in [0,1,2,0xffffffff] for a in [base-1,base,base+9,base+10,131065,0xffffffff]]
    check(tmp_path,wat,cases,base=base,window=17,ranges=lambda a:[(a[1],8)])


@pytest.mark.parametrize('op',['memory.copy','memory.fill','memory.init $p'])
def test_bulk_window_in_new_page_and_trap_precedence(tmp_path,op):
    base=65536;src=base if op=='memory.copy' else 0
    wat=f'''(module (memory 1 2) (data $p "ABCDEFGHIJKLMNOP")
      (func (export "run") (param i32 i32 i32 i32) (result i32)
        local.get 0 memory.grow drop
        local.get 1 local.get 2 local.get 3 {op} memory.size))'''
    cases=[(g,d,s,n) for g in [0,1,2,0xffffffff] for d,s,n in
           [(base,src,16),(base,src,0),(base-1,src,1),(base+16,src,1),
            (131071,src,2),(base,0xffffffff,1),(base,0xffffffff,0)]]
    def ranges(a):return [(a[1],a[3])]+([(a[2],a[3])] if op=='memory.copy' else [])
    check(tmp_path,wat,cases,base=base,ranges=ranges)


def test_window_beyond_available_memory_does_not_back_low_addresses(tmp_path):
    wat='''(module (memory 1) (func (export "run") (param i32 i32) (result i32)
      local.get 0 i32.const 0 local.get 1 memory.fill i32.const 42))'''
    cases=[(0,0),(65536,0),(0,1),(65535,1),(65535,2),(0xffffff00,0),(0xffffff00,1)]
    check(tmp_path,wat,cases,base=0xffffff00,window=256,ranges=lambda a:[a])


@pytest.mark.parametrize('base,window',[(-1,16),(1<<32,0),(0xffffffff,2),(0xffffff80,129)])
def test_invalid_window_rejected(base,window):
    with pytest.raises(ValueError,match='address space'):Limits(memory_base=base,memory_bytes=window)


def test_window_can_end_exactly_at_the_address_space_end():
    assert Limits(memory_base=0xffffffff,memory_bytes=1).memory_base==0xffffffff
    assert Limits(memory_base=0xffffff00,memory_bytes=256).memory_bytes==256


def test_compiled_c_array_fixture_and_cli(tmp_path):
    source=ROOT/'examples/array.wasm';module,data=load(source)
    assert module.segments==[(65536,bytes.fromhex('0300000005000000070000000b000000'))]
    assert any(op=='loop' for f in module.functions for op,_ in f.code)
    font=tmp_path/'array.ttf'
    command=[sys.executable,str(ROOT/'build.py'),str(source),'-o',str(font),'--export','run',
             '--memory-base','0x10000','--memory-bytes','16']
    subprocess.run(command,check=True,capture_output=True,text=True,timeout=30)
    cases=[(n,bias) for n in [0,1,2,3,4,5,0xffffffff] for bias in [0,1,10,-1,0xffffffff,0x80000000]]
    oracle=execute_binary(data,'run',['i32','i32'],cases)
    with NativeFont(font) as native:
        for args,result in zip(cases,oracle):
            if 'trap' in result:
                with pytest.raises(WasmTrap,match='unreachable'):native.invoke(*args)
            else:
                wanted=(sum([3,5,7,11][:args[0]])+args[0]*args[1])&0xffffffff
                assert int(result['values'][0])&0xffffffff==wanted
                assert module.invoke('run',args)==[wanted]
                assert native.invoke(*args)==wanted
        assert native.invoke(4,10)==native.invoke(4,10)==66
    compile_source(source,tmp_path/'zero.ttf',export='run')
    with NativeFont(tmp_path/'zero.ttf') as native:
        assert native.invoke(0,10)==0
        with pytest.raises(ExecutionBoundExceeded,match='memory'):native.invoke(1,10)
