# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compile source, without runtime input values, to a font and paired manifest."""
from pathlib import Path

from fontcircuit.gsub.circuit import emit_font, ResourceLimit
from .syntax import SourceText, VerilogResourceLimit
from .frontend import compile_source


def build(source, output, *, max_gates=12000, parameters=None, top=None, source_name="<source>"):
    source = source if isinstance(source,SourceText) else SourceText(source,source_name)
    module, circuit, results = compile_source(source, max_gates=max_gates, parameters=parameters, top=top)
    ports = lambda signals: [dict(name=s.name, width=s.width, signed=s.signed) for s in signals]
    extra = {'language': 'verilog', 'module': module.name,
             'verilog_subset': 'combinational-v2',
             'inputs': ports(module.inputs), 'outputs': ports(module.outputs), 'source': source}
    if module.parameters:
        extra['parameters'] = [dict(name=name, value=str(value.integer), width=value.width,
                                    signed=value.signed, local=name in module.localparams)
                               for name, value in module.parameters.items()]
    if module.hierarchy:
        extra['hierarchy'] = module.hierarchy
    try:
        return emit_font(circuit, results, circuit.verilog_flags,
                         [f'i{s.width}' for s in module.inputs],
                         [f'i{s.width}' for s in module.outputs], Path(output),
                         font_family='Verilog GSUB Registers',
                         extra=extra)
    except ResourceLimit as error:
        advice = ('reduce the design or increase --max-gates (maximum 32000)'
                  if 'max_gates=' in str(error) else 'reduce the design to fit OpenType glyph/layout limits')
        raise VerilogResourceLimit(f'{error}; font output exceeds its budget/capacity; {advice}',source.location(0)) from None
