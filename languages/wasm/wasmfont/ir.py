"""Validated, intentionally bounded straight-line integer Wasm frontend and reference VM.
Unsupported instructions fail closed; this is not a complete Wasm validator.
"""
import re
from .opcodes import EXTRA, BULK_MEMORY, BULK_TABLE
from .conversions import CONVERSIONS, convert
from dataclasses import dataclass
from pathlib import Path

OPS={0x6a:'i32.add',0x6b:'i32.sub',0x6c:'i32.mul',0x71:'i32.and',0x72:'i32.or',0x73:'i32.xor',0x74:'i32.shl',0x75:'i32.shr_s',0x76:'i32.shr_u',0x7c:'i64.add',0x7d:'i64.sub',0x7e:'i64.mul',0x83:'i64.and',0x84:'i64.or',0x85:'i64.xor',0x86:'i64.shl',0x87:'i64.shr_s',0x88:'i64.shr_u',0x77:'i32.rotl',0x78:'i32.rotr',0x89:'i64.rotl',0x8a:'i64.rotr',0x45:'i32.eqz',0x50:'i64.eqz',0x67:'i32.clz',0x68:'i32.ctz',0x69:'i32.popcnt',0x79:'i64.clz',0x7a:'i64.ctz',0x7b:'i64.popcnt'}
BINARY={x for x in OPS.values() if not x.endswith(('.eqz','.clz','.ctz','.popcnt'))}
@dataclass
class Function:
    params:list
    results:list
    locals:list
    code:list

@dataclass(frozen=True)
class BlockType:
    params: tuple[str, ...] = ()
    results: tuple[str, ...] = ()


def block_signature(arg):
    """Resolve both compact block types and integer/funcref signatures."""
    if isinstance(arg,BlockType):return arg
    if arg in (None,0x40):return BlockType()
    if arg in (0x7f,0x7e,0x70):return BlockType(results=({0x7f:'i32',0x7e:'i64',0x70:'funcref'}[arg],))
    raise NotImplementedError('unsupported block signature')

def uleb(b,p):
    n=0
    for shift in range(0,70,7):
        if p>=len(b):raise ValueError('truncated LEB')
        x=b[p];p+=1;n|=(x&127)<<shift
        if x<128:return n,p
    raise ValueError('oversized LEB')
def sleb(b,p,bits):
    n=0;shift=0
    while True:
        if p>=len(b):raise ValueError('truncated signed LEB')
        x=b[p];p+=1;n|=(x&127)<<shift;shift+=7
        if x<128:break
        if shift>bits+7:raise ValueError('oversized signed LEB')
    if x&64:n-=1<<shift
    return n,p
def vec(b,p,fn):
    count,p=uleb(b,p);out=[]
    for _ in range(count):
        v,p=fn(b,p);out.append(v)
    return out,p
MEMOPS={0x28:'i32.load',0x29:'i64.load',0x2c:'i32.load8_s',0x2d:'i32.load8_u',0x2e:'i32.load16_s',0x2f:'i32.load16_u',0x30:'i64.load8_s',0x31:'i64.load8_u',0x32:'i64.load16_s',0x33:'i64.load16_u',0x34:'i64.load32_s',0x35:'i64.load32_u',0x36:'i32.store',0x37:'i64.store',0x3a:'i32.store8',0x3b:'i32.store16',0x3c:'i64.store8',0x3d:'i64.store16',0x3e:'i64.store32'}
def section_order(sid):
    # The data-count section precedes code and data despite its larger ID.
    return {12:10,10:11,11:12}.get(sid,sid)

