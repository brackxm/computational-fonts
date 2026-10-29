# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Closed-world function addresses, checked indirect dispatch and module startup."""
import ctypes
import os
import random
import shutil
import subprocess

import pytest
from llvmlite import binding as llvm

from test_llvm import HERE, font
from llvmfont import compile_ir, Limits, LLVMError
from fontcircuit.runtime import WasmTrap, ExecutionBoundExceeded, IncompleteShaping
from fontcircuit.gsub.circuit import ResourceLimit


CALLBACKS = '''define i32 @add(i32 %a,i32 %b) { %r=add i32 %a,%b
 ret i32 %r }
define i32 @sub(i32 %a,i32 %b) { %r=sub i32 %a,%b
 ret i32 %r }
'''


def test_table_dispatch_native_and_actual_glyph_substitutions(tmp_path):
    source = CALLBACKS+'''
@table = constant [2 x ptr] [ptr @add,ptr @sub]
define i32 @f(i1 %which,i32 %a,i32 %b) {
 %index = zext i1 %which to i64
 %p = getelementptr [2 x ptr],ptr @table,i64 0,i64 %index
 %callee = load ptr,ptr %p
 %r = call i32 %callee(i32 %a,i32 %b)
 ret i32 %r
}'''
    llvm.initialize_native_target(); llvm.initialize_native_asmprinter()
    module = llvm.parse_assembly(source); module.triple = llvm.get_default_triple()
    with llvm.create_mcjit_compiler(module,llvm.Target.from_default_triple().create_target_machine()) as engine:
        engine.finalize_object()
        native = ctypes.CFUNCTYPE(ctypes.c_uint32,ctypes.c_uint8,ctypes.c_uint32,ctypes.c_uint32)(engine.get_function_address('f'))
        with font(tmp_path,source,function='f') as machine:
            assert machine.manifest['indirect_calls'][0]['targets']==['add','sub']
            rng=random.Random(74)
            for which in range(2):
                for _ in range(60):
                    a,b=rng.getrandbits(32),rng.getrandbits(32)
                    assert machine.invoke(which,a,b)==native(which,a,b)
            before=machine.encode([1,9,3])
            after=machine.shaper.shape(before)
            assert before!=after and machine.decode(after)==(6,)
            with pytest.raises(IncompleteShaping): machine.decode(machine.shaper.shape(before,enabled=False))


def test_function_pointer_parameters_returns_select_and_phi(tmp_path):
    source = CALLBACKS+'''
define ptr @choose(i1 %which) {
 %p = select i1 %which,ptr @sub,ptr @add
 ret ptr %p
}
define i32 @apply(ptr %p,i32 %a,i32 %b) {
 %r = call i32 %p(i32 %a,i32 %b)
 ret i32 %r
}
define i32 @f(i1 %which,i32 %a,i32 %b) {
entry:
 %p = call ptr @choose(i1 %which)
 br i1 %which,label %yes,label %no
yes: br label %end
no: br label %end
end:
 %q = phi ptr [%p,%yes],[@add,%no]
 %r = call i32 @apply(ptr %q,i32 %a,i32 %b)
 ret i32 %r
}'''
    with font(tmp_path,source,function='f') as machine:
        assert machine.invoke(0,20,7)==27
        assert machine.invoke(1,20,7)==13


def test_callback_discovery_fixed_point_and_side_effect_guards(tmp_path):
    source='''@state = global i32 0
@other = global ptr @second
define i32 @first(i32 %a) {
 %p = load ptr,ptr @other
 %r = call i32 %p(i32 %a)
 ret i32 %r
}
define i32 @second(i32 %a) {
 store i32 %a,ptr @state
 ret i32 %a
}
define i32 @untaken(i32 %a) {
 store i32 99,ptr @state
 %bad = udiv i32 1,0
 ret i32 %bad
}
define i32 @f(i32 %a) {
 %p = select i1 true,ptr @first,ptr @untaken
 %v = call i32 %p(i32 %a)
 %r = load i32,ptr @state
 ret i32 %r
}'''
    with font(tmp_path,source,function='f',limits=Limits(max_call_depth=3)) as machine:
        assert any('second' in site['targets'] for site in machine.manifest['indirect_calls'])
        for a in [0,17,0xffffffff]: assert machine.invoke(a)==a


