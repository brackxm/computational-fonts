# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Bounded static expansion, pure functions, array words and source diagnostics."""
import itertools
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from verilogfont.compiler import build
from verilogfont.frontend import compile_source
from verilogfont.syntax import SourceText, VerilogError, VerilogResourceLimit
from fontcircuit.gsub.circuit import ResourceLimit
from fontcircuit.runtime import NativeFont, WasmTrap
from test_iverilog import compare, IVERILOG, VVP

POPULATION = '''module m(input [63:0] a,output reg [6:0] y,output [31:0] final_i);
  integer i;
  always @* begin y=0; for(i=0;i<64;i=i+1) y=y+a[i]; end
  assign final_i=i;
endmodule'''

GENERATED = '''module top #(parameter W=8, ENABLE=1)(input [W-1:0] a,b,output [W-1:0] y);
  genvar g;
  generate if(ENABLE) begin: active
    for(g=0;g<W;g=g+1) begin: lanes
      localparam INDEX=g;
      wire x;
      cell_xor u(.a(a[INDEX]),.b(b[INDEX]),.y(x));
      assign y[INDEX]=x;
    end
  end else begin: inactive
    assign y=a;
  end endgenerate
endmodule
module cell_xor(input a,b,output y); assign y=a^b; endmodule'''

FUNCTIONS = '''module m(input signed [3:0] a,b,input choose,output signed [5:0] y,output reg [4:0] z);
  parameter BIAS=2;
  function signed [5:0] add_bias(input signed [3:0] x, v);
    reg signed [4:0] sum;
    begin sum=x+v; add_bias=sum+BIAS; end
  endfunction
  function [4:0] count;
    input [7:0] x;
    integer i;
    reg [4:0] tmp;
    begin tmp=0; for(i=7;i>=0;i=i-1) tmp=tmp+x[i]; count=tmp; end
  endfunction
  assign y=choose ? add_bias(a,b) : add_bias(b,a);
  always @* begin z=a; z=z+1; z=count({z[3:0],b}); end
endmodule'''

ARRAYS = '''module m(input signed [3:0] a,b,input signed [3:0] index,input [2:0] bit_index,
  input [1:0] patch,input [1:0] offset,output reg signed [5:0] y,output reg [3:0] word);
  reg signed [3:0] words[2:4];
  always @* begin
    words[2]=a; words[3]=b; words[4]=a+b;
    words[index][offset +: 2]=patch;
    word=words[4];
    y=0;
    if(index>=2 && index<=4) y=words[index];
  end
endmodule'''

FUNCTION_ARRAY = '''module m(input [7:0] a,input s,output [7:0] y);
  function [7:0] choose(input [7:0] value,input select);
    reg [7:0] words[0:1];
    begin words[0]=value; words[1]=~value; choose=words[select]; end
  endfunction
  assign y=choose(a,s);
endmodule'''

CASES = [
    ('''module m(input [3:0] a,input [2:0] index,output [3:0] y);
      function [3:0] f(input [3:0] x,input [2:0] n);
        reg [3:0] words[0:3];integer i;
        begin for(i=0;i<4;i=i+1)words[i]=x+i;f=words[n];end
      endfunction
      assign y=f(a,index);
    endmodule''','invalid_array_index'),
    (POPULATION,'invalid_select'), (GENERATED,'invalid_select'), (FUNCTIONS,'invalid_select'),
    (ARRAYS,'invalid_array_index'), (FUNCTION_ARRAY,'invalid_array_index'),
    ('''module m(input [7:0] a,output reg [7:0] y,output [31:0] final_i,final_j);
      integer i,j;
      always @* begin
        y=0;
        for(i=0;i<2;i=i+1) for(j=0;j<4;j=j+1) y[i*4+j]=a[7-i*4-j];
      end
      assign final_i=i; assign final_j=j;
    endmodule''','invalid_select'),
    ('''module m(input [3:0] a,output reg [3:0] y,output [31:0] final_i);
      integer i;
      always @* begin y=a; for(i=5;i<2;i=i+1) y=0; end
      assign final_i=i;
    endmodule''','invalid_select'),
    ('''module m(input [7:0] a,output [7:0] y);
      genvar row,col;
      for(row=0;row<2;row=row+1) begin: rows
        for(col=0;col<4;col=col+1) begin: cols
          assign y[row*4+col]=a[7-row*4-col];
        end
      end
    endmodule''','invalid_select'),
    ('''module m(input signed [3:0] a,output signed [7:0] y,z);
      function signed [3:0] twice(input signed [3:0] x); twice=x+x; endfunction
      function integer wider; input signed [3:0] x; begin wider=twice(x); end endfunction
      assign y=twice(a); assign z=wider(a);
    endmodule''','invalid_select'),
    ('''module m(input [3:0] a,output [3:0] y);
      wire [3:0] mem[1:0];
      assign mem[0]=a; assign mem[1]=~mem[0]; assign y=mem[1];
    endmodule''','invalid_array_index'),
    ('''module m(input [3:0] a,input signed [63:0] i,output [3:0] y);
      wire [3:0] mem[-1:1];
      assign mem[-1]=a; assign mem[0]=~a; assign mem[1]=a^4'h5;
      assign y=i>=-1 && i<=1 ? mem[i] : 4'h0;
    endmodule''','invalid_array_index'),
    ('''module m(input [3:0] a,b,input s,output [3:0] y);
      function [3:0] divide(input [3:0] x,d); divide=x/d; endfunction
      assign y=s ? divide(a,b) : a;
    endmodule''','integer_divide_by_zero'),
    ('''module m(input [3:0] a,output reg [3:0] y);
      function [3:0] f(input [3:0] x); begin x=x+1; f=x; end endfunction
      always @* begin y=a; y=f(y); y=f(y); end
    endmodule''','invalid_select'),
]


