"""Differential tests: complete modules -> GSUB -> HarfBuzz versus V8."""
import hashlib
import json
import random
from pathlib import Path
import subprocess
import shutil
import pytest
from wasmfont.compiler import compile_source,Limits,NativeCompiler
from wasmfont.frontend import load,parse_text,binary,validate
from wasmfont.oracle import execute_binary
from wasmfont.runtime import NativeFont,TokenShaper,WasmTrap,ExecutionBoundExceeded,IncompleteShaping
from wasmfont.gsub.circuit import Circuit,Value,emit_font,ResourceLimit
from fontTools.ttLib import TTFont


def differential(tmp_path,wat,cases,*,limits=None,binary_input=False):
    source=tmp_path/'program.wat';source.write_text(wat)
    module,data=load(source)
    if binary_input:source=tmp_path/'program.wasm';source.write_bytes(data)
    font=tmp_path/'program.ttf';manifest=compile_source(source,font,export='run',limits=limits)
    index=module.exports['run'][1];fn=module.functions[index]
    expected=execute_binary(data,'run',fn.params,cases)
    with NativeFont(font) as native:
        for args,reference in zip(cases,expected):
            if 'trap' in reference:
                with pytest.raises(WasmTrap):native.invoke(*args)
            else:
                output=native.invoke(*args);output=(output,) if len(fn.results)==1 else output
                assert output==tuple(int(v)&((1<<int(t[1:]))-1) for v,t in zip(reference['values'],fn.results)),(args,reference,output)
    return manifest,font


def pairs(width,count=20):
    mask=(1<<width)-1;sign=1<<(width-1);rng=random.Random(89001+width)
    boundary=[0,1,mask,sign,sign-1,mask-1]
    return [(x,y) for x in boundary for y in boundary]+[(rng.getrandbits(width),rng.getrandbits(width)) for _ in range(count)]


@pytest.mark.parametrize('width',[32,64])
def test_independent_intermediates(tmp_path,width):
    ty=f'i{width}'
    wat=f'''(module (func (export "run") (param $a {ty}) (param $b {ty}) (param $c {ty}) (result {ty})
      (local $sum {ty}) (local $delta {ty})
      local.get $a local.get $b {ty}.add local.tee $sum drop
      local.get $a local.get $b {ty}.sub local.set $delta
      local.get $sum local.get $delta {ty}.xor local.get $c {ty}.add))'''
    cases=[(a,b,c) for (a,b),c in zip(pairs(width),range(100))]
    manifest,font=differential(tmp_path,wat,cases,binary_input=True)
    assert manifest['lowered_instructions']>=10
    with NativeFont(font) as native:
        tokens=native.encode(cases[0]);assert any(t.endswith('_u') for t in tokens)
        with pytest.raises(IncompleteShaping):native.decode(native.shaper.shape(tokens,enabled=False))
    # Canonical output positions are explicitly written by the font.
    output=manifest['results'][0];assert output==list(range(output[0],output[0]+width))


@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('operation',['add','sub','and','or','xor','mul'])
def test_native_binary_operators(tmp_path,width,operation):
    ty=f'i{width}'
    wat=f'(module (func (export "run") (param {ty} {ty}) (result {ty}) local.get 0 local.get 1 {ty}.{operation}))'
    differential(tmp_path,wat,pairs(width,8 if operation=='mul' else 20))


@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('operation',['eq','ne','lt_s','lt_u','gt_s','gt_u','le_s','le_u','ge_s','ge_u'])
def test_native_comparison_composition(tmp_path,width,operation):
    ty=f'i{width}'
    wat=f'''(module (func (export "run") (param {ty} {ty}) (result i32)
      local.get 0 local.get 1 {ty}.{operation} i32.const 7 i32.add))'''
    differential(tmp_path,wat,pairs(width,10))


@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('operation',['shl','shr_u','shr_s','rotl','rotr'])
def test_dynamic_shifts(tmp_path,width,operation):
    ty=f'i{width}'
    wat=f'(module (func (export "run") (param {ty} {ty}) (result {ty}) local.get 0 local.get 1 {ty}.{operation}))'
    rng=random.Random(width)
    cases=[(rng.getrandbits(width),amount) for amount in (0,1,width-1,width,width+1,2*width,2*width-1,(1<<width)-1)]
    cases+=pairs(width,12)
    differential(tmp_path,wat,cases)


