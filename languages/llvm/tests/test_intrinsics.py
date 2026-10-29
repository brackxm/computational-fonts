# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Overflow, lifetime, immutable-data and memory-intrinsic differential tests."""
import ctypes
import itertools
import random
import shutil
import subprocess

import pytest
from llvmlite import binding as llvm

from test_llvm import HERE, font, evaluate, signed
from llvmfont import compile_ir, Limits, LLVMError
from fontcircuit.runtime import WasmTrap
from fontcircuit.gsub.circuit import ResourceLimit


def overflow_ir(op,width):
    return f'''declare {{i{width},i1}} @llvm.{op}.with.overflow.i{width}(i{width},i{width})
define {{i{width},i1}} @f(i{width} %a,i{width} %b) {{
 %r = call {{i{width},i1}} @llvm.{op}.with.overflow.i{width}(i{width} %a,i{width} %b)
 ret {{i{width},i1}} %r
}}'''


@pytest.mark.parametrize('op',['uadd','sadd','usub','ssub','umul','smul'])
def test_overflow_exhaustive_i8(op):
    program = compile_ir(overflow_ir(op,8))
    for a,b in itertools.product(range(256),repeat=2):
        x,y = (signed(a,8),signed(b,8)) if op[0]=='s' else (a,b)
        number = x+y if op[1:]=='add' else x-y if op[1:]=='sub' else x*y
        overflow = not (-128<=number<=127 if op[0]=='s' else 0<=number<=255)
        assert evaluate(program,[a,b])==((number&255,int(overflow)),set()),(op,a,b)


@pytest.mark.parametrize('width',[1,16,32,64])
@pytest.mark.parametrize('op',['uadd','sadd','usub','ssub','umul','smul'])
def test_overflow_native_llvm_and_harfbuzz(op,width,tmp_path):
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()
    source = overflow_ir(op,width)
    source += f'''
define i{width} @result(i{width} %a,i{width} %b) {{
 %r = call {{i{width},i1}} @f(i{width} %a,i{width} %b)
 %v = extractvalue {{i{width},i1}} %r,0
 ret i{width} %v
}}
define i8 @overflow(i{width} %a,i{width} %b) {{
 %r = call {{i{width},i1}} @f(i{width} %a,i{width} %b)
 %v = extractvalue {{i{width},i1}} %r,1
 %wide = zext i1 %v to i8
 ret i8 %wide
}}'''
    module = llvm.parse_assembly(source)
    module.triple = llvm.get_default_triple()
    target = llvm.Target.from_default_triple()
    typ = {1:ctypes.c_uint8,16:ctypes.c_uint16,32:ctypes.c_uint32,64:ctypes.c_uint64}[width]
    rng = random.Random(width)
    mask = (1<<width)-1
    with llvm.create_mcjit_compiler(module,target.create_target_machine()) as engine:
        engine.finalize_object()
        native_result = ctypes.CFUNCTYPE(typ,typ,typ)(engine.get_function_address('result'))
        native_flag = ctypes.CFUNCTYPE(ctypes.c_uint8,typ,typ)(engine.get_function_address('overflow'))
        with font(tmp_path,source,function='f') as machine:
            cases = [(mask,1),(0,1),(1<<(width-1),mask),(1<<(width-1),2&mask)]
            cases += [tuple(rng.getrandbits(width) for _ in range(2)) for _ in range(24)]
            for a,b in cases:
                assert machine.invoke(a,b)==(native_result(a,b)&mask,native_flag(a,b))


def test_overflow_poison_fields_and_select(tmp_path):
    source = overflow_ir('uadd',8).replace('i8 %a,i8 %b)\n ret','i8 poison,i8 %b)\n ret')
    # Poison propagates independently to both aggregate fields.
    with font(tmp_path,source) as machine:
        with pytest.raises(WasmTrap,match='poison_result'): machine.invoke(1,2)
    source = overflow_ir('uadd',8).replace('ret {i8,i1} %r','%ok = freeze {i8,i1} %r\n ret {i8,i1} %ok')
    with font(tmp_path,source) as machine: assert machine.invoke(255,1)==(0,1)


