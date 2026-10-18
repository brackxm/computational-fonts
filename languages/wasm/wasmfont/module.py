"""Bounded core Wasm module loader: memory, integer globals, active data segments.

Uses the existing function decoder; unsupported module constructs fail closed.
"""
from dataclasses import dataclass, field
from pathlib import Path
from .ir import parse_binary, uleb, sleb
from .state import MachineState
from .validation import validate_supported

@dataclass
class Module:
    functions: list
    initial_pages: int = 0
    maximum_pages: int = 16
    globals: list = field(default_factory=list)
    global_types: list = field(default_factory=list)
    mutable: list = field(default_factory=list)
    segments: list = field(default_factory=list)
    exports: dict = field(default_factory=dict)

    def invoke(self, export_name, args, *, state=None, fuel=100000):
        """Execute an exported function against a module instance (reference VM)."""
        from .reference.interpreter import run
        if export_name not in self.exports:
            raise KeyError(f'unknown export: {export_name}')
        kind, index = self.exports[export_name]
        if kind != 0:
            raise TypeError(f'export {export_name} is not a function')
        if state is None:
            state = self.instantiate()
        return run(self.functions, index, args, fuel=fuel, state=state)

    def instantiate(self):
        state = MachineState(pages=self.initial_pages, max_pages=self.maximum_pages,
                             globals=self.globals.copy(), global_types=self.global_types.copy(),
                             mutable=self.mutable.copy())
        for offset, payload in self.segments:
            state.bounds(offset, len(payload))
            state.memory[offset:offset+len(payload)] = payload
        return state

def load_binary(path):
    data=Path(path).read_bytes()
    if data[:8]!=b'\0asm\x01\0\0\0':raise ValueError('invalid Wasm header')
    validate_supported(data)
    sections={}; pos=8; previous=0
    while pos<len(data):
        section=data[pos];pos+=1
        size,pos=uleb(data,pos);end=pos+size
        if end>len(data):raise ValueError('truncated section')
        if section:
            if section in sections or section<previous:raise ValueError('duplicate/out-of-order section')
            previous=section;sections[section]=data[pos:end]
        pos=end
    def vector(section, parser):
        b=sections.get(section,b'\0');p=0;count,p=uleb(b,p);items=[]
        if count>100000:raise ValueError('excessive vector size')
        for _ in range(count):
            item,p=parser(b,p);items.append(item)
        if p!=len(b):raise ValueError('trailing section data')
        return items
    def limits(b,p):
        flag,p=uleb(b,p)
        if flag not in (0,1):raise NotImplementedError('shared/memory64 memory unsupported')
        minimum,p=uleb(b,p)
        if flag:maximum,p=uleb(b,p)
        else:maximum=max(16,minimum)
        if minimum>maximum or maximum>256:raise ValueError('unsupported memory limits')
        return (minimum,maximum),p
    def init_expr(b,p):
        if p>=len(b):raise ValueError('truncated initializer')
        opcode=b[p];p+=1
        if opcode not in (0x41,0x42):raise NotImplementedError('only constant initializers supported')
        value,p=sleb(b,p,32 if opcode==0x41 else 64)
        if p>=len(b) or b[p]!=0x0b:raise ValueError('initializer missing end')
        return value,p+1
    def global_entry(b,p):
        if p+2>len(b):raise ValueError('truncated global')
        typ={0x7f:'i32',0x7e:'i64'}.get(b[p]);mut=b[p+1];p+=2
        if typ is None or mut not in (0,1):raise NotImplementedError('unsupported global type')
        value,p=init_expr(b,p)
        return (typ,bool(mut),value),p
    def segment(b,p):
        flag,p=uleb(b,p)
        if flag==0:offset,p=init_expr(b,p)
        elif flag==2:
            index,p=uleb(b,p)
            if index!=0:raise NotImplementedError('multiple memories unsupported')
            offset,p=init_expr(b,p)
        else:raise NotImplementedError('passive data segments unsupported')
        length,p=uleb(b,p)
        if p+length>len(b):raise ValueError('truncated data segment')
        return (offset,b[p:p+length]),p+length
    def export(b,p):
        n,p=uleb(b,p)
        if p+n+1>len(b):raise ValueError('truncated export')
        name=b[p:p+n].decode('utf-8');p+=n;kind=b[p];p+=1;index,p=uleb(b,p)
        return (name,kind,index),p
    memories=vector(5,limits)
    if len(memories)>1:raise NotImplementedError('multiple memories unsupported')
    globals_=vector(6,global_entry)
    segments=vector(11,segment)
    exports=vector(7,export)
    functions=parse_binary(path)
    mapping={}
    for name,kind,index in exports:
        if name in mapping:raise ValueError('duplicate export')
        if kind==0 and index>=len(functions):raise ValueError('invalid function export')
        mapping[name]=(kind,index)
    if segments and not memories:raise ValueError('data segment without memory')
    m=Module(functions,*(memories[0] if memories else (0,0)),
             [v for _,_,v in globals_],[t for t,_,_ in globals_],
             [mut for _,mut,_ in globals_],segments,mapping)
    m.has_memory=bool(memories)
    m.instantiate() # validate segment bounds immediately
    return m
