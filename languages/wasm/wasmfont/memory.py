"""Sparse backed-memory layouts and compact dynamic memory access circuits."""
from fontcircuit.gsub.circuit import Value
from .selection import aligned,lookup,lookup_window,selectors


class MemoryLowering:
    def configure_memory(self,pages):
        requested=self.limits.memory_regions or ((self.limits.memory_base,self.limits.memory_bytes),)
        self.memory_layout=[];self.memory_addresses=[]
        for base,size in requested:
            size=min(size,max(0,pages*65536-base))
            if size:
                self.memory_layout.append((base,size,len(self.memory_addresses)))
                self.memory_addresses.extend(range(base,base+size))
        self.memory_index={address:i for i,address in enumerate(self.memory_addresses)}
        data=bytearray(len(self.memory_addresses))
        for offset,payload in self.module.segments:
            if offset is None:continue
            for base,size,index in self.memory_layout:
                start=max(base,offset);stop=min(base+size,offset+len(payload))
                if start<stop:data[index+start-base:index+stop-base]=payload[start-offset:stop-offset]
        return data

    def covered(self,address,end):
        covered=0
        for base,size,_ in self.memory_layout:
            lower=self.c.NOT(self.c.lt(address,self.c.const(base,32)))
            upper=self.c.NOT(self.c.lt(self.c.const(base+size,end.width),end))
            covered=self.c.OR(covered,self.c.AND(lower,upper))
        return covered

    def physical_index(self,address):
        known=self.c.known(address)
        if known is not None:return self.c.const(self.memory_index.get(known,0),32)
        index=self.c.const(0,32)
        # Only the low bits of physical indices are needed by bounded arrays.
        width=max(1,(len(self.memory_addresses)-1).bit_length())
        for base,size,start in self.memory_layout:
            inside=self.c.AND(self.c.NOT(self.c.lt(address,self.c.const(base,32))),
                              self.c.lt(address,self.c.const(base+size,32)))
            offset=self.c.add(Value(address.bits[:width]),self.c.const((start-base)%(1<<width),width))
            offset=Value(offset.bits+(0,)*(32-width))
            index=self.c.mux(inside,offset,index)
        return index

    def indexed_memory(self,state,address,offset,value,width,size,store,*,check_window,signed=False):
        effective=self.c.add(address,self.c.const(offset,32)) if offset else address
        if check_window:
            end=self.c.add(Value(address.bits+(0,0)),self.c.const(offset+size,34))
            self.guard(state,'limit.memory',self.c.NOT(self.covered(effective,end)))
        if state.predicate==0 or not state.memory:
            if not store:state.stack.append(self.c.const(0,width))
            return state
        index=self.physical_index(effective)
        if store:
            tests=selectors(self.c,index,len(state.memory))
            for at,test in enumerate(tests):
                for byte in range(min(size,len(state.memory)-at)):
                    state.memory[at+byte]=self.c.mux(test,Value(value.bits[byte*8:byte*8+8]),state.memory[at+byte])
        else:
            if size>1 and len(state.memory)>=32 and any(self.c.known(byte) is None for byte in state.memory):
                # Runtime-valued wide reads share the expensive high-address
                # selection. Keep the compact constant-data path unchanged.
                payload=lookup_window(self.c,state.memory,index,size)
                bits=[bit for byte in payload for bit in byte.bits]
            else:
                bits=[];index_width=max(1,(len(state.memory)-1).bit_length())
                short=Value(index.bits[:index_width])
                for byte in range(size):
                    at=self.c.add(short,self.c.const(byte,index_width)) if byte else short
                    bits.extend(lookup(self.c,state.memory,at).bits)
            fill=bits[-1] if signed else 0
            state.stack.append(Value(tuple(bits)+(fill,)*(width-len(bits))))
        return state

    def sparse_bulk(self,state,op,destination,source,size,destination_end,data):
        nonempty=self.c.nonzero(size)
        valid=self.covered(destination,destination_end)
        if op=='memory.copy':
            source_end=self.c.add(Value(source.bits+(0,)),Value(size.bits+(0,)))
            valid=self.c.AND(valid,self.covered(source,source_end))
        self.guard(state,'limit.memory',self.c.AND(nonempty,self.c.NOT(valid)))
        if state.predicate==0 or self.c.known(size)==0 or not state.memory:return state
        dest=self.physical_index(destination)
        if op=='memory.fill':payload=[Value(source.bits[:8])]*len(state.memory)
        else:
            values=state.memory if op=='memory.copy' else [self.c.const(byte,8) for byte in data]
            if not values:return state
            src=self.physical_index(source) if op=='memory.copy' else source
            payload=aligned(self.c,values,src,dest,len(state.memory))
        end=self.c.add(dest,size)
        bits=len(state.memory).bit_length()
        start=Value(dest.bits[:bits]);stop=Value(end.bits[:bits])
        for i,old in enumerate(state.memory):
            at=self.c.const(i,bits)
            inside=self.c.AND(self.c.NOT(self.c.lt(at,start)),self.c.lt(at,stop))
            state.memory[i]=self.c.mux(inside,payload[i],old)
        return state
