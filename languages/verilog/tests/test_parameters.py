# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Parameter elaboration, constant width semantics and specialized font execution."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from verilogfont.compiler import build
from verilogfont.frontend import Parser, VerilogError, compile_source
from fontcircuit.runtime import NativeFont, IncompleteShaping


@pytest.mark.parametrize('width', [2, 4, 8, 12, 16, 31, 63])
def test_parameterized_font_port_widths_and_outputs(tmp_path, width):
    source = (HERE/'examples/parameter_adder.v').read_text()
    path = tmp_path/'parameterized.ttf'
    mask = (1 << width)-1
    manifest = build(source, path, parameters={'WIDTH': width, 'MASK': "64'h5555555555555555"})
    assert manifest['parameter_types'] == [f'i{width}', f'i{width}']
    assert manifest['result_types'] == [f'i{width+1}', f'i{width}', f'i{width}']
    params = {p['name']: p for p in manifest['parameters']}
    assert params['WIDTH']['value'] == str(width)
    assert params['TOP_BIT']['local']
    assert params['MASK']['width'] == width
    with NativeFont(path) as font:
        for a,b in [(0,0), (mask,1), (mask,mask), (mask//3,mask//2)]:
            assert font.invoke(a,b) == (a+b, (a^b)&0x5555555555555555&mask, a^(1 << (width-1)))
        with pytest.raises(IncompleteShaping):
            font.decode(font.shaper.shape(font.encode([1,2]), enabled=False))


def test_parameter_dependencies_and_wire_initializers(tmp_path):
    source = '''module m #(parameter NEXT=4, WIDTH=NEXT*2)
      (input [WIDTH-1:0] a, output [WIDTH-1:0] y);
      localparam HALF=WIDTH/2;
      wire [WIDTH-1:0] swapped={a[HALF-1:0],a[WIDTH-1:HALF]};
      assign y=swapped;
    endmodule'''
    path = tmp_path/'dependencies.ttf'
    build(source, path)
    with NativeFont(path) as font:
        assert font.invoke(0xa5) == 0x5a


def test_full_width_parameter_manifest_retains_every_bit(tmp_path):
    path = tmp_path/'wide.ttf'
    manifest = build("module m #(parameter P=64'hffffffffffffffff)(output [63:0] y); assign y=P; endmodule", path)
    assert manifest['parameters'][0]['value'] == '18446744073709551615'
    with NativeFont(path) as font:
        assert font.invoke() == (1 << 64)-1


def test_parameter_inheritance_masks_and_sized_defaults(tmp_path):
    source = '''module m #(parameter [3:0] A=5'd31,B=A-1'b1, parameter C=8'hA5)
      (output [15:0] y); assign y={A,B,C}; endmodule'''
    path = tmp_path/'inheritance.ttf'
    build(source, path)
    with NativeFont(path) as font:
        assert font.invoke() == 0xfea5


def test_clog2_and_expression_repeat_counts_and_indices(tmp_path):
    source = '''module m #(parameter WIDTH=8, DEPTH=16)(input [WIDTH-1:0] a,
      output [$clog2(DEPTH)-1:0] slice, output [WIDTH-1:0] replicated);
      assign slice=a[(WIDTH/2)-1:0];
      assign replicated={(WIDTH/2){a[1:0]}};
    endmodule'''
    path = tmp_path/'counts.ttf'
    build(source, path)
    with NativeFont(path) as font:
        assert font.invoke(0xa6) == (6,0xaa)


@pytest.mark.parametrize('expression,value,width,signed', [
    ('8',8,32,True), ('8\'hff',255,8,False), ('-1',-1,32,True),
    ('(1<<31)',-(1<<31),32,True), ('(1<<31)>>31',1,32,True),
    ('(-7)/3',-2,32,True), ('(-7)%3',-1,32,True), ('7/(-3)',-2,32,True),
    ('7%(-3)',1,32,True), ('8\'hff+1',256,32,False),
    ('(-1)<0',1,1,False), ('(-1)<64\'d0',0,1,False),
    ('{4\'ha,4\'h5}',165,8,False), ('{2{4\'ha}}',170,8,False),
    ('2?8\'hff:16\'d1',255,16,False), ('$clog2(1)',0,32,True),
    ('$clog2(0)',0,32,True), ('$clog2(9)',4,32,True),
    ('1?8:1/0',8,32,True), ('0?1/0:8',8,32,True),
    ('0&&(1/0)',0,1,False), ('1||(1/0)',1,1,False),
])
def test_compile_time_constant_types_and_values(expression, value, width, signed):
    module = Parser(f'module m #(parameter P={expression})(output y); assign y=1\'b0; endmodule').parse()
    result = module.parameters['P']
    assert (result.integer,result.width,result.signed) == (value,width,signed)


@pytest.mark.parametrize('source,parameters', [
    ("module m #(parameter W=0)(input [W-1:0] a,output y);assign y=a[0];endmodule", None),
    ("module m #(parameter W=65)(input [W-1:0] a,output y);assign y=a[0];endmodule", None),
    ("module m #(parameter A=B,B=A)(output y);assign y=1'b0;endmodule", None),
    ("module m #(parameter A=A)(output y);assign y=1'b0;endmodule", None),
    ("module m #(parameter A=missing)(output y);assign y=1'b0;endmodule", None),
    ("module m(input a,output y);localparam A=a;assign y=a;endmodule", None),
    ("module m #(parameter A=1/0)(output y);assign y=1'b0;endmodule", None),
    ("module m #(parameter A=$clog2(-1))(output y);assign y=1'b0;endmodule", None),
    ("module m #(parameter A={1,2})(output y);assign y=1'b0;endmodule", None),
    ("module m #(parameter A=1)(output y);assign y={A+1};endmodule", None),
    ("module m #(parameter A=1,A=2)(output y);assign y=1'b0;endmodule", None),
    ("module m #(parameter A=1)(input A,output y);assign y=A;endmodule", None),
    ("module m(output y);localparam A=1;localparam A=2;assign y=1'b0;endmodule", None),
    ("module m(output y);localparam A=1;assign y=1'b0;endmodule", {'A': 2}),
    ("module m(output y);assign y=1'b0;endmodule", {'TYPO': 2}),
    ("module m #(parameter A=1)(output y);assign y=1'b0;endmodule", {'A': True}),
    ("module m #(parameter A=1)(output y);assign y=1'b0;endmodule", {'A': '1+2'}),
    ("module m #(parameter A=1)(output y);assign y=1'b0;endmodule", {'A': "8'b0b10"}),
    ("module m #(parameter [A:0] A=1)(output y);assign y=1'b0;endmodule", None),
    ("module m #(parameter A=2147483648)(output y);assign y=1'b0;endmodule", None),
    ("module m(input a,output y);wire w=a;assign w=a;assign y=w;endmodule", None),
    ("module m(input a,output y);wire w=a, w=a;assign y=w;endmodule", None),
    ("module m #(parameter integer A=1)(output y);assign y=1'b0;endmodule", None),
])
def test_rejects_invalid_parameters_and_elaboration(source, parameters):
    with pytest.raises(VerilogError):
        compile_source(source, parameters=parameters)


def test_cli_parameter_overrides_and_manifest(tmp_path):
    output = tmp_path/'adder.ttf'
    result = subprocess.run([sys.executable,str(HERE/'build.py'),str(HERE/'examples/parameter_adder.v'),
                             '-o',str(output),'-P','WIDTH=16','--parameter',"MASK=16'h0ff0"],
                            capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    manifest = json.loads(output.with_suffix('.json').read_text())
    assert manifest['inputs'][0]['width'] == 16
    assert {p['name']:p['value'] for p in manifest['parameters']} == {'WIDTH':'16','MASK':'4080','TOP_BIT':'32768'}
    with NativeFont(output) as font:
        assert font.invoke(65535,1) == (65536,4080,32767)


@pytest.mark.parametrize('arguments', [['-P','WIDTH'], ['-P','WIDTH='], ['-P','WIDTH=8','-P','WIDTH=16'],
                                    ['-P','UNKNOWN=2'], ['-P','TOP_BIT=2']])
def test_cli_rejects_bad_overrides_without_output(tmp_path, arguments):
    output = tmp_path/'bad.ttf'
    result = subprocess.run([sys.executable,str(HERE/'build.py'),str(HERE/'examples/parameter_adder.v'),
                             '-o',str(output),*arguments],capture_output=True,text=True)
    assert result.returncode == 2
    assert not output.exists()
    assert not output.with_suffix('.json').exists()


def test_parameter_resource_bounds_and_override_mapping():
    with pytest.raises(VerilogError, match='at most 128 parameters'):
        compile_source('module m(output y);' + ''.join(f'parameter P{i}=1;' for i in range(129)) +
                       "assign y=1'b0;endmodule")
    with pytest.raises(VerilogError, match='depth'):
        compile_source('module m(output y); parameter P=' + '+'.join(['1']*100) + ";assign y=1'b0;endmodule")
    with pytest.raises(VerilogError, match='mapping'):
        compile_source("module m(output y);assign y=1'b0;endmodule", parameters=['W=8'])


@pytest.mark.parametrize('source', [
    "module m(input [W-1:0] a,output y);parameter W=8;assign y=a[0];endmodule",
    "module m(input a,output y);wire [W-1:0] b;parameter W=8;assign b={W{a}};assign y=b[0];endmodule",
    "module m(output y);localparam HALF=W/2;parameter W=8;assign y=1'b0;endmodule",
    "module m(output y);parameter W=N*2;parameter N=4;assign y=1'b0;endmodule",
    "module m #(parameter W=N*2,parameter N=4)(output y);assign y=1'b0;endmodule",
    "module m(output y);parameter [N-1:0] W=8'hff;parameter N=4;assign y=W[0];endmodule",
])
def test_parameter_references_require_prior_declarations(source):
    with pytest.raises(VerilogError, match='before declaration'):
        compile_source(source)