def test_immutable_arrays_strings_structs_and_constant_geps(tmp_path):
    source = r'''
%S = type {i8,[2 x i32]}
@table = private constant %S {i8 9,[2 x i32] [i32 123456,i32 -7]}, align 4
@bytes = internal constant [6 x i8] c"A\00\FF\22\5CZ",align 1
define {i32,i8,i8} @f(i8 %index) {
 %i = and i8 %index,1
 %p = getelementptr %S,ptr @table,i64 0,i32 1,i8 %i
 %v = load i32,ptr %p,align 4
 %c = load i8,ptr getelementptr ([6 x i8],ptr @bytes,i64 0,i64 2),align 1
 %q = insertvalue {i32,i8,i8} zeroinitializer,i32 %v,0
 %r = insertvalue {i32,i8,i8} %q,i8 %c,1
 %s = extractvalue %S {i8 3,[2 x i32] zeroinitializer},0
 %t = insertvalue {i32,i8,i8} %r,i8 %s,2
 ret {i32,i8,i8} %t
}'''
    with font(tmp_path,source) as machine:
        assert machine.invoke(0)==(123456,255,3)
        assert machine.invoke(1)==(0xfffffff9,255,3)


def test_immutable_global_store_guards(tmp_path):
    source = '''@g = constant i8 5
define i8 @f(i1 %write) {
 br i1 %write,label %bad,label %ok
bad: store i8 9,ptr @g
 br label %ok
ok: %v = load i8,ptr @g
 ret i8 %v
}'''
    with font(tmp_path,source) as machine:
        assert machine.invoke(0)==5
        with pytest.raises(WasmTrap,match='readonly_memory'): machine.invoke(1)
        assert machine.invoke(0)==5


@pytest.mark.parametrize('source,match',[
    ('@g = externally_initialized global i8 5\ndefine i8 @f(){ %v = load i8,ptr @g\nret i8 %v }','storage'),
    ('@g = external constant i8\ndefine i8 @f(){ %v = load i8,ptr @g\nret i8 %v }','defined globals'),
    ('declare i8 @external()\n@g = constant ptr @external\ndefine i1 @f(){ %r = icmp eq ptr @g,null\nret i1 %r }','function addresses'),
    ('@g = thread_local constant i8 5\ndefine i8 @f(){ %v = load i8,ptr @g\nret i8 %v }','storage'),
])
def test_unsupported_globals(source,match):
    with pytest.raises(LLVMError,match=match): compile_ir(source)


def lifetime_source(body):
    return '''declare void @llvm.lifetime.start.p0(i64 immarg,ptr nocapture)
declare void @llvm.lifetime.end.p0(i64 immarg,ptr nocapture)
define i8 @f(i1 %again) {
 %p = alloca i8,align 1
''' + body + '\n}'


def test_lifetime_initial_dead_and_use_after_end(tmp_path):
    for body in [
        '%x = load i8,ptr %p\ncall void @llvm.lifetime.start.p0(i64 1,ptr %p)\nret i8 %x',
        'call void @llvm.lifetime.start.p0(i64 1,ptr %p)\nstore i8 19,ptr %p\ncall void @llvm.lifetime.end.p0(i64 1,ptr %p)\n%x = load i8,ptr %p\nret i8 %x',
    ]:
        with font(tmp_path,lifetime_source(body)) as machine:
            with pytest.raises(WasmTrap,match='invalid_memory'): machine.invoke(0)


