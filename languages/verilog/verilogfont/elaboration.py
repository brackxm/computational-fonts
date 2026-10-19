# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Specialize hierarchy and lower blocking statements to immutable bit drivers."""
from dataclasses import replace
from .syntax import Constant, Expr, VerilogError, VerilogResourceLimit, diagnostic, MAX_DEPTH, MAX_WIDTH
from .constants import ConstantEvaluator
from .model import Module, Signal, Statement, map_children, syntax_children

MAX_INSTANCES = 128
MAX_SIGNALS = 128
MAX_LOOP_ITERATIONS = 64
MAX_EXPANSIONS = 4096
MAX_GENERATED_SCOPES = 128
MAX_FUNCTION_CALLS = 128
MAX_FUNCTION_DEPTH = 8
MAX_ARRAY_WORDS = 16
MAX_ARRAY_BITS = 1024
MAX_CAPTURES = 4096
MAX_CAPTURE_BITS = 65536


def bit(expression, index):
    return Expr('select', (expression, index, index), expression.location)


def packed(bits, signed=False):
    return Expr('typed', (Expr('concat', tuple(reversed(bits))), len(bits), signed), next((b.location for b in bits if b.location),None))


def constant_expression(expr, parameters):
    if expr.op in ('typed','captured','call','array_read','case_eq','index_eq','bit_select','indexed_select'):
        return False
    if expr.op == 'name':
        return expr.args[0] in parameters
    return all(constant_expression(arg, parameters) for arg in expr.args if isinstance(arg, Expr))