@pytest.mark.parametrize('width',[32,64])
@pytest.mark.parametrize('operation',['eqz','clz','ctz','popcnt'])
def test_unary_results_are_binary_registers(tmp_path,width,operation):
    source=f'i{width}';result='i32' if operation=='eqz' else source
    wat=f'''(module (func (export "run") (param {source}) (result {result})
      local.get 0 {source}.{operation} {result}.const 3 {result}.add))'''
    rng=random.Random(832+width)
    cases=[(x,) for x in [0,1,(1<<width)-1,1<<(width-1),*[(1<<i) for i in range(width)],*[rng.getrandbits(width) for _ in range(12)]]]
    differential(tmp_path,wat,cases)


@pytest.mark.parametrize('operation,source,result',[
 ('i32.wrap_i64','i64','i32'),('i64.extend_i32_s','i32','i64'),('i64.extend_i32_u','i32','i64'),
 ('i32.extend8_s','i32','i32'),('i32.extend16_s','i32','i32'),('i64.extend8_s','i64','i64'),
 ('i64.extend16_s','i64','i64'),('i64.extend32_s','i64','i64')])
def test_native_conversions(tmp_path,operation,source,result):
    wat=f'(module (func (export "run") (param {source}) (result {result}) local.get 0 {operation} {result}.const 9 {result}.xor))'
    differential(tmp_path,wat,[(v,) for v in [0,-1,127,128,255,32767,32768,65535,0x7fffffff,0x80000000,0xffffffffffffffff]])


@pytest.mark.parametrize('width',[32,64])
def test_dynamic_select_and_locals(tmp_path,width):
    ty=f'i{width}'
    wat=f'''(module (func (export "run") (param {ty} {ty} i32) (result {ty}) (local {ty})
      local.get 0 local.get 1 {ty}.add local.get 0 local.get 1 {ty}.sub local.get 2 select
      local.tee 3 local.get 3 {ty}.xor local.get 3 {ty}.or))'''
    differential(tmp_path,wat,[(a,b,c) for a,b in pairs(width,2) for c in (0,1,0x80000000)])


def test_calls_mixed_widths_multiple_results_and_return(tmp_path):
    wat='''(module
      (func $pair (param $x i32) (result i32 i64)
        local.get $x i32.const 9 i32.add local.get $x i64.extend_i32_s return)
      (func (export "run") (param i32) (result i64)
        (local $wide i64) local.get 0 call $pair local.set $wide
        i64.extend_i32_u local.get $wide i64.xor))'''
    differential(tmp_path,wat,[(x,) for x in (0,1,-1,0x80000000,0x7fffffff)],binary_input=True)


def test_if_result_and_local_merge(tmp_path):
    wat='''(module (func (export "run") (param $a i32) (param $b i32) (result i32) (local $v i32)
      (if (result i32) (i32.lt_s (local.get $a) (local.get $b))
        (then (local.set $v (i32.add (local.get $a) (local.get $b))) (i32.const 7))
        (else (local.set $v (i32.sub (local.get $a) (local.get $b))) (i32.const 11)))
      local.get $v i32.xor))'''
    differential(tmp_path,wat,pairs(32))


def test_branch_result_and_stack_unwind(tmp_path):
    wat='''(module (func (export "run") (param $a i32) (result i32)
      i32.const 100 block $out (result i32)
        i32.const 7 local.get $a br_if $out drop i32.const 13
      end i32.add))'''
    differential(tmp_path,wat,[(0,),(1,),(-1,)],binary_input=True)


def test_br_table(tmp_path):
    wat='''(module (func (export "run") (param $x i32) (result i32) (local $r i32)
      block $done block $case1 block $case0
        local.get $x br_table $case0 $case1 $done
      end i32.const 10 local.set $r br $done
      end i32.const 20 local.set $r
      end local.get $r))'''
    differential(tmp_path,wat,[(v,) for v in (0,1,2,3,0xffffffff)],binary_input=True)


LOOP='''(module (func (export "run") (param $n i32) (result i32) (local $sum i32)
 block $done loop $again local.get $n i32.eqz br_if $done
 local.get $sum local.get $n i32.add local.set $sum
 local.get $n i32.const 1 i32.sub local.set $n br $again end end local.get $sum))'''


def test_bounded_loop(tmp_path):
    _,font=differential(tmp_path,LOOP,[(i,) for i in range(8)])
    with NativeFont(font) as native:
        for i in (8,9,0xffffffff):
            with pytest.raises(ExecutionBoundExceeded,match='loop'):native.invoke(i)


