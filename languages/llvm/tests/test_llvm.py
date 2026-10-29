# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Differential LLVM/native references and real HarfBuzz GSUB execution."""
import ctypes
import itertools
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys

import pytest
from llvmlite import binding as llvm

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from llvmfont import build, compile_ir, LLVMError, Limits
from fontcircuit.runtime import NativeFont, WasmTrap, ExecutionBoundExceeded, IncompleteShaping
from fontcircuit.gsub.circuit import ResourceLimit


def font(tmp_path,source,**options):
    path = tmp_path/'test.ttf'
    build(source,path,**options)
    return NativeFont(path)


def evaluate(program,args):
    values = program.circuit.evaluate_for_test(args)
    flags = {name for name,wire in program.flags.items() if values[wire]}
    result = tuple(sum(values[wire]<<i for i,wire in enumerate(value.bits)) for value in program.results)
    return result,flags


def binary(op,width=8,flags=''):
    return f'define i{width} @f(i{width} %a, i{width} %b) {{ %r = {op} {flags} i{width} %a, %b\n ret i{width} %r }}'


def signed(x,width): return x-(1<<width) if x>>(width-1) else x


def reference(op,a,b,width):
    mask = (1<<width)-1
    sa,sb = signed(a,width),signed(b,width)
    if op=='add': return (a+b)&mask
    if op=='sub': return (a-b)&mask
    if op=='mul': return (a*b)&mask
    if op=='and': return a&b
    if op=='or': return a|b
    if op=='xor': return a^b
    if op=='shl': return (a<<b)&mask
    if op=='lshr': return a>>b
    if op=='ashr': return (sa>>b)&mask
    if op=='udiv': return a//b
    if op=='urem': return a%b
    q = (abs(sa)//abs(sb))*(-1 if (sa<0)!=(sb<0) else 1)
    return (sa-q*sb if op=='srem' else q)&mask


def test_max_runtime_and_actual_substitutions(tmp_path):
    rng = random.Random(193)
    with font(tmp_path,(HERE/'examples/max.ll').read_text()) as machine:
        pairs = [(0,0),(-1,0),(-(1<<31),(1<<31)-1),(-5,-2)]
        pairs += [tuple(rng.randrange(-(1<<31),1<<31) for _ in range(2)) for _ in range(100)]
        for a,b in pairs: assert machine.invoke(a,b)==max(a,b)&0xffffffff
        encoded = machine.encode([3,9])
        shaped = machine.shaper.shape(encoded)
        assert shaped != encoded
        assert all(not x.endswith('_u') for x in shaped)
        assert machine.decode(shaped)==(9,)
        with pytest.raises(IncompleteShaping): machine.decode(machine.shaper.shape(encoded,enabled=False))
        assert machine.manifest['metrics']['gates']<200


@pytest.mark.parametrize('op',['add','sub','mul','and','or','xor','udiv','urem','sdiv','srem','shl','lshr','ashr'])
def test_exhaustive_i8_circuits(op):
    program = compile_ir(binary(op))
    for a,b in itertools.product(range(256),repeat=2):
        result,flags = evaluate(program,[a,b])
        if op in ('shl','lshr','ashr') and b>=8:
            assert 'trap.poison_result' in flags
        elif op in ('udiv','urem','sdiv','srem') and (b==0 or (op[0]=='s' and a==128 and b==255)):
            assert 'trap.undefined_behavior' in flags
        else:
            assert not flags,(op,a,b,flags)
            assert result==(reference(op,a,b,8),),(op,a,b,result)


@pytest.mark.parametrize('width',[1,8,16,32,64])
def test_random_wide_arithmetic_in_harfbuzz(tmp_path,width):
    rng = random.Random(width)
    mask = (1<<width)-1
    for op in ['add','sub','mul','xor','ashr']:
        with font(tmp_path,binary(op,width)) as machine:
            for a,b in [(mask,1),(1,0),(0,mask)] + [tuple(rng.getrandbits(width) for _ in range(2)) for _ in range(25)]:
                if op=='ashr': b %= width
                assert machine.invoke(a,b)==reference(op,a,b,width)


@pytest.mark.parametrize('predicate',['eq','ne','ugt','uge','ult','ule','sgt','sge','slt','sle'])
def test_comparisons(predicate,tmp_path):
    source = f'define i1 @f(i8 %a, i8 %b) {{ %r = icmp {predicate} i8 %a, %b\nret i1 %r }}'
    program = compile_ir(source)
    for a,b in itertools.product(range(256),repeat=2):
        x,y = (signed(a,8),signed(b,8)) if predicate.startswith('s') else (a,b)
        expected = {'eq':x==y,'ne':x!=y,'gt':x>y,'ge':x>=y,'lt':x<y,'le':x<=y}[predicate if predicate in ('eq','ne') else predicate[1:]]
        assert evaluate(program,[a,b])==((int(expected),),set())
    with font(tmp_path,source) as machine:
        assert machine.invoke(128,127)==evaluate(program,[128,127])[0][0]


def test_phi_parallel_updates_loop_and_limit(tmp_path):
    with font(tmp_path,(HERE/'examples/loop.ll').read_text(),limits=Limits(max_steps=16)) as machine:
        for n in range(7): assert machine.invoke(n)==n*(n-1)//2
        with pytest.raises(ExecutionBoundExceeded,match='block_steps'): machine.invoke(7)
    source = '''define i8 @f(i8 %n) {
entry: br label %loop
loop:
 %a = phi i8 [1, %entry], [%b, %loop]
 %b = phi i8 [2, %entry], [%a, %loop]
 %i = phi i8 [0, %entry], [%next, %loop]
 %next = add i8 %i, 1
 %done = icmp eq i8 %i, %n
 br i1 %done, label %exit, label %loop
exit: ret i8 %a
}'''
    with font(tmp_path,source) as machine:
        for n in range(8): assert machine.invoke(n)==(2 if n%2 else 1)


def test_branches_calls_and_recursion(tmp_path):
    source = '''define i8 @f(i8 %n) {
entry:
 %done = icmp eq i8 %n, 0
 br i1 %done, label %base, label %rec
base: ret i8 1
rec:
 %n1 = sub i8 %n, 1
 %small = call i8 @f(i8 %n1)
 %r = mul i8 %n, %small
 ret i8 %r
}'''
    with font(tmp_path,source,limits=Limits(max_call_depth=4,max_steps=4)) as machine:
        for n,expected in enumerate([1,1,2,6]): assert machine.invoke(n)==expected
        with pytest.raises(ExecutionBoundExceeded,match='call_depth'): machine.invoke(4)


def test_switch_phi(tmp_path):
    source = '''define i8 @f(i8 %n) {
entry: switch i8 %n, label %default [i8 2, label %two i8 3, label %three]
two: br label %exit
three: br label %exit
default: br label %exit
exit: %r = phi i8 [20, %two], [30, %three], [99, %default]
ret i8 %r
}'''
    with font(tmp_path,source) as machine:
        for n in range(256): assert machine.invoke(n)=={2:20,3:30}.get(n,99)


@pytest.mark.parametrize('op,flag',[('add','nsw'),('add','nuw'),('sub','nsw'),('sub','nuw'),('mul','nsw'),('mul','nuw'),('shl','nsw'),('shl','nuw'),('lshr','exact'),('ashr','exact'),('udiv','exact'),('sdiv','exact')])
def test_poison_flags(op,flag):
    program = compile_ir(binary(op,8,flag))
    for a,b in itertools.product(range(256),range(8) if op in ('shl','lshr','ashr') else [1,2,3,127,128,255]):
        _,flags = evaluate(program,[a,b])
        sa,sb = signed(a,8),signed(b,8)
        if flag=='exact':
            if op in ('lshr','ashr'): bad = bool(a&((1<<b)-1))
            elif op=='udiv': bad = bool(a%b)
            else:
                if sa==-128 and sb==-1: continue
                bad = bool(sa%sb)
        else:
            x,y = (sa,sb) if flag=='nsw' else (a,b)
            number = {'add':lambda:x+y,'sub':lambda:x-y,'mul':lambda:x*y,'shl':lambda:x<<b}[op]()
            bad = not (-128<=number<=127 if flag=='nsw' else 0<=number<=255)
        assert ('trap.poison_result' in flags)==bad,(op,flag,a,b,flags)


def test_poison_select_freeze_dead_paths_and_ub(tmp_path):
    source = '''define i8 @f(i1 %pick, i8 %x) {
 %bad = add nsw i8 %x, 127
 %r = select i1 %pick, i8 %bad, i8 42
 ret i8 %r
}'''
    with font(tmp_path,source) as machine:
        assert machine.invoke(0,10)==42
        with pytest.raises(WasmTrap,match='poison_result'): machine.invoke(1,10)
    with font(tmp_path,source.replace('ret i8 %r','%f = freeze i8 %r\nret i8 %f')) as machine:
        assert machine.invoke(1,10)==0
    source = '''define i8 @f(i1 %pick, i8 %x) {
 br i1 %pick, label %bad, label %ok
bad: %r = udiv i8 9, %x
 ret i8 %r
ok: ret i8 17
}'''
    with font(tmp_path,source) as machine:
        assert machine.invoke(0,0)==17
        with pytest.raises(WasmTrap,match='undefined_behavior'): machine.invoke(1,0)
    with font(tmp_path,'define i8 @f() { %x = udiv i8 1, 0\nret i8 7 }') as machine:
        with pytest.raises(WasmTrap,match='undefined_behavior'): machine.invoke()


def test_conversions_aggregates_and_memory(tmp_path):
    source = '''define {i8, i64} @f(i32 %a) {
 %small = trunc i32 %a to i8
 %wide = sext i8 %small to i64
 %p = insertvalue {i8, i64} poison, i8 %small, 0
 %q = insertvalue {i8, i64} %p, i64 %wide, 1
 %r = extractvalue {i8, i64} %q, 1, !annotation !0
 ret {i8, i64} %q
}
!0 = !{!"aggregate metadata"}'''
    with font(tmp_path,source) as machine:
        for n in [0,127,128,255,65535]: assert machine.invoke(n)==(n&255,signed(n&255,8)&((1<<64)-1))
    with font(tmp_path,(HERE/'examples/memory.ll').read_text()) as machine:
        for i in range(8): assert machine.invoke(i,0xfeedbeef)==0xfeedbeef


def test_invalid_memory_and_dynamic_aliasing(tmp_path):
    source = '''define i8 @f(i8 %index, i8 %value) {
 %a = alloca [4 x i8], align 1
 %p = getelementptr [4 x i8], ptr %a, i64 0, i8 %index
 store i8 %value, ptr %p, align 1
 %q = getelementptr [4 x i8], ptr %a, i64 0, i8 2
 %r = load i8, ptr %q, align 1
 ret i8 %r
}'''
    with font(tmp_path,source) as machine:
        for i in range(4): assert machine.invoke(i,123)==(123 if i==2 else 0)
        for i in [4,255]:
            with pytest.raises(WasmTrap,match='invalid_memory'): machine.invoke(i,123)


def test_bitcode_and_llvm_optimization(tmp_path):
    source = (HERE/'examples/max.ll').read_text()
    module = llvm.parse_assembly(source)
    with font(tmp_path,module.as_bitcode()) as machine: assert machine.invoke(-1,2)==2
    source = 'define i32 @f(i32 %a) { %p = alloca i32\nstore i32 %a, ptr %p\n%r = load i32, ptr %p\nret i32 %r }'
    with font(tmp_path,source,optimize=True) as machine: assert machine.invoke(123)==123
    with pytest.raises(LLVMError,match='verification'): compile_ir('define i32 @f() { ret i8 0 }')


@pytest.mark.parametrize('source,match',[
    ('define float @f(float %x) { ret float %x }','integer type'),
    ('define i32 @f(ptr %p) { %r = call i32 %p()\nret i32 %r }','integer type'),
    ('declare i32 @g(i32)\ndefine i32 @f(i32 %a) { %r = call i32 @g(i32 %a)\nret i32 %r }','external'),
    ('define i32 @f(ptr %p) { %r = load volatile i32, ptr %p\nret i32 %r }','modifier'),
    ('define i32 @f(i32 %x) { %r = icmp samesign ult i32 %x, 1\nret i32 %x }','modifier'),
    ('define i32 @f(i32 %x) { %p = alloca i8, i32 %x\nret i32 %x }','dynamic alloca'),
    ('define i7 @f(i7 %x) { ret i7 %x }','integer type'),
])
def test_explicit_rejections(source,match):
    with pytest.raises(LLVMError,match=match): compile_ir(source)


def test_limits_and_cli(tmp_path):
    with pytest.raises(ResourceLimit): compile_ir(binary('mul',64),limits=Limits(max_gates=1))
    with pytest.raises(LLVMError): Limits(max_steps=0)
    path = tmp_path/'max.ttf'
    result = subprocess.run([sys.executable,str(HERE/'build.py'),str(HERE/'examples/max.ll'),'-o',str(path)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    result = subprocess.run([sys.executable,str(HERE/'run.py'),str(path),'-5','-2','--signed'],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='-2'


def test_clang_native_and_bitcode_differential(tmp_path):
    clang = shutil.which('clang')
    if not clang: pytest.skip('Clang unavailable')
    source = HERE/'examples/programs.c'
    native = tmp_path/'reference.dylib'
    assembly = tmp_path/'programs.ll'
    bitcode = tmp_path/'programs.bc'
    subprocess.run([clang,'-shared','-fPIC','-O1',str(source),'-o',str(native)],check=True,capture_output=True)
    subprocess.run([clang,'-S','-emit-llvm','-O1','-fno-vectorize','-fno-slp-vectorize',str(source),'-o',str(assembly)],check=True,capture_output=True)
    subprocess.run([clang,'-c','-emit-llvm','-O1','-fno-vectorize','-fno-slp-vectorize',str(source),'-o',str(bitcode)],check=True,capture_output=True)
    library = ctypes.CDLL(str(native))
    rng = random.Random(732)
    for name in ['max','mix']:
        reference = getattr(library,name)
        reference.argtypes = [ctypes.c_uint32,ctypes.c_uint32]
        reference.restype = ctypes.c_uint32
        for source in [assembly,bitcode]:
            with font(tmp_path,source,function=name) as machine:
                for _ in range(80):
                    a,b = rng.getrandbits(32),rng.getrandbits(32)
                    assert machine.invoke(a,b)==reference(a,b)


def test_rust_frontend_when_installed(tmp_path):
    rustc = os.environ.get('RUSTC') or shutil.which('rustc')
    if not rustc: pytest.skip('rustc unavailable; Rust source retained for reproducible builds')
    assembly = tmp_path/'rust.ll'
    subprocess.run([rustc,'--crate-type=lib','--edition=2021','--emit=llvm-ir','-C','opt-level=1','-C','panic=abort',str(HERE/'examples/programs.rs'),'-o',str(assembly)],check=True,capture_output=True)
    with font(tmp_path,assembly,function='rust_max') as machine:
        for a,b in [(-4,8),(-8,-3),(0,0)]: assert machine.invoke(a,b)==max(a,b)&0xffffffff


@pytest.mark.parametrize('width',[32,64])
def test_llvm_jit_differential_all_integer_ops(tmp_path,width):
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()
    rng = random.Random(892+width)
    typ = ctypes.c_uint32 if width==32 else ctypes.c_uint64
    target = llvm.Target.from_default_triple()
    for op in ['add','sub','mul','and','or','xor','shl','lshr','ashr','udiv','sdiv','urem','srem']:
        source = binary(op,width)
        module = llvm.parse_assembly(source)
        module.triple = llvm.get_default_triple()
        with llvm.create_mcjit_compiler(module,target.create_target_machine()) as engine:
            engine.finalize_object()
            native = ctypes.CFUNCTYPE(typ,typ,typ)(engine.get_function_address('f'))
            with font(tmp_path,source) as machine:
                cases = [(0,1),((1<<width)-1,1),(1<<(width-1),3)]
                cases += [tuple(rng.getrandbits(width) for _ in range(2)) for _ in range(32)]
                for a,b in cases:
                    if op in ('shl','lshr','ashr'): b %= width
                    if op.endswith(('div','rem')) and b==0: b=1
                    assert machine.invoke(a,b)==native(a,b),(width,op,a,b)


def test_real_frontend_memory_loops_and_rust(tmp_path):
    clang = shutil.which('clang')
    if clang:
        native = tmp_path/'native.dylib'
        subprocess.run([clang,'-shared','-fPIC','-O0',str(HERE/'examples/programs.c'),'-o',str(native)],check=True,capture_output=True)
        library = ctypes.CDLL(str(native))
        for name,arguments in [('indexed',[(i,100+i) for i in range(12)]),
                               ('sum_loop',[(n,) for n in range(7)])]:
            reference = getattr(library,name)
            reference.argtypes = [ctypes.c_uint32]*len(arguments[0])
            reference.restype = ctypes.c_uint32
            with font(tmp_path,HERE/'examples/clang.ll',function=name,limits=Limits(max_steps=32)) as machine:
                for args in arguments: assert machine.invoke(*args)==reference(*args)
    for name in ['rust_max','rust_mix']:
        with font(tmp_path,HERE/'examples/rust.ll',function=name) as machine:
            for a,b in [(0,0),(-5,-2),(0xffffffff,0x80000000),(0xfeedbeefbaadf00d,0x123456789abcdef0)]:
                if name=='rust_max': expected = max(signed(a&0xffffffff,32),signed(b&0xffffffff,32))&0xffffffff
                else:
                    mask = (1<<64)-1
                    n = (a+b)&mask
                    expected = (((n<<7)|(n>>57))^b)&mask
                assert machine.invoke(a,b)==expected


def test_noundef_and_poison_boundaries(tmp_path):
    for call in ['call i8 @g(i8 noundef poison)','call noundef i8 @g(i8 poison)']:
        source = f'define i8 @g(i8 %a) {{ ret i8 %a }}\ndefine i8 @f() {{ %r = {call}\nret i8 42 }}'
        with font(tmp_path,source,function='f') as machine:
            with pytest.raises(WasmTrap,match='undefined_behavior'): machine.invoke()
    source = '''define i8 @f() {
 %x = freeze i1 poison
 br i1 %x, label %a, label %b
a: ret i8 1
b: ret i8 2
}'''
    with font(tmp_path,source) as machine: assert machine.invoke()==2
    with font(tmp_path,source.replace('%x = freeze i1 poison','%x = icmp eq i8 poison, 0')) as machine:
        with pytest.raises(WasmTrap,match='undefined_behavior'): machine.invoke()


@pytest.mark.parametrize('flag',['nuw','nsw'])
def test_trunc_flags(flag):
    source = f'define i8 @f(i32 %a) {{ %r = trunc {flag} i32 %a to i8\nret i8 %r }}'
    program = compile_ir(source)
    for a in [0,127,128,255,256,0xffffffff,0xffffff80]:
        _,flags = evaluate(program,[a])
        valid = 0<=a<=255 if flag=='nuw' else -128<=signed(a,32)<=127
        assert ('trap.poison_result' not in flags)==valid


@pytest.mark.parametrize('op',['fshl','fshr'])
def test_funnel_shifts(op,tmp_path):
    source = f'''declare i8 @llvm.{op}.i8(i8, i8, i8)
define i8 @f(i8 %a, i8 %b, i8 %n) {{
 %r = call i8 @llvm.{op}.i8(i8 %a, i8 %b, i8 %n)
 ret i8 %r
}}'''
    with font(tmp_path,source) as machine:
        for a,b,n in itertools.product([0,1,127,128,255],[1,15,128],range(17)):
            shift = n%8
            expected = (((a<<8)|b)<<(shift) >> 8)&255 if op=='fshl' else (((a<<8)|b)>>shift)&255
            assert machine.invoke(a,b,n)==expected


def test_memory_across_calls_and_branches(tmp_path):
    source = '''define void @put(ptr %p, i8 %v) { store i8 %v, ptr %p, align 1
 ret void }
define i8 @f(i1 %take, i8 %v) {
entry:
 %p = alloca i8
 store i8 9, ptr %p
 br i1 %take, label %yes, label %no
yes: call void @put(ptr %p, i8 %v)
 br label %end
no: store i8 17, ptr %p
 br label %end
end: %x = load i8, ptr %p
 ret i8 %x
}'''
    with font(tmp_path,source,function='f') as machine:
        assert machine.invoke(0,123)==17
        assert machine.invoke(1,123)==123


def test_inbounds_base_zero_and_one_past(tmp_path):
    source = '''define i1 @f(i64 %index, i64 %delta) {
 %a = alloca [4 x i8]
 %out = getelementptr i8, ptr %a, i64 %index
 %back = getelementptr inbounds i8, ptr %out, i64 %delta
 %fixed = freeze ptr %back
 %r = icmp eq ptr %fixed, null
 ret i1 %r
}'''
    with font(tmp_path,source) as machine:
        assert machine.invoke(5,-1)==1  # Invalid base cannot become inbounds again.
        assert machine.invoke(4,-1)==0  # One-past base can move back into the object.
        assert machine.invoke(5,0)==0   # All-zero GEP preserves a defined out-of-bounds pointer.
        assert machine.invoke(0,4)==0
        assert machine.invoke(0,5)==1


def test_zext_nneg_and_identifier_names(tmp_path):
    source = '''define i16 @volatile(i8 %noundef) {
 %nsw = zext nneg i8 %noundef to i16
 ret i16 %nsw
}'''
    with font(tmp_path,source) as machine:
        assert machine.invoke(127)==127
        with pytest.raises(WasmTrap,match='poison_result'): machine.invoke(128)


def test_checked_in_fonts_and_bitcode_reproduce(tmp_path):
    from importlib.util import spec_from_file_location,module_from_spec
    spec = spec_from_file_location('llvm_examples',HERE/'build_examples.py')
    examples = module_from_spec(spec)
    spec.loader.exec_module(examples)
    import json
    for name,source,function,args,expected in examples.DEMOS:
        path = tmp_path/f'{name}.ttf'
        manifest = build(HERE/'examples'/source,path,function=function,limits=Limits(max_steps=32))
        bundled = HERE/'fonts'/path.name
        assert path.read_bytes()==bundled.read_bytes()
        assert manifest==json.loads(bundled.with_suffix('.json').read_text())
    for source,name,args,expected in [('clang.bc','indexed',(2,100),111),('rust.bc','rust_mix',(2,3),643)]:
        with font(tmp_path,HERE/'examples'/source,function=name) as machine: assert machine.invoke(*args)==expected
