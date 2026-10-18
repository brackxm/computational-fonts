# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compile source, without runtime input values, to a font and paired manifest."""
from pathlib import Path

from fontcircuit.gsub.circuit import emit_font
from .frontend import compile_source


def build(source, output, *, max_gates=12000):
    module, circuit, results = compile_source(source, max_gates=max_gates)
    ports = lambda signals: [dict(name=s.name, width=s.width) for s in signals]
    return emit_font(circuit, results, {},
                     [f'i{s.width}' for s in module.inputs],
                     [f'i{s.width}' for s in module.outputs], Path(output),
                     font_family='Verilog GSUB Registers',
                     extra={'language': 'verilog', 'module': module.name,
                            'verilog_subset': 'unsigned-combinational-v1',
                            'inputs': ports(module.inputs), 'outputs': ports(module.outputs),
                            'source': source})