@pytest.mark.skipif(not (IVERILOG and VVP),reason='optional Icarus Verilog simulator is unavailable')
@pytest.mark.parametrize('source,undefined',CASES)
def test_expansion_against_icarus(tmp_path,source,undefined):
    compare(tmp_path,source,undefined=undefined)


def test_64_iteration_population_count_and_final_iterator(tmp_path):
    path=tmp_path/'pop.ttf'
    build(POPULATION,path)
    with NativeFont(path) as font:
        for value in (0,1,3,0x8000000000000000,0x123456789abcdef0,0xffffffffffffffff):
            assert font.invoke(value)==(value.bit_count(),64)


@pytest.mark.parametrize('enable',[0,1])
def test_generate_specialization_and_hierarchy_paths(tmp_path,enable):
    path=tmp_path/'generate.ttf'
    manifest=build(GENERATED,path,parameters={'ENABLE':enable})
    paths=[item['path'] for item in manifest.get('hierarchy',[])]
    assert paths==[f'active.lanes[{i}].u' for i in range(8)] if enable else paths==[]
    with NativeFont(path) as font:
        for a,b in itertools.product((0,1,0xa5,0xff),repeat=2):
            assert font.invoke(a,b)==(a^b if enable else a)


def test_array_traps_ignore_writes_and_guard_unused_function_results(tmp_path):
    source='''module m(input [3:0] a,input [63:0] i,input use_value,output reg [3:0] y);
      function [3:0] get(input [3:0] x,input [63:0] index);
        reg [3:0] mem[0:1];
        begin mem[0]=x;mem[1]=~x;mem[index]=4'h5;get=mem[index];end
      endfunction
      always @* begin y=a; if(use_value) y=get(a,i); end
    endmodule'''
    path=tmp_path/'array.ttf'
    build(source,path)
    with NativeFont(path) as font:
        for index in (0,1): assert font.invoke(9,index,1)==5
        for index in (2,1<<32,1<<63,0xffffffffffffffff):
            assert font.invoke(9,index,0)==9
            with pytest.raises(WasmTrap,match='invalid_array_index'): font.invoke(9,index,1)


def test_fault_replay_for_shared_captures_and_guarded_calls(tmp_path):
    source='''module m(input [3:0] a,b,input s,output reg [3:0] y,z);
      function [3:0] f(input [3:0] x,d); f=x/d; endfunction
      always @* begin
        y=0;z=0;
        if(s) begin y=f(a,b);z=y;end
      end
    endmodule'''
    path=tmp_path/'flags.ttf'
    build(source,path)
    with NativeFont(path) as font:
        assert font.invoke(7,0,0)==(0,0)
        assert font.invoke(7,2,1)==(3,3)
        with pytest.raises(WasmTrap,match='integer_divide_by_zero'): font.invoke(7,0,1)


