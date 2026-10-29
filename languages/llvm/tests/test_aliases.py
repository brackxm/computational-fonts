# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Alias identity and metadata-constrained callbacks through actual shaping."""
import ctypes
import os
import random
import shutil
import subprocess

import pytest
from llvmlite import binding as llvm

from test_llvm import HERE, font
from llvmfont import compile_ir, Limits, LLVMError
from fontcircuit.runtime import WasmTrap
from fontcircuit.gsub.circuit import ResourceLimit


ALIASES = '''@named = alias i32(i32),ptr @increment
@chained = internal alias i32(i32),ptr @named
@table = constant [2 x ptr] [ptr @named,ptr @chained]
define i32 @increment(i32 %x){%r=add i32 %x,7
 ret i32 %r}
define i32 @f(i1 %which,i32 %x){
 %n=zext i1 %which to i64
 %p=getelementptr [2 x ptr],ptr @table,i64 0,i64 %n
 %callback=load ptr,ptr %p
 %a=call i32 %callback(i32 %x)
 %b=call i32 @chained(i32 %a)
 ret i32 %b}'''


@pytest.mark.parametrize('bitcode',[False,True])
@pytest.mark.parametrize('optimize',[False,True])
def test_function_aliases_native_tables_and_entry(tmp_path,bitcode,optimize):
    llvm.initialize_native_target(); llvm.initialize_native_asmprinter()
    module=llvm.parse_assembly(ALIASES); module.verify(); module.triple=llvm.get_default_triple()
    source=module.as_bitcode() if bitcode else str(module)
    with llvm.create_mcjit_compiler(module,llvm.Target.from_default_triple().create_target_machine()) as engine:
        engine.finalize_object()
        native=ctypes.CFUNCTYPE(ctypes.c_uint32,ctypes.c_uint8,ctypes.c_uint32)(engine.get_function_address('f'))
        with font(tmp_path,source,function='f',optimize=optimize) as machine:
            rng=random.Random(383)
            for _ in range(50):
                which,x=rng.getrandbits(1),rng.getrandbits(32)
                assert machine.invoke(which,x)==native(which,x)
            assert len(machine.manifest['function_addresses'])==1
        with font(tmp_path,source,function='named',optimize=optimize) as machine:
            assert machine.invoke(0xffffffff)==6
            assert 'named' in machine.manifest['aliases']


def test_data_alias_offsets_mutation_identity_and_cyclic_relocations(tmp_path):
    source='''@array=global [2 x i32] [i32 7,i32 9]
@second=alias i32,getelementptr ([2 x i32],ptr @array,i64 0,i64 1)
@again=internal alias i32,ptr @second
@node=global {ptr,i32} {ptr @node_alias,i32 11}
@node_alias=alias {ptr,i32},ptr @node
define i32 @f(i32 %x){
 store i32 %x,ptr @again
 %p=getelementptr [2 x i32],ptr @array,i64 0,i64 1
 %same=icmp eq ptr %p,@second
 %back=load ptr,ptr @node_alias
 %value=getelementptr {ptr,i32},ptr %back,i64 0,i32 1
 %a=load i32,ptr %value
 %b=load i32,ptr %p
 %sum=add i32 %a,%b
 %r=select i1 %same,i32 %sum,i32 99
 ret i32 %r}'''
    llvm.initialize_native_target(); llvm.initialize_native_asmprinter()
    module=llvm.parse_assembly(source); module.triple=llvm.get_default_triple()
    with llvm.create_mcjit_compiler(module,llvm.Target.from_default_triple().create_target_machine()) as engine:
        engine.finalize_object()
        native=ctypes.CFUNCTYPE(ctypes.c_uint32,ctypes.c_uint32)(engine.get_function_address('f'))
        with font(tmp_path,source,function='f') as machine:
            assert set(machine.manifest['aliases'])=={'second','again','node_alias'}
            for x in [0,1,17,0xffffffff]: assert machine.invoke(x)==native(x)


def test_alias_readonly_and_quoted_symbols(tmp_path):
    source='''@"data space"=constant i32 7
@"alias space"=alias i32,ptr @"data space"
define i32 @f(i1 %write){
entry: br i1 %write,label %yes,label %end
yes: store i32 9,ptr @"alias space"
 br label %end
end: %r=load i32,ptr @"alias space"
 ret i32 %r}'''
    with font(tmp_path,source) as machine:
        assert machine.invoke(0)==7
        with pytest.raises(WasmTrap,match='readonly_memory'): machine.invoke(1)


def test_constructor_alias_and_associated_data_alias(tmp_path):
    source='''@value=global i32 0
@data_alias=internal alias i32,ptr @value
@init_alias=alias void(),ptr @init
@llvm.global_ctors=appending global [1 x {i32,ptr,ptr}] [
 {i32,ptr,ptr} {i32 101,ptr @init_alias,ptr @data_alias}]
define void @init(){store i32 13,ptr @data_alias
 ret void}
define i32 @f(i32 %x){%a=load i32,ptr @value
 %r=add i32 %a,%x
 store i32 99,ptr @value
 ret i32 %r}'''
    with font(tmp_path,source,function='f') as machine:
        for x in [0,17,0xffffffff,0]: assert machine.invoke(x)==(x+13)&0xffffffff
        assert machine.manifest['constructors'][0]['function']=='init'