def test_nested_loops_and_conditional_exit(tmp_path):
    wat='''(module (func (export "run") (param $n i32) (result i32) (local $i i32) (local $j i32) (local $r i32)
      block $end loop $outer
        local.get $i local.get $n i32.ge_u br_if $end
        i32.const 0 local.set $j
        block $inner_end loop $inner
          local.get $j i32.const 2 i32.ge_u br_if $inner_end
          local.get $r i32.const 1 i32.add local.set $r
          local.get $j i32.const 1 i32.add local.set $j br $inner
        end end
        local.get $i i32.const 1 i32.add local.set $i br $outer
      end end local.get $r))'''
    differential(tmp_path,wat,[(i,) for i in range(4)],limits=Limits(loop_iterations=4))


def test_bounded_recursion(tmp_path):
    wat='''(module (func $sum (export "run") (param $n i32) (result i32)
      (if (result i32) (i32.eqz (local.get $n)) (then (i32.const 0))
        (else (i32.add (local.get $n) (call $sum (i32.sub (local.get $n) (i32.const 1))))))))'''
    _,font=differential(tmp_path,wat,[(i,) for i in range(5)],limits=Limits(call_depth=5))
    with NativeFont(font) as native:
        with pytest.raises(ExecutionBoundExceeded,match='call'):native.invoke(5)


def test_conditional_unreachable_not_speculatively_trapped(tmp_path):
    wat='''(module (func (export "run") (param i32) (result i32)
      local.get 0 if unreachable end i32.const 42))'''
    differential(tmp_path,wat,[(0,),(1,),(-1,)])


@pytest.mark.parametrize('operation',['div_u','rem_u','div_s','rem_s'])
def test_native_division_and_traps(tmp_path,operation):
    wat=f'(module (func (export "run") (param i32 i32) (result i32) local.get 0 local.get 1 i32.{operation}))'
    differential(tmp_path,wat,pairs(32,6))


