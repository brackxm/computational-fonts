"""Additional integer, control-flow and reference instruction opcodes."""
EXTRA={0x00:'unreachable',0x01:'nop',0x02:'block',0x03:'loop',0x04:'if',0x05:'else',0x0c:'br',0x0d:'br_if',0x0e:'br_table',0x10:'call',0x11:'call_indirect',0x1a:'drop',0x1b:'select',0x1c:'select_t'}
for width,base in ((32,0x46),(64,0x51)):
 for offset,name in enumerate(('eq','ne','lt_s','lt_u','gt_s','gt_u','le_s','le_u','ge_s','ge_u')):
  EXTRA[base+offset]=f'i{width}.{name}'
for width,base in ((32,0x6d),(64,0x7f)):
 for offset,name in enumerate(('div_s','div_u','rem_s','rem_u')):EXTRA[base+offset]=f'i{width}.{name}'
EXTRA.update({0x77:'i32.rotl',0x78:'i32.rotr',0x89:'i64.rotl',0x8a:'i64.rotr'})
EXTRA.update({0x25:'table.get',0x26:'table.set',0xd0:'ref.null',0xd1:'ref.is_null',0xd2:'ref.func'})
EXTRA.update({0x12:'return_call',0x13:'return_call_indirect'})
EXTRA.update({0x14:'call_ref',0x15:'return_call_ref'})
EXTRA.update({0xd4:'ref.as_non_null',0xd5:'br_on_null',0xd6:'br_on_non_null'})
TAIL_CALLS={'return_call','return_call_indirect','return_call_ref'}

# Integer bulk-memory instructions under the 0xfc prefix.
BULK_MEMORY={'memory.init':0x08,'data.drop':0x09,'memory.copy':0x0a,'memory.fill':0x0b}
BULK_TABLE={'table.init':0x0c,'elem.drop':0x0d,'table.copy':0x0e,'table.grow':0x0f,'table.size':0x10,'table.fill':0x11}
