"""Sparse regions, gap bounds, compact indexed loads and capacity reports."""
from pathlib import Path
import random
import subprocess
import sys

import pytest

from wasmfont.compiler import compile_source,Limits
from wasmfont.capacity import CompilationCapacity
from wasmfont.frontend import load
from wasmfont.oracle import execute_binary
from wasmfont.runtime import NativeFont,WasmTrap,ExecutionBoundExceeded,IncompleteShaping
from wasmfont.reference.interpreter import WasmTrap as ReferenceTrap
from wasmfont.state import MemoryTrap
from wasmfont.gsub.circuit import Circuit,Value,ResourceLimit
from wasmfont.selection import lookup


def compare(tmp_path,wat,cases,regions,*,ranges=lambda args:[],limits=None):
    path=tmp_path/'regions.wat';path.write_text(wat)
    module,data=load(path);fn=module.functions[module.exports['run'][1]]
    expected=execute_binary(data,'run',fn.params,cases)
    limits=limits or Limits(memory_regions=regions)
    manifest=compile_source(path,path.with_suffix('.ttf'),export='run',limits=limits)
    regions=limits.memory_regions or ((limits.memory_base,limits.memory_bytes),)
    with NativeFont(path.with_suffix('.ttf')) as native:
        for args,want in zip(cases,expected):
            if 'trap' in want:
                with pytest.raises((ReferenceTrap,MemoryTrap)):module.invoke('run',args)
                with pytest.raises(WasmTrap):native.invoke(*args)
                continue
            result=tuple(int(v)&((1<<int(t[1:]))-1) for v,t in zip(want['values'],fn.results))
            assert tuple(module.invoke('run',args))==result
            if any(size and not any(base<=address<=base+count-size for base,count in regions) for address,size in ranges(args)):
                with pytest.raises(ExecutionBoundExceeded,match='memory'):native.invoke(*args)
            else:
                actual=native.invoke(*args)
                assert ((actual,) if len(result)==1 else actual)==result,args
        with pytest.raises(IncompleteShaping):native.decode(native.shaper.shape(native.encode(cases[0]),enabled=False))
    return manifest


@pytest.mark.parametrize('op',['i32.load','i64.load','i32.load8_s','i32.load16_s','i64.load32_s'])
@pytest.mark.parametrize('offset',[0,1024,65535])
def test_sparse_loads_offsets_gaps_and_unsigned_addresses(tmp_path,op,offset):
    regions=((1024,16),(65535,16))
    wat=f'''(module (memory 2) (data (i32.const 1024) "ABCDEFGHIJKLMNOP")
      (data (i32.const 65535) "qrstuvwxyz012345")
      (func (export "run") (param i32) (result {op[:3]}) local.get 0 {op} offset={offset}))'''
    size=int(op.split('load')[1].split('_')[0] or op[1:3])//8
    addresses={0,1,0xffffffff,131072-size}
    for base,length in regions:
        addresses.update(a for a in (base-offset-1,base-offset,base+length-size-offset,base+length-size-offset+1) if a>=0)
    compare(tmp_path,wat,[(a,) for a in sorted(addresses)],regions,ranges=lambda a:[(a[0]+offset,size)])


@pytest.mark.parametrize('op',['i32.store','i64.store','i32.store8','i64.store16','i64.store32'])
def test_writes_in_either_region_and_cross_gap_rejection(tmp_path,op):
    size=int(op.split('store')[1] or op[1:3])//8
    wat=f'''(module (memory 2) (func (export "run") (param i32 {op[:3]}) (result i64 i64 i64 i64)
      local.get 0 local.get 1 {op}
      i32.const 1024 i64.load i32.const 1032 i64.load i32.const 65536 i64.load i32.const 65544 i64.load))'''
    cases=[(a,v) for a in [0,1023,1024,1040-size,1041-size,1040,65536,65552-size,65553-size,0xffffffff] for v in [0,-1,0x807f060504030201]]
    compare(tmp_path,wat,cases,((1024,16),(65536,16)),ranges=lambda a:[(a[0],size)])