def test_lifetime_restart_poison_and_predication(tmp_path):
    source = lifetime_source('''
 call void @llvm.lifetime.start.p0(i64 1,ptr %p)
 store i8 19,ptr %p
 br i1 %again,label %reset,label %done
reset:
 call void @llvm.lifetime.end.p0(i64 1,ptr %p)
 call void @llvm.lifetime.end.p0(i64 1,ptr %p)
 call void @llvm.lifetime.start.p0(i64 -1,ptr %p)
 br label %done
done:
 %r = load i8,ptr %p
 ret i8 %r''')
    with font(tmp_path,source) as machine:
        assert machine.invoke(0)==19
        assert machine.invoke(1)==0  # Deterministic refinement of newly uninitialized bytes.
    source = lifetime_source('''
 call void @llvm.lifetime.start.p0(i64 1,ptr %p)
 call void @llvm.lifetime.start.p0(i64 1,ptr %p)
 %r = load i8,ptr %p
 ret i8 %r''')
    with font(tmp_path,source) as machine:
        with pytest.raises(WasmTrap,match='poison_result'): machine.invoke(0)


def copy_source(kind='memcpy',length='i64 %n',dest='%dest',src='@source',attributes=''):
    signature = f'llvm.{kind}.p0.p0.i64' if kind!='memset' else 'llvm.memset.p0.i64'
    second = 'i8' if kind=='memset' else 'ptr'
    call_src = 'i8 99' if kind=='memset' else 'ptr '+src
    return f'''@source = private constant [8 x i8] c"ABCDEFGH"
declare void @{signature}(ptr,{second},i64,i1 immarg)
define {{i8,i8,i8,i8}} @f(i64 %n) {{
 %dest = alloca [8 x i8],align 4
 store [8 x i8] zeroinitializer,ptr %dest,align 1
 call void @{signature}(ptr {attributes} {dest},{call_src},{length},i1 false)
 %p = load [8 x i8],ptr %dest,align 1
 %a = extractvalue [8 x i8] %p,0
 %b = extractvalue [8 x i8] %p,1
 %c = extractvalue [8 x i8] %p,2
 %d = extractvalue [8 x i8] %p,3
 %r0 = insertvalue {{i8,i8,i8,i8}} zeroinitializer,i8 %a,0
 %r1 = insertvalue {{i8,i8,i8,i8}} %r0,i8 %b,1
 %r2 = insertvalue {{i8,i8,i8,i8}} %r1,i8 %c,2
 %r3 = insertvalue {{i8,i8,i8,i8}} %r2,i8 %d,3
 ret {{i8,i8,i8,i8}} %r3
}}'''


@pytest.mark.parametrize('kind',['memcpy','memmove','memset'])
def test_dynamic_bulk_memory(kind,tmp_path):
    source = copy_source(kind)
    native_source = source+'''\ndefine i32 @oracle(i64 %n) {
 %r = call {i8,i8,i8,i8} @f(i64 %n)
 %a = extractvalue {i8,i8,i8,i8} %r,0
 %b = extractvalue {i8,i8,i8,i8} %r,1
 %c = extractvalue {i8,i8,i8,i8} %r,2
 %d = extractvalue {i8,i8,i8,i8} %r,3
 %aa = zext i8 %a to i32
 %bb = zext i8 %b to i32
 %cc = zext i8 %c to i32
 %dd = zext i8 %d to i32
 %bbb = shl i32 %bb,8
 %ccc = shl i32 %cc,16
 %ddd = shl i32 %dd,24
 %ab = or i32 %aa,%bbb
 %cd = or i32 %ccc,%ddd
 %value = or i32 %ab,%cd
 ret i32 %value
}'''
    llvm.initialize_native_target(); llvm.initialize_native_asmprinter()
    module = llvm.parse_assembly(native_source)
    module.triple = llvm.get_default_triple()
    target = llvm.Target.from_default_triple()
    with llvm.create_mcjit_compiler(module,target.create_target_machine()) as engine:
        engine.finalize_object()
        native = ctypes.CFUNCTYPE(ctypes.c_uint32,ctypes.c_uint64)(engine.get_function_address('oracle'))
        with font(tmp_path,source) as machine:
            for n in range(9):
                expected = tuple((99 if kind=='memset' else 65+i) if i<n else 0 for i in range(4))
                assert machine.invoke(n)==expected
                assert machine.invoke(n)==tuple(native(n)>>(i*8)&255 for i in range(4))
            for n in [9,1<<32,(1<<64)-1]:
                with pytest.raises(WasmTrap,match='invalid_memory'): machine.invoke(n)


