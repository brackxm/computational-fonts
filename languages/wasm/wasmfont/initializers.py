"""Typed, bounded evaluation of module constant expressions.

These declarations contain no calls or runtime state. Keep their instructions
alongside the resolved values so writing a module preserves validation inputs.
"""
from dataclasses import dataclass

from .ir import OPS, sleb, uleb,heap_type
from .types import ReferenceType,value_kind


INTEGER_OPERATORS = {op:name for op,name in OPS.items() if name.endswith(('.add','.sub','.mul'))}


@dataclass(frozen=True)
class ConstantExpression:
    code: tuple

    def evaluate(self, expected, globals_=()):
        stack=[]
        for op,arg in self.code:
            if op in ('i32.const','i64.const'):
                typ=op[:3];stack.append((typ,arg&((1<<int(typ[1:]))-1)))
            elif op in ('ref.null','ref.func'):
                stack.append(('funcref',None if op=='ref.null' else arg))
            elif op=='global.get':
                if not 0<=arg<len(globals_):raise ValueError('initializer global must be previously defined')
                typ,mutable,value=globals_[arg]
                if mutable:raise ValueError('initializer global must be immutable')
                stack.append((value_kind(typ),value))
            elif op in INTEGER_OPERATORS.values():
                typ,operation=op.split('.')
                if len(stack)<2 or any(t!=typ for t,_ in stack[-2:]):
                    raise ValueError('constant expression operand type mismatch')
                _,right=stack.pop();_,left=stack.pop()
                if operation=='add':value=left+right
                elif operation=='sub':value=left-right
                else:value=left*right
                stack.append((typ,value&((1<<int(typ[1:]))-1)))
            else:raise NotImplementedError(f'unsupported constant instruction: {op}')
        if len(stack)!=1 or stack[0][0]!=value_kind(expected):raise ValueError('constant expression result type mismatch')
        if isinstance(expected,ReferenceType) and not expected.nullable and stack[0][1] is None:
            raise ValueError('non-null reference initializer cannot be null')
        return stack[0][1]


def decode_expression(data,pos):
    code=[]
    while pos<len(data):
        opcode=data[pos];pos+=1
        if opcode==0x0b:return ConstantExpression(tuple(code)),pos
        if opcode in (0x41,0x42):
            width=32 if opcode==0x41 else 64
            arg,pos=sleb(data,pos,width);op=f'i{width}.const'
        elif opcode==0xd0:
            heap,pos=heap_type(data,pos)
            op,arg='ref.null',None if heap=='func' else heap
        elif opcode in (0x23,0xd2):
            arg,pos=uleb(data,pos);op='global.get' if opcode==0x23 else 'ref.func'
        elif opcode in INTEGER_OPERATORS:op,arg=INTEGER_OPERATORS[opcode],None
        else:raise NotImplementedError(f'unsupported constant opcode: 0x{opcode:02x}')
        code.append((op,arg))
    raise ValueError('initializer missing end')
