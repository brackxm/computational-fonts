"""Bounded structured Wasm interpreter for the existing Function IR.

Execution is reference-side only; native GSUB compilation uses wasmfont/compiler.py.
"""
from ..ir import Function, block_signature
from ..conversions import CONVERSIONS, convert
from ..state import MachineState, MemoryTrap

class WasmTrap(Exception): pass

COMPARE={'eq','ne','lt_s','lt_u','gt_s','gt_u','le_s','le_u','ge_s','ge_u'}

def run(functions, index, args, fuel=100000, state=None, start=None):
    state = state if state is not None else MachineState()
    budget=[fuel]
    def invoke(idx, argv, depth):
        if depth>128: raise WasmTrap('call depth exceeded')
        fn=functions[idx]
        if len(argv)!=len(fn.params): raise WasmTrap('argument count mismatch')
        values=[v if t=='funcref' else v&((1<<int(t[1:]))-1) for t,v in zip(fn.params,argv)]+[None if t=='funcref' else 0 for t in fn.locals]
        stack=[]; code=fn.code; matching={}; alternatives={}; frames=[]
        for pos,(op,arg) in enumerate(code):
            if op in ('block','loop','if'): frames.append(pos)
            elif op=='else':
                if not frames or code[frames[-1]][0]!='if' or frames[-1] in alternatives:
                    raise WasmTrap('unexpected else')
                alternatives[frames[-1]]=pos
            elif op=='end':
                if not frames:raise WasmTrap('unexpected end')
                start=frames.pop();matching[start]=pos
                if start in alternatives:matching[alternatives[start]]=pos
        if frames:raise WasmTrap('unterminated block')
        # The implicit function label carries the declared return values.
        pc=0; active=[(None,0,len(fn.results),len(fn.results))]
        def finish(frame):
            if len(stack)!=frame[1]+frame[3]:raise WasmTrap('block stack mismatch')
        def branch(level):
            nonlocal pc,active
            if not 0<=level<len(active):raise WasmTrap('invalid branch depth')
            start,height,arity,_=active[-1-level]
            if len(stack)<height+arity:raise WasmTrap('branch result stack underflow')
            results=stack[-arity:] if arity else []
            stack[height:]=results
            if start is None:
                active=[];pc=len(code)
            elif code[start][0]=='loop':
                active=active[:len(active)-level];pc=start+1
            else:
                active=active[:len(active)-level-1];pc=matching[start]+1
        while pc<len(code):
            budget[0]-=1
            if budget[0]<0:raise WasmTrap('instruction fuel exhausted')
            op,arg=code[pc];pc+=1
            if op in ('block','loop','if'):
                signature=block_signature(arg)
                cond=stack.pop() if op=='if' else True
                height=len(stack)-len(signature.params)
                if height<0:raise WasmTrap('block parameter stack underflow')
                arity=len(signature.params if op=='loop' else signature.results)
                frame=(pc-1,height,arity,len(signature.results))
                if op=='if' and not cond:
                    start=pc-1
                    if start in alternatives:
                        active.append(frame);pc=alternatives[start]+1
                    else:finish(frame);pc=matching[start]+1
                else:active.append(frame)
            elif op=='else':
                finish(active.pop());pc=matching[pc-1]+1
            elif op=='end':
                finish(active.pop())
            elif op=='br':branch(arg)
            elif op=='br_if':
                if stack.pop():branch(arg)
            elif op=='br_table':
                choice=stack.pop();branch(arg[choice] if choice<len(arg)-1 else arg[-1])
            elif op=='return':branch(len(active)-1)
            elif op in ('call','call_indirect'):
                target=arg
                if op=='call_indirect':
                    slot=stack.pop()
                    if not 0<=slot<len(state.table):raise WasmTrap('table_out_of_bounds')
                    target=state.table[slot]
                    if target is None:raise WasmTrap('uninitialized_element')
                    callee=functions[target]
                    if (tuple(callee.params),tuple(callee.results))!=(arg.params,arg.results):
                        raise WasmTrap('indirect_call_type_mismatch')
                callee=functions[target];n=len(callee.params)
                argv=stack[-n:] if n else []
                if n:del stack[-n:]
                stack.extend(invoke(target,argv,depth+1))
            elif op=='global.get':stack.append(state.globals[arg])
            elif op=='global.set':
                if not state.mutable[arg]:raise WasmTrap('immutable global')
                value=stack.pop();typ=state.global_types[arg]
                state.globals[arg]=value if typ=='funcref' else value&((1<<int(typ[1:]))-1)
            elif op=='memory.size':stack.append(state.pages)
            elif op=='memory.grow':stack.append(state.grow(stack.pop())&0xffffffff)
            elif op=='ref.null':stack.append(None)
            elif op=='ref.func':stack.append(arg)
            elif op=='ref.is_null':stack.append(int(stack.pop() is None))
            elif op=='elem.drop':state.element_segments[arg]=[]
            elif op=='table.size':stack.append(len(state.table))
            elif op=='table.grow':
                delta=stack.pop();initial=stack.pop();old=len(state.table)
                if old+delta>state.table_maximum:stack.append(0xffffffff)
                else:state.table.extend([initial]*delta);stack.append(old)
            elif op in ('table.get','table.set'):
                value=stack.pop() if op=='table.set' else None
                slot=stack.pop()
                if not 0<=slot<len(state.table):raise WasmTrap('table_out_of_bounds')
                if op=='table.get':stack.append(state.table[slot])
                else:state.table[slot]=value
            elif op in ('table.init','table.copy','table.fill'):
                size=stack.pop();source=stack.pop();destination=stack.pop()
                if destination+size>len(state.table):raise WasmTrap('table_out_of_bounds')
                if op=='table.fill':payload=[source]*size
                else:
                    entries=state.table if op=='table.copy' else state.element_segments[arg]
                    if source+size>len(entries):raise WasmTrap('table_out_of_bounds')
                    payload=entries[source:source+size]
                state.table[destination:destination+size]=payload
            elif op=='data.drop':state.data_segments[arg]=b''
            elif op=='memory.init':
                size=stack.pop();source=stack.pop();destination=stack.pop()
                state.bounds(destination,size)
                payload=state.data_segments[arg]
                if source+size>len(payload):raise MemoryTrap('out of bounds data segment access')
                state.memory[destination:destination+size]=payload[source:source+size]
            elif op in ('memory.copy','memory.fill'):
                size=stack.pop();source=stack.pop();destination=stack.pop()
                state.bounds(destination,size)
                if op=='memory.copy':
                    state.bounds(source,size)
                    # A snapshot gives memmove semantics for either overlap direction.
                    payload=state.memory[source:source+size]
                else:payload=bytes([source&255])*size
                state.memory[destination:destination+size]=payload
            elif op.startswith(('i32.load','i64.load')):
                width=int(op[1:3]);suffix=op.split('.',1)[1]
                size=width//8 if suffix=='load' else None
                if size is None:
                    import re
                    m=re.fullmatch(r'load(8|16|32)_(s|u)',suffix)
                    if not m:raise NotImplementedError(op)
                    size=int(m.group(1))//8
                offset=arg or 0
                address=stack.pop()+offset
                signed=suffix.endswith('_s')
                stack.append(state.load(address,size,signed)&((1<<width)-1))
            elif op.startswith(('i32.store','i64.store')):
                width=int(op[1:3]);suffix=op.split('.',1)[1]
                if suffix=='store':size=width//8
                else:
                    import re
                    m=re.fullmatch(r'store(8|16|32)',suffix)
                    if not m:raise NotImplementedError(op)
                    size=int(m.group(1))//8
                value=stack.pop();address=stack.pop()+(arg or 0)
                state.store(address,size,value)
            elif op=='drop':stack.pop()
            elif op in ('select','select_t'):
                c=stack.pop();b=stack.pop();a=stack.pop();stack.append(a if c else b)
            elif op=='nop':pass
            elif op=='unreachable':raise WasmTrap('unreachable executed')
            elif op=='local.get':stack.append(values[arg])
            elif op=='local.set':values[arg]=stack.pop()
            elif op=='local.tee':values[arg]=stack[-1]
            elif op.endswith('.const'):
                width=int(op[1:3]);stack.append(arg&((1<<width)-1))
            elif op.endswith('.eqz'):stack.append(int(stack.pop()==0))
            elif op in CONVERSIONS.values():stack.append(convert(op,stack.pop()))
            elif op.endswith(('.clz','.ctz','.popcnt')):
                width=int(op[1:3]);value=stack.pop()&((1<<width)-1)
                if op.endswith('.clz'):count=width-value.bit_length()
                elif op.endswith('.ctz'):count=width if value==0 else (value&-value).bit_length()-1
                else:count=value.bit_count()
                stack.append(count)
            elif op.startswith(('i32.','i64.')):
                width=int(op[1:3]);mask=(1<<width)-1;kind=op.split('.')[1]
                b=stack.pop();a=stack.pop()
                signed=lambda x: x-(1<<width) if x&(1<<(width-1)) else x
                sa,sb=signed(a),signed(b)
                if kind in COMPARE:
                    x,y=(sa,sb) if kind.endswith('_s') else (a,b)
                    relation=kind.split('_')[0]
                    v={'eq':lambda:x==y,'ne':lambda:x!=y,'lt':lambda:x<y,'gt':lambda:x>y,'le':lambda:x<=y,'ge':lambda:x>=y}[relation]()
                elif kind=='add':v=a+b
                elif kind=='sub':v=a-b
                elif kind=='mul':v=a*b
                elif kind=='and':v=a&b
                elif kind=='or':v=a|b
                elif kind=='xor':v=a^b
                elif kind=='shl':v=a<<(b&(width-1))
                elif kind=='shr_u':v=a>>(b&(width-1))
                elif kind=='shr_s':v=sa>>(b&(width-1))
                elif kind=='rotl':v=(a<<(b&(width-1)))|(a>>((-b)&(width-1)))
                elif kind=='rotr':v=(a>>(b&(width-1)))|(a<<((-b)&(width-1)))
                elif kind in ('div_u','rem_u','div_s','rem_s'):
                    if b==0:raise WasmTrap('integer divide by zero')
                    if kind.endswith('_s'):
                        if kind=='div_s' and sa==-(1<<(width-1)) and sb==-1:raise WasmTrap('integer overflow')
                        q=(abs(sa)//abs(sb))*(-1 if (sa<0) != (sb<0) else 1)
                        v=q if kind=='div_s' else sa-q*sb
                    else:v=a//b if kind=='div_u' else a%b
                else:raise NotImplementedError(op)
                stack.append(int(v)&(1 if kind in COMPARE else mask))
            else:raise NotImplementedError(op)
        if len(stack)!=len(fn.results):raise WasmTrap('result stack mismatch')
        return stack
    # A fresh module's initializer and export share fuel, but have independent
    # call stacks. Reused instances omit start and retain their existing state.
    if start is not None:invoke(start,[],0)
    return invoke(index,args,0)