@pytest.mark.parametrize('width',[32,64])
def test_bounded_dynamic_memory_roundtrip(tmp_path,width):
    ty=f'i{width}'
    wat=f'''(module (memory 1) (func (export "run") (param $a i32) (param $v {ty}) (result {ty})
      local.get $a local.get $v {ty}.store local.get $a {ty}.load))'''
    rng=random.Random(width)
    cases=[(address,rng.getrandbits(width)) for address in range(17-width//8)]
    _,font=differential(tmp_path,wat,cases+[(65536,42),(0xffffffff,42)])
    with NativeFont(font) as native:
        with pytest.raises(ExecutionBoundExceeded,match='memory'):native.invoke(16,0)
        with pytest.raises(WasmTrap,match='memory_out_of_bounds'):native.invoke(65536,0)


@pytest.mark.parametrize('source,width,loadop',[
 ('i32',8,'i32.load8_s'),('i32',8,'i32.load8_u'),('i32',16,'i32.load16_s'),('i32',16,'i32.load16_u'),
 ('i64',8,'i64.load8_s'),('i64',8,'i64.load8_u'),('i64',16,'i64.load16_s'),('i64',16,'i64.load16_u'),
 ('i64',32,'i64.load32_s'),('i64',32,'i64.load32_u')])
def test_narrow_memory_sign_extension(tmp_path,source,width,loadop):
    wat=f'''(module (memory 1) (func (export "run") (param $v {source}) (result {source})
      i32.const 3 local.get $v {source}.store{width} i32.const 3 {loadop}))'''
    differential(tmp_path,wat,[(x,) for x in (0,(1<<(width-1))-1,1<<(width-1),(1<<width)-1,-1)])


def test_memory_offset_overflow_is_not_wrapped(tmp_path):
    wat='''(module (memory 1) (func (export "run") (param i32) (result i32)
      local.get 0 i32.load offset=8 align=1))'''
    differential(tmp_path,wat,[(0,),(0xfffffff8,),(0xffffffff,),(65535,)])


def test_data_globals_calls_and_fresh_instances(tmp_path):
    wat=r'''(module (memory 1) (data (i32.const 0) "\01\02\03\04")
      (global $g (mut i32) (i32.const 5))
      (func $update (param i32) local.get 0 global.set $g)
      (func (export "run") (param i32) (result i32)
        global.get $g local.get 0 call $update global.get $g i32.add i32.const 0 i32.load i32.xor))'''
    _,font=differential(tmp_path,wat,[(1,),(7,),(-1,)])
    with NativeFont(font) as native:assert native.invoke(9)==native.invoke(9)


def test_conditional_memory_and_global_phi(tmp_path):
    wat='''(module (memory 1) (global $g (mut i32) (i32.const 0))
      (func (export "run") (param $c i32) (param $v i32) (result i32)
        local.get $c if
          i32.const 0 local.get $v i32.store local.get $v global.set $g
        else
          i32.const 0 i32.const 13 i32.store i32.const 7 global.set $g
        end i32.const 0 i32.load global.get $g i32.add))'''
    differential(tmp_path,wat,[(c,v) for c in (0,1,-1) for v in (0,123,0xffffffff)])


def test_conditional_memory_trap(tmp_path):
    wat='''(module (memory 1) (func (export "run") (param i32) (result i32)
      (if (result i32) (local.get 0) (then (i32.load (i32.const 65536))) (else (i32.const 7)))))'''
    differential(tmp_path,wat,[(0,),(1,)])


def test_memory_size(tmp_path):
    differential(tmp_path,'(module (memory 2) (func (export "run") (result i32) memory.size))',[()])


@pytest.mark.parametrize('wat',[
 '(module (func (export "run") (result i32) i32.add))',
 '(module (func (export "run") (result i32) i64.const 0))',
 '(module (func (export "run") (result i32) local.get 3))',
 '(module (func (export "run") (result i32) br 1))',
 '(module (global $g i32 (i32.const 0)) (func (export "run") i32.const 1 global.set $g))',
])
def test_independent_validator_rejects_ill_typed_wat(tmp_path,wat):
    source=tmp_path/'bad.wat';source.write_text(wat)
    with pytest.raises(ValueError,match='V8 rejected'):compile_source(source,tmp_path/'bad.ttf')


def test_unsupported_features_fail_closed(tmp_path):
    for i,wat in enumerate([
      '(module (memory 1) (func (export "run") (result i32) i32.const 1 memory.grow))',
      '(module (table 1 funcref))',
      '(module (func (export "run") (result f32) f32.const 0))',
    ]):
        source=tmp_path/f'unsupported{i}.wat';source.write_text(wat)
        with pytest.raises(NotImplementedError):compile_source(source,tmp_path/f'unsupported{i}.ttf')


def test_font_abi_and_budget_errors(tmp_path):
    source=tmp_path/'p.wat';source.write_text(LOOP)
    with pytest.raises(ResourceLimit):compile_source(source,tmp_path/'budget.ttf',limits=Limits(max_gates=16))
    font=tmp_path/'p.ttf';compile_source(source,font)
    with NativeFont(font) as native:
        with pytest.raises(ValueError):native.invoke(1,2)
        with pytest.raises(TypeError):native.invoke(1.5)
        with pytest.raises(IncompleteShaping):native.decode(native.encode([0]))
    manifest=json.loads(font.with_suffix('.json').read_text());manifest['font_sha256']='00'*32
    font.with_suffix('.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='does not match'):NativeFont(font)


@pytest.mark.parametrize('operation',['add','sub','mul','and','or','xor','lt_u','lt_s','shl','shr_u','shr_s','rotl','rotr'])
def test_exhaustive_reduced_width_circuits(operation):
    c=Circuit();a=c.argument(0,4);b=c.argument(1,4)
    if operation in ('add','sub'):result=c.add(a,b,operation=='sub')
    elif operation in ('and','or','xor'):result=c.bitwise(operation,a,b)
    elif operation=='mul':result=c.mul(a,b)
    elif operation.startswith('lt'):result=Value((c.lt(a,b,operation=='lt_s'),))
    else:result=c.shift(operation,a,b)
    for aa in range(16):
        for bb in range(16):
            x=aa if aa<8 else aa-16;y=bb if bb<8 else bb-16;k=bb&3
            expected={'add':aa+bb,'sub':aa-bb,'mul':aa*bb,'and':aa&bb,'or':aa|bb,'xor':aa^bb,
                      'lt_u':int(aa<bb),'lt_s':int(x<y),'shl':aa<<k,'shr_u':aa>>k,'shr_s':x>>k,
                      'rotl':(aa<<k)|(aa>>(4-k)),'rotr':(aa>>k)|(aa<<(4-k))}[operation]&15
            env=c.evaluate_for_test([aa,bb]);assert sum(env[w]<<i for i,w in enumerate(result.bits))==expected


@pytest.mark.parametrize('operation',['add','sub','mul'])
def test_exhaustive_reduced_width_harfbuzz(tmp_path,operation):
    c=Circuit();a=c.argument(0,4);b=c.argument(1,4)
    value=c.mul(a,b) if operation=='mul' else c.add(a,b,operation=='sub')
    font=tmp_path/'reduced.ttf';emit_font(c,[value],{},['i4','i4'],['i4'],font)
    with NativeFont(font) as native:
        for x in range(16):
            for y in range(16):
                expected=(x*y if operation=='mul' else x-y if operation=='sub' else x+y)&15
                assert native.invoke(x,y)==expected


def test_wat_comments_names_grouped_params_and_typeuse(tmp_path):
    wat='''(module (; outer (; nested ;) comment ;)
      (type $sig (func (param i32 i32) (result i32)))
      (func $mix (type $sig) local.get 0 local.get 1 i32.xor)
      (export "run" (func $mix)))'''
    differential(tmp_path,wat,pairs(32,3))


@pytest.mark.parametrize('export,width',[('run',32),('run64',64)])
def test_clang_compiled_wasm(tmp_path,export,width):
    source=Path(__file__).resolve().parents[1]/'examples'/'mix.wasm'
    module,data=load(source)
    assert len(module.functions)==3
    if export=='run':assert any(op=='call' for op,arg in module.functions[module.exports[export][1]].code)
    font=tmp_path/'from-c.ttf';compile_source(source,font,export=export)
    cases=pairs(width,40)
    fn=module.functions[module.exports[export][1]]
    reference=execute_binary(data,export,fn.params,cases)
    with NativeFont(font) as native:
        for args,expected in zip(cases,reference):assert native.invoke(*args)==int(expected['values'][0])&((1<<width)-1)


def test_compile_c_source_with_existing_clang(tmp_path):
    clang=shutil.which('clang')
    if not clang:pytest.skip('Clang not installed; bundled C-produced binary is tested separately')
    targets=subprocess.run([clang,'--print-targets'],check=True,capture_output=True,text=True,timeout=20)
    if not any(line.strip().startswith('wasm32') for line in targets.stdout.splitlines()):
        pytest.skip('Installed Clang has no wasm32 target; bundled C-produced binary is tested separately')
    if not (shutil.which('wasm-ld') or Path(clang).resolve().with_name('wasm-ld').is_file()):
        pytest.skip('wasm-ld not installed; bundled C-produced binary is tested separately')
    source=Path(__file__).resolve().parents[1]/'examples'/'mix.c';out=tmp_path/'rebuilt.wasm'
    command=[clang,'--target=wasm32','-O2','-nostdlib','-ffreestanding','-Wl,--no-entry',
             '-Wl,--export=run','-Wl,--export=run64','-Wl,--strip-all',str(source),'-o',str(out)]
    subprocess.run(command,check=True,capture_output=True,timeout=20)
    font=tmp_path/'rebuilt.ttf';compile_source(out,font,export='run')
    module,data=load(out);ref=execute_binary(data,'run',['i32','i32'],[(123,456)])
    with NativeFont(font) as native:assert native.invoke(123,456)==int(ref[0]['values'][0])&0xffffffff


def test_typeuse_with_named_local(tmp_path):
    wat='''(module (type $t (func (param i32) (result i32)))
      (func (export "run") (type $t) (local $x i32)
        i32.const 9 local.set $x local.get 0 local.get $x i32.add))'''
    # Check the WAT name resolver against the intended signature, not just its own binary.
    module=parse_text(wat)
    assert ('local.set',1) in module.functions[0].code
    differential(tmp_path,wat,[(0,),(4,),(-1,)])


def test_zero_page_memory_and_void_functions(tmp_path):
    differential(tmp_path,'(module (memory 0 0) (func (export "run") (result i32) memory.size))',[()])
    differential(tmp_path,'(module (func (export "run") nop))',[()])


def test_canonical_constant_and_identity_outputs_need_gsub(tmp_path):
    wat='(module (func (export "run") (param i32) (result i32 i32) local.get 0 i32.const 42))'
    _,font=differential(tmp_path,wat,[(0,),(99,),(-1,)])
    with NativeFont(font) as native:
        for args in [(0,),(99,)]:
            with pytest.raises(IncompleteShaping):native.decode(native.shaper.shape(native.encode(args),enabled=False))


def test_deterministic_font_and_command_line(tmp_path):
    import sys
    source=tmp_path/'a.wat';source.write_text('(module (func (export "run") (param i32 i32) (result i32) local.get 0 local.get 1 i32.add))')
    a=tmp_path/'a.ttf';b=tmp_path/'b.ttf';compile_source(source,a);compile_source(source,b)
    assert a.read_bytes()==b.read_bytes()
    root=Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable,str(root/'build.py'),str(source),'-o',str(b)],check=True,capture_output=True,timeout=20)
    result=subprocess.run([sys.executable,str(root/'run.py'),str(b),'4294967295','1'],check=True,capture_output=True,text=True,timeout=20)
    assert result.stdout.strip()=='0'