CONSTRAINED = '''@allowed_alias=alias i32(i32),ptr @allowed
define i32 @allowed(i32 %x){%r=add i32 %x,1
 ret i32 %r}
define i32 @excluded(i32 %x){%r=sub i32 %x,1
 ret i32 %r}
define i32 @f(i1 %which,i32 %x){
 %p=select i1 %which,ptr @allowed_alias,ptr @excluded
 %r=call i32 %p(i32 %x),!callees !0
 ret i32 %r}
!0=!{ptr @allowed_alias,ptr @allowed}'''


def test_callees_narrow_dispatch_and_violation_is_guarded(tmp_path):
    with font(tmp_path,CONSTRAINED,function='f',limits=Limits(max_indirect_targets=1)) as machine:
        site=machine.manifest['indirect_calls'][0]
        assert site['targets']==site['declared_targets']==['allowed']
        for x in [0,17,0xffffffff]: assert machine.invoke(1,x)==(x+1)&0xffffffff
        with pytest.raises(WasmTrap,match='invalid_indirect_call'): machine.invoke(0,12)
    # An excluded definition is not part of the constrained call graph.
    source=CONSTRAINED.replace('%r=sub i32 %x,1','%r=ptrtoint ptr null to i32')
    with font(tmp_path,source,function='f') as machine: assert machine.invoke(1,20)==21
    source='''define i8 @f(i1 %run){
entry: br i1 %run,label %bad,label %ok
bad: %r=call i8 null(),!callees !0
 ret i8 %r
ok: ret i8 7}
!0=!{}'''
    with font(tmp_path,source) as machine:
        assert machine.invoke(0)==7
        with pytest.raises(WasmTrap,match='invalid_indirect_call'): machine.invoke(1)


@pytest.mark.parametrize('metadata',['ptr @data','ptr @external','i32 7'])
def test_unsupported_callees_rejected(metadata):
    source=CONSTRAINED.replace('!0=!{ptr @allowed_alias,ptr @allowed}',f'!0=!{{{metadata}}}')
    source='@data=global i32 0\ndeclare i32 @external(i32)\n'+source
    with pytest.raises(LLVMError): compile_ir(source,function='f')


@pytest.mark.parametrize('definition',[
    '@alias=weak alias i32,ptr @value',
    '@alias=thread_local alias i32,ptr @value',
    '@alias=alias i32,inttoptr (i64 16 to ptr)',
    '@alias=alias i32,ptr @value,partition "part"',
])
def test_unsupported_alias_forms_rejected(definition):
    source='@value=global i32 7\n'+definition+'\ndefine i32 @f(){%r=load i32,ptr @alias\nret i32 %r}'
    with pytest.raises(LLVMError): compile_ir(source)


def test_alias_depth_and_nonfunction_entry():
    source='@value=global i32 0\n@a0=alias i32,ptr @value\n'
    source+='\n'.join(f'@a{i}=alias i32,ptr @a{i-1}' for i in range(1,65))
    source+='\ndefine i32 @f(){%r=load i32,ptr @a64\nret i32 %r}'
    with pytest.raises(ResourceLimit,match='alias graph'): compile_ir(source)
    with pytest.raises(LLVMError,match='function base'): compile_ir(source,function='a0')
    source='@a=alias i8(i8),ptr @f\ndefine i32 @f(i32 %x){ret i32 %x}'
    with pytest.raises(LLVMError,match='entry alias type'): compile_ir(source,function='a')


@pytest.mark.parametrize('level',[1,2])
def test_rust_generated_callees_and_merged_aliases_match_native(tmp_path,level):
    compiler=os.environ.get('RUSTC') or shutil.which('rustc')
    if not compiler: pytest.skip('Rust unavailable')
    source=HERE/'examples/aliases.rs'
    base=[compiler,'--edition=2021','-C',f'opt-level={level}','-C','panic=abort',str(source)]
    native=tmp_path/'aliases.dylib'
    subprocess.run(base+['--crate-type=cdylib','-o',str(native)],check=True,capture_output=True)
    library=ctypes.CDLL(str(native))
    reference=library.alias_dispatch
    reference.argtypes=[ctypes.c_uint32,ctypes.c_uint32]; reference.restype=ctypes.c_uint32
    for suffix,mode in [('ll','llvm-ir'),('bc','llvm-bc')]:
        path=tmp_path/f'aliases.{suffix}'
        subprocess.run(base+['--crate-type=lib',f'--emit={mode}','-o',str(path)],check=True,capture_output=True)
        module=llvm.parse_bitcode(path.read_bytes()) if suffix=='bc' else llvm.parse_assembly(path.read_text())
        assert '!callees' in str(module)
        if level==2: assert ' alias ' in str(module)
        with font(tmp_path,path,function='alias_dispatch') as machine:
            assert machine.manifest['indirect_calls'][0]['declared_targets']
            rng=random.Random(38)
            for which,x in [(0,0),(1,0xffffffff)]+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(50)]:
                assert machine.invoke(which,x)==reference(which,x)
        with font(tmp_path,path,function='original') as machine:
            assert machine.invoke(0xffffffff)==6
