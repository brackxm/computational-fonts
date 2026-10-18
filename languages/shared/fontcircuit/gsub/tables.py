"""Compact GSUB serializer with shared 0/1 write lookups.

Layout follows OpenType GSUB types 1, 6 (formats 1 and 2), and 7. Small batches
share filtering sets and use a common wildcard class for unrelated cells.
Headers and extension wrappers stay within both levels of Offset16 limits.

References: Microsoft OpenType specification, GSUB and Common Table Formats.
"""
from itertools import product
from bisect import bisect_left
import struct
from fontTools.ttLib import newTable
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.ttLib.tables import otTables
from fontTools.otlLib.builder import buildCoverage

MAX_LOOKUP_BATCH_SIZE=64


def u16(*values):
    if any(not 0<=v<=65535 for v in values):
        raise ValueError('GSUB layout exceeds a 16-bit offset or count')
    return struct.pack('>'+len(values)*'H',*values)


def coverage(ids):
    return u16(1,len(ids),*ids)


def block_offsets(blocks,start):
    """Offsets from a table's start to its consecutive variable-size blocks."""
    offsets=[]
    for block in blocks:
        offsets.append(start)
        start+=len(block)
    return offsets


def rule_set(rules):
    return u16(len(rules),*block_offsets(rules,2+2*len(rules)))+b''.join(rules)


def gate_subtable(group,circuit,gids):
    sources=circuit.wires[group[0]].sources
    rulesets=[]
    for position,destination in enumerate(group):
        rules=[]
        table=circuit.wires[destination].table
        for row,(pattern,result) in enumerate(zip(product((0,1),repeat=len(sources)),table)):
            context=[gids[f'w{s}_{v}'] for s,v in zip(sources,pattern)]
            # Earlier destinations in this same lookup have already been written.
            # Their values follow from the SAME at-most-four-bit gate inputs.
            context += [gids[f'w{prev}_{circuit.wires[prev].table[row]}'] for prev in group[:position]]
            backtrack=context[::-1]
            rules.append(u16(len(backtrack),*backtrack,1,0,1,0,result))
        rulesets.append(rule_set(rules))
    blocks=[*rulesets,coverage([gids[f'w{i}_u'] for i in group])]
    *offsets,coverage_at=block_offsets(blocks,6+2*len(group))
    return u16(1,coverage_at,len(group),*offsets)+b''.join(blocks)


def class_definition(mapping):
    ranges=[]
    for gid,value in sorted(mapping.items()):
        if ranges and ranges[-1][1]+1==gid and ranges[-1][2]==value:
            ranges[-1]=(ranges[-1][0],gid,value)
        else:ranges.append((gid,gid,value))
    return u16(2,len(ranges),*(item for span in ranges for item in span))


def truth_suffixes(table):
    """Disjoint newest-input-first decisions, stopping at a constant output.

    Rows use the same oldest-to-newest input order as Circuit.gate. A returned
    pattern constrains only that order's suffix; older inputs cannot affect its
    result. This shortens both the rule count and its backtrack context.
    """
    def visit(rows,pattern):
        result=table[rows[0]]
        if all(table[row]==result for row in rows):
            yield pattern,result
            return
        bit=1<<len(pattern)
        for value in (0,1):
            yield from visit([row for row in rows if bool(row&bit)==bool(value)],(value,*pattern))
    yield from visit(list(range(len(table))),())


def wildcard_class_definition(overrides,last_gid):
    """Class 1 everywhere except sparse operand overrides, without expansion."""
    ranges=[];at=0
    for gid,value in sorted(overrides.items()):
        if at<gid:ranges.append((at,gid-1,1))
        ranges.append((gid,gid,value));at=gid+1
    if at<=last_gid:ranges.append((at,last_gid,1))
    return u16(2,len(ranges),*(item for span in ranges for item in span))


def gate_contexts(group,circuit,exposed):
    """Each truth decision's destination, backtrack cells and required bits.

    Serialization and coalescing estimates use the same contexts. A context
    ends at the oldest required operand and lists cells newest first.
    """
    sources=circuit.wires[group[0]].sources
    for destination in group:
        preceding=[wire for wire in reversed(exposed) if wire<destination]
        for pattern,result in truth_suffixes(circuit.wires[destination].table):
            used=sources[len(sources)-len(pattern):]
            context=[wire for wire in preceding if used and wire>=used[0]]
            yield destination,context,dict(zip(used,pattern)),result


