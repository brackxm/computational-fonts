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
from fontcircuit.runtime import NativeFont

IVERILOG = os.environ.get('IVERILOG') or shutil.which('iverilog')
VVP = os.environ.get('VVP') or shutil.which('vvp')
pytestmark = pytest.mark.skipif(not (IVERILOG and VVP), reason='optional Icarus Verilog simulator is unavailable')


def compare(tmp_path, source):
    module = Parser(source).parse()
    rng = random.Random(914)
    cases = [[0]*len(module.inputs), [(1<<s.width)-1 for s in module.inputs]]
    cases += [[rng.getrandbits(s.width) for s in module.inputs] for _ in range(100)]
    lines = [source, 'module tb;']
    lines += [f'reg [{s.width-1}:0] {s.name};' for s in module.inputs]
    lines += [f'wire [{s.width-1}:0] {s.name};' for s in module.outputs]
    ports = module.inputs + module.outputs
    lines += [f'{module.name} dut(' + ','.join(f'.{s.name}({s.name})' for s in ports) + ');', 'initial begin']
    for values in cases:
        lines += [f"{s.name} = {s.width}'d{value};" for s, value in zip(module.inputs, values)]
        lines += ['#1; $display("' + ' '.join('%d' for _ in module.outputs) + '",' +
                  ','.join(s.name for s in module.outputs) + ');']
    lines += ['$finish; end endmodule']
    tb = tmp_path/'tb.v'
    tb.write_text('\n'.join(lines))
    program = tmp_path/'sim.vvp'
    result = subprocess.run([IVERILOG, '-g2005', '-s', 'tb', '-o', str(program), str(tb)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([VVP, str(program)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    # Newer Icarus releases append a $finish location to stdout.
    expected = [tuple(map(int, line.split())) for line in result.stdout.splitlines()
                if line.strip() and all(part.isdigit() for part in line.split())]
    assert len(expected) == len(cases), result.stdout
    path = tmp_path/'differential.ttf'
    build(source, path)
    with NativeFont(path) as font:
        for values, reference in zip(cases, expected):
            shaped = font.invoke(*values)
            assert ((shaped,) if len(module.outputs)==1 else shaped) == reference, values


@pytest.mark.parametrize('name', ['adder', 'alu', 'multiplier', 'bit_routes'])
def test_bundled_modules_against_icarus(tmp_path, name):
    compare(tmp_path, (HERE/'examples'/f'{name}.v').read_text())


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
