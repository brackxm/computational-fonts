# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Resource bounds, LLVM text tokens and failed-build cleanup regressions."""
import gc
import os
import subprocess
import sys

import pytest

from test_llvm import HERE, font, evaluate
from llvmfont import compile_ir, LLVMError
from fontcircuit.gsub.circuit import ResourceLimit


@pytest.mark.parametrize('count',[257,1<<32,1<<62])
@pytest.mark.parametrize('location',['result','global','byval'])
def test_large_array_lengths_are_rejected_before_expansion(count,location):
    typ=f'[{count} x i8]'
    if location=='result':
        source=f'define {typ} @f(){{ret {typ} zeroinitializer}}'
    elif location=='global':
        source=f'@data=constant {typ} zeroinitializer\ndefine i1 @f(){{%r=icmp eq ptr @data,null\nret i1 %r}}'
    else:
        source=f'define i8 @f(ptr byval({typ}) %p){{ret i8 7}}'
    with pytest.raises((ResourceLimit,LLVMError),match="aggregate exceeds 256|huge 'byval' arguments"):
        compile_ir(source)


@pytest.mark.parametrize('word',['volatile','atomic','musttail','addrspace','inalloca','nusw'])
def test_keyword_string_constants_are_data(tmp_path,word):
    source=f'''define [{len(word)} x i8] @f(){{
 %p=alloca [{len(word)} x i8]
 store [{len(word)} x i8] c"{word}",ptr %p
 %r=load [{len(word)} x i8],ptr %p
 ret [{len(word)} x i8] %r}}'''
    with font(tmp_path,source) as machine:
        assert machine.invoke()==tuple(word.encode('ascii'))


def test_real_volatile_access_is_still_rejected():
    source='@g=global i8 7\ndefine i8 @f(){%v=load volatile i8,ptr @g\nret i8 %v}'
    with pytest.raises(LLVMError,match='unsupported instruction modifier'):
        compile_ir(source)


def test_quoted_abi_type_and_function_names(tmp_path):
    source='''%"T@false( align 16)"=type {i32}
define void @"g quote("(ptr sret(%"T@false( align 16)") align 4 %out,
                        ptr byval(%"T@false( align 16)") align 4 %in){
 %v=load i32,ptr %in
 store i32 %v,ptr %out
 ret void}
define void @f(ptr sret(%"T@false( align 16)") align 4 %out,
               ptr byval(%"T@false( align 16)") align 4 %in){
 call void @"g quote("(ptr sret(%"T@false( align 16)") align 4 %out,
                       ptr byval(%"T@false( align 16)") align 4 %in)
 ret void}'''
    with font(tmp_path,source,function='f') as machine:
        assert machine.manifest['entry_abi']['byval'][0]['type']=='%"T@false( align 16)"'
        assert machine.invoke(0xfeedbeef)==0xfeedbeef


def test_quoted_result_type_does_not_hide_actual_callee(tmp_path):
    source='''%"T@false("=type {i32}
define %"T@false(" @g(i32 %x){
 %r=insertvalue %"T@false(" zeroinitializer,i32 %x,0
 ret %"T@false(" %r}
define i32 @f(i32 %x){
 %v=call %"T@false(" @g(i32 %x)
 %r=extractvalue %"T@false(" %v,0
 ret i32 %r}'''
    with font(tmp_path,source,function='f') as machine:
        assert machine.invoke(42)==42


def test_long_zero_gep_lifetime_chain_is_iterative():
    chain='\n'.join(f'%p{i}=getelementptr i8,ptr '+('%base' if i==0 else f'%p{i-1}')+',i64 0' for i in range(1100))
    source='''declare void @llvm.lifetime.start.p0(i64 immarg,ptr nocapture)
define i8 @f(){
 %base=alloca i8
'''+chain+'''
 call void @llvm.lifetime.start.p0(i64 1,ptr %p1099)
 store i8 23,ptr %p1099
 %r=load i8,ptr %p1099
 ret i8 %r}'''
    assert evaluate(compile_ir(source),[])==((23,),set())


def test_font_and_manifest_reproduce_across_python_hash_seeds(tmp_path):
    source=tmp_path/'flags.ll'
    source.write_text('''define i8 @f(i16 %a,i16 %b,i16 %n){
 %x=add nuw nsw i16 %a,%b
 %s=shl nuw nsw i16 %x,%n
 %r=trunc nuw nsw i16 %s to i8
 ret i8 %r}''')
    outputs=[]
    for seed in ['1','2']:
        output=tmp_path/f'seed-{seed}.ttf'
        subprocess.run([sys.executable,str(HERE/'build.py'),str(source),'-o',str(output)],
                       env=dict(os.environ,PYTHONHASHSEED=seed),check=True,capture_output=True)
        outputs.append((output.read_bytes(),output.with_suffix('.json').read_bytes()))
    assert outputs[0]==outputs[1]


@pytest.mark.parametrize('source',[
    'not LLVM IR',
    b'\xff',
    '''define i8 @f(){
entry: br label %end
end: %x=phi i8 [1,%end]
 ret i8 %x}''',
])
def test_failed_parse_and_verification_tracebacks_are_safe_to_collect(source):
    failures=[]
    for _ in range(10):
        try: compile_ir(source)
        except LLVMError as error: failures.append(error)
    assert len(failures)==10
    gc.collect()
    assert all('parsing/verification failed' in str(error) for error in failures)
    failures.clear(); gc.collect()
    assert evaluate(compile_ir('define i8 @f(){ret i8 42}'),[])==((42,),set())
