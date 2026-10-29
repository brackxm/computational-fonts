# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Symbol identity and store-size regressions checked with LLVM and HarfBuzz."""
import ctypes
from contextlib import contextmanager
import random
import shutil
import subprocess

import pytest
from llvmlite import binding as llvm

from test_llvm import font


@contextmanager
def native_engine(source, *, normalize_layout=False):
    llvm.initialize_native_target(); llvm.initialize_native_asmprinter()
    module=llvm.parse_assembly(source); module.verify()
    machine=llvm.Target.from_default_triple().create_target_machine()
    if normalize_layout:
        # MCJIT requires its host layout. First let LLVM promote all accesses
        # using the original layout, and verify no memory/layout-dependent
        # instructions remain before changing the layout for native execution.
        with llvm.create_pipeline_tuning_options(speed_level=1) as options:
            with llvm.create_pass_builder(machine,options) as builder:
                with llvm.create_new_module_pass_manager() as passes:
                    passes.add_sroa_pass(); passes.add_instruction_combine_pass()
                    passes.add_simplify_cfg_pass(); passes.run(module,builder)
        for function in module.functions:
            for block in function.blocks:
                assert all(inst.opcode not in ('load','store','alloca','getelementptr','call','ptrtoint','inttoptr') for inst in block.instructions),str(module)
        module.data_layout=str(machine.target_data)
    module.triple=llvm.get_default_triple()
    with llvm.create_mcjit_compiler(module,machine) as engine:
        engine.finalize_object()
        yield engine


@pytest.mark.parametrize('kind',['globals','functions'])
@pytest.mark.parametrize('bitcode',[False,True])
@pytest.mark.parametrize('optimize',[False,True])
def test_unnamed_symbol_identity_native_and_harfbuzz(tmp_path,kind,bitcode,optimize):
    if kind=='globals':
        source='''@0=constant i32 7
@1=constant i32 9
define i32 @f(i1 %which,i32 %x){
 %p=select i1 %which,ptr @1,ptr @0
 %v=load i32,ptr %p
 %r=add i32 %v,%x
 ret i32 %r}'''
    else:
        source='''define i32 @0(i32 %x){%r=add i32 %x,7
 ret i32 %r}
define i32 @1(i32 %x){%r=add i32 %x,9
 ret i32 %r}
define i32 @f(i1 %which,i32 %x){
 %a=call i32 @0(i32 %x)
 %p=select i1 %which,ptr @1,ptr @0
 %r=call i32 %p(i32 %a),!callees !0
 ret i32 %r}
!0=!{ptr @0,ptr @1}'''
    module=llvm.parse_assembly(source); module.verify()
    supplied=module.as_bitcode() if bitcode else source
    module.close()
    with native_engine(source) as engine:
        reference=ctypes.CFUNCTYPE(ctypes.c_uint32,ctypes.c_uint8,ctypes.c_uint32)(engine.get_function_address('f'))
        with font(tmp_path,supplied,function='f',optimize=optimize) as machine:
            rng=random.Random(672)
            for which in [0,1]:
                for x in [0,0xffffffff]+[rng.getrandbits(32) for _ in range(30)]:
                    assert machine.invoke(which,x)==reference(which,x)


def test_unnamed_data_alias_constructor_and_pointer_relocations(tmp_path):
    source='''@0=global i32 7
@1=global i32 9
@2=constant [2 x ptr] [ptr @0,ptr @1]
@3=alias i32,ptr @0
@4=alias void(),ptr @init
@llvm.global_ctors=appending global [1 x {i32,ptr,ptr}] [
 {i32,ptr,ptr} {i32 101,ptr @4,ptr @3}]
define void @init(){store i32 17,ptr @3
 ret void}
define i32 @f(i1 %which,i32 %x){
 %index=zext i1 %which to i64
 %p=getelementptr [2 x ptr],ptr @2,i64 0,i64 %index
 %q=load ptr,ptr %p
 %v=load i32,ptr %q
 %r=add i32 %v,%x
 ret i32 %r}'''
    compiler=shutil.which('clang')
    if not compiler: pytest.skip('Clang required for native loader startup')
    path=tmp_path/'constructors.ll'; path.write_text(source)
    native=tmp_path/'constructors.dylib'
    subprocess.run([compiler,'-O0','-shared','-fPIC',str(path),'-o',str(native)],check=True,capture_output=True)
    library=ctypes.CDLL(str(native))
    reference=library.f
    reference.argtypes=[ctypes.c_uint8,ctypes.c_uint32]; reference.restype=ctypes.c_uint32
    with font(tmp_path,source,function='f') as machine:
        assert set(machine.manifest['aliases'])=={'@3','@4'}
        assert machine.manifest['mutable_globals']==['@0','@1']
        for which in [0,1]:
            for x in [0,123,0xffffffff]: assert machine.invoke(which,x)==reference(which,x)


