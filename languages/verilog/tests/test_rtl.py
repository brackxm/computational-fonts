# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Procedural SSA, hierarchical boundaries, bit drivers and checked selectors."""
import itertools
import json
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from verilogfont.compiler import build
from verilogfont.frontend import Parser, VerilogError, compile_source
from fontcircuit.runtime import NativeFont, WasmTrap, IncompleteShaping


def test_blocking_order_if_else_case_and_partial_updates(tmp_path):
    source = '''module m(input [3:0] a,b,input [1:0] op,output reg [4:0] y);
      reg [4:0] temp;
      always @* begin
        temp=a+b;
        y=temp;
        if (a<b) begin temp=temp+1; y=temp; end
        else if (a==b) y=0;
        case (op)
          0: y=y;
          1,2: y[3:0]=y[3:0]^4'ha;
          default: begin y=~y; y[4]=1'b0; end
        endcase
      end
    endmodule'''
    path=tmp_path/'procedural.ttf'
    build(source,path)
    with NativeFont(path) as font:
        for a,b,op in itertools.product(range(16),range(16),range(4)):
            y = a+b+1 if a<b else 0 if a==b else a+b
            y = y if op==0 else y^10 if op in (1,2) else (~y)&15
            assert font.invoke(a,b,op)==y
        with pytest.raises(IncompleteShaping):
            font.decode(font.shaper.shape(font.encode([1,2,3]),enabled=False))


def test_exhaustive_case_without_default_and_first_match_priority(tmp_path):
    source='''module m(input [1:0] op,output reg [3:0] y);
      always @(*) case(op)
        0: y=1;
        1,2: y=3;
        1: y=7;
        3: y=9;
      endcase
    endmodule'''
    path=tmp_path/'case.ttf'
    build(source,path)
    with NativeFont(path) as font:
        assert [font.invoke(i) for i in range(4)]==[1,3,3,9]


def test_static_slice_drivers_and_bit_dependencies(tmp_path):
    source='''module m(input [1:0] a,output [3:0] y,output reg [3:0] z);
      assign y[1:0]=a;
      assign y[3:2]=~y[1:0];
      always @* begin z[1:0]=a; z[3:2]=~z[1:0]; end
    endmodule'''
    path=tmp_path/'slices.ttf'
    build(source,path)
    with NativeFont(path) as font:
        for a in range(4): assert font.invoke(a)==(a|((a^3)<<2),)*2


def test_separate_blocks_may_drive_disjoint_bits(tmp_path):
    path=tmp_path/'bits.ttf'
    build('''module m(input a,b, output reg [1:0] y);
      always @* y[0]=a;
      always @* y[1]=y[0]^b;
    endmodule''',path)
    with NativeFont(path) as font:
        for a,b in itertools.product(range(2),repeat=2):
            assert font.invoke(a,b)==a|((a^b)<<1)


HIERARCHY='''module top #(parameter W=4)(input signed [W-1:0] a,b,input s,
  output signed [W:0] y,output [W-1:0] other);
  wire signed [W:0] sum;
  branch #(.WIDTH(W)) left(.a(a),.b(b),.y(sum));
  leaf #(.WIDTH(W)) right(.a(a),.b(b),.y(other));
  assign y=s ? sum : a;
endmodule
module branch #(parameter WIDTH=2)(input signed [WIDTH-1:0] a,b,
  output reg signed [WIDTH:0] y);
  wire [WIDTH-1:0] mixed;
  leaf #(.WIDTH(WIDTH)) inner(.a(a),.b(b),.y(mixed));
  always @* begin y=a+b; if(mixed==0) y=-a; end
endmodule
module leaf #(parameter WIDTH=2)(input [WIDTH-1:0] a,b,output [WIDTH-1:0] y);
  assign y=a^b;
endmodule'''