def test_overlap_memmove_snapshot_and_memcpy_equal(tmp_path):
    base = '''declare void @llvm.KIND.p0.p0.i64(ptr,ptr,i64,i1 immarg)
define i64 @f() {
 %p = alloca i64,align 8
 store i64 578437695752307201,ptr %p,align 8
 %q = getelementptr i8,ptr %p,i64 1
 call void @llvm.KIND.p0.p0.i64(ptr %q,ptr %p,i64 7,i1 false)
 %r = load i64,ptr %p,align 8
 ret i64 %r
}'''
    with font(tmp_path,base.replace('KIND','memmove')) as machine:
        assert machine.invoke()==int.from_bytes(bytes([1,1,2,3,4,5,6,7]),'little')
    with font(tmp_path,base.replace('KIND','memcpy')) as machine:
        with pytest.raises(WasmTrap,match='memcpy_overlap'): machine.invoke()
    with font(tmp_path,base.replace('KIND','memcpy').replace('ptr %q,ptr %p','ptr %p,ptr %p')) as machine:
        assert machine.invoke()==578437695752307201


def test_copy_poison_zero_lengths_attributes_and_immutable_dest(tmp_path):
    declarations = 'declare void @llvm.memcpy.p0.p0.i64(ptr,ptr,i64,i1 immarg)\n'
    for pointers in ['ptr null,ptr null','ptr poison,ptr poison']:
        with font(tmp_path,declarations+f'define i8 @f() {{ call void @llvm.memcpy.p0.p0.i64({pointers},i64 0,i1 false)\nret i8 7 }}') as machine:
            assert machine.invoke()==7
    with font(tmp_path,copy_source(dest='null',length='i64 0',attributes='noundef nonnull')) as machine:
        with pytest.raises(WasmTrap,match='undefined_behavior'): machine.invoke(0)
    with font(tmp_path,copy_source(dest='@source',length='i64 1')) as machine:
        with pytest.raises(WasmTrap,match='readonly_memory'): machine.invoke(0)
    source = copy_source(src='%dest').replace('call void @llvm.memcpy','store i8 poison,ptr %dest\n call void @llvm.memcpy')
    with font(tmp_path,source) as machine:
        with pytest.raises(WasmTrap,match='poison_result'): machine.invoke(1)


def test_disjoint_range_noundef_and_gep_nuw(tmp_path):
    source = 'define range(i8 -2, 3) i8 @f(i8 %x) { ret i8 %x }'
    with font(tmp_path,source) as machine:
        for x in [254,255,0,1,2]: assert machine.invoke(x)==x
        for x in [3,253]:
            with pytest.raises(WasmTrap,match='poison_result'): machine.invoke(x)
    source = 'define i8 @f(i8 %x) { %r = or disjoint i8 %x,1\nret i8 %r }'
    with font(tmp_path,source) as machine:
        assert machine.invoke(2)==3
        with pytest.raises(WasmTrap,match='poison_result'): machine.invoke(1)
    source = '''define i1 @f() {
 %p = alloca [8 x i8]
 %q = getelementptr i8,ptr %p,i64 4
 %r = getelementptr inbounds nuw i8,ptr %q,i64 -1
 %x = freeze ptr %r
 %c = icmp eq ptr %x,null
 ret i1 %c
}'''
    with font(tmp_path,source) as machine: assert machine.invoke()==1


