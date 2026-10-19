"""Nullable function references and bounded mutable function-table circuits."""
from fontcircuit.gsub.circuit import Value
from .selection import lookup,selectors,aligned


class Reference(Value):
    """A tagged stack value; reference IDs cannot become integer operands."""


class TableLowering:
    def configure_table(self):
        self.reference_width=max(1,len(self.module.functions).bit_length())
        initial=self.module.table or []
        grows=any(op=='table.grow' for fn in self.module.functions for op,_ in fn.code)
        capacity=(self.module.table_maximum if self.module.table_maximum is not None else 256) if grows else len(initial)
        if self.module.table is None:capacity=0
        self.table_capacity=capacity
        targets={v for v in initial if v is not None}
        targets.update(v for segment in self.module.elements for v in segment.functions if v is not None)
        targets.update(v for t,v in zip(self.module.global_types,self.module.globals) if t=='funcref' and v is not None)
        targets.update(arg for fn in self.module.functions for op,arg in fn.code if op=='ref.func')
        self.reference_targets=sorted(targets)
        entries=[self.c.const(0 if target is None else target+1,self.reference_width)
                 for target in initial+[None]*(capacity-len(initial))]
        live=[self.c.const(int(segment.mode=='passive'),1) for segment in self.module.elements]
        return entries,self.c.const(len(initial),32),live

    @staticmethod
    def value_type(value):return 'funcref' if isinstance(value,Reference) else value.width

    @staticmethod
    def type_width(typ):return 'funcref' if typ=='funcref' else int(typ[1:])

    def pop_typed(self,state,typ):
        return self.pop_reference(state) if typ=='funcref' else self.pop(state,int(typ[1:]))

    def initial_value(self,typ,value=0):
        return self.reference(value) if typ=='funcref' else self.c.const(value,int(typ[1:]))

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
        if op=='elem.drop':state.elem_live[arg]=self.c.const(0,1);return state
        if self.module.table is None:raise ValueError('table operation requires a table')
        if op=='table.size':state.stack.append(state.table_size);return state
        if op=='table.grow':
            delta=self.pop(state,32);initial=self.pop_reference(state);old=state.table_size
            grown=self.c.add(Value(old.bits+(0,)),Value(delta.bits+(0,)))
            failed=self.c.lt(self.c.const(self.table_capacity,33),grown)
            state.stack.append(self.c.mux(failed,self.c.const(0xffffffff,32),old))
            for i,value in enumerate(state.table):
                at=self.c.const(i,33)
                new=self.c.AND(self.c.NOT(failed),self.c.AND(
                    self.c.NOT(self.c.lt(at,Value(old.bits+(0,)))),self.c.lt(at,grown)))
                state.table[i]=self.c.mux(new,initial,value)
            size=self.c.mux(failed,Value(old.bits[:9]),Value(grown.bits[:9]))
            state.table_size=Value(size.bits+(0,)*23)
            return state
        if op in ('table.get','table.set'):
            value=self.pop_reference(state) if op=='table.set' else None
            slot=self.pop(state,32)
            self.guard(state,'trap.table_out_of_bounds',self.c.NOT(self.c.lt(slot,state.table_size)))
            if op=='table.get':
                result=lookup(self.c,state.table,slot) if state.table else self.c.const(0,self.reference_width)
                state.stack.append(Reference(result.bits))
            else:
                for i,test in enumerate(selectors(self.c,slot,len(state.table))):
                    state.table[i]=self.c.mux(test,value,state.table[i])
            return state
        size=self.pop(state,32)
        source=self.pop_reference(state) if op=='table.fill' else self.pop(state,32)
        destination=self.pop(state,32)
        def end(address):return self.c.add(Value(address.bits+(0,)),Value(size.bits+(0,)))
        destination_end=end(destination)
        invalid=self.c.lt(Value(state.table_size.bits+(0,)),destination_end)
        if op=='table.copy':
            invalid=self.c.OR(invalid,self.c.lt(Value(state.table_size.bits+(0,)),end(source)))
        if op=='table.init':
            segment=self.module.elements[arg]
            available=self.c.mux(state.elem_live[arg].bits[0],self.c.const(len(segment.functions),33),self.c.const(0,33))
            invalid=self.c.OR(invalid,self.c.lt(available,end(source)))
        self.guard(state,'trap.table_out_of_bounds',invalid)
        # Active, declarative and explicitly dropped segments are empty here.
        if op=='table.init' and self.c.known(state.elem_live[arg])==0:return state
        if state.predicate==0 or self.c.known(size)==0 or not state.table:return state
        if op=='table.fill':payload=[source]*len(state.table)
        else:
            values=state.table if op=='table.copy' else [self.reference(target) for target in segment.functions]
            if not values:return state
            payload=aligned(self.c,values,source,destination,len(state.table))
        bits=len(state.table).bit_length()
        start=Value(destination.bits[:bits]);stop=Value(destination_end.bits[:bits])
        for i,value in enumerate(state.table):
            at=self.c.const(i,bits)
            inside=self.c.AND(self.c.NOT(self.c.lt(at,start)),self.c.lt(at,stop))
            state.table[i]=self.c.mux(inside,payload[i],value)
        return state

    def indirect_targets(self,state,selector,signature):
        self.guard(state,'trap.table_out_of_bounds',self.c.NOT(self.c.lt(selector,state.table_size)))
        if state.predicate==0:return {}
        known=[self.c.known(value) for value in state.table]
        candidates=sorted({value-1 for value in known if value}) if all(value is not None for value in known) else self.reference_targets
        reference=lookup(self.c,state.table,selector)
        empty=self.c.NOT(self.c.nonzero(reference));compatible=0;targets={}
        for target in candidates:
            fn=self.module.functions[target]
            if (tuple(fn.params),tuple(fn.results))==(signature.params,signature.results):
                test=self.c.eq(reference,self.reference(target))
                if test:
                    targets[target]=test;compatible=self.c.OR(compatible,test)
        mismatch=self.c.AND(self.c.NOT(empty),self.c.NOT(compatible))
        self.guard(state,'trap.uninitialized_element',empty)
        self.guard(state,'trap.indirect_call_type_mismatch',mismatch)
        return targets
