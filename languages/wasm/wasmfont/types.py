"""Function-reference value types and structural keys for acyclic signatures."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceType:
    heap: str | int = 'func'
    nullable: bool = True


def is_reference(typ):
    return typ=='funcref' or isinstance(typ,ReferenceType)


def value_kind(typ):
    return 'funcref' if is_reference(typ) else typ


def signature_keys(types):
    """Resolve aliases once; recursive/GC type definitions remain unsupported."""
    keys=[];interned={}
    for params,results in types:
        def key(typ):
            if not is_reference(typ):return typ
            heap,nullable=(typ.heap,typ.nullable) if isinstance(typ,ReferenceType) else ('func',True)
            if isinstance(heap,int):
                if not 0<=heap<len(keys):raise NotImplementedError('recursive function types are unsupported')
                heap=('type',keys[heap])
            return ('ref',nullable,heap)
        signature=tuple(map(key,params)),tuple(map(key,results))
        if signature not in interned:interned[signature]=len(interned)
        keys.append(interned[signature])
    return keys


def signature_key(params,results,keys):
    def key(typ):
        if not is_reference(typ):return typ
        heap,nullable=(typ.heap,typ.nullable) if isinstance(typ,ReferenceType) else ('func',True)
        return ('ref',nullable,('type',keys[heap]) if isinstance(heap,int) else heap)
    return tuple(map(key,params)),tuple(map(key,results))
