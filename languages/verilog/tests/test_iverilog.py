# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Optional independent Verilog simulator comparisons (iverilog + vvp)."""
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from verilogfont.compiler import build
from verilogfont.frontend import Parser
from fontcircuit.runtime import NativeFont, WasmTrap

IVERILOG = os.environ.get('IVERILOG') or shutil.which('iverilog')
VVP = os.environ.get('VVP') or shutil.which('vvp')
pytestmark = pytest.mark.skipif(not (IVERILOG and VVP), reason='optional Icarus Verilog simulator is unavailable')


def compare(tmp_path, source, parameters=None, top=None, undefined='invalid_select', max_gates=12000):
    module = Parser(source, parameters=parameters, top=top).parse()
    rng = random.Random(914)
    cases = [[0]*len(module.inputs), [(1<<s.width)-1 for s in module.inputs]]
    cases += [[((1 << (s.width-1))+offset) & ((1 << s.width)-1) for s in module.inputs]
              for offset in (-1,0,1)]
    cases += [[1 << (s.width-1) if i % 2 == parity else (1 << s.width)-1
               for i,s in enumerate(module.inputs)] for parity in (0,1)]
    cases += [[rng.getrandbits(s.width) for s in module.inputs] for _ in range(100)]
    if not module.inputs:
        cases = [[]]
    lines = [source, 'module tb;']
    lines += [f'reg [{s.width-1}:0] {s.name};' for s in module.inputs]
    # Observe unsigned output nets so comparisons use raw bits even for signed DUT ports.
    lines += [f'wire [{s.width-1}:0] {s.name};' for s in module.outputs]
    ports = module.inputs + module.outputs
    overrides = '#(' + ','.join(f'.{name}({value})' for name,value in parameters.items()) + ')' if parameters else ''
    lines += [f'{module.name} {overrides} dut(' + ','.join(f'.{s.name}({s.name})' for s in ports) + ');', 'initial begin']
    for values in cases:
        lines += [f"{s.name} = {s.width}'d{value};" for s, value in zip(module.inputs, values)]
        lines += ['#1; $display("' + ' '.join('%d' for _ in module.outputs) + '",' +
                  ','.join(s.name for s in module.outputs) + ');']
    lines += ['$finish; end endmodule']
    tb = tmp_path/'tb.v'
    tb.write_text('\n'.join(lines))
    program = tmp_path/'sim.vvp'
    result = subprocess.run([IVERILOG, '-g2005', '-gstrict-expr-width', '-s', 'tb', '-o', str(program), str(tb)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([VVP, str(program)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    # Newer Icarus releases append a $finish location to stdout.
    expected = [tuple(None if any(c in part.lower() for c in 'xz') else int(part)
                      for part in line.split()) for line in result.stdout.splitlines()
                if line.strip() and all(part.isdigit() or part.lower() in ('x','z') for part in line.split())]
    assert len(expected) == len(cases), result.stdout
    path = tmp_path/'differential.ttf'
    build(source, path, parameters=parameters, top=top, max_gates=max_gates)
    with NativeFont(path) as font:
        for values, reference in zip(cases, expected):
            if None in reference:
                with pytest.raises(WasmTrap,match=undefined):
                    font.invoke(*values)
                continue
            shaped = font.invoke(*values)
            assert ((shaped,) if len(module.outputs)==1 else shaped) == reference, values


@pytest.mark.parametrize('name', ['adder', 'alu', 'multiplier', 'bit_routes', 'parameter_adder', 'signed_math',
                                  'procedural_alu', 'hierarchical_adder', 'dynamic_routes', 'division',
                                  'population_count', 'generated_xor', 'array_lookup'])
def test_bundled_modules_against_icarus(tmp_path, name):
    compare(tmp_path, (HERE/'examples'/f'{name}.v').read_text(),
            undefined='integer_divide_by_zero' if name=='division' else 'invalid_array_index' if name=='array_lookup' else 'invalid_select')


def test_context_and_operator_composition_against_icarus(tmp_path):
    expressions = [
        'a+b', 'a*b', '-a', '~a', '+a', 'a-b-c', 'a+b*c', '(a+b)*c',
        'a<<b', 'a>>c', '(a+b)<<c', 'a<<(b+c)',
        'a ? b+c : c+a', 'a ? b : c ? a : b', '(a>b)+c', '(a+b)<c',
        '{a+b}', '{a,b}', '{2{b}}', '{2{a[2:0],b}}',
        '&a', '~&a', '|b', '~|b', '^c', '~^c', 'a^~b', 'a~^b',
        'a&&b', 'a||b', '!(a+b)', 'a==b', 'a!=b', 'a>=b', 'a<=b',
        'a|b&c', 'a^b|c', "a+8'hff", "a*9'o377", "a-8'd1", "a+4'b1111",
        'narrow', 'a+(b==c)', '{(a+b)*b}', '(a < b ? a : b) + c',
    ]
    outputs = ','.join(f'y{i}' for i in range(len(expressions)))
    source = f'module m(input [4:0] a, input [2:0] b, input [6:0] c, output [8:0] {outputs});\n'
    source += 'wire [2:0] narrow; assign narrow=a+b;\n'
    source += '\n'.join(f'assign y{i}={expr};' for i,expr in enumerate(expressions))
    compare(tmp_path, source + '\nendmodule')


def test_64_bit_composition_against_icarus(tmp_path):
    compare(tmp_path, '''module m(input [63:0] a,b, input [6:0] n,
      output [63:0] y, left, right, output eq, less);
      assign y=(a+b)^(a-b); assign left=a<<n; assign right=a>>n;
      assign eq=a==b; assign less=a<b;
    endmodule''')


@pytest.mark.parametrize('width', [2, 4, 12, 16, 31, 63])
def test_parameter_overrides_against_icarus(tmp_path, width):
    compare(tmp_path, (HERE/'examples/parameter_adder.v').read_text(),
            {'WIDTH': width, 'MASK': "64'h5555555555555555"})


def test_parameter_expression_bounds_and_replication_against_icarus(tmp_path):
    compare(tmp_path, '''module m #(parameter WIDTH=8, DEPTH=16)(input [WIDTH-1:0] a,
      output [$clog2(DEPTH)-1:0] slice, output [WIDTH-1:0] replicated);
      localparam HALF=WIDTH/2;
      wire [WIDTH-1:0] swapped={a[HALF-1:0],a[WIDTH-1:HALF]};
      assign slice=swapped[($clog2(DEPTH))-1:0];
      assign replicated={(WIDTH/2){a[1:0]}};
    endmodule''')


@pytest.mark.parametrize('expression', [
    'BASE', '-1', '(1<<31)', '(1<<31)>>31', '(-7)/3', '(-7)%3', '7/(-3)', '7%(-3)',
    "8'hff+1", "(-1)<0", "(-1)<64'd0", "{4'ha,4'h5}", "{2{4'ha}}",
    "1?(-1):64'd1", "1?BASE:64'd1", "BASE+U", "(-1)+U", "~BASE", "~(BASE+U)",
    '$clog2(9)', '$clog2(0)', 'BASE[3:0]', "{BASE[3:0],4'h0}",
    "{2{{2{4'ha}}}}", '((1<<30)*4)', "32'h80000000/(-1)",
    '1?8:1/0', '0?1/0:8', '0&&(1/0)', '1||(1/0)',
    '{BASE}', '{2{BASE}}', '$clog2(64\'hffffffffffffffff)',
])
def test_constant_type_and_context_rules_against_icarus(tmp_path, expression):
    compare(tmp_path, f'''module m #(parameter BASE=-1, parameter [63:0] U=64'd1,
      parameter P={expression})(output [63:0] y);
      localparam [63:0] OBS=P;
      assign y=OBS;
    endmodule''')


def test_unsigned_selects_from_signed_parameters_against_icarus(tmp_path):
    compare(tmp_path, '''module m #(parameter BASE=-1, WIDTH=8)(output [63:0] y, z);
      assign y=BASE[31:0]; assign z=WIDTH[3:0];
    endmodule''')


def test_parameter_assignment_context_preserves_full_product_against_icarus(tmp_path):
    compare(tmp_path, '''module m(output [63:0] y);
      parameter [63:0] PRODUCT=32'hffffffff*32'hffffffff;
      assign y=PRODUCT;
    endmodule''')


@pytest.mark.parametrize('override', [-1, 8, "16'hffff", "64'hffffffffffffffff"])
def test_untyped_override_infers_its_own_type_against_icarus(tmp_path, override):
    compare(tmp_path, '''module m #(parameter P=8'hff)(output [63:0] y);
      localparam [63:0] OBS=P; assign y=OBS;
    endmodule''', {'P': override})


def test_parameter_dependencies_against_icarus(tmp_path):
    compare(tmp_path, '''module m #(parameter NEXT=4, WIDTH=NEXT*2)
      (input [WIDTH-1:0] a, output [WIDTH-1:0] y);
      localparam HALF=WIDTH/2;
      wire [WIDTH-1:0] swapped={a[HALF-1:0],a[WIDTH-1:HALF]};
      assign y=swapped;
    endmodule''')


@pytest.mark.parametrize('expression', [
    'a+b', 'a-b', 'a*b', '-a', '~a', '+a', 'a+b*c', '(a+b)*c',
    'a+u', '(a+b)+u', '-(a+u)', '~(a+u)', '(a>>>b)+u',
    'a<b', 'a<=b', 'a>b', 'a>=b', 'a==b', 'a!=b', 'a<u', '(a+b)<c',
    'a ? b : c', 'a ? b : u', '(a ? b : c)+u',
    'a<<b', 'a<<<b', 'a>>b', 'a>>>b', '(a+b)>>>u', 'u>>>b',
    'a+1', 'a-1', 'a*(-1)', "a+8'shff", "a+8'hff", "a<8'shff", 'a<0',
    '{a}', '{a,b}', '{2{a}}', 'a[4:0]', 'a[4:0]+b',
    '$signed(u)+a', '$unsigned(a)+b', '$signed(a+b)', '$unsigned(a+b)',
    '$signed(u)>>>b', '$unsigned(a)>>>b', '$signed(a+u)+c',
    'a+P', 'a+Q', 'a+R', '{P}',
])
def test_signed_operator_composition_against_icarus(tmp_path, expression):
    compare(tmp_path, f'''module m #(parameter signed [3:0] P=4'hf,
      parameter Q=-1, parameter signed R=8'hff)(input signed [4:0] a,
      input signed [2:0] b, input signed [6:0] c, input [3:0] u,
      output signed [11:0] y);
      assign y={expression}; endmodule''')


def test_signed_wire_boundaries_and_mixed_context_against_icarus(tmp_path):
    compare(tmp_path, '''module m(input signed [3:0] a,b, input [3:0] u,
      output [8:0] sum, mixed, cast_sum, from_signed, from_unsigned, shift);
      wire signed [3:0] narrow=a+b;
      wire [3:0] raw=a+b;
      assign sum=a+b; assign mixed=a+b+u; assign cast_sum=$signed(a+b);
      assign from_signed=narrow; assign from_unsigned=raw;
      assign shift=(a>>>b)+u;
    endmodule''')


def test_signed_64_bit_shifts_and_comparisons_against_icarus(tmp_path):
    compare(tmp_path, '''module m(input signed [63:0] a,b, input signed [6:0] n,
      output signed [63:0] sum, difference, left, arithmetic, logical,
      output less, less_unsigned, eq);
      assign sum=a+b; assign difference=a-b; assign left=a<<<n;
      assign arithmetic=a>>>n; assign logical=a>>n;
      assign less=a<b; assign less_unsigned=a<$unsigned(b); assign eq=a==b;
    endmodule''')


@pytest.mark.parametrize('declaration', [
    "parameter signed A=8'hff, B=8'shff",
    "parameter signed [15:0] A=8'hff, B=8'shff",
    "parameter [15:0] A=8'shff, B=8'hff",
    "parameter A=8'shff, B=A>>>3",
    "parameter signed [3:0] A=-1, B=A<<<1",
    "parameter A=$signed(8'hff), B=$unsigned(8'shff)",
    "parameter A={1'b1<<1}, B={1?8'd1:8'd2}",
    "parameter A={$signed(1)}, B={$unsigned(-1)}",
])
def test_signed_parameter_rules_against_icarus(tmp_path, declaration):
    compare(tmp_path, f'''module m #({declaration})(output [63:0] y,z);
      assign y=A; assign z=B; endmodule''')


@pytest.mark.parametrize('override', ["8'shff", "-8'sd1", "16'sh8000", '-1'])
def test_signed_parameter_overrides_against_icarus(tmp_path, override):
    compare(tmp_path, '''module m #(parameter signed [15:0] P=0)(input signed [3:0] a,
      output signed [31:0] y); assign y=P+a; endmodule''', {'P': override})


@pytest.mark.parametrize('body', [
    'y=a; if(s) y=b; y=y+1;',
    'if(s) begin y=a+b; y=y+1; end else begin y=a-b; y=~y; end',
    'y=a; y[2:0]=b; y[4]=^y;',
    'y=a; {y[3:0],y[4]}={b,y[0]};',
    "case(s) 0:y=a;1:y=b;endcase",
    "case(a) 5'sd0:y=1; 8'hff:y=2; default:y=3;endcase",
    "case(a) 0:y=1; 5'sh1f:y=2; default:y=a;endcase",
    "case(a) b:y=1; 0,1:y=2; default:y=b;endcase",
    'y=0; if(s) y=a; else if(a<b) y=b; else y=a+b;',
])
def test_procedural_composition_against_icarus(tmp_path,body):
    compare(tmp_path,f'''module m(input signed [4:0] a,b,input s,output reg signed [4:0] y);
      always @* begin {body} end endmodule''')


def test_hierarchy_and_signed_boundaries_against_icarus(tmp_path):
    from test_rtl import HIERARCHY
    compare(tmp_path,HIERARCHY,{'W':5})


@pytest.mark.parametrize('source', [
    '''module m(input [7:0] a,input [5:0] i,output y);
      assign y=a[i]; endmodule''',
    '''module m(input [7:0] a,input signed [3:0] i,output [2:0] up,down);
      assign up=a[i+:3];assign down=a[i-:3];endmodule''',
    '''module m(input [7:0] a,input signed [4:0] i,input [2:0] v,
      output reg [7:0] up,down,one);
      always @* begin up=a;up[i+:3]=v;down=a;down[i-:3]=v;one=a;one[i]=v[0];end
      endmodule''',
    '''module m(input [7:0] a,input signed [4:0] i,output reg [2:0] y);
      always @* begin y=0; if(i>=0 && i<=5) y=a[i+:3];end endmodule''',
    '''module m(input [3:0] a,b,output [7:0] y);
      assign y[3:0]=a;assign y[7:4]=b^y[3:0];endmodule''',
    '''module m(input [7:0] a,output reg [7:0] y);
      always @* begin y=a;{y[3:0],y[7:4]}=y;end endmodule''',
    '''module m #(parameter P=8'ha5,Q=P[2+:4],R=P[6-:4])(output [7:0] y);
      assign y={Q,R};endmodule''',
    '''module m(input signed [2:0] a,input [3:0] b,output signed [7:0] y);
      child u(.x(a+b),.y(y));endmodule
      module child(input signed [4:0] x,output signed [5:0] y);
      assign y=x;endmodule''',
    '''module m(input [3:0] a,b,output [7:0] y);
      child u(.x(a+b),.y(y[4:0]));assign y[7:5]=3'b101;endmodule
      module child(input [4:0] x,output [4:0] y);assign y=x;endmodule''',
])
def test_selects_writes_and_port_context_against_icarus(tmp_path,source):
    compare(tmp_path,source)


@pytest.mark.parametrize('source', [
    '''module m(input [7:0] a,input signed i,output y);assign y=a[i];endmodule''',
    '''module m(input [7:0] a,input [63:0] i,output reg [7:0] y,output z);
      assign z=(i<8) ? a[i] : 1'b0;always @* begin y=a;y[i]=1'b1;end endmodule''',
    '''module m(input [63:0] a,input [5:0] i,output y);
      assign y=a[i];endmodule''',
    '''module m(input [7:0] a,input [2:0] i,output reg [7:0] y);
      always @* begin y=a;{y[i],y[0]}=2'b10;end endmodule''',
    '''module m #(parameter P=2'b10)(input a,output reg y);
      always @* case(a) {1{1'b0}}:y=1; P[1]:y=0; endcase endmodule''',
])
def test_selector_extremes_and_aliasing_against_icarus(tmp_path,source):
    compare(tmp_path,source)


@pytest.mark.parametrize('expression',[
    'a/b','a%b','a/u','a%u','u/b','u%b','(a+b)/b','(a+b)%b',
    'a/(b+1)','a%(b+1)','a/3','a%3','a/(-3)','a%(-3)',
    "a/8'sh80","a%8'sh80",'$signed(u)/b','$signed(u)%b',
    '(a/b)+u','(a%b)+u','{a/b}','{a%b}','$signed(a/b)','$unsigned(a/b)',
    '(a/b)*b+a%b',"a/(b|3'sd1)","a%(b|3'sd1)",
    'b ? a/b : 0','b ? a%b : 0','b && (a/b)','!b || !(a%b)',
])
def test_runtime_division_context_against_icarus(tmp_path,expression):
    compare(tmp_path,f'''module m(input signed [4:0] a,input signed [2:0] b,
      input [3:0] u,output signed [11:0] y);assign y={expression};endmodule''',
      undefined='integer_divide_by_zero')


@pytest.mark.parametrize('width',[1,3,5,13,32,64])
@pytest.mark.parametrize('signed',[False,True])
def test_dynamic_division_widths_against_icarus(tmp_path,width,signed):
    qualifier='signed' if signed else ''
    compare(tmp_path,f'''module m(input {qualifier} [{width-1}:0] a,b,
      output {qualifier} [{width-1}:0] q,r);assign q=a/b;assign r=a%b;endmodule''',
      undefined='integer_divide_by_zero')


@pytest.mark.parametrize('declaration',[
    'input signed [4:0] a,b,output signed [63:0] q,r',
    'input signed [7:0] a,b,output signed [8:0] q,r',
    'input [4:0] a, input [6:0] b,output [2:0] q,r',
])
def test_division_assignment_boundaries_against_icarus(tmp_path,declaration):
    compare(tmp_path,f'module m({declaration});assign q=a/b;assign r=a%b;endmodule',
            undefined='integer_divide_by_zero')


def test_division_in_procedural_hierarchy_and_partial_writes_against_icarus(tmp_path):
    compare(tmp_path,'''module m(input signed [4:0] a,b,input take,
      output signed [5:0] q,output reg [7:0] patched);
      unit #(.WIDTH(5)) u(.a(a),.b(b),.take(take),.q(q));
      always @* begin patched=8'ha5; if(b) patched[3:0]=a%b;end
    endmodule
    module unit #(parameter WIDTH=5)(input signed [WIDTH-1:0] a,b,input take,
      output reg signed [WIDTH:0] q);
      always @* begin q=0;case(take) 1: if(b) q=a/b; default:q=0;endcase end
    endmodule''',undefined='integer_divide_by_zero')


@pytest.mark.parametrize('operator',['/','%'])
def test_runtime_zero_constant_and_path_guard_against_icarus(tmp_path,operator):
    compare(tmp_path,f'''module m(input [3:0] a,input take,output [3:0] y);
      assign y=take ? a{operator}4'd0 : 4'd7;endmodule''',undefined='integer_divide_by_zero')
