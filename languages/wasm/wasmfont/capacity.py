"""Actionable capacity errors without changing the shared backend's budgets."""
from fontcircuit.gsub.circuit import ResourceLimit

MAX_LOWERED_INSTRUCTIONS=100000


class CompilationCapacity(ResourceLimit):
    def __init__(self,error,compiler):
        text=str(error);lower=text.lower()
        if 'too many lowered instructions' in lower:self.resource='instructions'
        elif 'max_gates' in lower:self.resource='gates'
        elif 'glyph-count' in lower:self.resource='glyphs'
        else:self.resource='lookup_offsets'
        self.details={'constructed_gates':compiler.c.gate_count,'gate_limit':compiler.limits.max_gates,
                      'backed_memory_bytes':len(getattr(compiler,'memory_addresses',())),
                      'memory_regions':len(getattr(compiler,'memory_layout',())),
                      'lowered_instructions':compiler.lowered_instructions,
                      'instruction_limit':MAX_LOWERED_INSTRUCTIONS}
        hint={'gates':'Reduce memory/loop/call bounds, or increase --max-gates within the supported cap.',
              'glyphs':'Reduce live inputs and intermediate results; increasing --max-gates cannot raise the glyph limit.',
              'lookup_offsets':'Reduce circuit size or bounds; increasing --max-gates cannot raise OpenType lookup-offset limits.',
              'instructions':'Reduce loop/call bounds or simplify the program; --max-gates does not change the instruction limit.'}[self.resource]
        progress=(f'lowered instructions {compiler.lowered_instructions}/{MAX_LOWERED_INSTRUCTIONS}; '
                  if self.resource=='instructions' else '')
        super().__init__(f'{text} [{self.resource}; {progress}constructed gates {self.details["constructed_gates"]}/{self.details["gate_limit"]}; '
                         f'backed bytes {self.details["backed_memory_bytes"]} in {self.details["memory_regions"]} regions]. {hint}')
