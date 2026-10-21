"""Shared wide reads preserve bounds and leave room for composed arithmetic."""
from pathlib import Path
import random

import pytest

from wasmfont.compiler import Limits
from wasmfont.frontend import memory_bytes
from wasmfont.gsub.circuit import Circuit,Value
from wasmfont.selection import lookup,lookup_window
from .test_memory_regions import compare
from .test_indirect_calls import compare as compare_program


SIZES=[(n,size) for n in [1,2,3,7,8,15,16,17,31,32,33,64,65,128,255,256]
       for size in [1,2,3,4,8] if size<=n]


@pytest.mark.parametrize('count,size',SIZES)
def test_shared_window_matches_padded_lookup_at_every_index(count,size):
    circuit=Circuit();index=circuit.argument(0,32)
    values=[circuit.argument(i+1,8) for i in range(count)]
    window=lookup_window(circuit,values,index,size)
    rng=random.Random(count*17+size);padded_count=1<<(count-1).bit_length()
    for at in range(padded_count):
        data=[rng.randrange(256) for _ in range(count)]
        wires=circuit.evaluate_for_test([at]+data)
        actual=[sum(wires[w]<<i for i,w in enumerate(value.bits)) for value in window]
        padded=data+[0]*(padded_count-count)
        assert actual==[padded[(at+i)%padded_count] for i in range(size)]
    constants=[circuit.const(i&255,8) for i in range(count)]
    for at in [0,count-size,count-1,padded_count-1]:
        result=lookup_window(circuit,constants,circuit.const(at,32),size)
        expected=[((at+i)%padded_count)&255 if (at+i)%padded_count<count else 0 for i in range(size)]
        assert [circuit.known(value) for value in result]==expected


@pytest.mark.parametrize('size',[0,4])
def test_invalid_window_lengths_fail_early(size):
    circuit=Circuit()
    with pytest.raises(ValueError,match='window'):
        lookup_window(circuit,[circuit.const(0,8)]*3,circuit.const(0,32),size)


@pytest.mark.parametrize('size',[2,3,4,8])
def test_repeated_runtime_bytes_do_not_introduce_selection_gates(size):
    circuit=Circuit();index=circuit.argument(0,32);value=circuit.argument(1,8)
    result=lookup_window(circuit,[value]*64,index,size)
    assert result==[value]*size
    assert circuit.gate_count==0


@pytest.mark.parametrize('count',[32,64,128,256])
def test_shared_wide_read_uses_less_than_sixty_percent_of_independent_lookup_cost(count):
    fast=Circuit();index=fast.argument(0,32);data=[fast.argument(i+1,8) for i in range(count)]
    lookup_window(fast,data,index,8)
    old=Circuit();index=old.argument(0,32);data=[old.argument(i+1,8) for i in range(count)]
    width=(count-1).bit_length();short=Value(index.bits[:width])
    for byte in range(8):lookup(old,data,old.add(short,old.const(byte,width)) if byte else short)
    assert fast.gate_count<old.gate_count*0.6


@pytest.mark.parametrize('low_bits',[(0,0,0),(1,1,1),(0,None,0),(None,1,0)])
def test_known_or_partial_alignment_keeps_correct_bytes_without_dead_lookahead(low_bits):
    circuit=Circuit();argument=circuit.argument(0,32)
    index=Value(tuple(argument.bits[i] if value is None else value for i,value in enumerate(low_bits))+argument.bits[3:])
    data=[circuit.argument(i+1,8) for i in range(128)]
    result=lookup_window(circuit,data,index,8)
    old=Circuit();argument_old=old.argument(0,32)
    index_old=Value(tuple(argument_old.bits[i] if value is None else value for i,value in enumerate(low_bits))+argument_old.bits[3:7])
    old_data=[old.argument(i+1,8) for i in range(128)]
    for byte in range(8):lookup(old,old_data,old.add(index_old,old.const(byte,7)) if byte else index_old)
    if low_bits==(0,0,0):assert circuit.gate_count<=old.gate_count
    rng=random.Random(103);values=[rng.randrange(256) for _ in range(128)]
    for at in range(128):
        wires=circuit.evaluate_for_test([at]+values)
        effective=(at&~7)|sum(((at>>i)&1 if value is None else value)<<i for i,value in enumerate(low_bits))
        actual=[sum(wires[w]<<i for i,w in enumerate(value.bits)) for value in result]
        assert actual==[values[(effective+i)%128] for i in range(8)]