@pytest.mark.parametrize('target',['null','poison','undef','%offset','%data','%wrong','%fast'])
def test_invalid_indirect_targets_are_diagnostics(target,tmp_path):
    source='''@data = global i32 0
define i32 @ok(i32 %a) {ret i32 %a}
define i64 @wrong(i64 %a) {ret i64 %a}
define fastcc i32 @fast(i32 %a) {ret i32 %a}
define i32 @f() {
 %offset = getelementptr i8,ptr @ok,i64 1
 %data = select i1 true,ptr @data,ptr null
 %wrong = select i1 true,ptr @wrong,ptr null
 %fast = select i1 true,ptr @fast,ptr null
 %r = call i32 TARGET(i32 7)
 ret i32 %r
}'''.replace('TARGET',target)
    with font(tmp_path,source,function='f') as machine:
        with pytest.raises(WasmTrap,match='invalid_indirect_call'): machine.invoke()


def test_mutable_callback_slot_and_memcpy(tmp_path):
    source=CALLBACKS+'''@slot = global ptr @add
declare void @llvm.memcpy.p0.p0.i64(ptr,ptr,i64,i1 immarg)
define i32 @f(i1 %subtract,i32 %a,i32 %b) {
 %p = select i1 %subtract,ptr @sub,ptr @add
 store ptr %p,ptr @slot
 %copy = alloca ptr,align 8
 call void @llvm.memcpy.p0.p0.i64(ptr %copy,ptr @slot,i64 8,i1 false)
 %q = load ptr,ptr %copy
 %r = call i32 %q(i32 %a,i32 %b)
 ret i32 %r
}'''
    with font(tmp_path,source,function='f') as machine:
        for which in [0,1,1,0]: assert machine.invoke(which,7,3)==(4 if which else 10)


def test_indirect_recursion_depth_limit(tmp_path):
    source='''@p = constant ptr @recurse
define i8 @recurse(i8 %n) {
entry:
 %done=icmp eq i8 %n,0
 br i1 %done,label %exit,label %body
exit: ret i8 0
body:
 %next=sub i8 %n,1
 %callback=load ptr,ptr @p
 %r=call i8 %callback(i8 %next)
 %out=add i8 %r,1
 ret i8 %out
}
define i8 @f(i8 %n) {
 %p = load ptr,ptr @p
 %r = call i8 %p(i8 %n)
 ret i8 %r
}'''
    with font(tmp_path,source,function='f',limits=Limits(max_call_depth=4)) as machine:
        assert machine.invoke(2)==2
        with pytest.raises(ExecutionBoundExceeded,match='call_depth'): machine.invoke(3)


def test_constructor_priorities_associated_symbols_and_callback_installation(tmp_path):
    source='''@state=global i32 0
@selected=global ptr null
@retained=global i8 0
@llvm.global_ctors=appending global [2 x {i32,ptr,ptr}] [
 {i32,ptr,ptr} {i32 202,ptr @last,ptr @retained},
 {i32,ptr,ptr} {i32 101,ptr @first,ptr null}]
define void @first(){store i32 7,ptr @state
 ret void}
define void @last(){%x=load i32,ptr @state
 %y=mul i32 %x,3
 %z=add i32 %y,1
 store i32 %z,ptr @state
 store ptr @callback,ptr @selected
 ret void}
define i32 @callback(i32 %x){%v=load i32,ptr @state
 %r=add i32 %v,%x
 ret i32 %r}
define i32 @f(i32 %x){
 %p=load ptr,ptr @selected
 %r=call i32 %p(i32 %x)
 ret i32 %r}'''
    clang=shutil.which('clang')
    if not clang: pytest.skip('Clang required to validate loader constructor priorities')
    path=tmp_path/'priority.ll'; path.write_text(source)
    native=tmp_path/'priority.dylib'
    # MCJIT.run_static_constructors executes raw array order; the native
    # assembler/linker pipeline implements LLVM's priority ordering.
    subprocess.run([clang,'-O0','-shared','-fPIC',str(path),'-o',str(native)],check=True,capture_output=True)
    library=ctypes.CDLL(str(native)); reference=library.f
    reference.argtypes=[ctypes.c_uint32]; reference.restype=ctypes.c_uint32
    with font(tmp_path,source,function='f') as machine:
        assert [item['priority'] for item in machine.manifest['constructors']]==[101,202]
        for x in [0,1,0xffffffff,100]: assert machine.invoke(x)==reference(x)