class Scope:
    def __init__(self, elaborator, definition, prefix, overrides, root, parent=None, constants=None, function=False):
        self.elaborator, self.definition, self.prefix = elaborator, definition, prefix
        if constants and constants.keys() & (definition.signals.keys() | definition.parameters.keys()):
            raise VerilogError('declaration collides with the implicit genvar constant',definition.location)
        self.evaluator = ConstantEvaluator(definition.parameters, overrides)
        inherited = dict(parent.parameters) if parent else {}
        inherited.update(constants or {})
        inherited = {k:v for k,v in inherited.items() if k not in definition.parameters and k not in definition.signals}
        self.evaluator.values.update(inherited)
        self.parameters = dict(inherited)
        self.parameters.update({name: self.evaluator.parameter(name) for name in definition.parameters})
        self.names = dict(parent.names) if parent and not function else {}
        self.arrays = dict(parent.arrays) if parent and not function else {}
        for name in definition.parameters: self.arrays.pop(name,None)
        self.readonly = set(parent.readonly) if parent and not function else set()
        self.functions = dict(parent.functions) if parent else {}
        self.genvars = ((parent.genvars if parent else set()) | definition.genvars) - (constants or {}).keys()
        self.depth = parent.depth+1 if parent else 0
        self.bound = {}
        self.signals = {}
        for name, (direction, bounds, signed, kind) in definition.signals.items():
            location = definition.locations.get(name,definition.location)
            try:
                width = self.evaluator.range_width(bounds) if bounds else 1
                indices = None
                if name in definition.arrays:
                    left,right = (self.evaluator.evaluate(e).integer for e in definition.arrays[name])
                    count = abs(right-left)+1
                    if count > MAX_ARRAY_WORDS:
                        raise VerilogResourceLimit(f'array {name} has {count} words; maximum is {MAX_ARRAY_WORDS}')
                    elaborator.array_bits += count*width
                    if elaborator.array_bits > MAX_ARRAY_BITS:
                        raise VerilogResourceLimit(f'array storage exceeds {MAX_ARRAY_BITS} bits; reduce array lengths or word widths')
                    indices = tuple(range(min(left,right),max(left,right)+1))
                self.names.pop(name,None)
                self.arrays.pop(name,None)
                for index in indices if indices is not None else (None,):
                    raw_name = name if index is None else f'{name}[{index}]'
                    flat = prefix+raw_name
                    signal = Signal(flat, direction if root else 'wire', width, signed,
                                    'reg' if kind == 'integer' else kind,location)
                    self.signals[raw_name] = signal
                    elaborator.module.signals[flat] = signal
                    elaborator.module.bit_drivers[flat] = [None]*width
                    if direction == 'input' and not function: self.readonly.add(flat)
                    if len(elaborator.module.signals) > MAX_SIGNALS:
                        raise VerilogResourceLimit(f'flattened design exceeds {MAX_SIGNALS} signals (array words count separately)')
                if indices is None:
                    self.names[name] = flat
                else:
                    self.arrays[name] = (tuple(Expr('name',(prefix+f'{name}[{i}]',),location) for i in indices),width,signed,indices)
            except VerilogError as error:
                raise error.at(location) from None
        for name,definition_ in definition.functions.items():
            self.functions[name] = (definition_,self)
        from .frontend import ExpressionTypes
        self.types = ExpressionTypes(elaborator.module)

    @diagnostic
    def bind(self, expr, depth=0):
        if depth >= MAX_DEPTH:
            raise VerilogResourceLimit('elaborated expression depth exceeds compiler bounds')
        if id(expr) in self.bound:
            return self.bound[id(expr)][1]
        op, args = expr.op, expr.args
        if op == 'name':
            if args[0] in self.parameters:
                value = self.parameters[args[0]]
                result = Expr('signed_literal' if value.signed else 'literal', (value.bits, value.width))
            elif args[0] in self.names:
                result = Expr('name', (self.names[args[0]],))
            else:
                if args[0] in self.arrays:
                    raise VerilogError(f'array requires a word index: {args[0]}')
                raise VerilogError(f'undeclared signal: {self.prefix}{args[0]}')
        elif op == 'call':
            result = Expr('call',(args[0],*(self.bind(a,depth+1) for a in args[1:])))
        elif op == 'select' and args[0].op == 'name' and args[0].args[0] in self.arrays:
            base,high,low = args
            if high is not low:
                raise VerilogError('unpacked arrays require a single word index')
            words,width,signed,indices = self.arrays[base.args[0]]
            if constant_expression(high,self.parameters):
                index = self.evaluator.evaluate(high).integer
                if index not in indices:
                    raise VerilogError(f'array index {index} is outside [{indices[0]}:{indices[-1]}]')
                result = words[indices.index(index)]
            else:
                result = Expr('array_read',(words,self.bind(high,depth+1),width,signed,indices))
        elif op == 'select':
            base, high, low = args
            base = self.bind(base, depth+1)
            if high is low and not constant_expression(high, self.parameters):
                result = Expr('bit_select', (base, self.bind(high, depth+1)))
            else:
                result = Expr('select', (base, self.evaluator.evaluate(high).integer,
                                       self.evaluator.evaluate(low).integer))
        elif op == 'indexed':
            base, index, width, direction = args
            width = self.evaluator.evaluate(width).integer
            if not 1 <= width <= MAX_WIDTH:
                raise VerilogError(f'indexed part width must be 1–{MAX_WIDTH}')
            base = self.bind(base, depth+1)
            if constant_expression(index, self.parameters):
                start = self.evaluator.evaluate(index).integer
                low = start if direction == '+:' else start-width+1
                result = Expr('select', (base, low+width-1, low))
            else:
                result = Expr('indexed_select', (base, self.bind(index, depth+1), width, direction))
        elif op == 'repeat':
            result = Expr(op, (self.evaluator.repeat_count(args[0]), self.bind(args[1], depth+1)))
        else:
            result = Expr(op, tuple(self.bind(a, depth+1) if isinstance(a, Expr) else a for a in args))
        result = replace(result,location=expr.location)
        self.bound[id(expr)] = (expr,result)  # Retain the source so its ID cannot be reused.
        return result

    @diagnostic
    def resolve(self, expr):
        result = map_children(expr, self.resolve)
        if result.op == 'call':
            return self.call(result.args[0],result.args[1:],result.location)
        return result

    @diagnostic
    def target(self, raw):
        target = self.bind(raw)
        for name, _, _, _ in self.parts(target)[0]:
            if name in self.readonly:
                raise VerilogError(f'cannot drive input: {name}')
        return target

    @diagnostic
    def parts(self, target):
        """Return (net, bit-or-(dynamic-index,delta), RHS-bit, word-guard)."""
        op,args = target.op,target.args
        if op == 'concat':
            parts,width = [],0
            for arg in reversed(args):
                subparts,subwidth,_ = self.parts(arg)
                parts.extend((name,index,offset+width,guard) for name,index,offset,guard in subparts)
                width += subwidth
            if width > MAX_WIDTH: raise VerilogError('assignment target exceeds 64 bits')
            keys = [(name,index) for name,index,_,guard in parts if isinstance(index,int) and guard is None]
            if len(set(keys)) != len(keys): raise VerilogError('overlapping concatenation assignment targets')
            return parts,width,False
        if op == 'array_read':
            words,index,width,signed,indices = args
            parts = []
            for word,integer in zip(words,indices):
                guard = Expr('index_eq',(index,integer),target.location)
                parts.extend((word.args[0],i,i,guard) for i in range(width))
            return parts,width,signed
        if op == 'name':
            signal = self.elaborator.module.signals.get(args[0])
            if signal is None: raise VerilogError('assignment targets must be declared signals')
            return [(signal.name,i,i,None) for i in range(signal.width)],signal.width,signal.signed
        if op not in ('select','bit_select','indexed_select') or args[0].op not in ('name','array_read'):
            raise VerilogError('assignment targets must be signals or signal slices')
        base_parts,base_width,_ = self.parts(args[0])
        if op == 'select':
            _,high,low = args
            if not 0 <= low <= high < base_width:
                raise VerilogError('assignment slice is outside its signal range')
            return [(name,i,offset-low,guard) for name,i,offset,guard in base_parts if low <= offset <= high],high-low+1,False
        width = 1 if op == 'bit_select' else args[2]
        delta = 0 if op == 'bit_select' or args[3] == '+:' else 1-width
        names = dict((name,guard) for name,_,_,guard in base_parts)
        return [(name,(args[1],delta+i),i,guard) for name,guard in names.items() for i in range(width)],width,False

    @diagnostic
    def assign(self, target, expression):
        parts,width,signed = self.parts(target)
        if any(not isinstance(index,int) or guard is not None for _,index,_,guard in parts):
            raise VerilogError('dynamic continuous targets leave undriven bits; use an initialized always @* block')
        expression = Expr('typed',(self.resolve(expression),width,signed),expression.location)
        self.elaborator.module.checks.append(expression)
        for name,index,offset,_ in parts:
            signal = self.elaborator.module.signals[name]
            if signal.kind != 'wire': raise VerilogError(f'continuous/instance driver requires a wire: {name}')
            self.elaborator.drive(name,index,bit(expression,offset))

    def loop_values(self, iterator, initial, condition, step, constants):
        evaluator = ConstantEvaluator({}, {})
        evaluator.values.update(self.parameters)
        evaluator.values.update(constants)
        try:
            current = evaluator.evaluate(initial).resized(32,True)
            seen,values = set(),[]
            while True:
                evaluator.values[iterator] = current
                evaluator.types.clear()
                if not evaluator.evaluate(condition).bits: break
                if current.bits in seen:
                    raise VerilogResourceLimit('for loop does not terminate: iterator value repeats')
                if len(values) >= MAX_LOOP_ITERATIONS:
                    raise VerilogResourceLimit(f'for loop exceeds {MAX_LOOP_ITERATIONS} iterations; reduce its compile-time bounds')
                seen.add(current.bits); values.append(current)
                current = evaluator.evaluate(step,32).resized(32,True)
            return values,current
        except VerilogResourceLimit: raise
        except VerilogError as error:
            raise VerilogError(f'for bounds and step must be compile-time expressions: {error.message}',error.location) from None

    @diagnostic
    def unroll(self, statement, constants=None, depth=0):
        if depth >= MAX_DEPTH: raise VerilogResourceLimit('loop expansion depth exceeds 64')
        constants = constants or {}
        self.elaborator.work(statement.location)
        substitutions = {}
        def substitute(expr):
            if id(expr) in substitutions: return substitutions[id(expr)]
            if expr.op == 'name' and expr.args[0] in constants:
                value = constants[expr.args[0]]
                result = Expr('signed_literal',(value.bits,32),expr.location)
            else:
                result = map_children(expr, substitute)
            substitutions[id(expr)] = result
            return result
        op,args = statement.op,statement.args
        if op == 'for':
            iterator,initial,condition,step,body = args
            if iterator in constants:
                raise VerilogError(f'nested for loop reuses iterator: {iterator}')
            if iterator not in self.definition.signals or self.definition.signals[iterator][3] != 'integer':
                raise VerilogError(f'for iterator must be a declared integer: {iterator}')
            def mentions(target):
                if target.op in ('select','indexed'):
                    return mentions(target.args[0])
                return (target.op == 'name' and target.args[0] == iterator) or any(
                    mentions(arg) for arg in target.args if isinstance(arg,Expr))
            for item in body.walk():
                if (item.op == 'assign' and mentions(item.args[0]) or
                        item.op == 'for' and item.args[0] == iterator):
                    raise VerilogError(f'for body must not assign its iterator: {iterator}')
            values,final = self.loop_values(iterator,initial,condition,step,constants)
            def set_iterator(value):
                return Statement('assign',(Expr('name',(iterator,),statement.location),
                    Expr('signed_literal',(value.bits,32),statement.location)),statement.location)
            items = []
            for value in values:
                items.extend((set_iterator(value),self.unroll(body,{**constants,iterator:value},depth+1)))
            items.append(set_iterator(final))
            return Statement('block',tuple(items),statement.location)
        return map_children(statement, lambda child:
            self.unroll(child,constants,depth+1) if isinstance(child,Statement) else substitute(child))

    @diagnostic
    def process(self, statement, initial=None, function=False):
        statement = self.unroll(statement)
        targets = {}
        for stmt in statement.walk():
            if stmt.op != 'assign': continue
            target = self.target(stmt.args[0])
            for name,index,_,_ in self.parts(target)[0]:
                signal = self.elaborator.module.signals[name]
                if signal.kind != 'reg':
                    raise VerilogError(f'procedural assignment requires reg: {name}',stmt.location)
                owned = targets.setdefault(name,set())
                owned.update([index] if isinstance(index,int) else range(signal.width))
        if function:
            targets = {s.name:set(range(s.width)) for s in self.signals.values()}
        environment = {name:[None if i in owned else bit(Expr('name',(name,)),i)
                             for i in range(self.elaborator.module.signals[name].width)] for name,owned in targets.items()}
        environment.update(initial or {})

        def read(expr,env):
            # Finish each expression before expanding calls, so enclosing AST
            # depth consumes worklist entries rather than Python stack frames.
            memo = {}
            pending = [(expr,False)]
            while pending:
                node,ready = pending.pop()
                if id(node) in memo: continue
                op,args = node.op,node.args
                try:
                    if op == 'name' and args[0] in env:
                        bits = env[args[0]]
                        if any(b is None for b in bits): raise VerilogError(f'read before definite assignment in always @*: {args[0]}')
                        result = packed(bits,self.elaborator.module.signals[args[0]].signed)
                    elif op == 'select' and args[0].op == 'name' and args[0].args[0] in env:
                        name,high,low = args[0].args[0],args[1],args[2]
                        if not 0 <= low <= high < len(env[name]): raise VerilogError('bit/part select is outside its signal range')
                        bits = env[name][low:high+1]
                        if any(b is None for b in bits): raise VerilogError(f'read before definite assignment in always @*: {name}')
                        result = packed(bits)
                    elif not ready:
                        pending.append((node,True))
                        pending.extend((child,False) for child in reversed(list(syntax_children(node))))
                        continue
                    else:
                        result = map_children(node,lambda child: memo[id(child)])
                        if op == 'call':
                            result = self.call(result.args[0],result.args[1:],node.location)
                    memo[id(node)] = replace(result,location=node.location)
                except VerilogError as error: raise error.at(node.location) from None
            return memo[id(expr)]

        def merge(condition,yes,no):
            result = {}
            for name in yes:
                bits = [None if a is None or b is None else a if a is b else Expr('?:',(condition,a,b),condition.location) for a,b in zip(yes[name],no[name])]
                if all(b is not None for b in bits):
                    value = self.elaborator.capture(packed(bits,self.elaborator.module.signals[name].signed))
                    bits = [bit(value,i) for i in range(len(bits))]
                result[name] = bits
            return result

        def execute(stmt,env,depth=0):
            if depth >= MAX_DEPTH: raise VerilogResourceLimit('procedural elaboration depth exceeds compiler bounds',stmt.location)
            op,args = stmt.op,stmt.args
            try:
                if op == 'block':
                    for item in args: env = execute(item,env,depth+1)
                    return env
                if op == 'assign':
                    parts,width,signed = self.parts(self.target(args[0]))
                    value = Expr('typed',(read(self.bind(args[1]),env),width,signed),args[1].location)
                    value = self.elaborator.capture(value)
                    # Capture all indices and the RHS in the old environment.
                    parts = [(name,index if isinstance(index,int) else (read(index[0],env),index[1]),offset,
                              read(guard,env) if guard is not None else None) for name,index,offset,guard in parts]
                    env = {name:list(bits) for name,bits in env.items()}
                    for name,index,offset,guard in parts:
                        if isinstance(index,int):
                            old = env[name][index]
                            env[name][index] = bit(value,offset) if guard is None else None if old is None else Expr('?:',(guard,bit(value,offset),old),stmt.location)
                        else:
                            base,delta = index
                            for i,old in enumerate(env[name]):
                                if old is not None:
                                    match = Expr('index_eq',(base,i-delta),stmt.location)
                                    if guard is not None: match = Expr('&&',(guard,match),stmt.location)
                                    env[name][i] = Expr('?:',(match,bit(value,offset),old),stmt.location)
                    return env
                if op == 'if':
                    condition = read(self.bind(args[0]),env)
                    self.elaborator.module.checks.append(condition)
                    return merge(condition,execute(args[1],env,depth+1),execute(args[2],env,depth+1))
                selector,items,default = args
                selector = read(self.bind(selector),env)
                labels = [read(self.bind(label),env) for group,_ in items for label in group]
                self.elaborator.module.checks.extend([selector,*labels])
                branches = [execute(item,env,depth+1) for _,item in items]
                result = execute(default,env,depth+1)
                if not default.args and branches and self.exhaustive(selector,labels): result = branches[-1]
                offset = len(labels)
                for (group,_),branch in reversed(list(zip(items,branches))):
                    offset -= len(group)
                    matches = [Expr('case_eq',(selector,*labels,i),selector.location) for i in range(offset,offset+len(group))]
                    condition = matches[0]
                    for match in matches[1:]: condition = Expr('||',(condition,match),selector.location)
                    result = merge(condition,branch,result)
                return result
            except VerilogError as error: raise error.at(stmt.location) from None

        result = execute(statement,environment)
        if function:
            return_signal = self.signals[self.definition.name]
            bits = result[return_signal.name]
            if any(b is None for b in bits): raise VerilogError(f'function return is not definitely assigned: {self.definition.name}')
            return self.elaborator.capture(packed(bits,return_signal.signed))
        for name,owned in targets.items():
            for index in sorted(owned):
                if result[name][index] is None: raise VerilogError(f'incomplete assignment would infer a latch: {name}[{index}]')
                self.elaborator.drive(name,index,result[name][index])

    def call(self,name,arguments,location):
        if name not in self.functions: raise VerilogError(f'unknown combinational function: {name}',location)
        definition,owner = self.functions[name]
        self.elaborator.called_functions.add((id(definition),owner))
        key = id(definition)
        if key in self.elaborator.function_stack: raise VerilogError(f'recursive function call: {name}',location)
        if len(self.elaborator.function_stack) >= MAX_FUNCTION_DEPTH:
            raise VerilogResourceLimit(f'function call depth exceeds {MAX_FUNCTION_DEPTH}',location)
        self.elaborator.function_calls += 1
        if self.elaborator.function_calls > MAX_FUNCTION_CALLS:
            raise VerilogResourceLimit(f'function expansion exceeds {MAX_FUNCTION_CALLS} calls; reduce repeated calls or loop bounds',location)
        inputs = [n for n,decl in definition.signals.items() if decl[0] == 'input']
        if len(arguments) != len(inputs): raise VerilogError(f'function {name} expects {len(inputs)} arguments, received {len(arguments)}',location)
        self.elaborator.function_stack.append(key)
        local = None
        previous_array_bits = self.elaborator.array_bits
        try:
            local = Scope(self.elaborator,definition,f'$fn{self.elaborator.function_calls}.',{},False,owner,function=True)
            initial = {}
            for argument,input_name in zip(arguments,inputs):
                width,signed = self.types.type_of(argument)
                signal = local.signals[input_name]
                value = Expr('typed',(Expr('typed',(argument,width,signed),location),signal.width,signal.signed),location)
                value = self.elaborator.capture(value)
                initial[signal.name] = [bit(value,i) for i in range(signal.width)]
            return local.process(definition.processes[0],initial,function=True)
        except VerilogError as error: raise error.at(location) from None
        finally:
            self.elaborator.function_stack.pop()
            self.elaborator.array_bits = previous_array_bits
            if local:
                for signal in local.signals.values():
                    del self.elaborator.module.signals[signal.name]
                    del self.elaborator.module.bit_drivers[signal.name]

    def exhaustive(self, selector, labels):
        width,signed = self.types.type_of(selector)
        if (1 << width) > len(labels): return False
        if not all(constant_expression(label,{}) for label in labels): return False
        types = [self.types.type_of(expr) for expr in [selector,*labels]]
        common_width,common_signed = max(t[0] for t in types),all(t[1] for t in types)
        evaluator = ConstantEvaluator({}, {})
        values = {evaluator.evaluate(label,common_width,common_signed).bits for label in labels}
        return all(Constant(i,width,signed).resized(common_width,common_signed).bits in values
                   for i in range(1 << width))


