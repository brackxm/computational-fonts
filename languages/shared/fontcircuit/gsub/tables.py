"""Compact GSUB serializer with shared 0/1 write lookups.

Layout follows OpenType GSUB types 1, 6 (formats 1 and 2), and 7. Small batches
share filtering sets and use a common wildcard class for unrelated cells.
Headers and extension wrappers stay within both levels of Offset16 limits.
Identical rule sets and definitions share storage within bounded offset windows.

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


def pack_chained_subtables(subtables):
    """Share identical blocks across bounded runs of Format 1/2 subtables.

    Rule sets use local class numbers, so otherwise unrelated gates often
    serialize to identical bytes. Coverage and class definitions can be shared
    too. Bound windows by their actual headers and distinct blocks, rather
    than charging repeatedly for shared bytes. The old original-byte windows
    remain a fallback, so extending sharing never makes the result larger.
    Every rewritten Offset16 is forward and in range; offsets inside shared
    blocks remain unchanged.

    Returns the packed bytes and each subtable's new start, in original order.
    Lookup order, filtering sets, rule priority and glyph IDs are preserved.
    """
    subtables=list(subtables)
    original=_pack_chained_windows(subtables,by_unique=False)
    shared=_pack_chained_windows(subtables,by_unique=True)
    return min((original,shared),key=lambda result:len(result[0]))


def _pack_chained_windows(subtables,*,by_unique):
    """Serialize one bounded-window policy without changing any table fields."""
    output=bytearray();positions=[];pending=[];size=0;known=set()

    def flush():
        headers=bytearray();parts=[];shared={}
        at=sum(len(header) for header,_ in pending)
        for original,blocks in pending:
            start=len(headers)
            positions.append(len(output)+start)
            header=bytearray(original)
            for field,block in blocks.items():
                if block not in shared:
                    shared[block]=at;parts.append(block);at+=len(block)
                header[field:field+2]=u16(shared[block]-start)
            headers.extend(header)
        output.extend(headers)
        output.extend(b''.join(parts))

    for subtable in subtables:
        format=int.from_bytes(subtable[:2],'big')
        if format==1:
            count=int.from_bytes(subtable[4:6],'big')
            length=6+2*count
            fields=[2,*range(6,length,2)]
        elif format==2:
            count=int.from_bytes(subtable[10:12],'big')
            length=12+2*count
            fields=[2,4,6,8,*range(12,length,2)]
        else:
            raise ValueError('Expected chained contextual Format 1 or 2')
        offsets={field:int.from_bytes(subtable[field:field+2],'big') for field in fields}
        starts=sorted(set(offsets.values())-{0})
        ends=dict(zip(starts,[*starts[1:],len(subtable)]))
        blocks={field:subtable[start:ends[start]] for field,start in offsets.items() if start}
        distinct=set(blocks.values())
        cost=length+sum(map(len,distinct-known)) if by_unique else len(subtable)
        if pending and size+cost>60000:
            flush();pending=[];size=0;known=set()
            cost=length+sum(map(len,distinct)) if by_unique else len(subtable)
        pending.append((subtable[:length],blocks));size+=cost;known.update(distinct)
    if pending:flush()
    if len(output)>=sum(map(len,subtables)):
        return b''.join(subtables),block_offsets(subtables,0)
    return bytes(output),positions


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
    sparse=u16(2,len(ranges),*(item for span in ranges for item in span))
    if not mapping:return sparse
    first,last=min(mapping),max(mapping)
    # Format 1 is smaller for nearby operand/destination glyph IDs. Missing
    # entries retain OpenType's default class zero in either representation.
    if 6+2*(last-first+1)>=len(sparse):return sparse
    return u16(1,first,last-first+1,*(mapping.get(gid,0) for gid in range(first,last+1)))


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
    # Backtrack class zero is the wildcard, so unrelated glyphs need no
    # entries. Class one rejects uninitialized operands; initialized bits get
    # distinct classes starting at two. Input classes are independent.
    back_classes={};source_classes={};next_class=2
    for wire in sources:
        for value in (0,1):
            back_classes[gids[f'w{wire}_{value}']]=next_class
            source_classes[wire,value]=next_class;next_class+=1
        # An uninitialized operand must never match a constrained input bit.
        if f'w{wire}_u' in gids:back_classes[gids[f'w{wire}_u']]=1
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
                classes=[source_classes[wire,all_values[wire]] if wire in all_values else 0
                         for wire in context]
                rules[destination].append(u16(len(classes),*classes,1,0,1,0,result))
    # Class zero has no rules; each destination's uninitialized glyph has its
    # own input class. Backtrack classes are independent of input classes.
    blocks=[*(rule_set(rules[wire]) for wire in destinations),
            coverage([gids[f'w{i}_u'] for i in destinations]),
            class_definition(back_classes),
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
    Compatibility exceptions retain singleton Format 1; other singleton
    representations are compared by their serialized size.
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


def coverage_cache_exception(group,gids):
    """Groups requiring Format 1 for the portable HarfBuzz cache workaround."""
    return any(0x7f00<=gids[f'w{wire}_u']<=0x7fff for wire in group)


def gate_batches(groups,size,gids):
    """Keep batches in dependency order, with portable singleton exceptions.

    HarfBuzz 14.2.1's Format 2 binary coverage cache can mistake its empty 0xff
    sentinel for a negative hit at glyph IDs 0x7f00..0x7fff (hb-cache.hh and
    Coverage::get_coverage_binary). Format 1 avoids that cache. Isolate the
    affected groups rather than imposing that engine's bug on the font ABI.
    """
    batches=[];pending=[]
    for group in groups:
        if coverage_cache_exception(group,gids):
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
    if coalesce is not None and type(coalesce) is not bool:
        raise ValueError('lookup coalescing must be True, False, or None (automatic)')
    # Compare the smallest feasible batch in each policy. Coalescing can fit
    # much narrower batches, avoiding the long wildcard contexts of wide ones.
    # Explicit options keep their requested policy and batch size.
    best=None
    for merged in (False,True) if coalesce is None else (coalesce,):
        for chosen in candidates:
            batches=gate_batches(groups,chosen,gids)
            exposed_batches=[sorted({wire for group in batch for wire in (*circuit.wires[group[0]].sources,*group)})
                             for batch in batches]
            packets=[coalesced_packets(batch,circuit,exposed) if merged else [[group] for group in batch]
                     for batch,exposed in zip(batches,exposed_batches)]
            layout=lookup_layout([1,1]+[len(items) for items in packets])
            if layout is not None:break
        else:continue
        has_class_singletons=any(len(batch)==1 and not coverage_cache_exception(batch[0],gids)
                                 for batch in batches)
        # Singleton groups can also use local classes and shared truth rules.
        # Compare both encodings: very small circuits may prefer Format 1.
        for class_singletons in (False,True) if has_class_singletons else (False,):
            metrics=_attach_layout(font,circuit,gates,names,gids,groups,batches,
                                   exposed_batches,packets,layout,chosen,class_singletons=class_singletons)
            # Other font tables and the ABI do not depend on this layout choice.
            size=sum((len(font.getTableData(tag))+3)&~3 for tag in ('GSUB','GDEF'))
            if best is None or size<best[0]:
                best=(size,font['GSUB'],font['GDEF'],metrics)
        # Both policies serialize singleton batches identically.
        if chosen==1:break
    if best is None:
        from .circuit import ResourceLimit
        raise ResourceLimit('GSUB lookup layout capacity exceeded; reduce the circuit or compilation bounds')
    _,font['GSUB'],font['GDEF'],metrics=best
    return metrics


def _attach_layout(font,circuit,gates,names,gids,groups,batches,exposed_batches,packets,layout,chosen,
                   class_singletons=False):
    """Serialize a feasible layout; callers may compare alternative policies."""
    # Shared SingleSubstFormat1 lookups: all scratch glyphs are ordered 0,1,u.
    scratch=[gids[f'w{i}_u'] for i in gates]
    scratch_coverage=coverage(scratch)
    # Both write lookups cover the same scratch cells. Their six-byte headers
    # point forward to one shared coverage after the two headers.
    payloads=[[struct.pack('>HHh',1,offset,delta)] for offset,delta in ((12,-2),(6,-1))]
    payloads += [[gate_subtable(packet[0],circuit,gids)
                  if len(batch)==1 and (not class_singletons or coverage_cache_exception(packet[0],gids)) else
                  batched_gate_subtable(packet[0],circuit,gids,exposed,companions=packet[1:])
                  for packet in items] for batch,exposed,items in zip(batches,exposed_batches,packets)]
    count=len(payloads)
    positions,extensions,payload_start=layout
    prefix=bytearray(payload_start)
    prefix[:2+2*count]=u16(count,*positions)
    packed,offsets=pack_chained_subtables(payload for subtables in payloads[2:] for payload in subtables)
    zero,one=payloads[0][0],payloads[1][0]
    gate_start=payload_start+len(zero)+len(one)+len(scratch_coverage)
    targets=iter([payload_start,payload_start+len(zero),*(gate_start+offset for offset in offsets)])
    for i,subtables in enumerate(payloads):
        header=u16(7,0 if i<2 else 0x10,len(subtables),*(pos-positions[i] for pos in extensions[i]))
        if i>=2:header+=u16(i-2)
        prefix[positions[i]:positions[i]+len(header)]=header
        for extension_pos in extensions[i]:
            prefix[extension_pos:extension_pos+8]=struct.pack('>HHI',1,1 if i<2 else 6,next(targets)-extension_pos)
    lookup_list=bytes(prefix)+zero+one+scratch_coverage+packed
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
                            'class_singleton_groups':sum(1 for batch in batches if
                                class_singletons and len(batch)==1 and not coverage_cache_exception(batch[0],gids)),
                            'gate_subtables':sum(map(len,packets)),
                            'coalesced_gate_groups':sum(len(packet) for items in packets for packet in items if len(packet)>1)}