@pytest.mark.parametrize('section',['.init_array','.init_array.00101','__DATA,__mod_init_func','__DATA_CONST,__mod_init_func'])
def test_initializer_section_cells_and_arrays(section,tmp_path):
    for typ,value in [('ptr','@init'),('[1 x ptr]','[ptr @init]')]:
        source=f'''@state=global i32 0
@startup=constant {typ} {value},section "{section}"
define void @init() {{store i32 27,ptr @state
 ret void}}
define i32 @f() {{%r=load i32,ptr @state
 ret i32 %r}}'''
        with font(tmp_path,source,function='f') as machine: assert machine.invoke()==27


def test_constructor_faults_bounds_and_fresh_instances(tmp_path):
    source='''@g=global i32 0
@llvm.global_ctors=appending global [1 x {i32,ptr,ptr}] [{i32,ptr,ptr} {i32 101,ptr @init,ptr null}]
define void @init(){%v=load i32,ptr @g
 %next=add i32 %v,1
 store i32 %next,ptr @g
 ret void}
define i32 @f(){%r=load i32,ptr @g
 ret i32 %r}'''
    with font(tmp_path,source,function='f') as machine:
        assert machine.invoke()==1 and machine.invoke()==1
    with font(tmp_path,source.replace('%v=load i32,ptr @g','%bad=udiv i32 1,0\n %v=load i32,ptr @g'),function='f') as machine:
        with pytest.raises(WasmTrap,match='undefined_behavior'): machine.invoke()
    loop=source.replace('define void @init(){%v=load i32,ptr @g\n %next=add i32 %v,1\n store i32 %next,ptr @g\n ret void}',
                        'define void @init(){entry: br label %loop\nloop: br label %loop}')
    with font(tmp_path,loop,function='f',limits=Limits(max_steps=4)) as machine:
        with pytest.raises(ExecutionBoundExceeded,match='block_steps'): machine.invoke()


def test_target_and_initializer_resource_limits():
    source=CALLBACKS+'''define i32 @f(i1 %c,i32 %a,i32 %b){
 %p=select i1 %c,ptr @add,ptr @sub
 %r=call i32 %p(i32 %a,i32 %b)
 ret i32 %r}'''
    with pytest.raises(ResourceLimit,match='max_indirect_targets'): compile_ir(source,function='f',limits=Limits(max_indirect_targets=1))
    source='''@llvm.global_ctors=appending global [2 x {i32,ptr,ptr}] [{i32,ptr,ptr} {i32 1,ptr @init,ptr null},{i32,ptr,ptr} {i32 2,ptr @init,ptr null}]
define void @init(){ret void}
define i8 @f(){ret i8 7}'''
    with pytest.raises(ResourceLimit,match='max_initializers'): compile_ir(source,function='f',limits=Limits(max_initializers=1))


@pytest.mark.parametrize('section',['.ctors','.CRT$XCU','.preinit_array','__DATA,__init_offsets'])
def test_unsupported_startup_sections_are_not_ignored(section):
    source=f'''@startup=constant ptr @init,section "{section}"
define void @init(){{ret void}}
define i8 @f(){{ret i8 7}}'''
    with pytest.raises(LLVMError,match='initialization section'): compile_ir(source,function='f')


