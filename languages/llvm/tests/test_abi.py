# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Bounded aggregate ABIs, caller-owned byval storage and native references."""
import ctypes
import gc
import os
import random
import shutil
import subprocess

import pytest
from llvmlite import binding as llvm

from test_llvm import HERE, font
from llvmfont import build, compile_ir, Limits, LLVMError
from fontcircuit.runtime import WasmTrap
from fontcircuit.gsub.circuit import ResourceLimit


BYVAL = '''%S=type {i32,ptr}
@value=global i32 5
@escaped=global ptr null
define ptr @copy(ptr byval(%S) align 8 %p){
 %old=load i32,ptr %p
 %next=add i32 %old,7
 store i32 %next,ptr %p
 %q=getelementptr %S,ptr %p,i64 0,i32 1
 %target=load ptr,ptr %q
 store i32 19,ptr %target
 store ptr %p,ptr @escaped
 ret ptr %p}
define i64 @f(i32 %x){
 %s=alloca %S,align 8
 %a=insertvalue %S zeroinitializer,i32 %x,0
 %b=insertvalue %S %a,ptr @value,1
 store %S %b,ptr %s
 %p=call ptr @copy(ptr byval(%S) align 8 %s)
 %changed=load i32,ptr %p
 %original=load i32,ptr %s
 %lo=zext i32 %changed to i64
 %hi=zext i32 %original to i64
 %high=shl i64 %hi,32
 %r=or i64 %high,%lo
 ret i64 %r}'''


def test_byval_native_copy_identity_pointer_fields_and_caller_lifetime(tmp_path):
    llvm.initialize_native_target(); llvm.initialize_native_asmprinter()
    module=llvm.parse_assembly(BYVAL); module.triple=llvm.get_default_triple()
    with llvm.create_mcjit_compiler(module,llvm.Target.from_default_triple().create_target_machine()) as engine:
        engine.finalize_object()
        native=ctypes.CFUNCTYPE(ctypes.c_uint64,ctypes.c_uint32)(engine.get_function_address('f'))
        with font(tmp_path,BYVAL,function='f') as machine:
            rng=random.Random(417)
            for x in [0,0xffffffff]+[rng.getrandbits(32) for _ in range(40)]:
                assert machine.invoke(x)==native(x)
    source=BYVAL+'''
define i32 @after_return(i32 %x){
 %ignored=call i64 @f(i32 %x)
 %p=load ptr,ptr @escaped
 %r=load i32,ptr %p
 ret i32 %r}'''
    with font(tmp_path,source,function='after_return') as machine:
        with pytest.raises(WasmTrap,match='invalid_memory'): machine.invoke(12)


def test_byval_aliasing_arguments_are_independent_copies(tmp_path):
    source='''define i32 @g(ptr byval(i32) align 4 %a,ptr byval(i32) align 4 %b){
 store i32 99,ptr %a
 %r=load i32,ptr %b
 ret i32 %r}
define i32 @f(i32 %x){%p=alloca i32,align 4
 store i32 %x,ptr %p
 %r=call i32 @g(ptr byval(i32) align 4 %p,ptr byval(i32) align 4 %p)
 ret i32 %r}'''
    with font(tmp_path,source,function='f') as machine:
        for x in [0,5,0xffffffff]: assert machine.invoke(x)==x


@pytest.mark.parametrize('target',['null','poison','%small'])
def test_byval_implicit_copy_checks_the_source_on_active_calls(tmp_path,target):
    source='''define void @g(ptr byval(i32) align 4 %p){ret void}
define i8 @f(i1 %run){
entry: %small=alloca i8
 br i1 %run,label %yes,label %no
yes: call void @g(ptr byval(i32) align 4 TARGET)
 ret i8 7
no: ret i8 7}'''.replace('TARGET',target)
    with font(tmp_path,source,function='f') as machine:
        assert machine.invoke(0)==7
        with pytest.raises(WasmTrap,match='invalid_memory'): machine.invoke(1)


@pytest.mark.parametrize('sret_index',[0,1])
@pytest.mark.parametrize('optimize',[False,True])
def test_entry_sret_byval_nested_fields_and_padding(tmp_path,sret_index,optimize):
    arguments=['ptr sret(%S) align 4 %out','ptr byval(%S) align 4 %in']
    if sret_index: arguments.reverse()
    source='''%S=type {i8,[2 x i16],i32}
define void @f('''+','.join(arguments)+''',i32 %delta){
 %value=load %S,ptr %in,align 4
 %old=extractvalue %S %value,2
 %sum=add i32 %old,%delta
 %result=insertvalue %S %value,i32 %sum,2
 store %S %result,ptr %out,align 4
 store %S zeroinitializer,ptr %in,align 4
 ret void}'''
    with font(tmp_path,source,optimize=optimize) as machine:
        assert machine.manifest['entry_abi']['sret']['parameter']==sret_index
        assert machine.manifest['parameters']==['in.0','in.1.0','in.1.1','in.2','delta']
        assert machine.invoke(7,123,456,0xffffffff,2)==(7,123,456,1)
        assert machine.invoke(1,2,3,4,5)==(1,2,3,9)