@pytest.mark.parametrize('function,inputs',[
    ('constant_lookup',[(i,) for i in range(12)]),
    ('copied_array',[(i,i*17) for i in range(12)]),
    ('checked_add',[(0,0),(0xffffffff,1),(0x7fffffff,0x7fffffff)]),
    ('checked_multiply',[(0,0),(0x80000000,0xffffffff),(0x7fffffff,2)]),
])
def test_clang_optimized_native_and_bitcode(function,inputs,tmp_path):
    clang = shutil.which('clang')
    if not clang: pytest.skip('Clang unavailable')
    native = tmp_path/'reference.dylib'
    assembly = tmp_path/'reference.ll'
    bitcode = tmp_path/'reference.bc'
    source = HERE/'examples/intrinsics.c'
    subprocess.run([clang,'-O1','-shared','-fPIC',str(source),'-o',str(native)],check=True,capture_output=True)
    for target,flag in [(assembly,'-S'),(bitcode,'-c')]:
        subprocess.run([clang,'-O1','-fno-vectorize','-fno-slp-vectorize','-emit-llvm',flag,str(source),'-o',str(target)],check=True,capture_output=True)
    library = ctypes.CDLL(str(native))
    reference = getattr(library,function)
    reference.argtypes = [ctypes.c_uint32]*len(inputs[0])
    reference.restype = ctypes.c_uint64 if function.startswith('checked_') else ctypes.c_uint32
    rng = random.Random(47)
    inputs = inputs + [tuple(rng.getrandbits(32) for _ in inputs[0]) for _ in range(30)]
    for source in [assembly,bitcode]:
        with font(tmp_path,source,function=function) as machine:
            for args in inputs: assert machine.invoke(*args)==reference(*args)


def test_rust_optimized_native_and_bitcode(tmp_path):
    import os
    rustc = os.environ.get('RUSTC') or shutil.which('rustc')
    if not rustc: pytest.skip('rustc unavailable')
    native = tmp_path/'rust.dylib'
    assembly = tmp_path/'rust.ll'
    bitcode = tmp_path/'rust.bc'
    source = HERE/'examples/intrinsics.rs'
    base = [rustc,'--edition=2021','-C','opt-level=1','-C','panic=abort',str(source)]
    subprocess.run(base+['--crate-type=cdylib','-o',str(native),'--cfg','native_reference'],check=True,capture_output=True)
    for target,kind in [(assembly,'llvm-ir'),(bitcode,'llvm-bc')]:
        subprocess.run(base+['--crate-type=lib','--emit='+kind,'-o',str(target)],check=True,capture_output=True)
    library = ctypes.CDLL(str(native))
    rng = random.Random(98)
    for name in ['rust_lookup','rust_checked_add','rust_checked_multiply']:
        reference = getattr(library,name)
        reference.argtypes = [ctypes.c_uint32]*(1 if name=='rust_lookup' else 2)
        reference.restype = ctypes.c_uint32 if name=='rust_lookup' else ctypes.c_uint64
        cases = [tuple(rng.getrandbits(32) for _ in reference.argtypes) for _ in range(50)]
        cases += [(0xffffffff,1),(0x80000000,0xffffffff)] if len(reference.argtypes)==2 else [(0,),(3,)]
        for source in [assembly,bitcode]:
            with font(tmp_path,source,function=name) as machine:
                for args in cases: assert machine.invoke(*args)==reference(*args)


def test_copy_alignment_dereferenceability_and_inline(tmp_path):
    decl = 'declare void @llvm.memcpy.p0.p0.i64(ptr,ptr,i64,i1 immarg)\n'
    for attribute,should_trap in [('align 4',False),('noundef align 4',True)]:
        source = decl+f'''define i8 @f() {{
 %p = alloca [8 x i8],align 8
 %q = getelementptr i8,ptr %p,i64 1
 call void @llvm.memcpy.p0.p0.i64(ptr {attribute} %q,ptr null,i64 0,i1 false)
 ret i8 7
}}'''
        with font(tmp_path,source) as machine:
            if should_trap:
                with pytest.raises(WasmTrap,match='undefined_behavior'): machine.invoke()
            else: assert machine.invoke()==7
    with font(tmp_path,copy_source(dest='null',length='i64 0',attributes='dereferenceable(1)')) as machine:
        with pytest.raises(WasmTrap,match='undefined_behavior'): machine.invoke(0)
    source = copy_source(length='i64 8').replace('llvm.memcpy.','llvm.memcpy.inline.')
    with font(tmp_path,source) as machine: assert machine.invoke(0)==(65,66,67,68)
    source = copy_source('memset',length='i64 8').replace('llvm.memset.','llvm.memset.inline.')
    with font(tmp_path,source) as machine: assert machine.invoke(0)==(99,99,99,99)