def initialized_buffer(regions):
    addresses=[address for base,size in regions for address in range(base,base+size)]
    # Fixed stores expose distinct runtime bits for every byte, including tails
    # of regions whose lengths are not multiples of a machine word.
    stores=' '.join(f'i32.const {address} local.get {i//8+1} i64.const {i%8*8} i64.shr_u i32.wrap_i64 i32.store8'
                    for i,address in enumerate(addresses))
    return stores,(len(addresses)+7)//8


@pytest.mark.parametrize('op',[
    'i32.load','i64.load','i32.load16_s','i32.load16_u',
    'i64.load16_s','i64.load16_u','i64.load32_s','i64.load32_u',
])
@pytest.mark.parametrize('sparse',[False,True])
@pytest.mark.parametrize('offset',[0,5])
def test_wide_reads_across_blocks_signed_extensions_and_sparse_region_edges(tmp_path,op,sparse,offset):
    regions=((1025,19),(65533,21)) if sparse else ((0,64),)
    stores,count=initialized_buffer(regions);size=memory_bytes(op)
    wat=f'''(module (memory 2)
      (func (export "run") (param i32 {' '.join(['i64']*count)}) (result {op[:3]})
        {stores} local.get 0 {op} offset={offset}))'''
    addresses={0,1,0xffffffff,131072-size,131072}
    for base,length in regions:
        addresses.update((base-offset-1,base-offset,base+length-size-offset,base+length-size-offset+1,base+length-offset))
        addresses.update(base+i-offset for i in [1,3,7,8,9,15,16] if i<=length-size)
    addresses=sorted(a for a in addresses if a>=0)
    rng=random.Random(83)
    values=[(0,)*count,(-1,)*count,tuple(rng.getrandbits(64) for _ in range(count))]
    cases=[(address,)+data for address in addresses for data in values]
    limits=Limits(memory_regions=regions) if sparse else Limits(memory_bytes=64)
    compare(tmp_path,wat,cases,regions,limits=limits,ranges=lambda args:[(args[0]+offset,size)])


def test_shared_reads_follow_growth_before_applying_backed_window_bounds(tmp_path):
    wat='''(module (memory 1 2)
      (func (export "run") (param i32 i32 i64) (result i64)
        local.get 0 memory.grow drop
        i32.const 65520 local.get 2 i64.store
        i32.const 65528 local.get 2 i64.const -1 i64.xor i64.store
        memory.size i32.const 2 i32.eq if
          i32.const 65536 local.get 2 i64.const 8 i64.rotl i64.store
          i32.const 65544 local.get 2 i64.const 32 i64.rotl i64.store
        end local.get 1 i64.load))'''
    cases=[(grow,address,value) for grow in [0,1,2,-1]
           for address in [0,65519,65520,65521,65528,65529,65535,65536,65576,65577,131072,0xffffffff]
           for value in [0,-1,0x807f060504030201]]
    compare(tmp_path,wat,cases,(),limits=Limits(memory_base=65520,memory_bytes=64),ranges=lambda args:[(args[1],8)])


def test_full_runtime_buffer_read_fits_a_smaller_construction_budget(tmp_path):
    count=128;stores=' '.join(f'i32.const {i*8} local.get {i+1} i64.store' for i in range(count//8))
    wat=f'''(module (memory 1) (func (export "run") (param i32 {' '.join(['i64']*(count//8))})
      (result i64) {stores} local.get 0 i64.load))'''
    rng=random.Random(97)
    cases=[(address,)+tuple(rng.getrandbits(64) for _ in range(count//8)) for address in range(count-7)]
    manifest=compare_program(tmp_path,wat,cases,limits=Limits(memory_bytes=count,max_gates=2500))[0]
    assert manifest['metrics']['gates']<2500
    assert manifest['metrics']['font_bytes']<650000


def test_two_unaligned_reads_compose_with_full_width_dynamic_division(tmp_path):
    source=Path(__file__).resolve().parents[1]/'examples'/'indexed_words.wat'
    rng=random.Random(99)
    cases=[(a,b,x,y,divisor) for a,b in [(0,0),(-1,0),(0x0807060504030201,0x1122334455667788)]
           for x,y in [(0,8),(1,9),(3,29),(7,31),(48,56),(56,56)] for divisor in [0,1,7,-1]]
    cases += [(rng.getrandbits(64),rng.getrandbits(64),rng.randrange(57),rng.randrange(57),rng.getrandbits(64)) for _ in range(20)]
    manifest=compare_program(tmp_path,source.read_text(),cases,limits=Limits(memory_bytes=64,max_gates=8000))[0]
    assert manifest['metrics']['gates']<8000
    assert manifest['metrics']['font_bytes']<2800000
