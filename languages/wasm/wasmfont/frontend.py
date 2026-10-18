"""Self-contained integer WAT reader, binary writer and V8-validated module loader.

The native compiler uses this frontend; old prototype parsers remain available
for backwards compatibility. No package download is required. Unsupported Wasm
proposals, imports, start functions and tables are rejected explicitly.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import tempfile
from pathlib import Path
from .ir import Function, BlockType, block_signature, OPS, MEMOPS
from .opcodes import EXTRA, BULK_MEMORY
from .conversions import CONVERSIONS
from .module import Module, load_binary
from .validation import validate

TYPES = {'i32':0x7f, 'i64':0x7e}
OPCODES = {name:opcode for opcode,name in {**OPS,**EXTRA,**CONVERSIONS,**MEMOPS}.items()}
OPCODES.update({'local.get':0x20,'local.set':0x21,'local.tee':0x22,
                'global.get':0x23,'global.set':0x24,'i32.const':0x41,
                'i64.const':0x42,'memory.size':0x3f,'memory.grow':0x40,
                'return':0x0f,'else':0x05,'end':0x0b})
OPCODES.update({name:0xfc for name in BULK_MEMORY})


@dataclass(frozen=True)
class TextString:
    """Quoted bytes, distinct from unquoted keywords, identifiers and numbers."""
    data: bytes


def tokenize(text: str) -> list:
    out=[]; i=0
    while i<len(text):
        if text[i].isspace(): i+=1; continue
        if text.startswith(';;',i):
            while i<len(text) and text[i] not in '\r\n':i+=1
            continue
        if text.startswith('(;',i):
            i+=2; depth=1
            while depth:
                if i>=len(text): raise ValueError('unclosed WAT block comment')
                if text.startswith('(;',i): depth+=1; i+=2
                elif text.startswith(';)',i): depth-=1; i+=2
                else: i+=1
            continue
        if text[i] in '()': out.append(text[i]); i+=1; continue
        if text[i]=='"':
            i+=1; raw=bytearray()
            while i<len(text) and text[i]!='"':
                if text[i]!='\\': raw.extend(text[i].encode('utf-8')); i+=1; continue
                i+=1
                if i>=len(text): raise ValueError('truncated WAT string escape')
                if re.fullmatch('[0-9a-fA-F]{2}',text[i:i+2]):
                    raw.append(int(text[i:i+2],16)); i+=2
                elif text.startswith('u{',i):
                    end=text.find('}',i+2)
                    if end<0: raise ValueError('invalid Unicode escape')
                    raw.extend(chr(int(text[i+2:end].replace('_',''),16)).encode('utf-8')); i=end+1
                elif text[i] in 'nt\\\'"r':
                    raw.extend({'n':b'\n','t':b'\t','r':b'\r','\\':b'\\',"'":b"'",'"':b'"'}[text[i]]); i+=1
                else: raise ValueError('unsupported WAT string escape')
            if i>=len(text): raise ValueError('unclosed WAT string')
            # Names are decoded as UTF-8 later; data segments retain raw bytes.
            out.append(TextString(bytes(raw))); i+=1; continue
        j=i
        while i<len(text) and not text[i].isspace() and text[i] not in '()' and not text.startswith(';;',i): i+=1
        out.append(text[j:i])
    return out


def sexpr(text: str) -> list:
    tokens=tokenize(text); stack=[[]]
    for t in tokens:
        if type(t) is str and t=='(': stack.append([])
        elif type(t) is str and t==')':
            if len(stack)==1: raise ValueError('unmatched closing parenthesis')
            item=stack.pop(); stack[-1].append(item)
        else: stack[-1].append(t)
    if len(stack)!=1 or len(stack[0])!=1 or not isinstance(stack[0][0],list):
        raise ValueError('expected one balanced WAT module')
    return stack[0][0]


def integer(token):
    if type(token) is not str:raise ValueError('integer requires an unquoted token')
    s=token.replace('_','')
    return int(s,16 if s.lstrip('+-').startswith('0x') else 10)


def integer_literal(token,width):
    value=integer(token)
    if not -(1<<(width-1))<=value<(1<<width):
        raise ValueError('integer literal out of range')
    return value


def name_string(value):
    if not isinstance(value,TextString): raise ValueError('expected quoted name')
    return value.data.decode('utf-8')


def index(token, names):
    if type(token) is not str:raise ValueError('index requires an unquoted identifier or integer')
    if str(token).startswith('$'):
        if token not in names: raise ValueError(f'unknown identifier {token}')
        return names[token]
    value=integer(token)
    if not 0<=value<=0xffffffff:raise ValueError('index must be an unsigned 32-bit integer')
    return value


def declaration(items, kind, destination, names):
    args=items[1:]
    if args and str(args[0]).startswith('$'):
        if len(args)!=2: raise ValueError('named declaration requires one type')
        if args[0] in names: raise ValueError('duplicate local identifier')
        names[args[0]]=len(destination)
        args=args[1:]
    if not args or any(x not in TYPES for x in args):
        raise NotImplementedError(f'only i32/i64 {kind} declarations are supported')
    destination.extend(args)


def parse_text(text: str) -> Module:
    root=sexpr(text)
    if not root or root[0]!='module': raise ValueError('expected module')
    fields=root[1:]
    if fields and isinstance(fields[0],str) and fields[0].startswith('$'): fields=fields[1:]
    if any(not isinstance(x,list) or not x for x in fields): raise ValueError('invalid module field')
    allowed={'func','type','memory','global','data','export','table','elem'}
    for x in fields:
        if x[0] not in allowed: raise NotImplementedError(f'unsupported module field: {x[0]}')
    function_fields=[x for x in fields if x[0]=='func']
    global_fields=[x for x in fields if x[0]=='global']
    def identifiers(entries):
        d={}
        for i,f in enumerate(entries):
            if len(f)>1 and isinstance(f[1],str) and f[1].startswith('$'):
                if f[1] in d: raise ValueError('duplicate identifier')
                d[f[1]]=i
        return d
    fnames=identifiers(function_fields); gnames=identifiers(global_fields)
    dnames=identifiers([x for x in fields if x[0]=='data'])
    table_fields=[x for x in fields if x[0]=='table'];table_names=identifiers(table_fields)
    identifiers([x for x in fields if x[0]=='elem'])
    if len(table_fields)>1:raise NotImplementedError('multiple tables unsupported')
    signatures=[]; tnames={}
    for x in fields:
        if x[0]!='type': continue
        parts=x[1:]
        if parts and isinstance(parts[0],str):
            if parts[0] in tnames: raise ValueError('duplicate type identifier')
            tnames[parts.pop(0)]=len(signatures)
        if len(parts)!=1 or not isinstance(parts[0],list) or parts[0][0]!='func':
            raise NotImplementedError('only function types supported')
        params=[]; results=[]
        for group in parts[0][1:]:
            if group[0]=='param': declaration(group,'param',params,{})
            elif group[0]=='result': declaration(group,'result',results,{})
            else: raise NotImplementedError('unsupported type declaration')
        signatures.append((params,results))
    module=Module([])
    module.initial_pages=0; module.maximum_pages=0
    if table_fields:
        vals=table_fields[0][1:]
        if vals and isinstance(vals[0],str) and vals[0].startswith('$'):vals=vals[1:]
        while vals and isinstance(vals[0],list) and vals[0] and vals[0][0]=='export':vals=vals[1:]
        if not vals or vals[-1]!='funcref':raise NotImplementedError('only funcref tables supported')
        limits=[integer(v) for v in vals[:-1]]
        if not 1<=len(limits)<=2:raise ValueError('table requires minimum and optional maximum')
        minimum=limits[0];maximum=limits[1] if len(limits)==2 else None
        if not 0<=minimum<=256 or maximum is not None and not minimum<=maximum<=256:
            raise ValueError('table limits must be within 0..256')
        module.table=[None]*minimum;module.table_maximum=maximum
    def export(n,kind,idx):
        n=name_string(n)
        if n in module.exports: raise ValueError('duplicate export')
        module.exports[n]=(kind,idx)
    def inline_export(items,kind,idx):
        if len(items)!=2:raise ValueError('inline export requires exactly one name')
        export(items[1],kind,idx)
    declaration_order={'export':0,'type':1,'param':2,'result':3,'local':4}
    for field in function_fields:
        items=field[1:]
        if items and isinstance(items[0],str) and items[0].startswith('$'): items=items[1:]
        params=[]; results=[]; local_types=[]; names={}; body=[]; typeuse=None
        phase=0
        for item in items:
            if phase<5 and isinstance(item,list) and item and item[0] in declaration_order:
                kind=item[0]
                if declaration_order[kind]<phase:raise ValueError('out-of-order function declaration: '+kind)
                phase=declaration_order[kind]
                if kind=='export':continue # Collected below in module-field order.
                if kind=='param': declaration(item,kind,params,names)
                elif kind=='result': declaration(item,kind,results,{})
                elif kind=='local':
                    alltypes=params+local_types
                    declaration(item,kind,alltypes,names); local_types=alltypes[len(params):]
                else:
                    if len(item)!=2:raise ValueError('type use requires exactly one index')
                    if typeuse is not None:raise ValueError('duplicate type use')
                    type_index=index(item[1],tnames)
                    if type_index>=len(signatures):raise ValueError('type index out of range')
                    typeuse=signatures[type_index]
            else: phase=5; body.append(item)
        if typeuse:
            if params or results:
                if (params,results)!=typeuse: raise ValueError('inline signature does not match type use')
            else:
                params,results=[list(x) for x in typeuse]
                names={name:idx+len(params) for name,idx in names.items()}
        parser=InstructionText(names,fnames,gnames,signatures,tnames,dnames,table_names)
        code=parser.sequence(body)
        module.functions.append(Function(params,results,local_types,code))
    memories=[x for x in fields if x[0]=='memory']
    if len(memories)>1: raise NotImplementedError('multiple memories unsupported')
    mnames=identifiers(memories)
    module.has_memory=bool(memories)
    if memories:
        vals=memories[0][1:]
        if vals and isinstance(vals[0],str) and vals[0].startswith('$'): vals=vals[1:]
        limits=[]
        for v in vals:
            if isinstance(v,list) and v and v[0]=='export': continue
            elif isinstance(v,str): limits.append(integer(v))
            else: raise NotImplementedError('unsupported memory declaration')
        if not 1<=len(limits)<=2: raise ValueError('memory requires minimum and optional maximum')
        minimum=limits[0]; maximum=limits[1] if len(limits)==2 else max(16,minimum)
        if not 0<=minimum<=maximum<=256: raise ValueError('memory declaration exceeds supported limits')
        module.initial_pages, module.maximum_pages=minimum,maximum
    for g in global_fields:
        vals=g[1:]
        if vals and isinstance(vals[0],str) and vals[0].startswith('$'): vals=vals[1:]
        while vals and isinstance(vals[0],list) and vals[0] and vals[0][0]=='export':
            vals=vals[1:]
        if len(vals)!=2: raise ValueError('invalid global declaration')
        typ,init=vals
        mutable=isinstance(typ,list)
        if mutable:
            if len(typ)!=2 or typ[0]!='mut': raise ValueError('invalid global mutability')
            typ=typ[1]
        if typ not in TYPES or not isinstance(init,list) or init[0]!=typ+'.const' or len(init)!=2:
            raise NotImplementedError('only integer constant global initializers supported')
        module.global_types.append(typ); module.mutable.append(mutable)
        module.globals.append(integer_literal(init[1],int(typ[1:])))
    # Collect exports in module-field order, preserving default entry selection.
    export_kinds={'func':0,'table':1,'memory':2,'global':3}
    export_indices={kind:0 for kind in export_kinds}
    for x in fields:
        if x[0] in export_kinds:
            kind=x[0];idx=export_indices[kind];export_indices[kind]+=1
            for item in x[1:]:
                if isinstance(item,list) and item and item[0]=='export':
                    inline_export(item,export_kinds[kind],idx)
        elif x[0]=='export':
            if len(x)!=3 or not isinstance(x[2],list) or len(x[2])!=2:
                raise ValueError('export requires a name and a two-item descriptor')
            kind,target=x[2]
            if kind=='func': export(x[1],0,index(target,fnames))
            elif kind=='global': export(x[1],3,index(target,gnames))
            elif kind=='memory': export(x[1],2,index(target,mnames))
            elif kind=='table': export(x[1],1,index(target,table_names))
            else: raise NotImplementedError('unsupported export kind')
        elif x[0]=='elem':
            vals=x[1:]
            if vals and isinstance(vals[0],str) and vals[0].startswith('$'):vals=vals[1:]
            if vals and isinstance(vals[0],list) and vals[0] and vals[0][0]=='table':
                if len(vals[0])!=2:raise ValueError('element table use requires one index')
                if index(vals[0][1],table_names)!=0:raise NotImplementedError('multiple tables unsupported')
                vals=vals[1:]
            if not vals or not isinstance(vals[0],list) or not vals[0] or vals[0][0]!='i32.const':
                raise NotImplementedError('only active constant-offset function-index element segments supported')
            if len(vals[0])!=2:raise ValueError('element offset requires exactly one integer immediate')
            offset=integer_literal(vals[0][1],32);entries=vals[1:]
            if entries and entries[0]=='func':entries=entries[1:]
            targets=[index(v,fnames) for v in entries]
            if module.table is None:raise ValueError('element segment without table')
            if not 0<=offset<=len(module.table)-len(targets):raise ValueError('element segment out of table bounds')
            if any(target>=len(module.functions) for target in targets):raise ValueError('invalid element function index')
            module.table[offset:offset+len(targets)]=targets
        elif x[0]=='data':
            vals=x[1:]
            if vals and isinstance(vals[0],str) and vals[0].startswith('$'): vals=vals[1:]
            offset=None
            if vals and isinstance(vals[0],list):
                if not vals[0] or vals[0][0]!='i32.const':
                    raise NotImplementedError('only memory-zero constant-offset active data segments supported')
                if len(vals[0])!=2 or not isinstance(vals[0][1],str):
                    raise ValueError('data offset requires exactly one integer immediate')
                if not module.has_memory:raise ValueError('data segment without memory')
                offset=integer_literal(vals[0][1],32);vals=vals[1:]
            if any(not isinstance(v,TextString) for v in vals): raise ValueError('invalid data payload')
            module.segments.append((offset,b''.join(v.data for v in vals)))
    return module


class InstructionText:
    def __init__(self,locals_,functions,globals_,signatures=(),type_names=None,data_names=None,table_names=None):
        self.locals=locals_;self.functions=functions;self.globals=globals_; self.labels=[]
        self.signatures=signatures;self.type_names=type_names or {}
        self.data_names=data_names or {}
        self.table_names=table_names or {}

    def label(self,token):
        if str(token).startswith('$'):
            for depth,label in enumerate(reversed(self.labels)):
                if label==token:return depth
            raise ValueError(f'unknown label {token}')
        return integer(token)

    def header(self,items,pos):
        label=None
        if pos<len(items) and isinstance(items[pos],str) and items[pos].startswith('$'):
            label=items[pos];pos+=1
        params=[];results=[];typeuse=None;inline=False;phase=0
        order={'type':0,'param':1,'result':2}
        while pos<len(items) and isinstance(items[pos],list) and items[pos] and items[pos][0] in order:
            group=items[pos];pos+=1;kind=group[0]
            if order[kind]<phase:raise ValueError('out-of-order block signature')
            phase=order[kind]
            if kind=='type':
                if len(group)!=2 or typeuse is not None:raise ValueError('block type use requires one index and may not repeat')
                idx=index(group[1],self.type_names)
                if idx>=len(self.signatures):raise ValueError('block type index out of range')
                typeuse=self.signatures[idx]
            else:
                inline=True
                if any(isinstance(x,str) and x.startswith('$') for x in group[1:]):
                    raise NotImplementedError('named block parameters are unsupported')
                if len(group)>1:declaration(group,kind,params if kind=='param' else results,{})
        if typeuse is not None:
            if inline and (params,results)!=typeuse:raise ValueError('inline block signature does not match type use')
            params,results=typeuse
        if typeuse is None and not params and len(results)<=1:
            typ=TYPES[results[0]] if results else 0x40
        else:typ=BlockType(tuple(params),tuple(results))
        return label,typ,pos

    def sequence(self,items):
        code,pos,stop=self._sequence(items,0,False)
        if pos!=len(items) or stop:raise ValueError('unmatched structured instruction')
        return code

    def _sequence(self,items,pos,nested):
        out=[]
        while pos<len(items):
            item=items[pos];pos+=1
            if isinstance(item,list): out.extend(self.folded(item));continue
            op=item
            if op in ('end','else'):
                if not nested: raise ValueError('unmatched '+op)
                return out,pos,op
            if op in ('block','loop','if'):
                label,typ,pos=self.header(items,pos); self.labels.append(label)
                body,pos,stop=self._sequence(items,pos,True)
                out.append((op,typ)); out.extend(body)
                if stop=='else':
                    if op!='if':raise ValueError('else outside if')
                    body,pos,stop=self._sequence(items,pos,True);out.append(('else',None));out.extend(body)
                if stop!='end':raise ValueError('missing end')
                if pos<len(items) and isinstance(items[pos],str) and items[pos].startswith('$'):
                    if items[pos]!=label:raise ValueError('end label mismatch')
                    pos+=1
                self.labels.pop();out.append(('end',None));continue
            instruction,pos=self.immediate(op,items,pos)
            out.append(instruction)
        return out,pos,None

    def immediate(self,op,items,pos):
        if op not in OPCODES:raise NotImplementedError(f'unsupported instruction {op}')
        arg=None
        if op in ('local.get','local.set','local.tee','global.get','global.set','call','br','br_if','i32.const','i64.const','memory.init','data.drop'):
            if pos>=len(items) or isinstance(items[pos],list):raise ValueError('missing immediate for '+op)
            token=items[pos];pos+=1
            if op.startswith('local.'):arg=index(token,self.locals)
            elif op.startswith('global.'):arg=index(token,self.globals)
            elif op=='call':arg=index(token,self.functions)
            elif op in ('br','br_if'):arg=self.label(token)
            elif op in ('memory.init','data.drop'):arg=index(token,self.data_names)
            else:
                arg=integer_literal(token,int(op[1:3]))
        elif op=='call_indirect':
            if pos<len(items) and isinstance(items[pos],TextString):raise ValueError('table index must be unquoted')
            if pos<len(items) and isinstance(items[pos],str) and (items[pos].startswith('$') or items[pos][:1] in '+-0123456789'):
                if index(items[pos],self.table_names)!=0:raise NotImplementedError('multiple tables unsupported')
                pos+=1
            label,typ,pos=self.header(items,pos)
            if label is not None:raise ValueError('unexpected indirect-call label')
            arg=block_signature(typ)
        elif op=='br_table':
            arg=[]
            while pos<len(items) and isinstance(items[pos],str) and (items[pos].startswith('$') or re.fullmatch(r'[+\-]?[0-9_]+',items[pos])):
                arg.append(self.label(items[pos]));pos+=1
            if not arg:raise ValueError('br_table requires a default target')
        elif op in MEMOPS.values():
            arg=0; align=None
            while pos<len(items) and isinstance(items[pos],str) and items[pos].startswith(('offset=','align=')):
                key,val=items[pos].split('=',1);val=integer(val);pos+=1
                if key=='offset':arg=val
                else:align=val
            natural=memory_bytes(op)
            if arg<0 or arg>0xffffffff or align is not None and (align<1 or align&(align-1) or align>natural):
                raise ValueError('invalid memory immediate')
        return (op,arg),pos

    def folded(self,items):
        if not items:raise ValueError('empty instruction expression')
        op=items[0]
        if op in ('block','loop','if'):
            label,typ,pos=self.header(items,1);body=items[pos:]
            if op=='if':
                then=next((i for i,x in enumerate(body) if isinstance(x,list) and x and x[0]=='then'),None)
                if then is None:raise ValueError('folded if requires then')
                condition=self.sequence(body[:then]);branches=body[then:]
                if len(branches)>2 or any(not isinstance(x,list) for x in branches):raise ValueError('invalid folded if')
                self.labels.append(label)
                out=condition+[('if',typ)]+self.sequence(branches[0][1:])
                if len(branches)==2:
                    if branches[1][0]!='else':raise ValueError('invalid folded else')
                    out += [('else',None)]+self.sequence(branches[1][1:])
                self.labels.pop();return out+[('end',None)]
            self.labels.append(label)
            out=[(op,typ)]+self.sequence(body);self.labels.pop()
            return out+[('end',None)]
        instruction,pos=self.immediate(op,items,1)
        operands=[]
        for expression in items[pos:]:
            if not isinstance(expression,list):raise ValueError('folded operands must be expressions')
            operands.extend(self.folded(expression))
        return operands+[instruction]


def memory_bytes(op):
    suffix=op.split('.',1)[1]
    found=re.search(r'(?:load|store)(8|16|32)',suffix)
    return int(found.group(1))//8 if found else int(op[1:3])//8


def unsigned_leb(n):
    if n<0:raise ValueError('negative unsigned LEB')
    out=bytearray()
    while True:
        b=n&127;n>>=7;out.append(b|(128 if n else 0))
        if not n:return bytes(out)


def signed_leb(n,width):
    n&=(1<<width)-1
    if n>>(width-1):n-=1<<width
    out=bytearray()
    while True:
        b=n&127;n>>=7
        done=(n==0 and not b&64) or (n==-1 and b&64)
        out.append(b if done else b|128)
        if done:return bytes(out)


def vector(items):
    return unsigned_leb(len(items))+b''.join(items)


def binary(module: Module) -> bytes:
    def sec(i,payload):return bytes([i])+unsigned_leb(len(payload))+payload
    def expr(typ,val):return bytes([OPCODES[typ+'.const']])+signed_leb(val,int(typ[1:]))+b'\x0b'
    types=[];indices=[]
    for f in module.functions:
        signature=(tuple(f.params),tuple(f.results))
        if signature not in types:types.append(signature)
        indices.append(types.index(signature))
    for f in module.functions:
        for op,arg in f.code:
            if op in ('block','loop','if','call_indirect') and isinstance(arg,BlockType):
                signature=(arg.params,arg.results)
                if signature not in types:types.append(signature)
    out=b'\0asm\x01\0\0\0'
    if types:out+=sec(1,vector([b'\x60'+vector([bytes([TYPES[t]]) for t in p])+vector([bytes([TYPES[t]]) for t in r]) for p,r in types]))
    if indices:out+=sec(3,vector([unsigned_leb(i) for i in indices]))
    if module.table is not None:
        maximum=module.table_maximum
        out+=sec(4,vector([b'\x70'+bytes([int(maximum is not None)])+unsigned_leb(len(module.table))+
                          (unsigned_leb(maximum) if maximum is not None else b'')]))
    has_memory=getattr(module,'has_memory',False) or module.maximum_pages or module.initial_pages
    if any(offset is not None for offset,_ in module.segments) and not has_memory:raise ValueError('data segment without memory')
    if has_memory:
        out+=sec(5,vector([b'\x01'+unsigned_leb(module.initial_pages)+unsigned_leb(module.maximum_pages)]))
    if module.globals:
        out+=sec(6,vector([bytes([TYPES[t],int(m)])+expr(t,v) for t,m,v in zip(module.global_types,module.mutable,module.globals)]))
    if module.exports:
        out+=sec(7,vector([unsigned_leb(len(n.encode('utf-8')))+n.encode('utf-8')+bytes([kind])+unsigned_leb(i) for n,(kind,i) in module.exports.items()]))
    if module.table is not None:
        elements=[];start=0;entries=[]
        for slot,target in enumerate(module.table+[None]):
            if target is None:
                if entries:elements.append(b'\x00'+expr('i32',start)+vector([unsigned_leb(v) for v in entries]));entries=[]
            else:
                if not entries:start=slot
                entries.append(target)
        if elements:out+=sec(9,vector(elements))
    if any(op in ('memory.init','data.drop') for f in module.functions for op,_ in f.code):
        out+=sec(12,unsigned_leb(len(module.segments)))
    bodies=[]
    for f in module.functions:
        code=bytearray(vector([b'\x01'+bytes([TYPES[t]]) for t in f.locals]))
        for op,arg in f.code:
            code.append(OPCODES[op])
            if op in ('block','loop','if'):
                if isinstance(arg,BlockType):code+=signed_leb(types.index((arg.params,arg.results)),33)
                else:code.append(0x40 if arg is None else arg)
            elif op in ('local.get','local.set','local.tee','global.get','global.set','call','br','br_if'):code+=unsigned_leb(arg)
            elif op=='call_indirect':code+=unsigned_leb(types.index((arg.params,arg.results)))+b'\x00'
            elif op.endswith('.const'):code+=signed_leb(arg,int(op[1:3]))
            elif op=='br_table':code+=vector([unsigned_leb(x) for x in arg[:-1]])+unsigned_leb(arg[-1])
            elif op in MEMOPS.values():code+=unsigned_leb(memory_bytes(op).bit_length()-1)+unsigned_leb(arg)
            elif op in ('memory.size','memory.grow'):code+=b'\x00'
            elif op in BULK_MEMORY:
                code+=unsigned_leb(BULK_MEMORY[op])
                if op in ('memory.init','data.drop'):code+=unsigned_leb(arg)
                code+=b'\x00'*(2 if op=='memory.copy' else 0 if op=='data.drop' else 1)
        code.append(0x0b);bodies.append(unsigned_leb(len(code))+code)
    if bodies:out+=sec(10,vector(bodies))
    if module.segments:out+=sec(11,vector([(b'\x01' if off is None else b'\0'+expr('i32',off))+unsigned_leb(len(payload))+payload for off,payload in module.segments]))
    return out


def load(path: str | Path) -> tuple[Module,bytes]:
    path=Path(path)
    if path.suffix.lower()=='.wat':
        module=parse_text(path.read_text());data=binary(module)
    else:data=path.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'module.wasm';p.write_bytes(data);module=load_binary(p)
    return module,data