def test_lifetime_in_loop_and_zero_gep(tmp_path):
    source = '''declare void @llvm.lifetime.start.p0(i64 immarg,ptr nocapture)
declare void @llvm.lifetime.end.p0(i64 immarg,ptr nocapture)
define i8 @f(i8 %n) {
entry:
 %p = alloca i8
 %zero = getelementptr i8,ptr %p,i64 0
 br label %loop
loop:
 %i = phi i8 [0,%entry],[%next,%loop]
 %total = phi i8 [0,%entry],[%added,%loop]
 call void @llvm.lifetime.start.p0(i64 1,ptr %zero)
 store i8 %i,ptr %p
 %value = load i8,ptr %p
 %added = add i8 %total,%value
 call void @llvm.lifetime.end.p0(i64 1,ptr %p)
 %next = add i8 %i,1
 %again = icmp ult i8 %next,%n
 br i1 %again,label %loop,label %exit
exit: ret i8 %added
}'''
    with font(tmp_path,source) as machine:
        for n in range(1,12): assert machine.invoke(n)==n*(n-1)//2


def test_bulk_memory_and_lifetime_rejections():
    with pytest.raises(LLVMError,match='volatile'):
        compile_ir(copy_source().replace('i1 false','i1 true'))
    with pytest.raises(ResourceLimit,match='max_memory_bytes'):
        compile_ir('@g = constant [128 x i8] zeroinitializer\ndefine i8 @f(){ %v = load i8,ptr @g\nret i8 %v }')
    with pytest.raises(LLVMError,match='absolute-address'):
        compile_ir('@g = constant i8 7,!absolute_symbol !0\ndefine i8 @f(){ %v = load i8,ptr @g\nret i8 %v }\n!0 = !{i64 0,i64 8}')
    source = lifetime_source('call void @llvm.lifetime.start.p0(i64 2,ptr %p)\nret i8 0')
    with pytest.raises(LLVMError,match='complete allocation'): compile_ir(source)
    source = '''declare void @llvm.lifetime.start.p0(i64 immarg,ptr nocapture)
define void @f(ptr %p) {call void @llvm.lifetime.start.p0(i64 1,ptr %p)
ret void}'''
    with pytest.raises(LLVMError,match='local alloca'): compile_ir(source)


def test_formal_call_and_return_range_contracts(tmp_path):
    source = '''define i8 @g(i8 range(i8 3, 10) %x) { ret i8 %x }
define i8 @f(i8 %x) {
 %r = call range(i8 4, 9) i8 @g(i8 %x)
 ret i8 %r
}'''
    with font(tmp_path,source,function='f') as machine:
        for x in [4,8]: assert machine.invoke(x)==x
        for x in [2,3,9,10]:
            with pytest.raises(WasmTrap,match='poison_result'): machine.invoke(x)
    source = '''define i8 @f() {
 %p = alloca i8
 store i8 poison,ptr %p
 %r = load i8,ptr %p,!noundef !0
 ret i8 7
}
!0 = !{}'''
    with font(tmp_path,source) as machine:
        with pytest.raises(WasmTrap,match='undefined_behavior'): machine.invoke()
    source = '''define i8 @f() {
 %p = alloca i8
 store i8 poison,ptr %p
 %"!noundef" = load i8,ptr %p
 ret i8 7
}'''
    with font(tmp_path,source) as machine: assert machine.invoke()==7
