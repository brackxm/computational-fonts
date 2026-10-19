# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Check frontend semantics and actual HarfBuzz execution, not just circuit IR."""
import hashlib
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from verilogfont.compiler import build
from verilogfont.frontend import VerilogError, compile_source
from fontcircuit.runtime import NativeFont, IncompleteShaping
from fontcircuit.gsub.circuit import ResourceLimit


def compiled(tmp_path, source):
    path = tmp_path / 'test.ttf'
    build(source, path)
    return NativeFont(path)


def test_context_preserves_carry_and_full_product(tmp_path):
    with compiled(tmp_path, (HERE / 'examples/adder.v').read_text()) as font:
        for a, b in itertools.product([0, 1, 127, 128, 254, 255], repeat=2):
            assert font.invoke(a, b) == a+b
    with compiled(tmp_path, (HERE / 'examples/multiplier.v').read_text()) as font:
        for a, b in itertools.product(range(16), repeat=2):
            assert font.invoke(a, b) == a*b


def test_alu_exhaustive_small_values_and_wide_shifts(tmp_path):
    with compiled(tmp_path, (HERE / 'examples/alu.v').read_text()) as font:
        for a, b, op in itertools.product([0, 1, 3, 7, 8, 15, 128, 255], repeat=3):
            op &= 3
            y = [a+b, a-b, a ^ b, a << b][op] & 255
            assert font.invoke(a, b, op) == (y, int(a == b), int(a < b))


def test_concatenation_replication_and_reductions(tmp_path):
    with compiled(tmp_path, (HERE / 'examples/bit_routes.v').read_text()) as font:
        for data, enable in itertools.product(range(256), range(2)):
            assert font.invoke(data, enable) == (((data & 15) << 4) | (data >> 4),
                                                data if enable else 0,
                                                data.bit_count() % 2, int(data == 255))


@pytest.mark.parametrize('expr,expected', [
    ('a + b * c', lambda a,b,c: a+b*c),
    ('(a + b) * c', lambda a,b,c: (a+b)*c),
    ('a | b & c', lambda a,b,c: a | (b&c)),
    ('a ^~ b', lambda a,b,c: ~(a^b)),
    ('~a', lambda a,b,c: ~a),
    ('-a', lambda a,b,c: -a),
    ('a ? b : c ? a : b', lambda a,b,c: b if a else a if c else b),
    ('a && b || c', lambda a,b,c: int(bool((a and b) or c))),
    ('a <= b', lambda a,b,c: int(a<=b)),
    ('a >= b', lambda a,b,c: int(a>=b)),
    ('a != b', lambda a,b,c: int(a!=b)),
    ('~&a', lambda a,b,c: int(a!=31)),
    ('~|a', lambda a,b,c: int(a==0)),
    ('~^a', lambda a,b,c: 1-(a.bit_count()%2)),
    ('a >> b', lambda a,b,c: a>>b),
    ('a << b', lambda a,b,c: a<<b),
])
def test_expression_semantics_in_font(tmp_path, expr, expected):
    source = f'module m(input [4:0] a,b,c, output [6:0] y); assign y={expr}; endmodule'
    rng = random.Random(491)
    with compiled(tmp_path, source) as font:
        for a, b, c in [(0,0,0), (31,31,31), (1,8,0)] + [tuple(rng.randrange(32) for _ in range(3)) for _ in range(30)]:
            # Unary arithmetic/bitwise operands extend to the 7-bit assignment
            # context; reductions still inspect the 5-bit input.
            assert font.invoke(a,b,c) == expected(a,b,c) & 127


def test_assignment_boundaries_and_self_determined_concatenations(tmp_path):
    source = '''module m(input [3:0] a,b, output [4:0] sum, boundary, concat);
      wire [3:0] narrow;
      assign boundary = narrow;
      assign narrow = a+b;
      assign sum = a+b;
      assign concat = {a+b};
    endmodule'''
    with compiled(tmp_path, source) as font:
        assert font.invoke(15,1) == (16,0,0)


def test_64_bit_ports_and_non_power_of_two_shifts(tmp_path):
    source = '''module m(input [63:0] a, input [6:0] n,
      output [63:0] left, right, output [4:0] narrow_shift);
      assign left=a<<n; assign right=a>>n; assign narrow_shift=5'b10101<<n;
    endmodule'''
    with compiled(tmp_path, source) as font:
        for n in [0,1,4,5,31,63,64,65,127]:
            a = 0xfedcba9876543210
            assert font.invoke(a,n) == ((a<<n)&((1<<64)-1), a>>n, (21<<n)&31)


def test_constants_identity_and_zero_inputs_require_shaping(tmp_path):
    for source, args, expected in [
        ("module m(output [7:0] y); assign y=8'hA5; endmodule", (), 165),
        ('module m(input [7:0] a, output [7:0] y); assign y=a; endmodule', (42,), 42),
    ]:
        with compiled(tmp_path, source) as font:
            assert font.invoke(*args) == expected
            with pytest.raises(IncompleteShaping):
                font.decode(font.shaper.shape(font.encode(args), enabled=False))


@pytest.mark.parametrize('literal', [
    "8'b0b10", "8'B0B10", "8'b2", "8'b0a", "8'o8", "8'da",
    "8'b_10", "8'o_17", "8'd_42", "8'h_ff", "8'h_", "8'b__",
])
def test_rejects_malformed_based_literals(literal):
    with pytest.raises(VerilogError, match='invalid based literal'):
        compile_source(f'module m(output [7:0] y); assign y={literal}; endmodule')


