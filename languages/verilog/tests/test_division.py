# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Fixed-width division, guarded errors, actual shaping and finite gate budgets."""
import itertools
from pathlib import Path
import random
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from verilogfont.compiler import build
from verilogfont.frontend import compile_source
from fontcircuit.gsub.circuit import ResourceLimit
from fontcircuit.runtime import NativeFont, WasmTrap, IncompleteShaping


def signed_integer(bits,width):
    return bits-(1 << width) if bits & (1 << (width-1)) else bits


def trunc_divmod(a,b):
    q=abs(a)//abs(b)
    if (a<0) != (b<0): q=-q
    return q,a-q*b


@pytest.mark.parametrize('signed',[False,True])
@pytest.mark.parametrize('width',[1,3,5])
def test_exhaustive_small_division_and_remainder_in_font(tmp_path,width,signed):
    qualifier='signed' if signed else ''
    path=tmp_path/'divide.ttf'
    manifest=build(f'''module m(input {qualifier} [{width-1}:0] a,b,
      output {qualifier} [{width-1}:0] q,r);assign q=a/b;assign r=a%b;endmodule''',path)
    assert set(manifest['flags'])=={'trap.integer_divide_by_zero'}
    mask=(1 << width)-1
    with NativeFont(path) as font:
        for a,b in itertools.product(range(1 << width),repeat=2):
            if b==0:
                with pytest.raises(WasmTrap,match='integer_divide_by_zero'): font.invoke(a,b)
            else:
                x,y=(signed_integer(n,width) for n in (a,b)) if signed else (a,b)
                q,r=trunc_divmod(x,y)
                assert font.invoke(a,b)==(q&mask,r&mask)
        with pytest.raises(IncompleteShaping):
            font.decode(font.shaper.shape(font.encode([1,1]),enabled=False))


@pytest.mark.parametrize('signed',[False,True])
@pytest.mark.parametrize('divisor',[-16,-8,-3,-1,1,2,3,8,15])
def test_constant_divisors_and_signed_remainders_exhaustively(tmp_path,signed,divisor):
    qualifier='signed' if signed else ''
    if not signed: divisor &= 31
    literal=f"-5'sd{-divisor}" if divisor<0 else f"5'sd{divisor}" if signed else f"5'd{divisor}"
    path=tmp_path/'constant.ttf'
    build(f'''module m(input {qualifier} [4:0] a,output {qualifier} [4:0] q,r);
      assign q=a/{literal};assign r=a%{literal};endmodule''',path)
    with NativeFont(path) as font:
        for bits in range(32):
            a=signed_integer(bits,5) if signed else bits
            q,r=trunc_divmod(a,divisor)
            assert font.invoke(bits)==(q&31,r&31)


def test_assignment_context_and_signed_overflow_are_verilog_values(tmp_path):
    path=tmp_path/'context.ttf'
    build('''module m(input signed [7:0] a,b,output signed [7:0] q,r,
      output signed [8:0] wide_q,wide_r);
      assign q=a/b;assign r=a%b;assign wide_q=a/b;assign wide_r=a%b;endmodule''',path)
    with NativeFont(path) as font:
        assert font.invoke(-128,-1)==(128,0,128,0)
        assert font.invoke(-7,3)==(254,255,510,511)
        assert font.invoke(7,-3)==(254,1,510,1)


def test_zero_checks_survive_wire_identities_and_constant_results(tmp_path):
    path=tmp_path/'identities.ttf'
    build('''module m(input [63:0] a,output [63:0] self_q,self_r,zero_q,zero_r);
      assign self_q=a/a;assign self_r=a%a;
      assign zero_q=64'd0/a;assign zero_r=64'd0%a;endmodule''',path)
    with NativeFont(path) as font:
        for a in [1,2,1<<63,(1<<64)-1]: assert font.invoke(a)==(1,0,0,0)
        with pytest.raises(WasmTrap,match='integer_divide_by_zero'): font.invoke(0)


def test_ternary_procedural_case_and_logical_guards(tmp_path):
    path=tmp_path/'guarded.ttf'
    build('''module m(input signed [4:0] a,b,input enable,
      output signed [4:0] q,output reg signed [4:0] r,
      output both,either);
      assign q=b ? a/b : 5'sd0;
      always @* begin
        r=0;
        case(enable) 1: if(b) r=a%b; default:r=0;endcase
      end
      assign both=(b!=0) && (a/b!=0);
      assign either=(b==0) || (a%b==0);
    endmodule''',path)
    with NativeFont(path) as font:
        for a,b,e in itertools.product(range(-16,16),range(-16,16),range(2)):
            q,r=trunc_divmod(a,b) if b else (0,0)
            assert font.invoke(a,b,e)==(q&31,(r if e else 0)&31,int(b!=0 and q!=0),int(b==0 or r==0))


