"""MVP integer conversions and sign extension, with wrapping semantics."""
CONVERSIONS={0xa7:'i32.wrap_i64',0xac:'i64.extend_i32_s',0xad:'i64.extend_i32_u',0xc0:'i32.extend8_s',0xc1:'i32.extend16_s',0xc2:'i64.extend8_s',0xc3:'i64.extend16_s',0xc4:'i64.extend32_s'}

def convert(op, value):
    if op=='i32.wrap_i64':return value&0xffffffff
    if op in ('i64.extend_i32_s','i64.extend_i32_u'):
        v=value&0xffffffff
        if op.endswith('_s') and v&0x80000000:v-=1<<32
        return v&0xffffffffffffffff
    if op.startswith(('i32.extend','i64.extend')) and op.endswith('_s'):
        width=int(op[1:3]);bits=int(op.split('extend')[1].split('_')[0]);v=value&((1<<bits)-1)
        if v&(1<<(bits-1)):v-=1<<bits
        return v&((1<<width)-1)
    raise NotImplementedError(op)