@pytest.mark.parametrize('target',['null','poison','%small','%unaligned','@readonly'])
def test_sret_validity_contract_even_without_stores_is_guarded(tmp_path,target):
    source='''@readonly=constant i64 0
define void @noop(ptr sret(i64) align 8 %p){ret void}
define i8 @f(i1 %run){
entry:
 %small=alloca i8
 %storage=alloca [16 x i8],align 8
 %unaligned=getelementptr i8,ptr %storage,i64 1
 br i1 %run,label %yes,label %no
yes:
 call void @noop(ptr sret(i64) align 8 TARGET)
 ret i8 77
no: ret i8 77}'''.replace('TARGET',target)
    with font(tmp_path,source,function='f') as machine:
        assert machine.invoke(0)==77
        with pytest.raises(WasmTrap,match='undefined_behavior'): machine.invoke(1)


def test_byval_poison_and_padding_are_copied_without_interpretation(tmp_path):
    source='''%S=type {i8,i32}
define i8 @g(ptr byval(%S) align 4 %p){%v=load i8,ptr %p
 ret i8 %v}
define i8 @f(i1 %read_poison){
 %s=alloca %S,align 4
 %a=insertvalue %S poison,i8 7,0
 store %S %a,ptr %s
 %r=call i8 @g(ptr byval(%S) align 4 %s)
 %v=select i1 %read_poison,i8 poison,i8 %r
 ret i8 %v}'''
    with font(tmp_path,source,function='f') as machine:
        assert machine.invoke(0)==7
        with pytest.raises(WasmTrap,match='poison_result'): machine.invoke(1)
    source=source.replace('%v=load i8,ptr %p','%q=getelementptr %S,ptr %p,i64 0,i32 1\n %w=load i32,ptr %q\n %v=trunc i32 %w to i8')
    with font(tmp_path,source,function='f') as machine:
        with pytest.raises(WasmTrap,match='poison_result'): machine.invoke(0)


def test_indirect_abi_compatibility_and_direct_mismatch(tmp_path):
    source='''define i32 @copy(ptr byval(i32) align 4 %p){%r=load i32,ptr %p
 ret i32 %r}
define i32 @raw(ptr %p){%r=load i32,ptr %p
 ret i32 %r}
define i32 @f(i1 %which,i32 %x){%p=alloca i32,align 4
 store i32 %x,ptr %p
 %fn=select i1 %which,ptr @copy,ptr @raw
 %r=call i32 %fn(ptr byval(i32) align 4 %p)
 ret i32 %r}'''
    with font(tmp_path,source,function='f') as machine:
        assert machine.manifest['indirect_calls'][0]['targets']==['copy']
        assert machine.invoke(1,42)==42
        with pytest.raises(WasmTrap,match='invalid_indirect_call'): machine.invoke(0,42)
    source=source.replace('%fn(ptr byval(i32) align 4 %p)','@copy(ptr %p)')
    with pytest.raises(LLVMError,match='signature mismatch'): compile_ir(source,function='f')


def test_abi_rejections_and_memory_limits():
    with pytest.raises(LLVMError,match='integer type'):
        compile_ir('define void @f(ptr sret({ptr}) %p){ret void}')
    with pytest.raises(LLVMError,match='zero-sized'):
        compile_ir('define void @f(ptr sret({}) %p){ret void}')
    with pytest.raises(ResourceLimit,match='byte budget'):
        compile_ir('define void @f(ptr sret([65 x i8]) %p){ret void}')
    with pytest.raises(LLVMError,match='ABI'):
        compile_ir('define i8 @f(ptr byref(i8) %p){ret i8 7}')
    # One caller object and two caller-owned byval copies need twelve bytes.
    source='''define void @g(ptr byval(i32) align 4 %p){ret void}
define i8 @f(){%p=alloca i32,align 4
 call void @g(ptr byval(i32) align 4 %p)
 call void @g(ptr byval(i32) align 4 %p)
 ret i8 7}'''
    with pytest.raises(ResourceLimit,match='max_memory_bytes'):
        compile_ir(source,function='f',limits=Limits(max_memory_bytes=8))