@pytest.mark.parametrize('operator',['/','%'])
def test_known_zero_divisor_obeys_the_taken_path(tmp_path,operator):
    path=tmp_path/'known-zero.ttf'
    build(f'''module m(input [3:0] a,input take,output [3:0] y);
      assign y=take ? a{operator}4'd0 : 4'd7;endmodule''',path)
    with NativeFont(path) as font:
        assert font.invoke(5,0)==7
        with pytest.raises(WasmTrap,match='integer_divide_by_zero'): font.invoke(5,1)


def test_unused_continuous_division_is_checked_independently(tmp_path):
    path=tmp_path/'unused.ttf'
    build('''module m(input [3:0] a,b,input take,output [3:0] y);
      wire [3:0] divided=a/b;assign y=take ? divided : a;endmodule''',path)
    with NativeFont(path) as font:
        assert font.invoke(7,2,0)==7
        with pytest.raises(WasmTrap,match='integer_divide_by_zero'): font.invoke(7,0,0)


@pytest.mark.parametrize('signed',[False,True])
def test_full_64_bit_dynamic_division_in_font(tmp_path,signed):
    qualifier='signed' if signed else ''
    path=tmp_path/'wide.ttf'
    manifest=build(f'''module m(input {qualifier} [63:0] a,b,output {qualifier} [63:0] q,r);
      assign q=a/b;assign r=a%b;endmodule''',path)
    assert manifest['metrics']['gates']<6000
    mask=(1 << 64)-1
    rng=random.Random(184)
    values=[0,1,2,3,(1<<63)-1,1<<63,(1<<63)+1,mask]
    cases=list(itertools.product(values,repeat=2))+[(rng.getrandbits(64),rng.getrandbits(64)) for _ in range(30)]
    with NativeFont(path) as font:
        for a,b in cases:
            if b==0:
                with pytest.raises(WasmTrap,match='integer_divide_by_zero'): font.invoke(a,b)
            else:
                a,b=(signed_integer(n,64) for n in (a,b)) if signed else (a,b)
                q,r=trunc_divmod(a,b)
                assert font.invoke(a,b)==(q&mask,r&mask)


def test_division_budget_sharing_and_structural_optimizations():
    source='''module m(input [63:0] a,b,output [63:0] q,r);
      assign q=a/b;assign r=a%b;endmodule'''
    _,c,_=compile_source(source)
    assert c.gate_count<5000
    with pytest.raises(ResourceLimit,match='max_gates=100'):
        compile_source(source,max_gates=100)
    _,c,_=compile_source('''module m(input [63:0] a,output [63:0] q,r);
      assign q=a/64'd8;assign r=a%64'd8;endmodule''')
    assert c.gate_count==0
    _,c,_=compile_source('''module m(input [63:0] a,output [63:0] q,r);
      assign q=a/a;assign r=a%a;endmodule''')
    assert c.gate_count<70


def test_cli_reports_zero_divisors_without_results_or_traceback(tmp_path):
    path=tmp_path/'divide.ttf'
    build('''module m(input [3:0] a,b,output [3:0] y);assign y=a/b;endmodule''',path)
    result=subprocess.run([sys.executable,str(HERE/'run.py'),str(path),'7','0'],capture_output=True,text=True)
    assert result.returncode==2
    assert 'division or remainder by zero' in result.stderr
    assert 'Traceback' not in result.stderr
    assert not result.stdout


def test_widened_signed_division_retains_overflow_bit_while_narrowing():
    source='''module m(input signed [4:0] a,b,output signed [63:0] q,r);
      assign q=a/b;assign r=a%b;endmodule'''
    _,c,_=compile_source(source)
    assert c.gate_count<300


def test_widened_signed_division_preserves_positive_minimum_quotient(tmp_path):
    path=tmp_path/'extended.ttf'
    build('''module m(input signed [4:0] a,b,output signed [63:0] q,r);
      assign q=a/b;assign r=a%b;endmodule''',path)
    mask=(1 << 64)-1
    with NativeFont(path) as font:
        for a,b in itertools.product(range(-16,16),repeat=2):
            if b:
                q,r=trunc_divmod(a,b)
                assert font.invoke(a,b)==(q&mask,r&mask)
            else:
                with pytest.raises(WasmTrap,match='integer_divide_by_zero'): font.invoke(a,b)


def test_quotient_and_remainder_reuse_the_same_divider():
    source='''module m(input signed [31:0] a,b,output signed [31:0] q%s);
      assign q=a/b;%s endmodule'''
    _,only_q,_=compile_source(source % ('',''))
    _,both,_=compile_source(source % (',r','assign r=a%b;'))
    # A second result can add linear sign correction, not another divider.
    assert both.gate_count <= only_q.gate_count+4*32


def test_cli_rejects_over_budget_division_without_writing_artifacts(tmp_path):
    source=tmp_path/'wide.v'
    source.write_text('''module m(input [63:0] a,b,output [63:0] q);
      assign q=a/b;endmodule''')
    output=tmp_path/'wide.ttf'
    result=subprocess.run([sys.executable,str(HERE/'build.py'),str(source),'-o',str(output),'--max-gates','100'],
                          capture_output=True,text=True)
    assert result.returncode==2
    assert 'max_gates=100' in result.stderr
    assert not output.exists() and not output.with_suffix('.json').exists()
