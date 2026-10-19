"""Dropped payloads stay cheap; lowering budgets have their own diagnostics."""
from pathlib import Path
import random
import subprocess
import sys

import pytest

from wasmfont.capacity import CompilationCapacity
from wasmfont.compiler import compile_source,Limits
from wasmfont.frontend import load
from wasmfont.oracle import execute_binary
from .test_indirect_calls import compare


@pytest.mark.parametrize('regions',[(),((0,16),),((0,8),(1024,8))])
@pytest.mark.parametrize('mode',['dropped','active'])
def test_large_unavailable_data_keeps_dynamic_zero_length_init_small(tmp_path,regions,mode):
    rng=random.Random(123)
    payload=''.join(f'\\{rng.randrange(256):02x}' for _ in range(4096))
    wat=f'''(module (memory 1) (data $p {'(i32.const 0)' if mode=='active' else ''} "{payload}")
      (func (export "run") (param i32 i32 i32 i64) (result i64)
        i32.const 0 local.get 3 i64.store
        {'data.drop $p' if mode=='dropped' else ''}
        local.get 0 local.get 1 local.get 2 memory.init $p
        i32.const 0 i64.load))'''
    cases=[(d,s,n,seed) for d,s,n in [
        (0,0,0),(16,0,0),(65535,0,0),(65536,0,0),(65537,0,0),
        (0,1,0),(0,4096,0),(0,0,1),(16,0,1),(0xffffffff,0,0),(0,0,0xffffffff),
    ] for seed in [0,0x807f060504030201,-1]]
    manifest,_,_=compare(tmp_path,wat,cases,limits=Limits(memory_regions=regions,max_gates=500))
    assert manifest['metrics']['gates']<500


@pytest.mark.parametrize('mode',['dropped','active','declarative'])
def test_large_unavailable_elements_preserve_table_and_bounds_with_small_budget(tmp_path,mode):
    rng=random.Random(122);count=256 if mode=='active' else 4096
    entries=' '.join(rng.choice(['$a','$b']) for _ in range(count))
    head={'dropped':'func','active':'(i32.const 0) func','declarative':'declare func'}[mode]
    size=256 if mode=='active' else 3
    wat=f'''(module (table {size} funcref) (elem (i32.const 0) $a $b $a)
      (elem $p {head} {entries})
      (func $a (result i32) i32.const 11) (func $b (result i32) i32.const 22)
      (func (export "run") (param i32 i32 i32) (result i32 i32 i32 i32)
        {'elem.drop $p' if mode=='dropped' else ''}
        local.get 0 local.get 1 local.get 2 table.init $p
        table.size i32.const 0 call_indirect (result i32)
        i32.const 1 call_indirect (result i32) i32.const 2 call_indirect (result i32)))'''
    cases=[
        (0,0,0),(2,0,0),(size,0,0),(size+1,0,0),(0xffffffff,0,0),
        (0,1,0),(0,count,0),(0,0,1),(size,0,1),(0,0xffffffff,1),(0,0,0xffffffff),
    ]
    manifest,_,_=compare(tmp_path,wat,cases,limits=Limits(max_gates=500))
    assert manifest['metrics']['gates']<500


def test_instruction_exhaustion_has_its_own_capacity_kind_and_cli_advice(tmp_path):
    loops=''
    for i in range(3):loops+=f'i32.const 64 local.set {i} loop $l{i} '
    for i in reversed(range(3)):
        loops+=f'local.get {i} i32.const 1 i32.sub local.tee {i} br_if $l{i} end '
    path=tmp_path/'instructions.wat'
    path.write_text(f'(module (func (export "run") (result i32) (local i32 i32 i32) {loops} i32.const 42))')
    _,data=load(path)
    assert execute_binary(data,'run',[],[()])==[{'values':['42']}]
    font=tmp_path/'instructions.ttf'
    with pytest.raises(CompilationCapacity,match='too many lowered instructions') as caught:
        compile_source(path,font,export='run',limits=Limits(loop_iterations=64,max_gates=16))
    error=caught.value
    assert error.resource=='instructions'
    assert error.details['instruction_limit']==100000
    assert error.details['lowered_instructions']==100001
    assert error.details['constructed_gates']==0
    assert 'OpenType' not in str(error)
    assert not font.exists() and not font.with_suffix('.json').exists()
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,str(root/'build.py'),str(path),'-o',str(font),
                           '--export','run','--loop-bound','64','--max-gates','16'],
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==2
    assert 'lowered instructions 100001/100000' in result.stderr
    assert '[instructions;' in result.stderr and 'OpenType' not in result.stderr
    assert not font.exists() and not font.with_suffix('.json').exists()
