"""Bounded WebAssembly stack-machine -> SSA bit registers -> GSUB.

Runtime operands never enter the compiler. Structured paths become predicated
circuits; direct calls are inlined, loops/recursion have explicit execution
bounds. A taken exhausted path reports a resource bound, NOT a Wasm result.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass, replace
from pathlib import Path
import hashlib
import json

from fontcircuit.gsub.circuit import Circuit, Value, emit_font, ResourceLimit, DEFAULT_MAX_GATES, MAX_GATES
from .frontend import load, memory_bytes
from .ir import MEMOPS, block_signature
from .conversions import CONVERSIONS


@dataclass(frozen=True)
class Limits:
    loop_iterations: int = 8
    call_depth: int = 8
    memory_bytes: int = 16
    max_gates: int = DEFAULT_MAX_GATES

    def __post_init__(self):
        if not 1<=self.loop_iterations<=64:raise ValueError('loop_iterations must be 1..64')
        if not 1<=self.call_depth<=32:raise ValueError('call_depth must be 1..32')
        if not 0<=self.memory_bytes<=256:raise ValueError('memory_bytes must be 0..256')
        if not 1<=self.max_gates<=MAX_GATES:raise ValueError(f'max_gates must be 1..{MAX_GATES}')


@dataclass(frozen=True)
class Instruction:
    op: str
    arg: object = None
    body: tuple = ()
    alternative: tuple = ()


def structure(code) -> tuple:
    def read(pos,nested=False):
        nodes=[]
        while pos<len(code):
            op,arg=code[pos];pos+=1
            if op in ('end','else'):
                if not nested:raise ValueError('unmatched '+op)
                return tuple(nodes),pos,op
            if op in ('block','loop','if'):
                body,pos,stop=read(pos,True);alternative=()
                if stop=='else':
                    if op!='if':raise ValueError('else outside if')
                    alternative,pos,stop=read(pos,True)
                if stop!='end':raise ValueError('missing structured end')
                nodes.append(Instruction(op,arg,body,alternative))
            else:nodes.append(Instruction(op,arg))
        return tuple(nodes),pos,None
    nodes,pos,stop=read(0)
    return nodes


@dataclass
class State:
    predicate: int
    stack: list[Value]
    locals: list[Value]
    globals: list[Value]
    memory: list[Value]
    data_live: list[Value]
    pages: Value

    def copy(self, **changes):
        return replace(self,stack=self.stack.copy(),locals=self.locals.copy(),
                       globals=self.globals.copy(),memory=self.memory.copy(),data_live=self.data_live.copy(),**changes)


@dataclass(frozen=True)
class Label:
    ident: int
    height: int
    widths: tuple[int,...]


@dataclass
class Flow:
    state: State
    target: int | None = None


class NativeCompiler:
    def __init__(self,module,limits: Limits | None=None):
        self.module=module;self.limits=limits or Limits()
        self.c=Circuit(self.limits.max_gates)
        self.ast=[structure(f.code) for f in module.functions]
        self.flags={name:0 for name in ('trap.unreachable','trap.memory_out_of_bounds',
                   'trap.integer_divide_by_zero','trap.integer_overflow',
                   'limit.loop','limit.call','limit.memory')}
        self.serial=0
        self.lowered_instructions=0

    def label(self,height,widths):
        self.serial+=1;return Label(self.serial,height,tuple(widths))

    def flag(self,name,predicate):
        self.flags[name]=self.c.OR(self.flags.get(name,0),predicate)

    def guard(self,state,name,condition):
        self.flag(name,self.c.AND(state.predicate,condition))
        state.predicate=self.c.AND(state.predicate,self.c.NOT(condition))

    def pop(self,state,width=None):
        if not state.stack:raise ValueError('operand stack underflow')
        v=state.stack.pop()
        if width is not None and v.width!=width:raise ValueError('operand type mismatch')
        return v

    def normalize(self,state,label,fallthrough=False):
        n=len(label.widths)
        if len(state.stack)<label.height+n:raise ValueError('branch result stack underflow')
        if fallthrough and len(state.stack)!=label.height+n:raise ValueError('block result stack mismatch')
        results=state.stack[-n:] if n else []
        if tuple(v.width for v in results)!=label.widths:raise ValueError('branch result type mismatch')
        state.stack=state.stack[:label.height]+results
        return state

    def merge(self,states):
        states=[s for s in states if s.predicate!=0]
        if not states:return None
        out=states[0].copy()
        for state in states[1:]:
            for attr in ('stack','locals','globals','memory','data_live'):
                a=getattr(out,attr);b=getattr(state,attr)
                if len(a)!=len(b):raise ValueError('incompatible control-flow state shapes')
                setattr(out,attr,[self.c.mux(state.predicate,y,x) for x,y in zip(a,b)])
            out.pages=self.c.mux(state.predicate,state.pages,out.pages)
            out.predicate=self.c.OR(out.predicate,state.predicate)
        return out

    def compact(self,flows):
        targets={flow.target for flow in flows}
        out=[]
        for target in sorted(targets,key=lambda x:-1 if x is None else x):
            state=self.merge([f.state for f in flows if f.target==target])
            if state is not None:out.append(Flow(state,target))
        return out

    def sequence(self,nodes,state,labels,depth):
        flows=[Flow(state)]
        for node in nodes:
            next_=[]
            for flow in flows:
                if flow.state.predicate==0:continue
                if flow.target is not None:next_.append(flow)
                else:next_.extend(self.instruction(node,flow.state,labels,depth))
            flows=self.compact(next_)
            if not flows:break
        return flows

    def call(self,index,args,parent,depth):
        if not 0<=index<len(self.module.functions):raise ValueError('invalid function index')
        fn=self.module.functions[index]
        if [v.width for v in args]!=[int(t[1:]) for t in fn.params]:raise ValueError('call argument type mismatch')
        if depth>=self.limits.call_depth:
            self.flag('limit.call',parent.predicate)
            return None
        state=State(parent.predicate,[],args+[self.c.const(0,int(t[1:])) for t in fn.locals],
                    parent.globals.copy(),parent.memory.copy(),parent.data_live.copy(),parent.pages)
        label=self.label(0,[int(t[1:]) for t in fn.results])
        flows=self.sequence(self.ast[index],state,[label],depth+1)
        returns=[]
        for flow in flows:
            if flow.target not in (None,label.ident):raise ValueError('branch escaped function')
            returns.append(self.normalize(flow.state,label,flow.target is None))
        result=self.merge(returns)
        if result is None:return None
        result.locals=parent.locals.copy()
        result.stack=parent.stack+result.stack
        return result

    def structured(self,node,state,labels,depth):
        signature=block_signature(node.arg)
        parameters=tuple(int(t[1:]) for t in signature.params)
        types=tuple(int(t[1:]) for t in signature.results)
        condition=self.c.nonzero(self.pop(state,32)) if node.op=='if' else None
        height=len(state.stack)-len(parameters)
        if height<0 or tuple(v.width for v in state.stack[height:])!=parameters:
            raise ValueError('block parameter stack mismatch')
        if node.op=='if':
            label=self.label(height,types)
            yes=state.copy(predicate=self.c.AND(state.predicate,condition))
            no=state.copy(predicate=self.c.AND(state.predicate,self.c.NOT(condition)))
            flows=[]
            if yes.predicate!=0:flows+=self.sequence(node.body,yes,labels+[label],depth)
            if no.predicate!=0:flows+=self.sequence(node.alternative,no,labels+[label],depth)
        elif node.op=='block':
            label=self.label(height,types)
            flows=self.sequence(node.body,state,labels+[label],depth)
        else:
            # Backedges carry the loop's parameters; exits carry its results.
            label=self.label(height,parameters)
            end_label=Label(label.ident,label.height,types)
            current=state;exits=[]
            for _ in range(self.limits.loop_iterations):
                if current is None or current.predicate==0:break
                iteration=self.sequence(node.body,current,labels+[label],depth)
                backedges=[]
                for flow in iteration:
                    if flow.target==label.ident:backedges.append(self.normalize(flow.state,label))
                    else:
                        if flow.target is None:self.normalize(flow.state,end_label,True)
                        exits.append(flow)
                current=self.merge(backedges)
            if current is not None:self.flag('limit.loop',current.predicate)
            return self.compact(exits)
        for flow in flows:
            if flow.target is None:self.normalize(flow.state,label,True)
            elif flow.target==label.ident:
                self.normalize(flow.state,label);flow.target=None
        return self.compact(flows)

    def instruction(self,node,state,labels,depth):
        self.lowered_instructions+=1
        if self.lowered_instructions>100000:raise ResourceLimit('too many lowered instructions')
        op,arg=node.op,node.arg
        if op in ('block','loop','if'):return self.structured(node,state,labels,depth)
        if op in ('br','br_if','br_table','return'):
            if op=='return':label=labels[0];return [Flow(self.normalize(state,label),label.ident)]
            if op=='br_table':
                selector=self.pop(state,32)
                choices=[];matched=0
                for i,target in enumerate(arg[:-1]):
                    test=self.c.eq(selector,self.c.const(i,32));matched=self.c.OR(matched,test)
                    choices.append((target,test))
                choices.append((arg[-1],self.c.NOT(matched)))
                flows=[]
                for target,test in choices:
                    if not 0<=target<len(labels):raise ValueError('invalid branch depth')
                    selected=state.copy(predicate=self.c.AND(state.predicate,test));label=labels[-1-target]
                    if selected.predicate!=0:flows.append(Flow(self.normalize(selected,label),label.ident))
                return self.compact(flows)
            if not 0<=arg<len(labels):raise ValueError('invalid branch depth')
            label=labels[-1-arg]
            if op=='br':return [Flow(self.normalize(state,label),label.ident)]
            condition=self.c.nonzero(self.pop(state,32))
            yes=state.copy(predicate=self.c.AND(state.predicate,condition))
            no=state.copy(predicate=self.c.AND(state.predicate,self.c.NOT(condition)))
            return [Flow(self.normalize(yes,label),label.ident),Flow(no)]
        if op=='unreachable':self.flag('trap.unreachable',state.predicate);return []
        if op=='nop':return [Flow(state)]
        if op=='drop':self.pop(state);return [Flow(state)]
        if op=='select':
            condition=self.c.nonzero(self.pop(state,32));no=self.pop(state);yes=self.pop(state,no.width)
            state.stack.append(self.c.mux(condition,yes,no));return [Flow(state)]
        if op.startswith('local.'):
            if not 0<=arg<len(state.locals):raise ValueError('invalid local index')
            if op=='local.get':state.stack.append(state.locals[arg])
            else:
                value=self.pop(state,state.locals[arg].width);state.locals[arg]=value
                if op=='local.tee':state.stack.append(value)
            return [Flow(state)]
        if op.startswith('global.'):
            if not 0<=arg<len(state.globals):raise ValueError('invalid global index')
            if op=='global.get':state.stack.append(state.globals[arg])
            else:
                if not self.module.mutable[arg]:raise ValueError('global is immutable')
                state.globals[arg]=self.pop(state,state.globals[arg].width)
            return [Flow(state)]
        if op=='call':
            if not 0<=arg<len(self.module.functions):raise ValueError('invalid call index')
            args=[self.pop(state,int(t[1:])) for t in reversed(self.module.functions[arg].params)][::-1]
            result=self.call(arg,args,state,depth)
            return [Flow(result)] if result is not None else []
        if op=='call_indirect':
            selector=self.pop(state,32)
            args=[self.pop(state,int(t[1:])) for t in reversed(arg.params)][::-1]
            table=self.module.table
            if table is None:raise ValueError('indirect call requires a table')
            self.guard(state,'trap.table_out_of_bounds',self.c.NOT(self.c.lt(selector,self.c.const(len(table),32))))
            targets={};empty=0;mismatch=0
            for slot,target in enumerate(table):
                test=self.c.eq(selector,self.c.const(slot,32))
                if target is None:empty=self.c.OR(empty,test);continue
                fn=self.module.functions[target]
                if (tuple(fn.params),tuple(fn.results))!=(arg.params,arg.results):
                    mismatch=self.c.OR(mismatch,test);continue
                targets[target]=self.c.OR(targets.get(target,0),test)
            self.guard(state,'trap.uninitialized_element',empty)
            self.guard(state,'trap.indirect_call_type_mismatch',mismatch)
            results=[]
            for target,test in targets.items():
                selected=state.copy(predicate=self.c.AND(state.predicate,test))
                if selected.predicate==0:continue
                result=self.call(target,args,selected,depth)
                if result is not None:results.append(result)
            result=self.merge(results)
            return [Flow(result)] if result is not None else []
        if op=='memory.size':
            state.stack.append(state.pages);return [Flow(state)]
        if op=='memory.grow':
            delta=self.pop(state,32);old=state.pages
            if self.c.known(delta)==0:
                state.stack.append(old);return [Flow(state)]
            # A 33-bit sum prevents unsigned deltas from wrapping into success.
            grown=self.c.add(Value(old.bits+(0,)),Value(delta.bits+(0,)))
            failed=self.c.lt(self.c.const(self.module.maximum_pages,33),grown)
            state.stack.append(self.c.mux(failed,self.c.const(0xffffffff,32),old))
            # Module limits cap memory at 256 pages, so only nine bits can be live.
            pages=self.c.mux(failed,Value(old.bits[:9]),Value(grown.bits[:9]))
            state.pages=Value(pages.bits+(0,)*23)
            return [Flow(state)]
        if op=='data.drop':
            if not 0<=arg<len(state.data_live):raise ValueError('invalid data segment index')
            state.data_live[arg]=self.c.const(0,1);return [Flow(state)]
        if op in ('memory.copy','memory.fill','memory.init'):return self.bulk_memory(op,state,arg)
        if op in MEMOPS.values():return self.memory(op,arg,state)
        if op in CONVERSIONS.values():
            source=64 if op=='i32.wrap_i64' else 32 if op.startswith('i64.extend_i32') else int(op[1:3])
            value=self.pop(state,source);target=int(op[1:3])
            if op=='i32.wrap_i64':bits=value.bits[:32]
            elif op.startswith('i64.extend_i32'):
                bits=value.bits+((value.bits[-1] if op.endswith('_s') else 0),)*32
            else:
                small=int(op.split('extend')[1].split('_')[0]);bits=value.bits[:small]+(value.bits[small-1],)*(target-small)
            state.stack.append(Value(bits));return [Flow(state)]
        if not op.startswith(('i32.','i64.')):raise NotImplementedError('unsupported native instruction '+op)
        width=int(op[1:3]);kind=op.split('.')[1]
        if kind=='const':state.stack.append(self.c.const(arg,width));return [Flow(state)]
        if kind in ('eqz','clz','ctz','popcnt'):
            a=self.pop(state,width)
            value=Value((self.c.NOT(self.c.nonzero(a)),)+(0,)*31) if kind=='eqz' else self.c.count(kind,a)
            state.stack.append(value);return [Flow(state)]
        b=self.pop(state,width);a=self.pop(state,width)
        if kind=='add':value=self.c.add(a,b)
        elif kind=='sub':value=self.c.add(a,b,True)
        elif kind in ('and','or','xor'):value=self.c.bitwise(kind,a,b)
        elif kind in ('eq','ne','lt_s','lt_u','le_s','le_u','gt_s','gt_u','ge_s','ge_u'):value=self.c.compare(kind,a,b)
        elif kind in ('shl','shr_s','shr_u','rotl','rotr'):value=self.c.shift(kind,a,b)
        elif kind=='mul':value=self.c.mul(a,b)
        elif kind in ('div_s','div_u','rem_s','rem_u'):
            self.guard(state,'trap.integer_divide_by_zero',self.c.NOT(self.c.nonzero(b)))
            if kind=='div_s':
                overflow=self.c.AND(self.c.eq(a,self.c.const(1<<(width-1),width)),self.c.eq(b,self.c.const(-1,width)))
                self.guard(state,'trap.integer_overflow',overflow)
            divisor=self.c.known(b)
            # Constant power-of-two divisors are implemented as wire routing,
            # not as a quadratic restoring-divider network. Signed division
            # truncates toward zero; signed remainder keeps the dividend sign.
            signed=kind.endswith('_s')
            signed_divisor=(divisor-(1<<width) if divisor is not None and divisor & (1<<(width-1)) else divisor)
            magnitude=abs(signed_divisor) if signed and signed_divisor is not None else divisor
            if magnitude is not None and magnitude>0 and magnitude & (magnitude-1)==0:
                distance=magnitude.bit_length()-1
                if signed:
                    # Truncation toward zero via sign-dependent bias:
                    # trunc(a / 2**k) = (a + (a < 0 ? 2**k-1 : 0)) >>s k.
                    # Avoids two full-width conditional negations and a mux.
                    negative=a.bits[-1]
                    bias=Value((negative,)*distance+(0,)*(width-distance))
                    adjusted=self.c.add(a,bias) if distance else a
                    q=Value(adjusted.bits[distance:]+(adjusted.bits[-1],)*distance)
                    if signed_divisor<0:
                        q=self.c.add(self.c.const(0,width),q,True)
                    # Remainder is a - trunc(a / |d|)*|d|. For a
                    # negative divisor the quotient sign changes, but the
                    # remainder always retains the dividend's sign.
                    positive_q=Value(adjusted.bits[distance:]+(adjusted.bits[-1],)*distance)
                    shifted=Value((0,)*distance+positive_q.bits[:width-distance])
                    r=self.c.add(a,shifted,True) if distance else self.c.const(0,width)
                else:
                    q=Value(a.bits[distance:]+(0,)*distance)
                    r=Value(a.bits[:distance]+(0,)*(width-distance))
                value=q if kind.startswith('div') else r
                state.stack.append(value)
                return [Flow(state)]
            if kind.endswith('_s'):
                neg_a=a.bits[-1];neg_b=b.bits[-1]
                aa=self.c.mux(neg_a,self.c.add(self.c.const(0,width),a,True),a)
                bb=self.c.mux(neg_b,self.c.add(self.c.const(0,width),b,True),b)
                q,r=self.c.unsigned_divmod(aa,bb)
                q=self.c.mux(self.c.XOR(neg_a,neg_b),self.c.add(self.c.const(0,width),q,True),q)
                r=self.c.mux(neg_a,self.c.add(self.c.const(0,width),r,True),r)
            else:q,r=self.c.unsigned_divmod(a,b)
            value=q if kind.startswith('div') else r
        else:raise NotImplementedError('unsupported native instruction '+op)
        state.stack.append(value)
        return [Flow(state)]

    def memory_size(self,state,width):
        """Current size in bytes, with no Wasm-width wrapping of endpoints."""
        return Value((0,)*16+state.pages.bits[:width-16])

    def bulk_memory(self,op,state,segment=None):
        size=self.pop(state,32);source=self.pop(state,32);destination=self.pop(state,32)
        # The 33-bit sums preserve overflow, including for zero-length accesses.
        def end(address):
            return self.c.add(Value(address.bits+(0,)),Value(size.bits+(0,)))
        destination_end=end(destination)
        ends=[destination_end]+([end(source)] if op=='memory.copy' else [])
        def exceeds(bound):
            result=0
            limit=self.c.const(bound,33) if isinstance(bound,int) else bound
            for value in ends:result=self.c.OR(result,self.c.lt(limit,value))
            return result
        # Check both Wasm ranges before applying the implementation's window bound.
        invalid=exceeds(self.memory_size(state,33))
        if op=='memory.init':
            if not 0<=segment<len(state.data_live):raise ValueError('invalid data segment index')
            data=self.module.segments[segment][1]
            available=self.c.mux(state.data_live[segment].bits[0],self.c.const(len(data),33),self.c.const(0,33))
            invalid=self.c.OR(invalid,self.c.lt(available,end(source)))
        self.guard(state,'trap.memory_out_of_bounds',invalid)
        self.guard(state,'limit.memory',self.c.AND(self.c.nonzero(size),exceeds(len(state.memory))))
        if state.predicate==0 or self.c.known(size)==0 or not state.memory:return [Flow(state)]
        # A dropped segment can only admit a zero-byte initialization.
        if op=='memory.init' and self.c.known(state.data_live[segment])==0:return [Flow(state)]
        if op in ('memory.copy','memory.init'):
            # Align a snapshot of the source bytes with the destination. A barrel
            # rotation needs O(window * log(window)) byte muxes, rather than a
            # separate dynamic load/store for every possible source/destination.
            length=len(state.memory) if op=='memory.copy' else len(data)
            count=1<<(length-1).bit_length() if length else 1
            rotation_bits=count.bit_length()-1
            delta=self.c.add(Value(source.bits[:rotation_bits]),
                             Value(destination.bits[:rotation_bits]),subtract=True)
            known=self.c.known(delta)
            if op=='memory.init' and known is not None:
                # Constant addresses only need the bytes visible in this window.
                payload=[self.c.const(data[at] if at<length else 0,8)
                         for i in range(len(state.memory)) for at in [(i+known)%count]]
            else:
                if op=='memory.copy':payload=state.memory
                else:
                    palette=[self.c.const(b,8) for b in range(256)]
                    payload=[palette[b] for b in data]
                payload=payload+[self.c.const(0,8)]*(count-length)
                for bit in range(rotation_bits):
                    step=1<<bit
                    payload=[self.c.mux(delta.bits[bit],payload[(i+step)%count],value)
                             for i,value in enumerate(payload)]
                payload=[payload[i%count] for i in range(len(state.memory))]
        else:payload=[Value(source.bits[:8])]*len(state.memory)
        # On a valid nonempty access, both endpoints fit the backed window.
        # Empty ranges have equal endpoints and select no bytes at any width.
        index_bits=len(state.memory).bit_length()
        start=Value(destination.bits[:index_bits]);stop=Value(destination_end.bits[:index_bits])
        for i,old in enumerate(state.memory):
            at=self.c.const(i,index_bits)
            in_range=self.c.AND(self.c.NOT(self.c.lt(at,start)),self.c.lt(at,stop))
            state.memory[i]=self.c.mux(in_range,payload[i],old)
        return [Flow(state)]

    def memory(self,op,offset,state):
        width=int(op[1:3]);size=memory_bytes(op);store='.store' in op
        value=self.pop(state,width) if store else None
        address=self.pop(state,32)
        pages=self.c.known(state.pages)
        def exceeds(bound):
            maximum=bound-offset-size
            if maximum<0:return 1
            if maximum>=0xffffffff:return 0
            return self.c.lt(self.c.const(maximum,32),address)
        # Effective addresses use unbounded offset addition, never i32 wrapping.
        if pages is not None:invalid=exceeds(pages*65536)
        else:
            # Address + offset + access size can require 34 bits in total.
            end=self.c.add(Value(address.bits+(0,0)),self.c.const(offset+size,34))
            invalid=self.c.lt(self.memory_size(state,34),end)
        self.guard(state,'trap.memory_out_of_bounds',invalid)
        self.guard(state,'limit.memory',exceeds(len(state.memory)))
        known=self.c.known(address)
        if known is not None:
            at=known+offset
            if not 0<=at<=len(state.memory)-size:
                if not store:state.stack.append(self.c.const(0,width))
                return [Flow(state)]
            if store:
                for i in range(size):state.memory[at+i]=Value(value.bits[8*i:8*i+8])
            else:
                bits=tuple(bit for byte in state.memory[at:at+size] for bit in byte.bits)
                fill=bits[-1] if op.endswith('_s') else 0
                state.stack.append(Value(bits+(fill,)*(width-len(bits))))
            return [Flow(state)]
        tests={at:self.c.eq(address,self.c.const(at-offset,32)) for at in range(max(offset,0),len(state.memory)-size+1)}
        if store:
            for at,test in tests.items():
                for i in range(size):
                    new=Value(value.bits[8*i:8*i+8]);state.memory[at+i]=self.c.mux(test,new,state.memory[at+i])
        else:
            bits=[0]*(size*8)
            for at,test in tests.items():
                for i in range(size*8):bits[i]=self.c.OR(bits[i],self.c.AND(test,state.memory[at+i//8].bits[i%8]))
            fill=bits[-1] if op.endswith('_s') else 0
            state.stack.append(Value(tuple(bits)+(fill,)*(width-len(bits))))
        return [Flow(state)]

    def lower(self,export=None):
        if export is None:
            candidates=[(n,i) for n,(k,i) in self.module.exports.items() if k==0]
            if candidates:export,index=candidates[0]
            elif self.module.functions:index=0;export=None
            else:raise ValueError('module has no functions')
        elif isinstance(export,int):index=export;export=None
        else:
            if export not in self.module.exports:raise ValueError('unknown export '+export)
            kind,index=self.module.exports[export]
            if kind!=0:raise ValueError('selected export is not a function')
        if not 0<=index<len(self.module.functions):raise ValueError('invalid entry function')
        fn=self.module.functions[index]
        args=[self.c.argument(i,int(t[1:])) for i,t in enumerate(fn.params)]
        can_grow=any(op=='memory.grow' for f in self.module.functions for op,_ in f.code)
        # The backed window fits in the first page. Reserve zero bytes for growth
        # from zero pages; the current page count still guards every access.
        backed_pages=self.module.maximum_pages if can_grow else self.module.initial_pages
        byte_count=min(self.limits.memory_bytes,backed_pages*65536)
        data=bytearray(byte_count)
        for offset,payload in self.module.segments:
            if offset is None:continue
            # Untouched data outside the backed window remains inaccessible and is
            # reported as a bound, so dropping its glyph representation is sound.
            n=max(0,min(len(payload),byte_count-offset))
            if n:data[offset:offset+n]=payload[:n]
        parent=State(1,[],[],[self.c.const(v,int(t[1:])) for v,t in zip(self.module.globals,self.module.global_types)],
                     [self.c.const(v,8) for v in data],
                     [self.c.const(int(offset is None),1) for offset,_ in self.module.segments],
                     self.c.const(self.module.initial_pages,32))
        result=self.call(index,args,parent,0)
        values=result.stack if result is not None else [self.c.const(0,int(t[1:])) for t in fn.results]
        return values,fn,index,export


def compile_source(source,output,*,export=None,limits=None):
    module,data=load(source)
    compiler=NativeCompiler(module,limits)
    values,fn,index,export=compiler.lower(export)
    manifest=emit_font(compiler.c,values,compiler.flags,fn.params,fn.results,output,extra={
        'source_sha256':hashlib.sha256(data).hexdigest(),'export':export,'function_index':index,
        'limits':vars(compiler.limits),'lowered_instructions':compiler.lowered_instructions,
        'execution':'single HarfBuzz shaping invocation; fresh module state',
    })
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('-o','--output',type=Path,default=Path(__file__).resolve().parents[1] / 'wasm-native.ttf')
    parser.add_argument('--export');parser.add_argument('--loop-bound',type=int,default=8)
    parser.add_argument('--call-depth',type=int,default=8);parser.add_argument('--memory-bytes',type=int,default=16)
    parser.add_argument('--max-gates',type=int,default=Limits().max_gates)
    args=parser.parse_args()
    try:
        manifest=compile_source(args.source,args.output,export=args.export,
                                limits=Limits(args.loop_bound,args.call_depth,args.memory_bytes,args.max_gates))
    except (ValueError,NotImplementedError,RuntimeError) as exc:parser.exit(2,str(exc)+'\n')
    print(json.dumps(manifest['metrics'],indent=2))

if __name__=='__main__':main()
