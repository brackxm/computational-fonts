# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Quoted startup attributes and resource limits before large allocations."""
import ctypes
import random
import shutil
import subprocess
import sys

import pytest

from test_llvm import font, evaluate
from llvmfont import compile_ir, LLVMError, Limits
from llvmfont.compiler import MAX_SOURCE_BYTES
from fontcircuit.gsub.circuit import ResourceLimit


@pytest.mark.parametrize('section',[
    '.init_array','.init_array.101',
    '__DATA,__mod_init_func','__DATA_CONST,__mod_init_func',
])
@pytest.mark.parametrize('array',[False,True])
def test_quoted_global_name_cannot_shadow_initializer_section(tmp_path,section,array):
    compiler=shutil.which('clang')
    if not compiler: pytest.skip('Clang required for native loader startup')
    initializer='[1 x ptr] [ptr @init]' if array else 'ptr @init'
    source=f'''@state=internal global i32 0
@"section "=constant {initializer},section "{section}"
define internal void @init(){{
 store i32 42,ptr @state
 ret void}}
define i32 @f(i32 %x){{
 %state=load i32,ptr @state
 %r=add i32 %state,%x
 ret i32 %r}}'''
    # Compare equivalent startup tables using the host's loader format.
    # There is only one initializer, so ELF priority does not change the result.
    native_section='__DATA,__mod_init_func' if sys.platform=='darwin' else '.init_array'
    native_source=source.replace(f'section "{section}"',f'section "{native_section}"')
    path=tmp_path/'startup.ll'; path.write_text(native_source)
    native=tmp_path/'startup.dylib'
    subprocess.run([compiler,'-O0','-shared','-fPIC',str(path),'-o',str(native)],check=True,capture_output=True)
    library=ctypes.CDLL(str(native))
    reference=library.f; reference.argtypes=[ctypes.c_uint32]; reference.restype=ctypes.c_uint32
    with font(tmp_path,source,function='f') as machine:
        assert machine.manifest['constructors']==[{
            'function':'init','priority':101 if section.endswith('.101') else 65535,
            'source':section,
        }]
        rng=random.Random(811)
        for x in [0,0xffffffff]+[rng.getrandbits(32) for _ in range(20)]:
            assert machine.invoke(x)==reference(x)


@pytest.mark.parametrize('section',[
    '__DATA,__mod_init_func,mod_init_funcs',
    '__DATA_CONST,__mod_term_func,mod_term_funcs',
    '__DATA,__custom_startup,mod_init_funcs',
])
def test_unhandled_macho_startup_flags_are_rejected(section):
    source=f'''@"section "=constant ptr @init,section "{section}"
define void @init(){{ret void}}
define i8 @f(){{ret i8 7}}'''
    with pytest.raises(LLVMError,match='unsupported module initialization section'):
        compile_ir(source,function='f')


@pytest.mark.parametrize('byval',[False,True])
@pytest.mark.parametrize('optimize',[False,True])
def test_entry_input_capacity_is_checked_during_lowering(byval,optimize):
    parameters=','.join(['ptr byval([64 x i64]) align 8']*8 if byval else ['i64']*512)
    source='define i8 @f('+parameters+'){ret i8 7}'
    with pytest.raises(ResourceLimit,match='entry arguments exceed OpenType glyph-count'):
        compile_ir(source,limits=Limits(max_memory_bytes=4096),optimize=optimize)


def test_entry_input_capacity_allows_a_smaller_interface():
    source='define i8 @f('+','.join(['i64']*511)+'){ret i8 7}'
    program=compile_ir(source)
    assert len(program.parameter_types)==511
    assert evaluate(program,[0]*511)==((7,),set())


@pytest.mark.parametrize('kind',['text','bytes','path'])
@pytest.mark.parametrize('extra',[0,1])
def test_source_byte_limit_exact_boundary(tmp_path,kind,extra):
    prefix=b'define i8 @f(){ret i8 7}\n;'
    data=prefix+b'x'*(MAX_SOURCE_BYTES+extra-len(prefix))
    if kind=='path':
        source=tmp_path/'limit.ll'; source.write_bytes(data)
    else: source=data.decode('ascii') if kind=='text' else data
    if extra:
        with pytest.raises(LLVMError,match='source exceeds 1 MiB'): compile_ir(source)
    else: assert evaluate(compile_ir(source),[])==((7,),set())


def test_source_limit_counts_utf8_bytes():
    source=';'+('\u0100'*(MAX_SOURCE_BYTES//2))
    with pytest.raises(LLVMError,match='source exceeds 1 MiB'): compile_ir(source)
