"""Nullable function references and bounded mutable function-table circuits."""
from fontcircuit.gsub.circuit import Value
from .selection import lookup,selectors,aligned
from .ir import table_operand
from .types import is_reference,signature_key,signature_keys


class Reference(Value):
    """A tagged stack value; reference IDs cannot become integer operands."""


class TableLowering:
    def configure_table(self):
        self.type_keys=signature_keys(self.module.function_types)
        self.reference_width=max(1,len(self.module.functions).bit_length())
        grows={table_operand(op,arg).table for fn in self.module.functions for op,arg in fn.code if op=='table.grow'}
        entries=[];sizes=[];self.table_spans=[]
        for index,table in enumerate(self.module.tables):
            initial=table.entries
            capacity=(table.maximum if table.maximum is not None else 256) if index in grows else len(initial)
            self.table_spans.append((len(entries),capacity))
            entries.extend(self.c.const(0 if target is None else target+1,self.reference_width)
                           for target in initial+[None]*(capacity-len(initial)))
            sizes.append(self.c.const(len(initial),32))
        initial=[v for table in self.module.tables for v in table.entries]
        targets={v for v in initial if v is not None}
        targets.update(v for segment in self.module.elements for v in segment.functions if v is not None)
        targets.update(v for t,v in zip(self.module.global_types,self.module.globals) if is_reference(t) and v is not None)
        targets.update(arg for fn in self.module.functions for op,arg in fn.code if op=='ref.func')
        self.reference_targets=sorted(targets)
        live=[self.c.const(int(segment.mode=='passive'),1) for segment in self.module.elements]
        return entries,sizes,live

    def table_view(self,state,index):
        if not 0<=index<len(self.table_spans):raise ValueError('invalid table index')
        start,capacity=self.table_spans[index]
        return start,capacity,state.table[start:start+capacity],state.table_sizes[index]

    @staticmethod
    def value_type(value):return 'funcref' if isinstance(value,Reference) else value.width

    @staticmethod
    def type_width(typ):return 'funcref' if is_reference(typ) else int(typ[1:])

    def pop_typed(self,state,typ):
        return self.pop_reference(state) if is_reference(typ) else self.pop(state,int(typ[1:]))

    def initial_value(self,typ,value=0):
        return self.reference(value) if is_reference(typ) else self.c.const(value,int(typ[1:]))

    def reference(self,target):
        return Reference(self.c.const(0 if target is None else target+1,self.reference_width).bits)

    def pop_reference(self,state):
        value=self.pop(state)
        if not isinstance(value,Reference):raise ValueError('expected a function reference')
        return value

    def mux_value(self,test,yes,no):
        if isinstance(yes,Reference)!=isinstance(no,Reference):raise ValueError('incompatible reference/integer values')
        value=self.c.mux(test,yes,no)
        return Reference(value.bits) if isinstance(yes,Reference) else value

    def table_instruction(self,op,arg,state):
        if op=='ref.null':state.stack.append(self.reference(None));return state
        if op=='ref.func':state.stack.append(self.reference(arg));return state
        if op=='ref.is_null':
            state.stack.append(Value((self.c.NOT(self.c.nonzero(self.pop_reference(state))),)+(0,)*31));return state
        if op=='ref.as_non_null':
            reference=self.pop_reference(state)
            self.guard(state,'trap.null_reference',self.c.NOT(self.c.nonzero(reference)))
            state.stack.append(reference);return state
        if op=='elem.drop':state.elem_live[arg]=self.c.const(0,1);return state
        use=table_operand(op,arg)
        start,capacity,table,table_size=self.table_view(state,use.table)
        if op=='table.size':state.stack.append(table_size);return state
        if op=='table.grow':
            delta=self.pop(state,32);initial=self.pop_reference(state);old=table_size
            grown=self.c.add(Value(old.bits+(0,)),Value(delta.bits+(0,)))
            failed=self.c.lt(self.c.const(capacity,33),grown)
            state.stack.append(self.c.mux(failed,self.c.const(0xffffffff,32),old))
            for i,value in enumerate(table):
                at=self.c.const(i,33)
                new=self.c.AND(self.c.NOT(failed),self.c.AND(
                    self.c.NOT(self.c.lt(at,Value(old.bits+(0,)))),self.c.lt(at,grown)))
                state.table[start+i]=self.c.mux(new,initial,value)
            size=self.c.mux(failed,Value(old.bits[:9]),Value(grown.bits[:9]))
            state.table_sizes[use.table]=Value(size.bits+(0,)*23)
            return state
        if op in ('table.get','table.set'):
            value=self.pop_reference(state) if op=='table.set' else None
            slot=self.pop(state,32)
            self.guard(state,'trap.table_out_of_bounds',self.c.NOT(self.c.lt(slot,table_size)))
            if op=='table.get':
                result=lookup(self.c,table,slot) if table else self.c.const(0,self.reference_width)
                state.stack.append(Reference(result.bits))
            else:
                for i,test in enumerate(selectors(self.c,slot,len(table))):
                    state.table[start+i]=self.c.mux(test,value,table[i])
            return state
        size=self.pop(state,32)
        source=self.pop_reference(state) if op=='table.fill' else self.pop(state,32)
        destination=self.pop(state,32)
        def end(address):return self.c.add(Value(address.bits+(0,)),Value(size.bits+(0,)))
        destination_end=end(destination)
        invalid=self.c.lt(Value(table_size.bits+(0,)),destination_end)
        if op=='table.copy':
            _,_,source_table,source_size=self.table_view(state,use.source)
            invalid=self.c.OR(invalid,self.c.lt(Value(source_size.bits+(0,)),end(source)))
        if op=='table.init':
            segment=self.module.elements[use.element]
            available=self.c.mux(state.elem_live[use.element].bits[0],self.c.const(len(segment.functions),33),self.c.const(0,33))
            invalid=self.c.OR(invalid,self.c.lt(available,end(source)))
        self.guard(state,'trap.table_out_of_bounds',invalid)
        # Active, declarative and explicitly dropped segments are empty here.
        if op=='table.init' and self.c.known(state.elem_live[use.element])==0:return state
        if state.predicate==0 or self.c.known(size)==0 or not table:return state
        if op=='table.fill':payload=[source]*len(table)
        else:
            values=source_table if op=='table.copy' else [self.reference(target) for target in segment.functions]
            if not values:return state
            payload=aligned(self.c,values,source,destination,len(table))
        bits=len(table).bit_length()
        first=Value(destination.bits[:bits]);stop=Value(destination_end.bits[:bits])
        for i,value in enumerate(table):
            at=self.c.const(i,bits)
            inside=self.c.AND(self.c.NOT(self.c.lt(at,first)),self.c.lt(at,stop))
            state.table[start+i]=self.c.mux(inside,payload[i],value)
        return state

    def indirect_targets(self,state,selector,signature,table_index=0):
        _,_,table,table_size=self.table_view(state,table_index)
        self.guard(state,'trap.table_out_of_bounds',self.c.NOT(self.c.lt(selector,table_size)))
        if state.predicate==0:return {}
        known=[self.c.known(value) for value in table]
        candidates=sorted({value-1 for value in known if value}) if all(value is not None for value in known) else self.reference_targets
        reference=lookup(self.c,table,selector)
        return self.reference_call_targets(state,reference,signature,candidates=candidates)

    def reference_call_targets(self,state,reference,signature,*,candidates=None,typed=False):
        if typed:
            self.guard(state,'trap.null_reference',self.c.NOT(self.c.nonzero(reference)))
            if state.predicate==0:return {}
            known=self.c.known(reference)
            candidates=[known-1] if known else self.reference_targets
        elif candidates is None:candidates=self.reference_targets
        empty=self.c.NOT(self.c.nonzero(reference));compatible=0;targets={}
        expected=signature_key(signature.params,signature.results,self.type_keys)
        for target in candidates:
            fn=self.module.functions[target]
            if signature_key(fn.params,fn.results,self.type_keys)==expected:
                test=self.c.eq(reference,self.reference(target))
                if test:
                    targets[target]=test;compatible=self.c.OR(compatible,test)
        if not typed:
            mismatch=self.c.AND(self.c.NOT(empty),self.c.NOT(compatible))
            self.guard(state,'trap.uninitialized_element',empty)
            self.guard(state,'trap.indirect_call_type_mismatch',mismatch)
        return targets