def batched_gate_subtable(group,circuit,gids,exposed,*,companions=()):
    """Format 2 rules skip other gates' cells through one wildcard class.

    A shared filtering set exposes the batch's sources and destinations. The
    rule constrains its own source bits and accepts every state of other cells.
    Coalesced groups also enumerate bounded intervening operand bits, keeping
    each destination's truth function independent of those extra bits.
    """
    groups=[group,*companions]
    destinations=sorted(wire for item in groups for wire in item)
    sources=sorted({source for item in groups for source in circuit.wires[item[0]].sources})
    back_classes={};source_classes={};next_class=2
    for wire in sources:
        for value in (0,1):
            back_classes[gids[f'w{wire}_{value}']]=next_class
            source_classes[wire,value]=next_class;next_class+=1
        # An uninitialized operand must never match a constrained input bit.
        if f'w{wire}_u' in gids:back_classes[gids[f'w{wire}_u']]=0
    rules={destination:[] for destination in destinations}
    for item in groups:
        for destination,context,values,result in gate_contexts(item,circuit,exposed):
            extra=[wire for wire in context if wire in sources and wire not in values]
            # Other groups' operands have distinct classes too. Enumerate only
            # those intervening bits, preserving the original don't-care rule.
            # These operands precede the destination and are already initialized
            # in tape order. Uninitialized operands fail closed.
            for pattern_extra in product((0,1),repeat=len(extra)):
                all_values={**values,**dict(zip(extra,pattern_extra))}
                classes=[source_classes[wire,all_values[wire]] if wire in all_values else 1
                         for wire in context]
                rules[destination].append(u16(len(classes),*classes,1,0,1,0,result))
    # Class zero has no rules; each destination's uninitialized glyph has its
    # own input class. Backtrack classes are independent of input classes.
    blocks=[*(rule_set(rules[wire]) for wire in destinations),
            coverage([gids[f'w{i}_u'] for i in destinations]),
            wildcard_class_definition(back_classes,len(gids)-1),
            class_definition({gids[f'w{i}_u']:n+1 for n,i in enumerate(destinations)}),
            class_definition({})]
    *offsets,coverage_at,back_at,input_at,lookahead_at=block_offsets(blocks,12+2*(len(destinations)+1))
    return (u16(2,coverage_at,back_at,input_at,lookahead_at,len(destinations)+1,0,*offsets)+
            b''.join(blocks))


def can_coalesce(groups,circuit,exposed):
    """Bound rule expansion and leave room for each subtable's Offset16 fields."""
    sources={source for group in groups for source in circuit.wires[group[0]].sources}
    size=1024  # Conservative allowance for headers, coverage and class tables.
    for group in groups:
        for _,context,values,_ in gate_contexts(group,circuit,exposed):
            extra=sum(wire in sources and wire not in values for wire in context)
            if extra>3:return False
            size+=(14+2*len(context))*(1<<extra)
    return size<=60000


def coalesced_packets(batch,circuit,exposed):
    """Share a subtable between adjacent groups with bounded rule expansion.

    At most three extra operand bits may occur in any rule. A conservative
    serialized-size bound also keeps every subtable's local Offset16 in range.
    Singleton batches retain Format 1 for the portable coverage-cache workaround.
    """
    packets=[];index=0
    while index<len(batch):
        pair=batch[index:index+2]
        count=2 if len(pair)==2 and can_coalesce(pair,circuit,exposed) else 1
        packets.append(pair[:count]);index+=count
    return packets


def lookup_layout(counts):
    """Place headers in two waves so both Offset16 levels remain in range."""
    cumulative=[0]
    for count in counts:cumulative.append(cumulative[-1]+8*count)
    # Keep the second wave's extension wrappers below one Offset16 window.
    split=bisect_left(cumulative,max(0,cumulative[-1]-65400))
    positions=[0]*len(counts);extensions=[[] for _ in counts]
    at=2+2*len(counts)
    for first,last in ((0,split),(split,len(counts))):
        for i in range(first,last):
            positions[i]=at
            at+=6+2*counts[i]+(2 if i>=2 else 0)
        for i in range(first,last):
            extensions[i]=list(range(at,at+8*counts[i],8));at+=8*counts[i]
    if any(position>65535 for position in positions):return None
    if any(extension-position>65535 for position,items in zip(positions,extensions) for extension in items):return None
    return positions,extensions,at


def gate_batches(groups,size,gids):
    """Keep batches in dependency order, with portable singleton exceptions.

    HarfBuzz 14.2.1's Format 2 binary coverage cache can mistake its empty 0xff
    sentinel for a negative hit at glyph IDs 0x7f00..0x7fff (hb-cache.hh and
    Coverage::get_coverage_binary). Format 1 avoids that cache. Isolate the
    affected groups rather than imposing that engine's bug on the font ABI.
    """
    batches=[];pending=[]
    for group in groups:
        if any(0x7f00<=gids[f'w{wire}_u']<=0x7fff for wire in group):
            if pending:batches.append(pending);pending=[]
            batches.append([group])
        else:
            pending.append(group)
            if len(pending)==size:batches.append(pending);pending=[]
    if pending:batches.append(pending)
    return batches


