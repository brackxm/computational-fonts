"""The package command line uses the same examples and font ABI as the scripts."""
from pathlib import Path
import subprocess
import sys


def test_package_compile_and_invoke(tmp_path):
    root = Path(__file__).resolve().parents[1]
    font = tmp_path / 'add.ttf'
    subprocess.run(
        [sys.executable, '-m', 'wasmfont', 'examples/add.wat', '--export', 'add', '-o', str(font)],
        cwd=root, check=True, capture_output=True, text=True, timeout=20,
    )
    result = subprocess.run(
        [sys.executable, '-m', 'wasmfont.runtime', str(font), '4294967295', '1'],
        cwd=root, check=True, capture_output=True, text=True, timeout=20,
    )
    assert result.stdout.strip() == '0'
