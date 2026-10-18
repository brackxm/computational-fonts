# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Check independent frontend loading and compatibility with existing imports."""
from pathlib import Path
import subprocess
import sys


LANGUAGES = Path(__file__).resolve().parents[2]


def run_isolated(tmp_path, language, source):
    bootstrap = f'import sys; sys.path.insert(0, {str(LANGUAGES / language)!r})\n'
    result = subprocess.run([sys.executable, '-c', bootstrap + source], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_verilog_builds_and_runs_without_importing_wasm(tmp_path):
    run_isolated(tmp_path, 'verilog', '''
class RejectWasm:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'wasmfont' or fullname.startswith('wasmfont.'):
            raise AssertionError('Verilog depends on the Wasm package')
sys.meta_path.insert(0, RejectWasm())
from verilogfont.compiler import build
from fontcircuit.runtime import NativeFont
from fontcircuit.gsub.circuit import Circuit
assert Circuit.__module__ == 'fontcircuit.gsub.circuit'
build("module m(input [7:0] a, output [7:0] y); assign y=a+8'd1; endmodule", 'm.ttf')
with NativeFont('m.ttf') as font:
    assert font.invoke(255) == 0
''')


def test_wasm_compatibility_imports_share_the_same_implementation(tmp_path):
    run_isolated(tmp_path, 'wasm', '''
from pathlib import Path
import wasmfont
from wasmfont import runtime, harfbuzz
from wasmfont.gsub import circuit, tables
from wasmfont.compiler import Circuit as CompilerCircuit
from fontcircuit import runtime as shared_runtime, harfbuzz as shared_harfbuzz
from fontcircuit.gsub import circuit as shared_circuit, tables as shared_tables
assert runtime.NativeFont is shared_runtime.NativeFont
assert runtime.IncompleteShaping is shared_runtime.IncompleteShaping
assert harfbuzz.run is shared_harfbuzz.run
assert circuit.Circuit is shared_circuit.Circuit is CompilerCircuit
assert tables.attach_tables is shared_tables.attach_tables
assert Path(shared_runtime.__file__).parent.parent.name == 'shared'
assert Path(shared_circuit.__file__).parents[2].name == 'shared'
''')