def test_numbered_and_quoted_numeric_globals_are_distinct(tmp_path):
    source='''@0=constant i32 7
@"0"=constant i32 13
@"@0"=constant i32 17
define i64 @f(i32 %x){
 %a=load i32,ptr @0
 %b=load i32,ptr @"0"
 %c=load i32,ptr @"@0"
 %aa=zext i32 %a to i64
 %bb=zext i32 %b to i64
 %cc=zext i32 %c to i64
 %hi=shl i64 %cc,16
 %mid=shl i64 %bb,8
 %first=or i64 %hi,%mid
 %packed=or i64 %first,%aa
 %extra=zext i32 %x to i64
 %r=add i64 %packed,%extra
 ret i64 %r}'''
    with native_engine(source) as engine:
        reference=ctypes.CFUNCTYPE(ctypes.c_uint64,ctypes.c_uint32)(engine.get_function_address('f'))
        with font(tmp_path,source,function='f') as machine:
            for x in [0,100,0xffffffff]: assert machine.invoke(x)==reference(x)


def test_interleaved_unnamed_functions_and_globals_keep_reference_identity(tmp_path):
    source='''define i32 @0(){ret i32 7}
@1=constant i32 9
define i32 @2(){ret i32 13}
@3=constant i32 17
define i32 @f(){
 %a=call i32 @0()
 %b=call i32 @2()
 %c=load i32,ptr @1
 %d=load i32,ptr @3
 %x=add i32 %a,%b
 %y=add i32 %c,%d
 %r=add i32 %x,%y
 ret i32 %r}'''
    with native_engine(source) as engine:
        reference=ctypes.CFUNCTYPE(ctypes.c_uint32)(engine.get_function_address('f'))
        with font(tmp_path,source,function='f') as machine:
            assert machine.invoke()==reference()==46


@pytest.mark.parametrize('selector,increment',[('@0',7),('0',13),('@"0"',13),('@"@0"',17)])
def test_numeric_entry_selection_is_unambiguous(tmp_path,selector,increment):
    source='''define i32 @0(i32 %x){%r=add i32 %x,7
 ret i32 %r}
define i32 @"0"(i32 %x){%r=add i32 %x,13
 ret i32 %r}
define i32 @"@0"(i32 %x){%r=add i32 %x,17
 ret i32 %r}'''
    with font(tmp_path,source,function=selector) as machine:
        assert machine.invoke(23)==23+increment
    single='define i32 @0(i32 %x){ret i32 %x}'
    with font(tmp_path,single) as machine:
        assert machine.manifest['function']=='@0'
        assert machine.invoke(42)==42


@pytest.mark.parametrize('width',[1,16,32,64])
@pytest.mark.parametrize('mode',['sentinel','exact_span'])
def test_scalar_store_size_and_load_span_native(tmp_path,width,mode):
    size=(width+7)//8
    alignment=size*2
    # LLVM requires i8 ABI alignment to remain one byte.
    byte_type='i8'
    count=size+1 if mode=='sentinel' else size
    source=f'''target datalayout="e-p:64:64-i{width}:{alignment*8}"
define i{8 if mode=='sentinel' else width} @f(i{width} %x){{
 %p=alloca [{count} x {byte_type}],align {alignment}
'''
    if mode=='sentinel':
        source+=f''' %q=getelementptr {byte_type},ptr %p,i64 {size}
 store i8 99,ptr %q,align 1
 store i{width} %x,ptr %p,align 1
 %r=load i8,ptr %q,align 1
 ret i8 %r}}'''
    else:
        source+=f''' store i{width} %x,ptr %p,align 1
 %r=load i{width},ptr %p,align 1
 ret i{width} %r}}'''
    typ={1:ctypes.c_uint8,8:ctypes.c_uint8,16:ctypes.c_uint16,32:ctypes.c_uint32,64:ctypes.c_uint64}[width]
    mask=(1<<width)-1
    with native_engine(source,normalize_layout=True) as engine:
        reference=ctypes.CFUNCTYPE(ctypes.c_uint8 if mode=='sentinel' else typ,typ)(engine.get_function_address('f'))
        with font(tmp_path,source) as machine:
            rng=random.Random(674+width)
            for x in [0,mask]+[rng.getrandbits(width) for _ in range(24)]:
                assert machine.invoke(x)==(reference(x) if mode=='sentinel' else reference(x)&mask)