@pytest.mark.parametrize('language',['clang','rust'])
def test_real_frontend_callback_programs_match_native(language,tmp_path):
    if language=='clang':
        compiler=shutil.which('clang')
        if not compiler: pytest.skip('Clang unavailable')
        source=HERE/'examples/dispatch.c'
        native=tmp_path/'dispatch.dylib'
        subprocess.run([compiler,'-O1','-shared','-fPIC',str(source),'-o',str(native)],check=True,capture_output=True)
        paths=[]
        for suffix,mode in [('ll','-S'),('bc','-c')]:
            path=tmp_path/('dispatch.'+suffix)
            subprocess.run([compiler,'-O1','-fno-vectorize','-fno-slp-vectorize','-emit-llvm',mode,str(source),'-o',str(path)],check=True,capture_output=True)
            paths.append(path)
    else:
        compiler=os.environ.get('RUSTC') or shutil.which('rustc')
        if not compiler: pytest.skip('Rust unavailable')
        source=HERE/'examples/dispatch.rs'
        native=tmp_path/'dispatch.dylib'
        base=[compiler,'--edition=2021','-C','opt-level=1','-C','panic=abort',str(source)]
        subprocess.run(base+['--crate-type=cdylib','--cfg','native_reference','-o',str(native)],check=True,capture_output=True)
        paths=[]
        for suffix,mode in [('ll','llvm-ir'),('bc','llvm-bc')]:
            path=tmp_path/('dispatch.'+suffix)
            subprocess.run(base+['--crate-type=lib','--emit='+mode,'-o',str(path)],check=True,capture_output=True)
            paths.append(path)
    library=ctypes.CDLL(str(native))
    prefix='rust_' if language=='rust' else ''
    reset=getattr(library,prefix+'reset_reference'); reset.argtypes=[]; reset.restype=None
    rng=random.Random(33)
    for name in ['dispatch','dispatch_twice','copied_dispatch','constructor_dispatch']:
        function=prefix+name
        reference=getattr(library,function)
        count=2 if name=='constructor_dispatch' else 3
        reference.argtypes=[ctypes.c_uint32]*count; reference.restype=ctypes.c_uint32
        cases=[tuple(rng.getrandbits(32) for _ in range(count)) for _ in range(50)]
        cases += [(i,10,3) for i in range(4)] if count==3 else [(10,3)]
        for source in paths:
            with font(tmp_path,source,function=function) as machine:
                for args in cases:
                    reset()  # Reproduce a new module instance, including constructor effects.
                    assert machine.invoke(*args)==reference(*args),(language,name,args)


def test_clang_constructor_program_matches_loader_native(tmp_path):
    clang=shutil.which('clang')
    if not clang: pytest.skip('Clang unavailable')
    source=HERE/'examples/constructors.c'
    native=tmp_path/'constructors.dylib'
    subprocess.run([clang,'-O0','-shared','-fPIC',str(source),'-o',str(native)],check=True,capture_output=True)
    library=ctypes.CDLL(str(native))
    reference=library.initialized
    reference.argtypes=[ctypes.c_uint32]; reference.restype=ctypes.c_uint32
    for suffix,mode in [('ll','-S'),('bc','-c')]:
        path=tmp_path/('constructors.'+suffix)
        subprocess.run([clang,'-O0','-emit-llvm',mode,str(source),'-o',str(path)],check=True,capture_output=True)
        with font(tmp_path,path,function='initialized') as machine:
            assert [item['priority'] for item in machine.manifest['constructors']]==[101,202]
            for x in [0,1,5,0xffffffff]: assert machine.invoke(x)==reference(x)


