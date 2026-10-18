"""Additional integer and control-flow instruction opcodes."""
EXTRA={0x00:'unreachable',0x01:'nop',0x02:'block',0x03:'loop',0x04:'if',0x05:'else',0x0c:'br',0x0d:'br_if',0x0e:'br_table',0x10:'call',0x1a:'drop',0x1b:'select'}
for width,base in ((32,0x46),(64,0x51)):
 for offset,name in enumerate(('eq','ne','lt_s','lt_u','gt_s','gt_u','le_s','le_u','ge_s','ge_u')):
  EXTRA[base+offset]=f'i{width}.{name}'
for width,base in ((32,0x6d),(64,0x7f)):
 for offset,name in enumerate(('div_s','div_u','rem_s','rem_u')):EXTRA[base+offset]=f'i{width}.{name}'
EXTRA.update({0x77:'i32.rotl',0x78:'i32.rotr',0x89:'i64.rotl',0x8a:'i64.rotr'})
