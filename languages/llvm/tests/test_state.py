# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Saturation and provenance-preserving bounded global/pointer memory."""
import ctypes
import itertools
import os
import random
import shutil
import subprocess

import pytest
from llvmlite import binding as llvm

from test_llvm import HERE, font, evaluate, signed
from llvmfont import compile_ir, LLVMError, Limits
from fontcircuit.runtime import WasmTrap


def saturation_ir(op,width):
    return f'''declare i{width} @llvm.{op}.sat.i{width}(i{width},i{width})
define i{width} @f(i{width} %a,i{width} %b) {{
 %r = call i{width} @llvm.{op}.sat.i{width}(i{width} %a,i{width} %b)
 ret i{width} %r
}}'''


def saturation_reference(op,a,b,width):
    x,y = (signed(a,width),signed(b,width)) if op[0]=='s' else (a,b)
    value = x+y if op[1:]=='add' else x-y if op[1:]=='sub' else x<<b
    low,high = (-(1<<(width-1)),(1<<(width-1))-1) if op[0]=='s' else (0,(1<<width)-1)
    return max(low,min(high,value))&((1<<width)-1)


@pytest.mark.parametrize('op',['uadd','sadd','usub','ssub','ushl','sshl'])
def test_saturation_exhaustive_i8(op):
    program = compile_ir(saturation_ir(op,8))
    for a,b in itertools.product(range(256),repeat=2):
        result,flags = evaluate(program,[a,b])
        if op.endswith('shl') and b>=8:
            assert 'trap.poison_result' in flags
        else:
            assert not flags,(op,a,b)
            assert result==(saturation_reference(op,a,b,8),)


@pytest.mark.parametrize('width',[1,8,16,32,64])
@pytest.mark.parametrize('op',['uadd','sadd','usub','ssub','ushl','sshl'])
def test_saturation_native_llvm_and_harfbuzz(op,width,tmp_path):
    llvm.initialize_native_target(); llvm.initialize_native_asmprinter()
    source = saturation_ir(op,width)
    module = llvm.parse_assembly(source)
    module.triple = llvm.get_default_triple()
    target = llvm.Target.from_default_triple()
    typ = {1:ctypes.c_uint8,8:ctypes.c_uint8,16:ctypes.c_uint16,32:ctypes.c_uint32,64:ctypes.c_uint64}[width]
    rng = random.Random(width)
    mask = (1<<width)-1
    cases = [(mask,1),(1<<(width-1),mask),(0,mask),(1<<(width-1),1)]
    cases += [tuple(rng.getrandbits(width) for _ in range(2)) for _ in range(30)]
    with llvm.create_mcjit_compiler(module,target.create_target_machine()) as engine:
        engine.finalize_object()
        reference = ctypes.CFUNCTYPE(typ,typ,typ)(engine.get_function_address('f'))
        with font(tmp_path,source) as machine:
            for a,b in cases:
                if op.endswith('shl'): b %= width
                assert machine.invoke(a,b)==reference(a,b)&mask
            if op.endswith('shl'):
                with pytest.raises(WasmTrap,match='poison_result'): machine.invoke(0,width)


def test_saturation_poison_select_and_freeze(tmp_path):
    source = '''declare i8 @llvm.sadd.sat.i8(i8,i8)
define i8 @f(i1 %pick) {
 %p = call i8 @llvm.sadd.sat.i8(i8 poison,i8 1)
 %r = select i1 %pick,i8 %p,i8 42
 ret i8 %r
}'''
    with font(tmp_path,source) as machine:
        assert machine.invoke(0)==42
        with pytest.raises(WasmTrap,match='poison_result'): machine.invoke(1)
    with font(tmp_path,source.replace('ret i8 %r','%s = freeze i8 %r\nret i8 %s')) as machine:
        assert machine.invoke(1)==0


def test_mutable_global_native_fresh_instance_and_calls(tmp_path):
    source = '''@counter = global i32 3
define i32 @step(i32 %x) {
 %v = load i32,ptr @counter
 %next = add i32 %v,%x
 store i32 %next,ptr @counter
 ret i32 %next
}
define i32 @f(i32 %a,i32 %b) {
 %x = call i32 @step(i32 %a)
 %y = call i32 @step(i32 %b)
 %r = xor i32 %x,%y
 ret i32 %r
}'''
    llvm.initialize_native_target(); llvm.initialize_native_asmprinter()
    module = llvm.parse_assembly(source); module.triple = llvm.get_default_triple()
    target = llvm.Target.from_default_triple()
    with llvm.create_mcjit_compiler(module,target.create_target_machine()) as engine:
        engine.finalize_object()
        reference = ctypes.CFUNCTYPE(ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32)(engine.get_function_address('f'))
        state = ctypes.c_uint32.from_address(engine.get_global_value_address('counter'))
        with font(tmp_path,source,function='f') as machine:
            assert machine.manifest['global_state']=='fresh-per-shape'
            assert machine.manifest['mutable_globals']==['counter']
            rng = random.Random(97)
            for a,b in [(2,3),(2,3),(0xffffffff,2)] + [tuple(rng.getrandbits(32) for _ in range(2)) for _ in range(60)]:
                state.value = 3  # A font invocation is a new module instance.
                assert machine.invoke(a,b)==reference(a,b)


