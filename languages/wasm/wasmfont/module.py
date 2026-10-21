"""Bounded core Wasm module loader: memory, globals, tables and segments.

Uses the existing function decoder; unsupported module constructs fail closed.
"""
from dataclasses import dataclass, field
from pathlib import Path
from .ir import parse_binary, uleb, section_order,value_type
from .state import MachineState
from .validation import validate_supported
from .initializers import decode_expression
from .types import is_reference

MAX_TABLES=16


@dataclass
class FunctionTable:
    entries: list[int | None]
    maximum: int | None = None
    element_type: object = 'funcref'


@dataclass
class ElementSegment:
    mode: str
    offset: int
    functions: list[int | None]
    expressions: bool = False
    table: int = 0
    element_type: object = 'funcref'

@dataclass
class Module:
    functions: list
    initial_pages: int = 0
    maximum_pages: int = 16
    globals: list = field(default_factory=list)
    global_types: list = field(default_factory=list)
    mutable: list = field(default_factory=list)
    segments: list = field(default_factory=list) # (offset, bytes); None marks passive data.
    exports: dict = field(default_factory=dict)
    table: list[int | None] | None = None
    table_maximum: int | None = None
    start: int | None = None
    elements: list[ElementSegment] = field(default_factory=list)
    extra_tables: list[FunctionTable] = field(default_factory=list)
    # Original declaration instructions, keyed by kind and declaration index
    # (plus entry index for reference elements). Values above stay resolved.
    constant_expressions: dict = field(default_factory=dict)
    function_types: list = field(default_factory=list)
    table_type: object = 'funcref'

    @property
    def tables(self):
        return ([] if self.table is None else [FunctionTable(self.table,self.table_maximum,self.table_type)])+self.extra_tables

    def add_table(self,entries,maximum,element_type='funcref'):
        if len(self.tables)>=MAX_TABLES:raise ValueError(f'at most {MAX_TABLES} function tables are supported')
        if self.table is None:self.table=entries;self.table_maximum=maximum;self.table_type=element_type
        else:self.extra_tables.append(FunctionTable(entries,maximum,element_type))

    def invoke(self, export_name, args, *, state=None, fuel=100000):
        """Execute an exported function against a module instance (reference VM)."""
        from .reference.interpreter import run
        if export_name not in self.exports:
            raise KeyError(f'unknown export: {export_name}')
        kind, index = self.exports[export_name]
        if kind != 0:
            raise TypeError(f'export {export_name} is not a function')
        start = self.start if state is None else None
        if state is None:state = self._initial_state()
        return run(self.functions, index, args, fuel=fuel, state=state, start=start)

    def _initial_state(self):
        """Initialize declarations without executing Wasm (also used by loading)."""
        state = MachineState(pages=self.initial_pages, max_pages=self.maximum_pages,
                             globals=self.globals.copy(), global_types=self.global_types.copy(),
                             mutable=self.mutable.copy(),
                             data_segments=[payload if offset is None else b'' for offset,payload in self.segments],
                             table=self.table.copy() if self.table is not None else [],
                             extra_tables=[table.entries.copy() for table in self.extra_tables],
                             extra_table_maxima=[table.maximum if table.maximum is not None else 256 for table in self.extra_tables],
                             function_types=self.function_types,
                             element_segments=[segment.functions.copy() if segment.mode=='passive' else [] for segment in self.elements],
                             table_maximum=(self.table_maximum if self.table_maximum is not None else 256) if self.table is not None else 0)
        for offset, payload in self.segments:
            if offset is None:continue
            state.bounds(offset, len(payload))
            state.memory[offset:offset+len(payload)] = payload
        return state

    def instantiate(self, *, fuel=100000):
        """Create a reference instance and execute its start function once."""
        state=self._initial_state()
        if self.start is not None:
            from .reference.interpreter import run
            run(self.functions,self.start,[],fuel=fuel,state=state)
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
            if section in sections or section_order(section)<previous:raise ValueError('duplicate/out-of-order section')
            previous=section_order(section);sections[section]=data[pos:end]
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
    constant_expressions={};global_values=[]
    def initializer(b,p,typ,key):
        expression,p=decode_expression(b,p)
        value=expression.evaluate(typ,global_values)
        constant_expressions[key]=expression
        return value,p
    def global_entry(b,p):
        typ,p=value_type(b,p)
        if p>=len(b):raise ValueError('truncated global')
        mut=b[p];p+=1
        if mut not in (0,1):raise NotImplementedError('unsupported global mutability')
        value,p=initializer(b,p,typ,('global',len(global_values)))
        global_values.append((typ,bool(mut),value))
        return global_values[-1],p
    table_index=0
    def table_type(b,p):
        nonlocal table_index
        current=table_index;table_index+=1
        explicit=b[p]==0x40
        if explicit:
            if b[p:p+2]!=b'\x40\x00':raise ValueError('invalid table initializer prefix')
            p+=2
        typ,p=value_type(b,p)
        if not is_reference(typ):raise NotImplementedError('only function-reference tables supported')
        flag,p=uleb(b,p)
        if flag not in (0,1):raise NotImplementedError('unsupported table limits')
        minimum,p=uleb(b,p);maximum=None
        if flag:maximum,p=uleb(b,p)
        if minimum>256 or maximum is not None and not minimum<=maximum<=256:
            raise ValueError('table limits must be within 0..256')
        initial=None
        if explicit:
            expression,p=decode_expression(b,p)
            # Defined globals are outside the table-initializer context.
            initial=expression.evaluate(typ)
            constant_expressions['table',current]=expression
        return (minimum,maximum,initial,typ),p
    element_index=0
    def element(b,p):
        nonlocal element_index
        current=element_index;element_index+=1
        flag,p=uleb(b,p)
        if flag>7:raise NotImplementedError('unsupported element segment mode')
        mode='passive' if flag in (1,5) else 'declarative' if flag in (3,7) else 'active'
        offset=0;table_index=0
        if flag in (2,6):
            table_index,p=uleb(b,p)
        if mode=='active':offset,p=initializer(b,p,'i32',('elem',current))
        expressions=bool(flag&4)
        typ='funcref'
        if flag in (1,2,3,5,6,7):
            if expressions:
                typ,p=value_type(b,p)
                if not is_reference(typ):raise NotImplementedError('only function-reference elements supported')
            else:
                if b[p]!=0:raise NotImplementedError('unsupported element kind')
                p+=1
        count,p=uleb(b,p);entries=[]
        for at in range(count):
            value,p=initializer(b,p,typ,('element',current,at)) if expressions else uleb(b,p)
            entries.append(value)
        return ElementSegment(mode,offset,entries,expressions,table_index,typ),p
    data_index=0
    def segment(b,p):
        nonlocal data_index
        current=data_index;data_index+=1
        flag,p=uleb(b,p)
        if flag==0:offset,p=initializer(b,p,'i32',('data',current))
        elif flag==1:offset=None
        elif flag==2:
            index,p=uleb(b,p)
            if index!=0:raise NotImplementedError('multiple memories unsupported')
            offset,p=initializer(b,p,'i32',('data',current))
        else:raise NotImplementedError('unsupported data segment mode')
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
    functions,function_types=parse_binary(path,with_types=True)
    tables=vector(4,table_type)
    if len(tables)>MAX_TABLES:raise ValueError(f'at most {MAX_TABLES} function tables are supported')
    elements=vector(9,element)
    initialized_tables=[[initial]*minimum for minimum,_,initial,_ in tables]
    for element_ in elements:
        offset,entries=element_.offset,element_.functions
        if any(index is not None and index>=len(functions) for index in entries):raise ValueError('invalid element function index')
        if element_.mode!='active':continue
        if element_.table>=len(tables):raise ValueError('element segment without table')
        table=initialized_tables[element_.table]
        if not 0<=offset<=len(table)-len(entries):raise ValueError('element segment out of table bounds')
        table[offset:offset+len(entries)]=entries
    mapping={}
    for name,kind,index in exports:
        if name in mapping:raise ValueError('duplicate export')
        if kind==0 and index>=len(functions):raise ValueError('invalid function export')
        mapping[name]=(kind,index)
    if any(offset is not None for offset,_ in segments) and not memories:raise ValueError('data segment without memory')
    m=Module(functions,*(memories[0] if memories else (0,0)),
             [v for _,_,v in globals_],[t for t,_,_ in globals_],
             [mut for _,mut,_ in globals_],segments,mapping)
    m.has_memory=bool(memories)
    m.constant_expressions=constant_expressions
    m.function_types=function_types
    for entries,(_,maximum,_,typ) in zip(initialized_tables,tables):m.add_table(entries,maximum,typ)
    m.elements=elements
    if 8 in sections:
        m.start,end=uleb(sections[8],0)
        if end!=len(sections[8]):raise ValueError('trailing start section data')
        if m.start>=len(functions):raise ValueError('invalid start function index')
        fn=functions[m.start]
        if fn.params or fn.results:raise ValueError('start function must have no parameters or results')
    m._initial_state() # validate segment bounds without executing a start function
    return m