def parse_binary(path):
    b=Path(path).read_bytes()
    if b[:8]!=b'\0asm\x01\0\0\0':raise ValueError('bad Wasm header')
    sections={};p=8;last_section=0
    while p<len(b):
        sid=b[p];p+=1;n,p=uleb(b,p)
        if p+n>len(b):raise ValueError('truncated section')
        if sid>12:raise ValueError('unknown section id')
        if sid and sid in sections:raise ValueError('duplicate section')
        if sid and section_order(sid)<=last_section:raise ValueError('out-of-order section')
        if sid:last_section=section_order(sid)
        sections[sid]=b[p:p+n];p+=n
    def valtype(b,p):
        if p>=len(b) or b[p] not in (0x7f,0x7e,0x70):raise NotImplementedError('only i32/i64/funcref value types')
        return {0x7f:'i32',0x7e:'i64',0x70:'funcref'}[b[p]],p+1
    def functype(b,p):
        if b[p]!=0x60:raise ValueError('invalid function type')
        a,p=vec(b,p+1,valtype);r,p=vec(b,p,valtype);return (a,r),p
    types,_=vec(sections.get(1,b'\0'),0,functype)
    indices,_=vec(sections.get(3,b'\0'),0,uleb)
    code=sections.get(10,b'\0');bodies,_=vec(code,0,lambda b,p:(b[(q:=uleb(b,p)[1]):q+uleb(b,p)[0]],q+uleb(b,p)[0]))
    if len(indices)!=len(bodies):raise ValueError('function/code count mismatch')
    result=[]
    for idx,body in zip(indices,bodies):
        if idx>=len(types):raise ValueError('invalid function type index')
        params,returns=types[idx];p=0;groups,p=uleb(body,p);locals_=[]
        for _ in range(groups):
            n,p=uleb(body,p)
            if p<len(body) and body[p]==0x70:t='funcref';p+=1
            else:t,p=valtype(body,p)
            locals_.extend([t]*n)
            if len(locals_)>10000:raise ValueError('too many locals')
        instructions=[]
        while p<len(body):
            op=body[p];p+=1
            if op==0x0b:
                if p==len(body):break
                instructions.append(('end',None));continue
            if op in (0x20,0x21,0x22):
                n,p=uleb(body,p);instructions.append(({0x20:'local.get',0x21:'local.set',0x22:'local.tee'}[op],n))
            elif op in (0x41,0x42):
                n,p=sleb(body,p,32 if op==0x41 else 64);instructions.append(('i32.const' if op==0x41 else 'i64.const',n))
            elif op in MEMOPS:
                align,p=uleb(body,p)
                # Bit 6 introduces an additional memory-index immediate. Do
                # not reinterpret that index as an offset or subsequent opcode.
                if align>=0x40:raise NotImplementedError('extended memory operands are unsupported')
                offset,p=uleb(body,p)
                if offset>0xffffffff:raise ValueError('memory offset overflow')
                instructions.append((MEMOPS[op],offset))
            elif op in (0x23,0x24):
                idx,p=uleb(body,p);instructions.append(('global.get' if op==0x23 else 'global.set',idx))
            elif op in (0x3f,0x40):
                memory_index,p=uleb(body,p)
                if memory_index!=0:raise NotImplementedError('multiple memories unsupported')
                instructions.append(('memory.size' if op==0x3f else 'memory.grow',None))
            elif op==0xfc:
                subopcode,p=uleb(body,p)
                name=next((name for name,code in {**BULK_MEMORY,**BULK_TABLE}.items() if code==subopcode),None)
                if name is None:raise NotImplementedError(f'unsupported Wasm opcode 0xfc {subopcode}')
                arg=None
                if name in ('memory.init','data.drop','table.init','elem.drop'):arg,p=uleb(body,p)
                for _ in range(2 if name in ('memory.copy','table.copy') else 0 if name in ('data.drop','elem.drop') else 1):
                    memory_index,p=uleb(body,p)
                    if memory_index!=0:raise NotImplementedError('multiple tables unsupported' if name in BULK_TABLE else 'multiple memories unsupported')
                instructions.append((name,arg))
            elif op in OPS:instructions.append((OPS[op],None))
            elif op in CONVERSIONS:instructions.append((CONVERSIONS[op],None))
            elif op in EXTRA:
                name=EXTRA[op];arg=None
                if name in ('block','loop','if'):
                    if p>=len(body):raise ValueError('missing block type')
                    if body[p] in (0x40,0x7f,0x7e,0x70):arg=body[p];p+=1
                    else:
                        type_index,p=sleb(body,p,33)
                        if type_index<0:raise NotImplementedError('only integer block signatures supported')
                        if type_index>=len(types):raise ValueError('block type index out of range')
                        params_,results_=types[type_index]
                        arg=BlockType(tuple(params_),tuple(results_))
                elif name=='select_t':
                    values,p=vec(body,p,valtype)
                    if len(values)!=1:raise ValueError('typed select requires exactly one value type')
                    arg=values[0]
                elif name in ('br','br_if','call','ref.func'):arg,p=uleb(body,p)
                elif name in ('table.get','table.set'):
                    table,p=uleb(body,p)
                    if table!=0:raise NotImplementedError('multiple tables unsupported')
                elif name=='ref.null':
                    heaptype,p=sleb(body,p,33)
                    if heaptype!=-16:raise NotImplementedError('only nullable function references supported')
                elif name=='call_indirect':
                    type_index,p=uleb(body,p);table_index,p=uleb(body,p)
                    if type_index>=len(types):raise ValueError('indirect call type index out of range')
                    if table_index!=0:raise NotImplementedError('multiple tables unsupported')
                    params_,results_=types[type_index]
                    arg=BlockType(tuple(params_),tuple(results_))
                elif name=='br_table':
                    labels,p=vec(body,p,uleb);default,p=uleb(body,p);arg=labels+[default]
                instructions.append((name,arg))
            elif op==0x0f:instructions.append(('return',None))
            else:raise NotImplementedError(f'unsupported Wasm opcode 0x{op:02x}')
        else:raise ValueError('missing function end')
        result.append(Function(params,returns,locals_,instructions))
    return result