@pytest.mark.parametrize('aggregate',['{i32}','<{i32}>'])
def test_aggregate_abi_alignment_does_not_expand_store_span(tmp_path,aggregate):
    source=f'''target datalayout="e-p:64:64-a:128"
%S=type {aggregate}
define i32 @f(i32 %x){{
 %p=alloca [4 x i8],align 16
 %a=insertvalue %S zeroinitializer,i32 %x,0
 store %S %a,ptr %p,align 1
 %b=load %S,ptr %p,align 1
 %r=extractvalue %S %b,0
 ret i32 %r}}'''
    with native_engine(source,normalize_layout=True) as engine:
        reference=ctypes.CFUNCTYPE(ctypes.c_uint32,ctypes.c_uint32)(engine.get_function_address('f'))
        with font(tmp_path,source) as machine:
            for x in [0,23,0xffffffff]: assert machine.invoke(x)==reference(x)


@pytest.mark.parametrize('aggregate',['[2 x i32]','{i32,i32}','<{i32,i32}>'])
def test_aggregate_stride_and_scalar_padding_poison(tmp_path,aggregate):
    # Scalar fields retain allocation stride while loads ignore poisoned padding.
    source=f'''target datalayout="e-p:64:64-i32:64"
%S=type {aggregate}
define i32 @f(i32 %x){{
 %p=alloca %S,align 8
 %q=getelementptr %S,ptr %p,i64 0,i32 1
 store i32 %x,ptr %q,align 1
 %padding=getelementptr i8,ptr %p,i64 12
 store i8 poison,ptr %padding,align 1
 %r=load i32,ptr %q,align 1
 ret i32 %r}}'''
    with native_engine(source,normalize_layout=True) as engine:
        reference=ctypes.CFUNCTYPE(ctypes.c_uint32,ctypes.c_uint32)(engine.get_function_address('f'))
        with font(tmp_path,source) as machine:
            for x in [0,23,0xffffffff]: assert machine.invoke(x)==reference(x)


def test_overaligned_pointer_representation_and_adjacent_byte(tmp_path):
    source='''target datalayout="e-p:64:128"
@g=constant i32 42
define i32 @f(){
 %p=alloca [16 x i8],align 16
 %q=getelementptr i8,ptr %p,i64 8
 store i8 99,ptr %q,align 1
 store ptr @g,ptr %p,align 1
 %back=load ptr,ptr %p,align 1
 %v=load i32,ptr %back,align 1
 %byte=load i8,ptr %q,align 1
 %extra=zext i8 %byte to i32
 %r=add i32 %v,%extra
 ret i32 %r}'''
    with native_engine(source,normalize_layout=True) as engine:
        reference=ctypes.CFUNCTYPE(ctypes.c_uint32)(engine.get_function_address('f'))
        with font(tmp_path,source) as machine: assert machine.invoke()==reference()==141


@pytest.mark.parametrize('pointer',[False,True])
def test_global_allocation_padding_survives_typed_initialization(tmp_path,pointer):
    typ,size,decl=('ptr',16,'@g=constant i32 17\n@slot=constant ptr @g') if pointer else ('i32',8,'@slot=constant i32 17')
    source=f'''target datalayout="e-p:64:128-i32:64"
{decl}
declare void @llvm.memcpy.p0.p0.i64(ptr,ptr,i64,i1 immarg)
define i32 @f(){{
 %p=alloca [{size} x i8],align 16
 call void @llvm.memcpy.p0.p0.i64(ptr %p,ptr dereferenceable({size}) @slot,i64 {size},i1 false)
 %v=load {typ},ptr %p,align 1
'''
    source+=(' %r=load i32,ptr %v,align 1\n ret i32 %r}' if pointer else ' ret i32 %v}')
    with native_engine(source,normalize_layout=True) as engine:
        reference=ctypes.CFUNCTYPE(ctypes.c_uint32)(engine.get_function_address('f'))
        with font(tmp_path,source) as machine: assert machine.invoke()==reference()==17
