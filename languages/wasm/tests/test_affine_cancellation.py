"""Affine cancellation must be valid for both Wasm integer widths."""
import pytest
from pathlib import Path
from wasmfont.reference.lowering import compile_module
from wasmfont.harfbuzz import run

@pytest.mark.parametrize('width', [32, 64])
@pytest.mark.parametrize('operation,expected', [('sub', 7), ('add', 19)])
def test_affine_cancellation(tmp_path, width, operation, expected):
    # (a + 13) - (a + 6) = 7
    # (a + 13) + (6 - a) = 19
    rhs = (f'local.get 0 i{width}.const 6 i{width}.add' if operation == 'sub'
           else f'i{width}.const 6 local.get 0 i{width}.sub')
    wat = (f'(module (func (param i{width}) (param i{width}) (result i{width}) '
           f'local.get 0 i{width}.const 13 i{width}.add '
           f'{rhs} i{width}.{operation}))')
    src = tmp_path/'example.wat'; src.write_text(wat)
    font = tmp_path/'example.ttf'; lowered = compile_module(src, font)
    for a in (0, 1, 0xffffffff, 1 << (width-1)):
        tokens = run(font, lowered.encode(a, 123))
        assert lowered.decode(tokens) == expected