def test_abi_named_types_fonts_and_manifests_reproduce(tmp_path):
    source='''%Result=type {i8,i32}
define void @f(ptr sret(%Result) align 4 %p,i32 %x){
 %a=insertvalue %Result zeroinitializer,i8 7,0
 %r=insertvalue %Result %a,i32 %x,1
 store %Result %r,ptr %p
 ret void}'''
    first,second=tmp_path/'first.ttf',tmp_path/'second.ttf'
    manifest=build(source,first)
    for _ in range(5):
        compile_ir(source)
        gc.collect()  # Dispose modules before their isolated LLVM contexts.
    failures=[]
    for _ in range(3):
        try: compile_ir(source.replace('i32','i128'))
        except LLVMError as error: failures.append(error)
    gc.collect()  # Tracebacks may retain Lowering objects after a failed build.
    assert len(failures)==3
    failures.clear(); gc.collect()
    assert build(source,second)==manifest
    assert first.read_bytes()==second.read_bytes()
    module=llvm.parse_assembly(source)
    with font(tmp_path,module.as_bitcode()) as machine: assert machine.invoke(0x12345678)==(7,0x12345678)


class Triple(ctypes.Structure):
    _fields_=[('a',ctypes.c_uint64),('b',ctypes.c_uint64),('c',ctypes.c_uint64)]


@pytest.mark.parametrize('language',['clang','rust'])
def test_frontend_aggregate_abis_native_text_and_bitcode(tmp_path,language):
    if language=='clang':
        compiler=shutil.which('clang')
        if not compiler: pytest.skip('Clang unavailable')
        source=HERE/'examples/abi.c'
        base=[compiler,'-O1','-fno-vectorize','-fno-slp-vectorize',str(source)]
        native_command=base+['-shared','-fPIC']
        modes=[('ll','-S'),('bc','-c')]
        functions=['make_triple','call_triple','choose_triple']
    else:
        compiler=os.environ.get('RUSTC') or shutil.which('rustc')
        if not compiler: pytest.skip('Rust unavailable')
        source=HERE/'examples/abi.rs'
        base=[compiler,'--edition=2021','-C','opt-level=1','-C','panic=abort',str(source)]
        native_command=base+['--crate-type=cdylib']
        modes=[('ll','--emit=llvm-ir'),('bc','--emit=llvm-bc')]
        functions=['rust_triple','rust_call_triple','rust_choose_triple']
    native=tmp_path/'abi.dylib'
    subprocess.run(native_command+['-o',str(native)],check=True,capture_output=True)
    library=ctypes.CDLL(str(native))
    rng=random.Random(528)
    cases=[(0,0),(0xffffffffffffffff,1),(1<<63,(1<<63)-1)]+[(rng.getrandbits(64),rng.getrandbits(64)) for _ in range(25)]
    for suffix,mode in modes:
        path=tmp_path/f'abi.{suffix}'
        command=base+(['-emit-llvm',mode] if language=='clang' else ['--crate-type=lib',mode])
        subprocess.run(command+['-o',str(path)],check=True,capture_output=True)
        for function in functions:
            reference=getattr(library,function)
            choose='choose' in function
            scalar='call' in function
            reference.argtypes=([ctypes.c_uint32] if choose else [])+[ctypes.c_uint64]*2
            reference.restype=ctypes.c_uint64 if scalar else Triple
            with font(tmp_path,path,function=function) as machine:
                for i,(x,y) in enumerate(cases):
                    arguments=(i&1,x,y) if choose else (x,y)
                    expected=reference(*arguments)
                    if not scalar:
                        expected=(expected.a,expected.b,expected.c) if language=='clang' else tuple(bytes(expected))
                    assert machine.invoke(*arguments)==expected,(language,function,arguments)
        if language=='clang':
            # x86-64 Clang uses byval; compare C values through the host ABI.
            path=tmp_path/f'abi-x86.{suffix}'
            subprocess.run(base+['-target','x86_64-apple-macosx11.0.0','-emit-llvm',mode,'-o',str(path)],check=True,capture_output=True)
            reference=library.use_triple
            reference.argtypes=[Triple]; reference.restype=ctypes.c_uint64
            for function in ['use_triple','call_triple']:
                with font(tmp_path,path,function=function) as machine:
                    for x,y in cases:
                        if function=='use_triple':
                            arguments=(x,y,x^y)
                            expected=reference(Triple(*arguments))
                        else:
                            arguments=(x,y)
                            native_call=library.call_triple
                            native_call.argtypes=[ctypes.c_uint64]*2; native_call.restype=ctypes.c_uint64
                            expected=native_call(*arguments)
                        assert machine.invoke(*arguments)==expected