def test_fastcc_void_and_aggregate_callback_signatures(tmp_path):
    source='''@callback=constant ptr @increment
define fastcc i8 @increment(i8 %x){%r=add i8 %x,1
 ret i8 %r}
define i8 @f(i8 %x){%p=load ptr,ptr @callback
 %r=call fastcc i8 %p(i8 %x)
 ret i8 %r}'''
    with font(tmp_path,source,function='f') as machine: assert machine.invoke(255)==0
    source='''@state=global i32 0
@callback=constant ptr @set
define void @set(i32 %x){store i32 %x,ptr @state
 ret void}
define i32 @f(i32 %x){%p=load ptr,ptr @callback
 call void %p(i32 %x)
 %r=load i32,ptr @state
 ret i32 %r}'''
    with font(tmp_path,source,function='f') as machine: assert machine.invoke(123)==123
    source='''@callback=constant ptr @pair
define {i32,i1} @pair(i32 %x){
 %a=insertvalue {i32,i1} poison,i32 %x,0
 %r=insertvalue {i32,i1} %a,i1 true,1
 ret {i32,i1} %r}
define {i32,i1} @f(i32 %x){%p=load ptr,ptr @callback
 %r=call {i32,i1} %p(i32 %x)
 ret {i32,i1} %r}'''
    with font(tmp_path,source,function='f') as machine: assert machine.invoke(91)==(91,1)


def test_constructor_indirect_calls_and_equal_priority_order(tmp_path):
    source='''@state=global i32 0
@callback=constant ptr @set
@llvm.global_ctors=appending global [2 x {i32,ptr,ptr}] [
 {i32,ptr,ptr} {i32 101,ptr @first,ptr null},
 {i32,ptr,ptr} {i32 101,ptr @second,ptr null}]
define void @set(){store i32 5,ptr @state
 ret void}
define void @first(){%p=load ptr,ptr @callback
 call void %p()
 ret void}
define void @second(){%v=load i32,ptr @state
 %r=mul i32 %v,2
 store i32 %r,ptr @state
 ret void}
define i32 @f(){%r=load i32,ptr @state
 ret i32 %r}'''
    with font(tmp_path,source,function='f') as machine:
        # LLVM leaves ties unspecified; the compiler chooses stable array order.
        assert machine.invoke()==10
        assert [x['function'] for x in machine.manifest['constructors']]==['first','second']
        assert machine.manifest['indirect_calls'][0]['targets']==['set']


def test_bad_constructor_signatures_associations_and_nonnull_loads(tmp_path):
    source='define preserve_mostcc i32 @helper(i32 %x){ret i32 %x}\ndefine i32 @f(i32 %x){%r=call preserve_mostcc i32 @helper(i32 %x)\nret i32 %r}'
    with pytest.raises(LLVMError,match='unsupported calling convention'): compile_ir(source,function='f')
    source='''@llvm.global_ctors=appending global [1 x {i32,ptr,ptr}] [{i32,ptr,ptr} {i32 101,ptr @init,ptr null}]
define i32 @init(){ret i32 1}
define i8 @f(){ret i8 7}'''
    with pytest.raises(LLVMError,match='constructors must'): compile_ir(source,function='f')
    source=source.replace('define i32 @init(){ret i32 1}','define void @init(){ret void}')
    source='@associated=external global i8\n'+source.replace('ptr @init,ptr null','ptr @init,ptr @associated')
    with pytest.raises(LLVMError,match='associated symbols'): compile_ir(source,function='f')
    source='''@startup=global ptr @init,section ".init_array"
define void @init(){ret void}
define i8 @f(){ret i8 7}'''
    with pytest.raises(LLVMError,match='immutable'): compile_ir(source,function='f')
    source='''@llvm.used=appending global [1 x ptr] [ptr @f],section "llvm.metadata"
define i1 @f(){%p=load ptr,ptr @llvm.used
 %r=icmp eq ptr %p,null
 ret i1 %r}'''
    with pytest.raises(LLVMError,match='linker metadata|intrinsic global'): compile_ir(source)
    source='''@p=constant ptr null
define i1 @f(){%p=load ptr,ptr @p,!nonnull !0
 %r=icmp eq ptr %p,null
 ret i1 %r}
!0=!{}'''
    with font(tmp_path,source) as machine:
        with pytest.raises(WasmTrap,match='poison_result'): machine.invoke()
    with font(tmp_path,source.replace('!nonnull !0','!nonnull !0,!noundef !0')) as machine:
        with pytest.raises(WasmTrap,match='undefined_behavior'): machine.invoke()