class Elaborator:
    def __init__(self, definitions, overrides, top):
        self.definitions,self.overrides,self.top = definitions,overrides,top
        self.module = Module('',{},{},{},set())
        self.count = 0
        self.expansions = self.generated_scopes = self.function_calls = self.array_bits = self.capture_bits = 0
        self.function_stack = []
        self.called_functions = set()
        self.scope_names = set()

    def work(self,location=None):
        self.expansions += 1
        if self.expansions > MAX_EXPANSIONS:
            raise VerilogResourceLimit(f'elaboration exceeds {MAX_EXPANSIONS} expanded statements/scopes; reduce nested loops or function calls',location)

    def capture(self,expression):
        from .frontend import ExpressionTypes
        width,signed = ExpressionTypes(self.module).type_of(expression)
        self.capture_bits += width
        if len(self.module.captures) >= MAX_CAPTURES or self.capture_bits > MAX_CAPTURE_BITS:
            raise VerilogResourceLimit(f'procedural expansion exceeds {MAX_CAPTURES} values or {MAX_CAPTURE_BITS} value bits; reduce loop bounds or function size',expression.location)
        identifier = len(self.module.captures)
        self.module.captures[identifier] = expression
        return Expr('captured',(identifier,width,signed),expression.location)

    def drive(self,name,index,value):
        if self.module.signals[name].direction == 'input':
            raise VerilogError(f'cannot drive input: {name}')
        drivers = self.module.bit_drivers[name]
        if drivers[index] is not None:
            raise VerilogError(f'multiple drivers for {name}[{index}]')
        drivers[index] = value

    def scope(self, name, prefix, overrides, stack):
        if name in stack:
            raise VerilogError(f'recursive module hierarchy: {" -> ".join((*stack,name))}')
        if len(stack) >= 16:
            raise VerilogResourceLimit('module hierarchy depth exceeds 16')
        self.count += 1
        if self.count > MAX_INSTANCES:
            raise VerilogResourceLimit(f'flattened design exceeds {MAX_INSTANCES} instances')
        if name not in self.definitions:
            raise VerilogError(f'unknown module: {name}')
        definition = self.definitions[name]
        scope = Scope(self,definition,prefix,overrides,not stack)
        if not stack:
            self.module.name = name
            self.module.parameters = scope.parameters
            self.module.localparams = {n for n,p in definition.parameters.items() if p.local}
        else:
            self.module.hierarchy.append(dict(path=prefix[:-1],module=name,
                parameters=[dict(name=n,value=str(v.integer),width=v.width,signed=v.signed,
                                 local=definition.parameters[n].local) for n,v in scope.parameters.items()]))
        self.populate(scope,stack+(name,))
        return scope

    def generated(self,parent,label,definition,stack,constants=None,location=None):
        if parent.depth >= 16:
            raise VerilogResourceLimit('generate scope depth exceeds 16; reduce generate nesting',location)
        self.generated_scopes += 1
        self.work(location)
        if self.generated_scopes > MAX_GENERATED_SCOPES:
            raise VerilogResourceLimit(f'generate expansion exceeds {MAX_GENERATED_SCOPES} scopes; reduce generate bounds',location)
        prefix = parent.prefix+label+'.'
        base_label = label.split('[',1)[0]
        declarations = parent.definition.signals.keys() | parent.definition.parameters.keys() | parent.definition.genvars | parent.definition.functions.keys()
        if prefix in self.scope_names or base_label in declarations or any(i.name == base_label for i in parent.definition.instances):
            raise VerilogError(f'duplicate generate scope or declaration: {prefix[:-1]}',location)
        self.scope_names.add(prefix)
        scope = Scope(self,definition,prefix,{},False,parent,constants)
        self.populate(scope,stack)

    def populate(self,scope,stack):
        definition,prefix = scope.definition,scope.prefix
        try:
            for target,value in definition.assignments: scope.assign(scope.target(target),scope.bind(value))
            for process in definition.processes: scope.process(process)
            for generate in definition.generates:
                try:
                    if generate.op == 'genfor':
                        iterator,initial,condition,step,label,body = generate.args
                        if iterator not in scope.genvars:
                            raise VerilogError(f'generate iterator must be a declared genvar: {iterator}')
                        values,_ = scope.loop_values(iterator,initial,condition,step,{})
                        for value in values:
                            self.generated(scope,f'{label}[{value.integer}]',body,stack,{iterator:value},generate.location)
                    elif generate.op == 'genif':
                        condition,yes_label,yes,no_label,no = generate.args
                        if scope.evaluator.evaluate(condition).bits:
                            self.generated(scope,yes_label,yes,stack,location=generate.location)
                        elif no is not None:
                            self.generated(scope,no_label,no,stack,location=generate.location)
                    else:
                        self.generated(scope,*generate.args,stack,location=generate.location)
                except VerilogError as error: raise error.at(generate.location) from None
            for instance in definition.instances:
                try:
                    overrides = {}
                    for parameter,expression in instance.parameters.items():
                        value = scope.evaluator.evaluate(expression)
                        overrides[parameter] = Expr('signed_literal' if value.signed else 'literal',(value.bits,value.width),expression.location)
                    child = self.scope(instance.module,prefix+instance.name+'.',overrides,stack)
                    ports = {n:s for n,s in child.signals.items() if definition_port(child.definition,n)}
                    if instance.ports.keys() != ports.keys():
                        raise VerilogError(f'connect every port exactly once on instance {prefix}{instance.name}')
                    for port,signal in ports.items():
                        expression = instance.ports[port]
                        direction = child.definition.signals[port][0]
                        if direction == 'input':
                            if expression is None: raise VerilogError(f'unconnected input: {prefix}{instance.name}.{port}')
                            value = scope.resolve(scope.bind(expression))
                            width,signed = scope.types.type_of(value)
                            child.assign(Expr('name',(signal.name,),instance.location),Expr('typed',(value,width,signed),expression.location))
                        elif expression is not None:
                            scope.assign(scope.target(expression),Expr('name',(signal.name,),instance.location))
                except VerilogError as error: raise error.at(instance.location) from None
            self.validate_functions(scope)
        except VerilogError as error: raise error.at(definition.location) from None

    def validate_functions(self,scope):
        # Unused declarations still obey the subset and their own expansion
        # budgets, without adding dead function circuits to the emitted font.
        for name,definition in scope.definition.functions.items():
            if (id(definition),scope) in self.called_functions: continue
            module = self.module
            previous = (self.function_calls,self.expansions,self.capture_bits,self.array_bits)
            self.module = Module('',{},{},{},set())
            self.function_calls = self.expansions = self.capture_bits = self.array_bits = 0
            try:
                arguments = []
                for direction,bounds,signed,_ in definition.signals.values():
                    if direction != 'input': continue
                    width = scope.evaluator.range_width(bounds) if bounds else 1
                    arguments.append(Expr('signed_literal' if signed else 'literal',(0,width),definition.location))
                scope.call(name,tuple(arguments),definition.location)
                from .frontend import ExpressionTypes
                types = ExpressionTypes(self.module)
                for expression in [*self.module.captures.values(),*self.module.checks]:
                    types.type_of(expression)
            finally:
                self.module = module
                self.function_calls,self.expansions,self.capture_bits,self.array_bits = previous

    def elaborate(self):
        if not self.definitions:
            raise VerilogError('at least one module is required')
        def referenced_modules(definition):
            result = {i.module for i in definition.instances}
            for generate in definition.generates:
                for value in generate.args:
                    if hasattr(value,'instances'): result.update(referenced_modules(value))
            return result
        referenced = set().union(*(referenced_modules(d) for d in self.definitions.values()))
        top = self.top
        if top is None:
            roots = self.definitions.keys()-referenced
            if not roots:
                raise VerilogError('recursive module hierarchy has no top module')
            if len(roots) != 1:
                raise VerilogError('ambiguous top module; select one with --top')
            top = next(iter(roots))
        if top not in self.definitions:
            raise VerilogError(f'unknown top module: {top}')
        self.scope(top,'',self.overrides,())
        if not self.module.outputs:
            raise VerilogError('at least one output port is required')
        for name,drivers in self.module.bit_drivers.items():
            if self.module.signals[name].direction == 'input': continue
            if any(value is None for value in drivers):
                raise VerilogError(f'undriven signal or bits: {name}',self.module.signals[name].location)
            self.module.assignments[name] = packed(drivers,self.module.signals[name].signed)
        return self.module


def definition_port(definition,name):
    return name in definition.signals and definition.signals[name][0] in ('input','output')
