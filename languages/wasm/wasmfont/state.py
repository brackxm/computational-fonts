"""Bounded Wasm linear memory and mutable integer globals (reference runtime)."""
from dataclasses import dataclass, field

class MemoryTrap(Exception): pass

@dataclass
class MachineState:
    pages: int = 1
    max_pages: int = 16
    globals: list = field(default_factory=list)
    global_types: list = field(default_factory=list)
    mutable: list = field(default_factory=list)
    memory: bytearray = field(init=False)

    def __post_init__(self):
        if not 0 <= self.pages <= self.max_pages <= 256: raise ValueError('invalid memory bounds')
        self.memory=bytearray(self.pages*65536)
        if not (len(self.globals)==len(self.global_types)==len(self.mutable)):
            raise ValueError('global metadata mismatch')
        for i,t in enumerate(self.global_types):
            if t not in ('i32','i64'):raise ValueError('unsupported global type')
            self.globals[i] &= (1<<int(t[1:]))-1

    def bounds(self,address,size):
        if address < 0 or address+size>len(self.memory):raise MemoryTrap('out of bounds memory access')
    def load(self,address,size,signed=False):
        self.bounds(address,size)
        return int.from_bytes(self.memory[address:address+size],'little',signed=signed)
    def store(self,address,size,value):
        self.bounds(address,size)
        self.memory[address:address+size]=(value&((1<<(size*8))-1)).to_bytes(size,'little')
    def grow(self,delta):
        old=self.pages
        if delta<0 or old+delta>self.max_pages:return -1
        self.memory.extend(bytearray(delta*65536));self.pages+=delta
        return old