@pytest.mark.parametrize('body,message',[
    ('integer i; always @* begin y=0;for(i=0;i<65;i=i+1)y=a;end','64 iterations'),
    ('integer i; always @* begin y=0;for(i=0;i<1;i=i)y=a;end','does not terminate'),
    ('integer i; always @* begin y=0;for(i=0;i<a;i=i+1)y=a;end','compile-time'),
    ('reg [3:0] i; always @* begin y=0;for(i=0;i<4;i=i+1)y=a;end','declared integer'),
    ('integer i; always @* begin y=0;for(i=0;i<4;i=i+1)begin y=a;i=2;end end','must not assign'),
    ('integer i; always @* begin y=0;for(i=0;i<2;i=i+1)for(i=0;i<2;i=i+1)y=a;end','must not assign'),
    ('integer i; always @* for(i=0;i<0;i=i+1)y=a;','undriven'),
    ('genvar i; for(i=0;i<65;i=i+1) begin:g wire w;assign w=a[0];end always @* y=a;','64 iterations'),
    ('integer i;for(i=0;i<1;i=i+1)begin:g assign y=a;end','declared genvar'),
    ('if(a)begin:g assign y=a;end else begin:h assign y=0;end','non-parameter'),
    ('reg [3:0] mem[0:16];always @* begin y=a;end','16'),
    ('reg [3:0] mem[0:1];always @* begin mem[0]=a;mem[1]=a;y=mem[2];end','array index 2'),
    ('reg [3:0] mem[0:1];always @* begin mem[a[0]]=a;y=mem[0];end','read before definite'),
    ('function [3:0] f(input [3:0] x); f=f(x);endfunction always @* y=f(a);','recursive function'),
    ('function [3:0] f(input [3:0] x);if(x) f=x;endfunction always @* y=f(a);','not definitely assigned'),
    ('function [3:0] f(input [3:0] x);reg [3:0] t;f=t;endfunction always @* y=f(a);','read before definite'),
    ('function [3:0] f(input [3:0] x);f=a;endfunction always @* y=f(a);','undeclared signal'),
    ('function [3:0] f(input [3:0] x);f=x;endfunction always @* y=f(a,a);','expects 1'),
    ('always @* y=missing(a);','unknown combinational function'),
])
def test_rejected_expansion_and_state(body,message):
    with pytest.raises(VerilogError,match=message):
        compile_source(f'module m(input [3:0] a,output reg [3:0] y);{body} endmodule')


def test_nested_expansion_and_storage_budgets():
    source='''module m(input a,output reg y);integer i,j;
      always @* begin y=a;for(i=0;i<64;i=i+1)for(j=0;j<64;j=j+1)y=y^a;end
    endmodule'''
    with pytest.raises(VerilogResourceLimit,match='4096'):
        compile_source(source)
    source='''module m(input a,output y);reg [63:0] first[0:15],second[0:0];assign y=a;endmodule'''
    with pytest.raises(VerilogResourceLimit,match='1024 bits'):
        compile_source(source)


def test_function_depth_and_call_budgets():
    functions='\n'.join(f'function f{i}(input x);f{i}='+('x' if i==8 else f'f{i+1}(x)')+';endfunction' for i in range(9))
    with pytest.raises(VerilogResourceLimit,match='depth exceeds 8'):
        compile_source(f'module m(input a,output y);{functions} assign y=f0(a);endmodule')
    source='''module m(input a,output reg y);integer i;
      function f(input x);f=x;endfunction
      always @* begin y=a;for(i=0;i<64;i=i+1)begin y=f(y);y=f(y);end y=f(y);end
    endmodule'''
    with pytest.raises(VerilogResourceLimit,match='128 calls'):
        compile_source(source)


def test_diagnostic_source_names_lines_and_columns():
    source=SourceText.combine([
        ('top.v','module top(input a,output y);\n  leaf u(.a(a),.y(y));\nendmodule'),
        ('cells/leaf.v','module leaf(input a,output y);\n  assign y=missing;\nendmodule')])
    with pytest.raises(VerilogError) as caught: compile_source(source)
    assert 'cells/leaf.v:2:12:' in str(caught.value)
    assert 'assign y=missing;' in str(caught.value)
    with pytest.raises(VerilogError,match='syntax.v:2:'):
        compile_source('module m(input a,output y);\n assign y=;\nendmodule',source_name='syntax.v')


def test_diagnostic_loop_and_gate_limits(tmp_path):
    with pytest.raises(ResourceLimit,match='loop.v:3:'):
        compile_source('''module m(input a,output reg y);integer i;
          always @* begin y=a;
          for(i=0;i<65;i=i+1)y=a;end endmodule''',source_name='loop.v')
    with pytest.raises(ResourceLimit) as caught:
        build('module m(input [7:0] a,b,output [7:0] y);\n assign y=a*b;\nendmodule',tmp_path/'limit.ttf',max_gates=2,source_name='mult.v')
    assert 'mult.v:2:' in str(caught.value)
    assert '--max-gates' in str(caught.value)
    with pytest.raises(ResourceLimit,match='font output exceeds'):
        build('module m(input [3:0] a,output [3:0] y);assign y=a;endmodule',tmp_path/'copies.ttf',max_gates=1)


def test_cli_multifile_diagnostics_preserve_input_files(tmp_path):
    top,leaf=tmp_path/'top.v',tmp_path/'leaf.v'
    top.write_text('module top(input a,output y); leaf u(.a(a),.y(y));endmodule')
    leaf.write_text('module leaf(input a,output y);\n assign y=oops;\nendmodule')
    result=subprocess.run([sys.executable,str(HERE/'build.py'),str(top),str(leaf),'-o',str(tmp_path/'bad.ttf')],capture_output=True,text=True)
    assert result.returncode==2
    assert f'{leaf}:2:' in result.stderr
    assert 'undeclared signal: u.oops' in result.stderr
    assert not (tmp_path/'bad.ttf').exists()