def test_cyclic_global_initializers_and_pointer_fields(tmp_path):
    source = '''%Node = type {i32,ptr}
@head = global ptr @one
@one = global %Node {i32 10,ptr @two}
@two = global %Node {i32 20,ptr @one}
define i32 @f(i32 %x) {
 %p = load ptr,ptr @head
 %next = getelementptr %Node,ptr %p,i64 0,i32 1
 %q = load ptr,ptr %next
 store i32 %x,ptr %q
 %back = getelementptr %Node,ptr %q,i64 0,i32 1
 %first = load ptr,ptr %back
 %a = load i32,ptr %first
 %b = load i32,ptr %q
 %r = add i32 %a,%b
 ret i32 %r
}'''
    with font(tmp_path,source) as machine:
        assert machine.manifest['pointer_memory']=='opaque-provenance-v1'
        for value in [0,1,17,0xffffffff]: assert machine.invoke(value)==(10+value)&0xffffffff


def test_pointer_aggregates_copy_and_dynamic_aliasing(tmp_path):
    source = '''declare void @llvm.memcpy.p0.p0.i64(ptr,ptr,i64,i1 immarg)
define i32 @f(i1 %choose,i32 %value) {
 %a = alloca i32,align 4
 %b = alloca i32,align 4
 %src = alloca {i32,ptr},align 8
 %dst = alloca {i32,ptr},align 8
 store i32 7,ptr %a
 store i32 11,ptr %b
 %p = select i1 %choose,ptr %a,ptr %b
 %s = insertvalue {i32,ptr} zeroinitializer,i32 %value,0
 %t = insertvalue {i32,ptr} %s,ptr %p,1
 store {i32,ptr} %t,ptr %src,align 8
 call void @llvm.memcpy.p0.p0.i64(ptr %dst,ptr %src,i64 16,i1 false)
 %copy = load {i32,ptr},ptr %dst,align 8
 %number = extractvalue {i32,ptr} %copy,0
 %pointer = extractvalue {i32,ptr} %copy,1
 store i32 %number,ptr %pointer
 %x = load i32,ptr %a
 %y = load i32,ptr %b
 %r = add i32 %x,%y
 ret i32 %r
}'''
    with font(tmp_path,source) as machine:
        for choose in range(2):
            for value in [0,17,0xffffffff]:
                assert machine.invoke(choose,value)==(value+(11 if choose else 7))&0xffffffff


def test_null_pointer_zeroing_and_unaligned_memmove(tmp_path):
    source = '''declare void @llvm.memset.p0.i64(ptr,i8,i64,i1 immarg)
define i1 @f() {
 %p = alloca ptr,align 8
 call void @llvm.memset.p0.i64(ptr %p,i8 0,i64 8,i1 false)
 %q = load ptr,ptr %p
 %r = icmp eq ptr %q,null
 ret i1 %r
}'''
    with font(tmp_path,source) as machine: assert machine.invoke()==1
    source = '''declare void @llvm.memmove.p0.p0.i64(ptr,ptr,i64,i1 immarg)
define i32 @f(i32 %value) {
 %a = alloca i32,align 4
 %bytes = alloca [16 x i8],align 8
 store i32 %value,ptr %a
 store ptr %a,ptr %bytes,align 8
 %dest = getelementptr i8,ptr %bytes,i64 1
 call void @llvm.memmove.p0.p0.i64(ptr %dest,ptr %bytes,i64 8,i1 false)
 %p = load ptr,ptr %dest,align 1
 %r = load i32,ptr %p
 ret i32 %r
}'''
    with font(tmp_path,source) as machine:
        for value in [0,91,0xffffffff]: assert machine.invoke(value)==value


def test_pointer_returns_caller_memory_and_dangling_diagnostics(tmp_path):
    source = '''define fastcc nonnull ptr @identity(ptr noundef nonnull returned align 4 dereferenceable(4) %p) {
 ret ptr %p
}
define i32 @f(i32 %x) {
 %p = alloca i32,align 4
 store i32 %x,ptr %p
 %q = call fastcc ptr @identity(ptr %p)
 %r = load i32,ptr %q
 ret i32 %r
}'''
    with font(tmp_path,source,function='f') as machine: assert machine.invoke(123)==123
    source = '''define ptr @leak() { %p = alloca i32
 ret ptr %p }
define i1 @f() {
 %p = call ptr @leak()
 %q = getelementptr inbounds i32,ptr %p,i64 1
 %r = icmp eq ptr %p,%q
 ret i1 %r
}'''
    with font(tmp_path,source,function='f') as machine: assert machine.invoke()==0
    source = source.replace('%r = icmp eq ptr %p,%q','%v = load i32,ptr %p\n %r = icmp eq i32 %v,0')
    with font(tmp_path,source,function='f') as machine:
        with pytest.raises(WasmTrap,match='invalid_memory'): machine.invoke()


