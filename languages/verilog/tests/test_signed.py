# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Signed datapaths execute in the font; hosts only decode the result bits."""
import itertools
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


def test_signed_arithmetic_exhaustive_small_inputs(tmp_path):
    source = '''module m(input wire signed [3:0] a,b,
      output signed [4:0] sum,difference,negated,
      output signed [7:0] product, output less,le,gt,ge,eq,ne);
      assign sum=a+b; assign difference=a-b; assign negated=-a;
      assign product=a*b; assign less=a<b; assign le=a<=b;
      assign gt=a>b; assign ge=a>=b; assign eq=a==b; assign ne=a!=b;
    endmodule'''
    path = tmp_path/'signed.ttf'
    build(source, path)
    with NativeFont(path) as font:
        for a,b in itertools.product(range(-8,8), repeat=2):
            assert font.invoke(a,b) == ((a+b)&31, (a-b)&31, (-a)&31, (a*b)&255,
                                        int(a<b), int(a<=b), int(a>b), int(a>=b), int(a==b), int(a!=b))
        with pytest.raises(IncompleteShaping):
            font.decode(font.shaper.shape(font.encode([-8,7]), enabled=False))


def test_signed_shift_counts_are_not_masked(tmp_path):
    path = tmp_path/'shifts.ttf'
    build('''module m(input signed [4:0] a, input [63:0] n,
      output signed [6:0] arithmetic,left, output [6:0] logical);
      assign arithmetic=a>>>n; assign left=a<<<n; assign logical=a>>n;
    endmodule''', path)
    with NativeFont(path) as font:
        for a,n in itertools.product(range(-16,16), [0,1,4,5,6,7,8,31,63,64,65,1<<63,(1<<64)-1]):
            arithmetic = a >> min(n,7)
            left = (a << n)&127 if n < 7 else 0
            logical = (a&127) >> min(n,7)
            assert font.invoke(a,n) == (arithmetic&127,left,logical)


def test_mixed_operands_zero_extend_before_arithmetic(tmp_path):
    path = tmp_path/'mixed.ttf'
    build('''module m(input signed [3:0] a,b, input [3:0] u,
      output [7:0] mixed, signed_sum, cast_sum, concat_sum, selected,
      output less_signed,less_mixed);
      assign mixed=a+b+u; assign signed_sum=a+b;
      assign cast_sum=$signed(a+b); assign concat_sum={a+b};
      assign selected=a[3:0]; assign less_signed=a<b; assign less_mixed=a<u;
    endmodule''', path)
    with NativeFont(path) as font:
        assert font.invoke(-1,1,0) == (16,0,0,0,15,1,0)
        assert font.invoke(7,7,15) == (29,14,254,14,7,0,1)


@pytest.mark.parametrize('literal,bits', [
    ("8'shff",65535), ("8'Sb1000_0000",65408), ("8'so177",127),
    ("8'sd255",65535), ("4'shff",65535), ('-1',65535),
    ("$unsigned(8'shff)",255), ("$signed(8'hff)",65535),
    ("{1'b1 << 1}",0), ("{1 ? 8'shff : 8'sd0}",255),
    ("{$signed(1)}",1), ("{$unsigned(-1)}",65535),
])
def test_literals_and_casts_shape_with_assignment_context(tmp_path, literal, bits):
    path = tmp_path/'literal.ttf'
    build(f'module m(output [15:0] y); assign y={literal}; endmodule', path)
    with NativeFont(path) as font:
        assert font.invoke() == bits


def test_signed_declaration_groups_and_parameter_types():
    module = Parser('''module m #(parameter signed A=8'hff, B=8'sd1,
      parameter signed [15:0] C=8'hff, D=8'shff,
      parameter [15:0] E=8'shff)
      (input signed [3:0] a,b, input c, output signed [7:0] y,z, output raw);
      wire signed [3:0] narrow=a+b, other=a-b;
      localparam signed [4:0] NEG=-1;
      assign y=narrow; assign z=other; assign raw=c;
    endmodule''').parse()
    assert [s.signed for s in module.inputs] == [True,True,False]
    assert [s.signed for s in module.outputs] == [True,True,False]
    assert module.signals['narrow'].signed and module.signals['other'].signed
    assert [(v.integer,v.width,v.signed) for v in module.parameters.values()] == [
        (-1,8,True), (1,8,True), (255,16,True), (-1,16,True), (65535,16,False), (-1,5,True)]


@pytest.mark.parametrize('expression', ["8'sb2", "8'sh_ff", "8'sdx", "8'sbz", "8'sh?",
    '{a+1}', '{1{1}}', '$signed(a,b)', '$unsigned()', '$signed(missing)'])
def test_invalid_signed_syntax_and_unsized_concatenations(expression):
    with pytest.raises(VerilogError):
        compile_source(f'module m(input signed [3:0] a,output [7:0] y); assign y={expression}; endmodule')


def run_font(path, *values):
    return subprocess.run([sys.executable,str(HERE/'run.py'),str(path),*map(str,values)],
                          capture_output=True,text=True)


def test_cli_formats_signed_outputs_and_preserves_bit_patterns(tmp_path):
    path = tmp_path/'signed.ttf'
    manifest = build((HERE/'examples/signed_math.v').read_text(),path)
    assert manifest['verilog_subset'] == 'combinational-v2'
    assert [p['signed'] for p in manifest['inputs']] == [True,True,False]
    assert [p['signed'] for p in manifest['outputs']] == [True,True,True,False]
    result = run_font(path,-128,3,2)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "sum=-125 (0x183, 9'b110000011)",
        "product=-384 (0xfe80, 16'b1111111010000000)",
        "shifted=-32 (0xe0, 8'b11100000)", "less=1 (0x1, 1'b1)"]


def test_cli_keeps_legacy_unsigned_fonts_readable(tmp_path):
    path = tmp_path/'legacy.ttf'
    manifest = build((HERE/'examples/adder.v').read_text(),path)
    manifest['verilog_subset'] = 'unsigned-combinational-v1'
    for port in manifest['inputs']+manifest['outputs']:
        del port['signed']
    path.with_suffix('.json').write_text(json.dumps(manifest))
    result = run_font(path,255,1)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "sum=256 (0x100, 9'b100000000)"


@pytest.mark.parametrize('signed', [None, 0, 1, 'true'])
def test_cli_rejects_missing_or_invalid_signed_metadata(tmp_path, signed):
    path = tmp_path/'bad.ttf'
    manifest = build("module m(output signed y); assign y=1'sb1; endmodule", path)
    if signed is None:
        del manifest['outputs'][0]['signed']
    else:
        manifest['outputs'][0]['signed'] = signed
    path.with_suffix('.json').write_text(json.dumps(manifest))
    result = run_font(path)
    assert result.returncode == 2
    assert 'invalid Verilog port metadata' in result.stderr


def test_cli_preserves_signed_64_bit_precision(tmp_path):
    path = tmp_path/'wide.ttf'
    build("""module m(output signed [63:0] low, high);
      assign low=64'sh8000000000000000; assign high=64'sh7fffffffffffffff;
    endmodule""", path)
    result = run_font(path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "low=-9223372036854775808 (0x8000000000000000, 64'b1" + '0'*63 + ')',
        "high=9223372036854775807 (0x7fffffffffffffff, 64'b0" + '1'*63 + ')']