@pytest.mark.parametrize('declaration,message',[
    ('function [64:0] f(input x);f=x;endfunction','ranges must'),
    ('function f(input x);f=missing;endfunction','undeclared signal'),
    ('function f(input x);f=f(x);endfunction','recursive function'),
    ('function f(input x);if(x)f=1;endfunction','not definitely assigned'),
    ('function f(input x);f=$clog2(x);endfunction','only in constant'),
    ('function f(input x);f=x;endfunction wire f;','duplicate declaration'),
    ('function f(input x);f=x;endfunction genvar f;','duplicate declaration'),
    ('function f(input x);f=x;endfunction parameter W=f(1);','not parameter/range constants'),
])
def test_unused_function_declarations_are_validated(declaration,message):
    with pytest.raises(VerilogError,match=message):
        compile_source(f'module m(input a,output y);{declaration} assign y=a;endmodule')


def test_unused_function_validation_does_not_add_gates():
    plain='module m(input [7:0] a,output [7:0] y);assign y=a;endmodule'
    unused='''module m(input [7:0] a,output [7:0] y);
      function [7:0] costly(input [7:0] x);costly=x*x;endfunction
      assign y=a;endmodule'''
    assert compile_source(plain)[1].gate_count==compile_source(unused)[1].gate_count==0


def test_generate_scope_and_capture_bit_budgets():
    source='''module m(input a,output y);genvar i,j;
      for(i=0;i<2;i=i+1)begin:outer_scope
        for(j=0;j<64;j=j+1)begin:inner_scope end
      end
      assign y=a;endmodule'''
    with pytest.raises(VerilogResourceLimit,match='128 scopes'): compile_source(source)
    statements='y=y^a;'*20
    source=f'''module m(input a,output reg [63:0] y);integer i;
      always @* begin y=0;for(i=0;i<64;i=i+1)begin {statements} end end endmodule'''
    with pytest.raises(VerilogResourceLimit,match='65536 value bits'): compile_source(source)


def test_module_instances_can_contain_arrays(tmp_path):
    source='''module top(input [3:0] a,input s,output [3:0] y);
      cell_array u(.a(a),.s(s),.y(y));endmodule
      module cell_array(input [3:0] a,input s,output reg [3:0] y);
        reg [3:0] words[0:1];
        always @* begin words[0]=a;words[1]=~a;y=words[s];end
      endmodule'''
    path=tmp_path/'hier-array.ttf'
    build(source,path)
    with NativeFont(path) as font:
        for a,s in itertools.product(range(16),range(2)):
            assert font.invoke(a,s)==(a^15 if s else a)


def test_array_limit_boundary_and_cli_trap(tmp_path):
    source='''module m(input [63:0] a,input [4:0] index,output reg [63:0] y);
      reg [63:0] words[15:0];integer i;
      always @* begin for(i=0;i<16;i=i+1)words[i]=a^i;y=words[index];end
    endmodule'''
    path=tmp_path/'max-array.ttf'
    build(source,path)
    with NativeFont(path) as font:
        assert font.invoke(0xffffffffffffffff,15)==0xfffffffffffffff0
    result=subprocess.run([sys.executable,str(HERE/'run.py'),str(path),'0','16'],capture_output=True,text=True)
    assert result.returncode==2 and not result.stdout
    assert 'array index is outside its declared bounds' in result.stderr


def test_long_wire_chain_keeps_compilation_depth(tmp_path):
    count=55
    wires=','.join(f'w{i}' for i in range(count))
    assignments=''.join(f'assign w{i}='+('a' if i==count-1 else f'w{i+1}')+';'
                        for i in range(count))
    source=f'module m(input a,output y);wire {wires};assign y=w0;{assignments}endmodule'
    path=tmp_path/'wire-chain.ttf'
    manifest=build(source,path,max_gates=1)
    assert manifest['metrics']['gates']==1  # Only the canonical output copy.
    with NativeFont(path) as font:
        assert [font.invoke(a) for a in range(2)]==[0,1]


@pytest.mark.parametrize('terms',[20,28])
def test_function_depth_combined_with_expression_depth(tmp_path,terms):
    functions=[]
    for i in range(8):
        expression=('x' if i==7 else f'f{i+1}(x)')+'+x'*terms+"+4'd1"
        functions.append(f'function [3:0] f{i}(input [3:0] x);f{i}={expression};endfunction')
    source='module m(input [3:0] a,output [3:0] y);'+'\n'.join(functions)+'\nassign y=f0(a);endmodule'
    path=tmp_path/'nested-functions.ttf'
    build(source,path)
    with NativeFont(path) as font:
        for a in range(16):
            assert font.invoke(a)==(a*(1+8*terms)+8)&15