def parse_wat(path):
    s=Path(path).read_text();s=re.sub(r';;[^\n]*','',s)
    if not re.search(r'\(module\b',s):raise ValueError('missing module')
    # Flat WAT instructions, including named locals; folded expression syntax is not supported.
    matches=list(re.finditer(r'\(func\b',s));out=[]
    for m in matches:
        start=m.start();depth=0;end=None
        for i in range(start,len(s)):
            depth+=(s[i]=='(')-(s[i]==')')
            if depth==0:end=i+1;break
        if end is None:raise ValueError('unclosed function')
        body=s[m.end():end-1];names={};params=[];returns=[];locals_=[]
        def decl(match):
            kind=match.group(1);tokens=match.group(2).split();typ=None
            for token in tokens:
                if token in ('i32','i64'):typ=token
                elif token.startswith('$') and kind!='result':
                    names[token]=len(params)+len(locals_)
                else:raise NotImplementedError('unsupported declaration')
            if typ is None:raise ValueError('missing value type')
            if kind=='param':params.append(typ)
            elif kind=='local':locals_.append(typ)
            else:returns.append(typ)
            return ' '
        body=re.sub(r'\((param|result|local)\s+([^()]*)\)',decl,body)
        body=re.sub(r'\(export\s+"[^"]+"\)', ' ',body)
        body=re.sub(r'^\s*\$[\w.]+',' ',body)
        tokens=body.split();code=[];i=0
        while i<len(tokens):
            op=tokens[i];i+=1
            if op in ('local.get','local.set','local.tee','global.get','global.set','i32.const','i64.const'):
                if i==len(tokens):raise ValueError('missing operand')
                arg=tokens[i];i+=1
                arg=names[arg] if arg in names else int(arg,0)
                code.append((op,arg))
            elif op in MEMOPS.values():
                code.append((op,0))
            elif op in ('memory.size','memory.grow'):
                code.append((op,None))
            elif op in BINARY or op in ('i32.eqz','i64.eqz','i32.clz','i32.ctz','i32.popcnt','i64.clz','i64.ctz','i64.popcnt','return') or op in EXTRA.values() or op in CONVERSIONS.values() or op in ('end',):
                if op in ('br','br_if','call'):
                    arg=int(tokens[i],0);i+=1;code.append((op,arg))
                elif op in ('block','loop','if'):
                    code.append((op,None))
                elif op=='br_table':raise NotImplementedError('WAT br_table syntax not yet supported')
                else:code.append((op,None))
            else:raise NotImplementedError(f'unsupported WAT token {op}')
        out.append(Function(params,returns,locals_,code))
    return out

def execute(fn,args):
    if len(args)!=len(fn.params):raise ValueError('wrong argument count')
    values=[v&((1<<(32 if t=='i32' else 64))-1) for t,v in zip(fn.params,args)]+[0]*len(fn.locals)
    stack=[]
    for op,arg in fn.code:
        if op=='local.get':stack.append(values[arg])
        elif op=='local.set':values[arg]=stack.pop()
        elif op=='local.tee':values[arg]=stack[-1]
        elif op.endswith('.const'):stack.append(arg&((1<<int(op[1:3]))-1))
        elif op.endswith('.eqz'):stack.append(int(stack.pop()==0))
        elif op in CONVERSIONS.values():stack.append(convert(op,stack.pop()))
        elif op.endswith(('.clz','.ctz','.popcnt')):
            v=stack.pop();width=int(op[1:3]);v&=(1<<width)-1
            if op.endswith('.popcnt'): stack.append(v.bit_count())
            elif op.endswith('.clz'): stack.append(width-v.bit_length())
            else: stack.append(width if v==0 else (v&-v).bit_length()-1)
        elif op=='return':
            count=len(fn.results)
            if len(stack)<count:raise ValueError('return result stack underflow')
            stack=stack[-count:] if count else []
            break
        elif op in BINARY:
            b=stack.pop();a=stack.pop();width=int(op[1:3]);mask=(1<<width)-1;operation=op.split('.')[1]
            if operation=='add':v=a+b
            elif operation=='sub':v=a-b
            elif operation=='mul':v=a*b
            elif operation=='and':v=a&b
            elif operation=='or':v=a|b
            elif operation=='xor':v=a^b
            elif operation=='shl':v=a<<(b&(width-1))
            elif operation=='shr_u':v=a>>(b&(width-1))
            elif operation=='rotl':
                k=b&(width-1);v=(a<<k)|(a>>(width-k))
            elif operation=='rotr':
                k=b&(width-1);v=(a>>k)|(a<<(width-k))
            elif operation=='shr_s':v=((a^ (1<<(width-1)))-(1<<(width-1)))>>(b&(width-1))
            stack.append(v&mask)
        else:raise NotImplementedError(op)
    if len(stack)!=len(fn.results):raise ValueError('result stack mismatch')
    return stack