@pytest.mark.parametrize('op',['memory.copy','memory.fill','memory.init $p'])
def test_cross_region_bulk_copy_snapshots_and_segment_sources(tmp_path,op):
    regions=((1025,17),(65533,17));payload=''.join(f'\\{(i*37+0x81)&255:02x}' for i in range(23))
    wat=f'''(module (memory 2) (data (i32.const 1025) "ABCDEFGHIJKLMNOPQ") (data $p "{payload}")
      (func (export "run") (param i32 i32 i32) (result i64 i64 i32 i64 i64 i32)
        local.get 0 local.get 1 local.get 2 {op}
        i32.const 1025 i64.load i32.const 1033 i64.load i32.const 1041 i32.load8_u
        i32.const 65533 i64.load i32.const 65541 i64.load i32.const 65549 i32.load8_u))'''
    def src(at):return at if op.startswith('memory.init') else 1025+at
    cases=[(d,s,n) for d,s,n in [(65533,src(0),17),(65534,src(0),16),(1026,src(0),16),
           (1025,src(1),16),(1041,src(0),1),(1041,src(0),2),(65532,src(0),1),
           (0,src(0),0),(131072,0,0),(131073,0,0),(0xffffffff,0,1),(65533,0xffffffff,1)]]
    rng=random.Random(123)
    for _ in range(30):
        base=rng.choice([1025,65533]);d=rng.randrange(17);s=rng.randrange(17)
        cases.append((base+d,src(s),rng.randrange(18-max(d,s))))
    compare(tmp_path,wat,cases,regions,ranges=lambda a:[(a[0],a[2])]+([(a[1],a[2])] if op=='memory.copy' else []))


def test_adjacent_regions_merge_and_preserve_active_data_overlays(tmp_path):
    regions=((1024,4),(1028,4),(65536,8))
    wat='''(module (memory 2) (data (i32.const 1022) "ABCDEFGHIJKL")
      (data (i32.const 1026) "xyz") (data (i32.const 65536) "12345678")
      (func (export "run") (result i64 i64) i32.const 1024 i64.load i32.const 65536 i64.load))'''
    manifest=compare(tmp_path,wat,[()],regions)
    assert manifest['limits']['memory_regions']==((1024,8),(65536,8))


def test_regions_follow_growth_and_start_initialization(tmp_path):
    wat='''(module (memory 0 2) (func $init i32.const 1 memory.grow drop
      i32.const 1024 i32.const 42 i32.store) (start $init)
      (func (export "run") (param i32 i32) (result i32 i32)
        local.get 0 memory.grow drop
        local.get 1 i32.const 7 i32.store8
        i32.const 1024 i32.load memory.size))'''
    cases=[(g,a) for g in [0,1,2,0xffffffff] for a in [1024,1031,1032,65536,65543,65544,131072]]
    compare(tmp_path,wat,cases,((1024,8),(65536,8)),ranges=lambda a:[(a[1],1)])


@pytest.mark.parametrize('regions',[
    ((0,0),),((-1,1),),((0xffffffff,2),),((0,200),(1024,57)),((0,16),(8,16)),
    ((0,8),(0,8)),((0,),),((0,1,2),),((0,'16'),),None,tuple((i*2,1) for i in range(17)),
])
def test_invalid_region_configs_fail_early(regions):
    with pytest.raises(ValueError):Limits(memory_regions=regions)


def test_cli_accepts_repeated_hex_regions(tmp_path):
    path=tmp_path/'cli.wat';path.write_text('''(module (memory 2)
      (func (export "run") (result i32 i32)
        i32.const 1024 i32.const 7 i32.store i32.const 65536 i32.const 9 i32.store
        i32.const 1024 i32.load i32.const 65536 i32.load))''')
    root=Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable,str(root/'build.py'),str(path),'-o',str(path.with_suffix('.ttf')),
                    '--memory-region','0x10000:4','--memory-region','1024:4'],check=True,capture_output=True,timeout=30)
    with NativeFont(path.with_suffix('.ttf')) as native:assert native.invoke()==(7,9)