def test_nested_hierarchy_specializes_and_preserves_signed_boundaries(tmp_path):
    path=tmp_path/'hierarchy.ttf'
    manifest=build(HIERARCHY,path,parameters={'W':5})
    assert manifest['module']=='top'
    assert [h['path'] for h in manifest['hierarchy']]==['left','left.inner','right']
    assert all(h['parameters'][0]['value']=='5' for h in manifest['hierarchy'])
    with NativeFont(path) as font:
        for a,b,s in itertools.product([-16,-1,0,1,15],[-16,-1,0,1,15],range(2)):
            y = -a if a==b else a+b
            assert font.invoke(a,b,s)==((y if s else a)&63,(a^b)&31)


def test_output_port_slice_connections_and_self_determined_input_expression(tmp_path):
    path=tmp_path/'ports.ttf'
    build('''module m(input [3:0] a,b,output [7:0] y);
      assign y[7:5]=3'b101;
      sum u(.a(a+b),.y(y[4:0]));
    endmodule
    module sum(input [4:0] a,output [4:0] y);assign y=a;endmodule''',path)
    with NativeFont(path) as font: assert font.invoke(15,15)==174


def test_top_selection_cli_and_explicit_unconnected_output(tmp_path):
    source='''module first(output y);assign y=1'b0;endmodule
      module second(output y); helper u(.y(y),.unused()); endmodule
      module helper(output y,unused);assign y=1'b1;assign unused=1'b0;endmodule'''
    with pytest.raises(VerilogError,match='ambiguous top'):
        compile_source(source)
    path=tmp_path/'source.v'; path.write_text(source)
    output=tmp_path/'chosen.ttf'
    result=subprocess.run([sys.executable,str(HERE/'build.py'),str(path),'--top','second','-o',str(output)],
                          capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    with NativeFont(output) as font: assert font.invoke()==1
    assert json.loads(output.with_suffix('.json').read_text())['module']=='second'


def test_dynamic_reads_and_indexed_directions(tmp_path):
    path=tmp_path/'read.ttf'
    build('''module m(input [7:0] data,input [2:0] i,input down,
      output bit_value,output [2:0] part);
      assign bit_value=data[i];
      assign part=down ? data[i -: 3] : data[i +: 3];
    endmodule''',path)
    with NativeFont(path) as font:
        for data,i,down in itertools.product([0,1,0xa5,255],range(8),range(2)):
            low=i-2 if down else i
            if low<0 or low+3>8:
                with pytest.raises(WasmTrap,match='invalid_select'): font.invoke(data,i,down)
            else:
                assert font.invoke(data,i,down)==((data>>i)&1,(data>>low)&7)


def test_guarded_invalid_reads_and_signed_negative_indices(tmp_path):
    path=tmp_path/'guard.ttf'
    build('''module m(input [4:0] data,input signed [3:0] i,
      output reg y, output both,either);
      always @* begin y=0; if(i>=0 && i<5) y=data[i]; end
      assign both=(i>=0 && i<5) && data[i];
      assign either=(i<0 || i>=5) || data[i];
    endmodule''',path)
    with NativeFont(path) as font:
        for data,i in itertools.product([0,21,31],range(-8,8)):
            valid=0<=i<5
            b=(data>>i)&1 if valid else 0
            assert font.invoke(data,i)==(b,b,int(not valid or b))


def test_dynamic_partial_writes_clip_and_preserve_other_bits(tmp_path):
    path=tmp_path/'write.ttf'
    build('''module m(input [7:0] data,input signed [4:0] i,input [2:0] value,
      output reg [7:0] bit_write,up,down);
      always @* begin
        bit_write=data; bit_write[i]=value[0];
        up=data; up[i +: 3]=value;
        down=data; down[i -: 3]=value;
      end
    endmodule''',path)
    def write(data,start,value,width):
        for n in range(width):
            index=start+n
            if 0<=index<8: data=(data&~(1<<index))|(((value>>n)&1)<<index)
        return data
    with NativeFont(path) as font:
        for data,i,value in itertools.product([0,0xa5,255],range(-16,16),[0,3,7]):
            assert font.invoke(data,i,value)==(write(data,i,value,1),write(data,i,value,3),write(data,i-2,value,3))


def test_concatenated_assignments_capture_rhs_before_writes(tmp_path):
    path=tmp_path/'concat.ttf'
    build('''module m(input [7:0] a,output reg [7:0] y,output [7:0] z);
      assign {z[3:0],z[7:4]}=a;
      always @* begin y=a; {y[3:0],y[7:4]}=y; end
    endmodule''',path)
    with NativeFont(path) as font:
        for a in range(256): assert font.invoke(a)==(((a&15)<<4)|(a>>4),)*2


@pytest.mark.parametrize('source,message',[
    ('module m(input a,output reg y);always @* if(a)y=1;endmodule','latch'),
    ('module m(input a,output reg [1:0] y);always @* y[0]=a;endmodule','undriven'),
    ('module m(input a,output reg y);always @* y=y+a;endmodule','read before'),
    ('module m(input a,output reg y);always @* case(a) 0:y=0;endcase endmodule','latch'),
    ('module m(input a,output reg y);always @* y<=a;endmodule','nonblocking'),
    ('module m(input a,output y);always @* y=a;endmodule','requires reg'),
    ('module m(input a,output reg y);assign y=a;endmodule','requires a wire'),
    ('module m(input a,output reg y);always @(a)y=a;endmodule','expected'),
    ('module m(input a,output reg y);always @(posedge a)y=a;endmodule','expected'),
    ('module m(input a,output reg y);always @* y=a;always @* y=~a;endmodule','multiple drivers'),
    ("module m(input a,output [1:0] y);assign y[0]=a;assign y[0]=~a;assign y[1]=a;endmodule",'multiple drivers'),
    ('module m(output [1:0] y);assign y[0]=y[1];assign y[1]=y[0];endmodule','cycle'),
    ('module m(input [7:0] a,input i,output y);assign y=a[i+:i];endmodule','non-parameter'),
    ('module m(input a,output y);missing u(.a(a),.y(y));endmodule','unknown module'),
    ('module m(output y);m u(.y(y));endmodule','recursive'),
    ('module m(output y);assign y=0;endmodule module m(output y);assign y=1;endmodule','duplicate module'),
    ('module m(input a,output y);n u(.a(a),.a(a),.y(y));endmodule module n(input a,output y);assign y=a;endmodule','duplicate named'),
    ('module m(input a,output y);n u(.a(),.y(y));endmodule module n(input a,output y);assign y=a;endmodule','unconnected input'),
    ('module m(input a,output y);n u(.typo(a),.y(y));endmodule module n(input a,output y);assign y=a;endmodule','connect every port'),
    ('module m(input a,output y);assign y[a]=a;endmodule','dynamic continuous'),
    ('module m(input [1:0] i,input a,output reg [3:0] y);always @* y[i]=a;endmodule','latch'),
    ('module m(input a,output reg y);always @* case(a) default:y=0;default:y=1;endcase endmodule','duplicate case'),
])
def test_rejects_state_ambiguity_bad_connections_and_conflicting_bits(source,message):
    with pytest.raises(VerilogError,match=message): compile_source(source)


def test_wide_dynamic_indices_never_truncate_or_mask(tmp_path):
    # Icarus 13 truncates some wide read indices internally. Check the full
    # 64-bit bounds independently instead of adopting that simulator behavior.
    path=tmp_path/'wide-index.ttf'
    build('''module m(input [63:0] i,output bit_value,output reg [7:0] written);
      parameter [7:0] DATA=8'ha5;
      assign bit_value=DATA[i];
      always @* begin written=DATA;written[i]=1'b0;end
    endmodule''',path)
    with NativeFont(path) as font:
        for i in range(8): assert font.invoke(i)==((165>>i)&1,165&~(1<<i))
        for i in [8,31,63,64,1<<32,(1<<32)+1,1<<63,(1<<64)-1]:
            with pytest.raises(WasmTrap,match='invalid_select'): font.invoke(i)


def test_cli_reports_invalid_dynamic_reads_without_a_traceback(tmp_path):
    path=tmp_path/'routes.ttf'
    build((HERE/'examples/dynamic_routes.v').read_text(),path)
    result=subprocess.run([sys.executable,str(HERE/'run.py'),str(path),'165','8','3'],
                          capture_output=True,text=True)
    assert result.returncode==2
    assert 'outside its vector bounds' in result.stderr
    assert 'Traceback' not in result.stderr
    assert not result.stdout


@pytest.mark.parametrize('source,kwargs,message',[
    ('module m(output y);assign y=1;endmodule',{'top':'missing'},'unknown top'),
    ('module m(output y);m u(.y(y));endmodule',{'top':'m'},'recursive'),
    ('module m(output y);n #(.BAD(1)) u(.y(y));endmodule module n(output y);assign y=1;endmodule',{},'unknown parameter'),
    ('module m(output y);n #(.P(1)) u(.y(y));endmodule module n(output y);localparam P=0;assign y=P[0];endmodule',{},'cannot override localparam'),
    ('module m(input a,output y);n u(.a(a));endmodule module n(input a,output y);assign y=a;endmodule',{},'connect every port'),
    ('module m(input a,output y);n u(.a(a),.y(y)),u(.a(a),.y(y));endmodule module n(input a,output y);assign y=a;endmodule',{},'duplicate instance'),
])
def test_hierarchy_errors_are_diagnosed(source,kwargs,message):
    with pytest.raises(VerilogError,match=message): compile_source(source,**kwargs)


def test_hierarchy_and_flattened_resource_bounds():
    depth='\n'.join(f'module m{i}(output y);m{i+1} u(.y(y));endmodule' for i in range(17))
    depth+='\nmodule m17(output y);assign y=1;endmodule'
    with pytest.raises(VerilogError,match='depth exceeds 16'): compile_source(depth)
    instances='module m(output y);assign y=1;'+''.join(f'empty u{i}();' for i in range(128))+'endmodule module empty();endmodule'
    with pytest.raises(VerilogError,match='exceeds 128 instances'): compile_source(instances)
    signals='module m(output y);assign y=1;'+''.join(f'unit u{i}(.out());' for i in range(64))+'endmodule module unit(output out);wire spare=1;assign out=spare;endmodule'
    with pytest.raises(VerilogError,match='exceeds 128 signals'): compile_source(signals)
    modules='\n'.join(f'module m{i}(output y);assign y=1;endmodule' for i in range(33))
    with pytest.raises(VerilogError,match='at most 32 module'): compile_source(modules,top='m0')


def test_cli_combines_source_files_without_overwriting_any_input(tmp_path):
    top=tmp_path/'top.v'
    child=tmp_path/'child.json'
    top.write_text('module top(input [3:0] a,b,output [4:0] y);unit u(.a(a),.b(b),.y(y));endmodule // end of file')
    child.write_text('module unit(input [3:0] a,b,output [4:0] y);assign y=a+b;endmodule')
    command=[sys.executable,str(HERE/'build.py'),str(top),str(child),'--top','top']
    result=subprocess.run(command+['-o',str(tmp_path/'combined.ttf')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    with NativeFont(tmp_path/'combined.ttf') as font: assert font.invoke(15,15)==30
    original=child.read_text()
    result=subprocess.run(command+['-o',str(child.with_suffix('.ttf'))],capture_output=True,text=True)
    assert result.returncode==2
    assert child.read_text()==original
    assert not child.with_suffix('.ttf').exists()


@pytest.mark.parametrize('expression', ["{y[0],a}","{y[0],a}|2'b00","{y[0],a}<<0", "{a,y[1]}>>0"])
def test_structural_whole_net_wiring_resolves_only_required_bits(tmp_path,expression):
    path=tmp_path/'wiring.ttf'
    build(f'module m(input a,output [1:0] y);assign y={expression};endmodule',path)
    with NativeFont(path) as font:
        for a in range(2): assert font.invoke(a)==a*3