def test_valid_based_literals_still_shape_with_case_and_underscores(tmp_path):
    literals = ["8'b10_10", "8'B10__10_", "8'o1_7", "8'O17_",
                "8'd4_2", "8'D42_", "8'hf_f", "8'HF__F_", "4'hff"]
    source = 'module m(output [7:0] ' + ','.join(f'y{i}' for i in range(len(literals))) + ');'
    source += ''.join(f'assign y{i}={literal};' for i,literal in enumerate(literals))
    with compiled(tmp_path, source + 'endmodule') as font:
        assert font.invoke() == (10, 10, 15, 15, 42, 42, 255, 255, 15)


@pytest.mark.parametrize('body', [
    "assign y=1'bx;", "assign y=1'bz;", "assign y=1'b?;",
    'assign y=a**1;', 'assign y=a%$clog2(a);', 'assign y={a+1};',
    "assign y=2'sdx;", 'assign y=$unsigned(a,b);',
    'always @* y=a;', 'initial y=0;', 'reg z;', 'logic z;',
    'assign y=a; assign y=a;', 'assign a=y; assign y=a;',
    'assign y=missing;', 'assign y=a[8];', 'assign y=a[0:1];',
    'assign y=a[a:0];', 'assign y=a===a;', 'assign y=a>>>>a;',
    'assign y=a**a;', 'assign y=8\'b2;', 'assign y={65{a}};',
    "assign y={64'h0,1'b0};", 'assign y=a; wire unused;',
    'wire loop; assign loop=loop; assign y=a;',
    'wire b,c; assign b=c; assign c=b; assign y=a;',
    'assign z=a; assign y=a;',
])
def test_rejects_invalid_or_unsupported_source_even_when_unused(body):
    with pytest.raises(VerilogError):
        compile_source(f'module m(input a, output y); {body} endmodule')


@pytest.mark.parametrize('source', [
    'module m(a,y); input a; output y; assign y=a; endmodule',
    'module m(input unsigned a, output y); assign y=a; endmodule',
    'module m(input [0:7] a, output y); assign y=a; endmodule',
    'module m(input [64:0] a, output y); assign y=a; endmodule',
    'module m(input a,a, output y); assign y=a; endmodule',
    'module m(input a); endmodule',
    'module m(output y); endmodule',
    'module m(output y); assign y=1\'b0; endmodule garbage',
    '/* unterminated',
    'module m(output y); assign y=1\'b0;',
    '`define A 1',
])
def test_module_contract(source):
    with pytest.raises(VerilogError):
        compile_source(source)


def test_resource_bounds():
    with pytest.raises(ResourceLimit):
        compile_source('module m(input [7:0] a,b, output [7:0] y); assign y=a*b; endmodule', max_gates=1)
    with pytest.raises(VerilogError, match='depth'):
        compile_source('module m(input a, output y); assign y=' + '+'.join(['a']*200) + '; endmodule')
    with pytest.raises(VerilogError):
        compile_source('module m(input a, output y); assign y=' + '('*100+'a'+')'*100 + '; endmodule')
    with pytest.raises(VerilogError, match='source exceeds'):
        compile_source(' '*65537)


def test_bundled_fonts_match_fresh_builds_and_metadata(tmp_path):
    for source in sorted((HERE/'examples').glob('*.v')):
        path = tmp_path / f'{source.stem}.ttf'
        manifest = build(source.read_text(), path)
        bundled = HERE / 'playground/assets' / path.name
        assert path.read_bytes() == bundled.read_bytes()
        assert manifest == json.loads(bundled.with_suffix('.json').read_text())
        assert manifest['font_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert manifest['language'] == 'verilog'


def test_cli_build_and_run(tmp_path):
    output = tmp_path / 'adder.ttf'
    build_result = subprocess.run([sys.executable, str(HERE/'build.py'),
                                  str(HERE/'examples/adder.v'), '-o', str(output)],
                                 capture_output=True, text=True)
    assert build_result.returncode == 0, build_result.stderr
    result = subprocess.run([sys.executable, str(HERE/'run.py'), str(output), '255', '1'],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "sum=256 (0x100, 9'b100000000)"


def test_tampered_font_fails_closed(tmp_path):
    path = tmp_path/'m.ttf'
    build("module m(output y); assign y=1'b1; endmodule", path)
    manifest = json.loads(path.with_suffix('.json').read_text())
    manifest['font_sha256'] = '0'*64
    path.with_suffix('.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='does not match'):
        NativeFont(path)


def test_cli_rejects_invalid_port_metadata(tmp_path):
    path = tmp_path/'m.ttf'
    build("module m(output y); assign y=1'b1; endmodule", path)
    manifest = json.loads(path.with_suffix('.json').read_text())
    manifest['outputs'][0]['width'] = 64
    path.with_suffix('.json').write_text(json.dumps(manifest))
    result = subprocess.run([sys.executable, str(HERE/'run.py'), str(path)],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert 'invalid Verilog port metadata' in result.stderr


def test_cli_preserves_source_that_collides_with_manifest(tmp_path):
    source = tmp_path/'source.json'
    text = "module m(output y); assign y=1'b1; endmodule"
    source.write_text(text)
    result = subprocess.run([sys.executable, str(HERE/'build.py'), str(source),
                             '-o', str(source.with_suffix('.ttf'))], capture_output=True, text=True)
    assert result.returncode == 2
    assert source.read_text() == text