@pytest.mark.parametrize('count',[32,64,128])
def test_shared_indexed_read_circuit_reduces_gate_cost(count):
    fast=Circuit();idx=fast.argument(0,32);data=[fast.argument(i+1,8) for i in range(count)]
    result=lookup(fast,data,idx)
    slow=Circuit();old_idx=slow.argument(0,32);old_data=[slow.argument(i+1,8) for i in range(count)];bits=[0]*8
    for i,value in enumerate(old_data):
        test=slow.eq(old_idx,slow.const(i,32))
        for bit in range(8):bits[bit]=slow.OR(bits[bit],slow.AND(test,value.bits[bit]))
    assert fast.gate_count<slow.gate_count*0.45
    rng=random.Random(count)
    for index in range(count):
        values=[rng.randrange(256) for _ in range(count)]
        actual=fast.evaluate_for_test([index]+values)
        assert sum(actual[wire]<<bit for bit,wire in enumerate(result.bits))==values[index]


def test_large_dynamic_memory_lookup_fits_smaller_construction_budget(tmp_path):
    stores=' '.join(f'i32.const {i*8} local.get {i+1} i64.store' for i in range(8))
    wat=f'''(module (memory 1) (func (export "run") (param i32 {' '.join(['i64']*8)}) (result i32)
      {stores} local.get 0 i32.load8_u))'''
    rng=random.Random(17)
    cases=[(i,)+tuple(rng.getrandbits(64) for _ in range(8)) for i in range(64)]
    manifest=compare(tmp_path,wat,cases,(),limits=Limits(memory_bytes=64,max_gates=800))
    assert manifest['metrics']['gates']<800


def test_capacity_diagnostics_identify_gate_budget(tmp_path):
    path=tmp_path/'gates.wat';path.write_text('(module (func (param i64 i64) (result i64) local.get 0 local.get 1 i64.mul))')
    with pytest.raises(CompilationCapacity,match='max_gates=16') as caught:
        compile_source(path,path.with_suffix('.ttf'),limits=Limits(max_gates=16,memory_regions=((1024,8),(65536,8))))
    assert caught.value.resource=='gates' and caught.value.details['gate_limit']==16
    assert isinstance(caught.value,ResourceLimit)


def test_capacity_diagnostics_distinguish_glyph_limits(tmp_path):
    path=tmp_path/'glyphs.wat';path.write_text(f'(module (func (param {" ".join(["i64"]*520)}) (result i32) i32.const 0))')
    with pytest.raises(CompilationCapacity,match='glyph-count') as caught:compile_source(path,path.with_suffix('.ttf'))
    assert caught.value.resource=='glyphs'


def test_capacity_diagnostics_distinguish_lookup_offsets(tmp_path,monkeypatch):
    import wasmfont.compiler as compiler
    path=tmp_path/'offsets.wat';path.write_text('(module (func (result i32) i32.const 42))')
    def fail(*args,**kwargs):raise ResourceLimit('OpenType lookup layout capacity exceeded')
    monkeypatch.setattr(compiler,'emit_font',fail)
    with pytest.raises(CompilationCapacity,match='lookup layout capacity') as caught:compile_source(path,path.with_suffix('.ttf'))
    assert caught.value.resource=='lookup_offsets'


def test_compiled_c_uses_separate_stack_and_global_regions(tmp_path):
    source=Path(__file__).resolve().parents[1]/'examples'/'sparse_array.wasm'
    module,data=load(source);font=tmp_path/'sparse.ttf'
    compile_source(source,font,export='run',limits=Limits(memory_regions=((65024,16),(65536,16))))
    cases=[(count,bias) for count in range(6) for bias in [0,10,0xffffffff,0x80000000]]
    expected=execute_binary(data,'run',['i32','i32'],cases)
    with NativeFont(font) as native:
        for args,want in zip(cases,expected):
            if 'trap' in want:
                with pytest.raises(WasmTrap,match='unreachable'):native.invoke(*args)
            else:
                result=int(want['values'][0])&0xffffffff
                assert module.invoke('run',args)==[result]
                assert native.invoke(*args)==result
        assert native.invoke(4,10)==66
        assert native.invoke(4,10)==66
