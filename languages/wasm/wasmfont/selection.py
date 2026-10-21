"""Shared bounded indexed reads, address decoding and snapshot alignment."""
from fontcircuit.gsub.circuit import Value


def lookup(circuit,values,index):
    if not values:raise ValueError('indexed read requires a nonempty array')
    known=circuit.known(index)
    zero=circuit.const(0,values[0].width)
    if known is not None:return values[known] if known<len(values) else zero
    count=1<<(len(values)-1).bit_length()
    layer=list(values)+[zero]*(count-len(values))
    for bit in range(count.bit_length()-1):
        layer=[circuit.mux(index.bits[bit],layer[i+1],layer[i]) for i in range(0,len(layer),2)]
    return layer[0]


def lookup_window(circuit,values,index,length):
    """Read consecutive entries, sharing a block selection and a short shift.

    Like the dynamic lookup tree, this uses the low index bits of a padded
    power-of-two array. Callers must check the logical range before using it.
    """
    if not 1<=length<=len(values):raise ValueError('indexed window must fit a nonempty array')
    if length==1:return [lookup(circuit,values,index)]
    count=1<<(len(values)-1).bit_length();width=values[0].width
    zero=circuit.const(0,width);padded=list(values)+[zero]*(count-len(values))
    known=circuit.known(index)
    if known is not None:return [padded[(known+i)%count] for i in range(length)]
    block_bits=(length-1).bit_length();block=1<<block_bits
    shifts=[bit for bit in range(block_bits) if index.bits[bit] not in (0,1)]
    fixed=sum(1<<bit for bit in range(block_bits) if index.bits[bit]==1)
    span=length+sum(1<<bit for bit in shifts)
    # Keep only entries reachable after applying the known alignment bits.
    # Wrapping matches the original low-bit lookup behavior.
    candidates=[Value(tuple(bit for i in range(span) for bit in padded[(start+fixed+i)%count].bits))
                for start in range(0,count,block)]
    selected=lookup(circuit,candidates,Value(index.bits[block_bits:]))
    window=[Value(selected.bits[i*width:(i+1)*width]) for i in range(span)]
    for bit in reversed(shifts):
        step=1<<bit
        remaining=sum(1<<lower for lower in shifts if lower<bit)
        window=[circuit.mux(index.bits[bit],window[i+step],window[i])
                for i in range(length+remaining)]
    return window


def selectors(circuit,index,count):
    known=circuit.known(index)
    if known is not None:return [int(known==i) for i in range(count)]
    predicates=[1]
    for bit in reversed(range((count-1).bit_length())):
        yes=index.bits[bit];no=circuit.NOT(yes)
        predicates=[test for parent in predicates for test in
                    (circuit.AND(parent,no),circuit.AND(parent,yes))]
    return predicates[:count]


def aligned(circuit,values,source,destination,output_count):
    """Align an immutable snapshot using a power-of-two barrel rotation."""
    if not values:raise ValueError('alignment requires a nonempty array')
    count=1<<(len(values)-1).bit_length();bits=count.bit_length()-1
    delta=circuit.add(Value(source.bits[:bits]),Value(destination.bits[:bits]),subtract=True)
    known=circuit.known(delta);zero=circuit.const(0,values[0].width)
    if known is not None:
        return [values[at] if at<len(values) else zero for i in range(output_count) for at in [(i+known)%count]]
    payload=list(values)+[zero]*(count-len(values))
    for bit in range(bits):
        step=1<<bit
        payload=[circuit.mux(delta.bits[bit],payload[(i+step)%count],value) for i,value in enumerate(payload)]
    return [payload[i%count] for i in range(output_count)]