def test_unsupported_pointer_byte_interpretation_and_corruption(tmp_path):
    source = '''define i32 @f() {
 %a = alloca i32
 %slot = alloca ptr,align 8
 store ptr %a,ptr %slot
 %byte = load i8,ptr %slot
 %r = zext i8 %byte to i32
 ret i32 %r
}'''
    with font(tmp_path,source) as machine:
        with pytest.raises(WasmTrap,match='pointer_as_integer'): machine.invoke()
    source = '''define i1 @f() {
 %a = alloca i32
 %slot = alloca ptr,align 8
 store ptr %a,ptr %slot
 store i8 0,ptr %slot
 %p = load ptr,ptr %slot
 %r = icmp eq ptr %p,null
 ret i1 %r
}'''
    with font(tmp_path,source) as machine:
        with pytest.raises(WasmTrap,match='pointer_representation'): machine.invoke()
    source = source.replace('store ptr %a,ptr %slot\n store i8 0,ptr %slot','store i64 1,ptr %slot')
    with font(tmp_path,source) as machine:
        with pytest.raises(WasmTrap,match='pointer_representation'): machine.invoke()


def test_pointer_poison_freeze_and_inactive_paths(tmp_path):
    source = '''define i1 @f() {
 %p = alloca ptr
 store ptr poison,ptr %p
 %q = load ptr,ptr %p
 %f = freeze ptr %q
 %r = icmp eq ptr %f,null
 ret i1 %r
}'''
    with font(tmp_path,source) as machine: assert machine.invoke()==1
    source = '''@target = global i32 7
@pointer = constant ptr @target
define i32 @f(i1 %take,i32 %value) {
 br i1 %take,label %yes,label %exit
yes:
 %p = load ptr,ptr @pointer
 store i32 %value,ptr %p
 br label %exit
exit: %r = load i32,ptr @target
 ret i32 %r
}'''
    with font(tmp_path,source) as machine:
        assert machine.invoke(0,123)==7
        assert machine.invoke(1,123)==123
        assert machine.invoke(0,123)==7


def test_module_initializers_and_call_convention_rejections():
    source = '''@g = global i32 0
@llvm.global_dtors = appending global [1 x {i32,ptr,ptr}] [{i32,ptr,ptr} {i32 65535,ptr @init,ptr null}]
define void @init() { store i32 7,ptr @g
 ret void }
define i32 @f() { %v = load i32,ptr @g
 ret i32 %v }'''
    with pytest.raises(LLVMError,match='destructors'): compile_ir(source,function='f')
    source = 'define fastcc i32 @helper(i32 %x) {ret i32 %x}\ndefine i32 @f(i32 %x) {%r = call i32 @helper(i32 %x)\nret i32 %r}'
    with pytest.raises(LLVMError,match='mismatch'): compile_ir(source,function='f')


@pytest.mark.parametrize('language',['clang','rust'])
def test_optimized_state_programs_against_native(language,tmp_path):
    if language=='clang':
        compiler = shutil.which('clang')
        if not compiler: pytest.skip('Clang unavailable')
        src = HERE/'examples/state.c'
        native = tmp_path/'state.dylib'
        subprocess.run([compiler,'-O1','-shared','-fPIC',str(src),'-o',str(native)],check=True,capture_output=True)
        outputs = []
        for suffix,mode in [('ll','-S'),('bc','-c')]:
            path = tmp_path/('state.'+suffix)
            subprocess.run([compiler,'-O1','-fno-vectorize','-fno-slp-vectorize','-emit-llvm',mode,str(src),'-o',str(path)],check=True,capture_output=True)
            outputs.append(path)
    else:
        compiler = os.environ.get('RUSTC') or shutil.which('rustc')
        if not compiler: pytest.skip('Rust unavailable')
        src = HERE/'examples/state.rs'
        native = tmp_path/'state.dylib'
        base = [compiler,'--edition=2021','-C','opt-level=1','-C','panic=abort',str(src)]
        subprocess.run(base+['--crate-type=cdylib','--cfg','native_reference','-o',str(native)],check=True,capture_output=True)
        outputs = []
        for suffix,mode in [('ll','llvm-ir'),('bc','llvm-bc')]:
            path = tmp_path/('state.'+suffix)
            subprocess.run(base+['--crate-type=lib','--emit='+mode,'-o',str(path)],check=True,capture_output=True)
            outputs.append(path)
    library = ctypes.CDLL(str(native))
    rng = random.Random(10)
    for name in ['saturating_add','saturating_sub','global_calls','pointer_table','pointer_copy']:
        function = ('rust_' if language=='rust' else '')+name
        reference = getattr(library,function)
        reference.argtypes = [ctypes.c_uint32,ctypes.c_uint32]
        reference.restype = ctypes.c_uint32
        cases = [(0,0),(0xffffffff,1),(0x80000000,0x7fffffff),(0xffffffff,0xffffffff)]
        cases += [tuple(rng.getrandbits(32) for _ in range(2)) for _ in range(50)]
        for path in outputs:
            with font(tmp_path,path,function=function) as machine:
                for a,b in cases: assert machine.invoke(a,b)==reference(a,b),(language,name,a,b)