def attach_tables(font,circuit,live,names,*,batch_size=None,coalesce=None):
    gids={name:i for i,name in enumerate(names)}
    gates=[i for i in live if circuit.wires[i].kind=='gate']
    # Pair gates with identical source sets (e.g. full-adder sum and carry).
    # Each pair is scheduled at its first wire; all its sources precede that wire.
    groups=[];pending={}
    for i in gates:
        sources=circuit.wires[i].sources
        if sources in pending:
            pending.pop(sources).append(i)
        else:
            group=[i];groups.append(group);pending[sources]=group
    if batch_size is not None and (type(batch_size) is not int or not 1<=batch_size<=MAX_LOOKUP_BATCH_SIZE):
        raise ValueError(f'lookup batch size must be an integer from 1 to {MAX_LOOKUP_BATCH_SIZE}')
    candidates=range(1,MAX_LOOKUP_BATCH_SIZE+1) if batch_size is None else (batch_size,)
    # Preserve compact existing layouts; coalescing is a second capacity tier.
    if coalesce is not None and type(coalesce) is not bool:
        raise ValueError('lookup coalescing must be True, False, or None (automatic)')
    for merged,chosen in product((False,True) if coalesce is None else (coalesce,),candidates):
        batches=gate_batches(groups,chosen,gids)
        exposed_batches=[sorted({wire for group in batch for wire in (*circuit.wires[group[0]].sources,*group)})
                         for batch in batches]
        packets=[coalesced_packets(batch,circuit,exposed) if merged else [[group] for group in batch]
                 for batch,exposed in zip(batches,exposed_batches)]
        layout=lookup_layout([1,1]+[len(items) for items in packets])
        if layout is not None:break
    else:
        from .circuit import ResourceLimit
        raise ResourceLimit('GSUB lookup layout capacity exceeded; reduce the circuit or compilation bounds')
    # Shared SingleSubstFormat1 lookups: all scratch glyphs are ordered 0,1,u.
    scratch=[gids[f'w{i}_u'] for i in gates]
    payloads=[[struct.pack('>HHh',1,6,delta)+coverage(scratch)] for delta in (-2,-1)]
    payloads += [[gate_subtable(packet[0],circuit,gids) if len(batch)==1 else
                  batched_gate_subtable(packet[0],circuit,gids,exposed,companions=packet[1:])
                  for packet in items] for batch,exposed,items in zip(batches,exposed_batches,packets)]
    count=len(payloads)
    positions,extensions,payload_start=layout
    prefix=bytearray(payload_start)
    prefix[:2+2*count]=u16(count,*positions)
    payload_parts=[];at=payload_start
    for i,subtables in enumerate(payloads):
        header=u16(7,0 if i<2 else 0x10,len(subtables),*(pos-positions[i] for pos in extensions[i]))
        if i>=2:header+=u16(i-2)
        prefix[positions[i]:positions[i]+len(header)]=header
        for extension_pos,payload in zip(extensions[i],subtables):
            prefix[extension_pos:extension_pos+8]=struct.pack('>HHI',1,1 if i<2 else 6,at-extension_pos)
            payload_parts.append(payload);at+=len(payload)
    lookup_list=bytes(prefix)+b''.join(payload_parts)
    script_list=u16(1)+b'DFLT'+u16(8)+u16(4,0)+u16(0,0xffff,1,0)
    feature_list=u16(1)+b'calt'+u16(8)+u16(0,len(batches),*range(2,count))
    raw=struct.pack('>IHHH',0x00010000,10,10+len(script_list),10+len(script_list)+len(feature_list))
    raw+=script_list+feature_list+lookup_list
    gsub=DefaultTable('GSUB');gsub.data=raw;font['GSUB']=gsub
    gdef=newTable('GDEF');gdef.table=otTables.GDEF();gdef.table.Version=0x00010002
    gdef.table.GlyphClassDef=otTables.ClassDef()
    gdef.table.GlyphClassDef.classDefs={name:3 for name in names[2:]}
    gdef.table.AttachList=None;gdef.table.LigCaretList=None;gdef.table.MarkAttachClassDef=None
    sets=otTables.MarkGlyphSetsDef();sets.MarkSetTableFormat=1;sets.MarkSetCount=len(batches)
    sets.Coverage=[]
    for batch,exposed in zip(batches,exposed_batches):
        if len(batch)==1:
            group=batch[0]
            members=[f'w{s}_{v}' for s in circuit.wires[group[0]].sources for v in (0,1)]
            members += [f'w{i}_{v}' for i in group for v in (0,1,'u')]
        else:
            members=[f'w{s}_{v}' for s in exposed for v in (0,1,'u') if f'w{s}_{v}' in gids]
        sets.Coverage.append(buildCoverage(members,gids))
    gdef.table.MarkGlyphSetsDef=sets;font['GDEF']=gdef
    return len(gates),count,{'gate_groups':len(groups),'lookup_batch_size':chosen,
                            'unpacked_gate_groups':sum(len(batch)==1 for batch in batches),
                            'gate_subtables':sum(map(len,packets)),
                            'coalesced_gate_groups':sum(len(packet) for items in packets for packet in items if len(packet)>1)}
