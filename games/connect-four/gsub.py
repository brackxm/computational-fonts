# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: GPL-3.0-only
"""Shared GSUB helpers and explicitly guarded fixed-register stage programs."""
from io import StringIO

from fontTools.feaLib.builder import Builder
from fontTools.otlLib.builder import buildCoverage, buildLookup
from fontTools.ttLib.tables import otTables

MAX_CONTEXT = 64


def glyph_class(names):
    return '[' + ' '.join(names) + ']'


class RegisterTape:
    """Keep register membership and offsets together, in declaration order."""

    def __init__(self, **groups):
        self.slots = []
        self.offsets = {}
        for name, members in groups.items():
            self.offsets[name] = len(self.slots)
            self.slots.extend(members)

    def at(self, name, index=0):
        return self.offsets[name] + index


def context_lookup(font, slots, records):
    if not 1 <= len(slots) <= MAX_CONTEXT:
        raise ValueError('GSUB stage contexts must contain 1–64 registers')
    table = otTables.ContextSubst()
    table.Format = 3
    table.Coverage = [buildCoverage(names, font.getReverseGlyphMap()) for names in slots]
    table.GlyphCount = len(slots)
    table.SubstLookupRecord = []
    for slot, index in records:
        if not 0 <= slot < len(slots):
            raise ValueError('GSUB instruction targets a register outside its context')
        record = otTables.SubstLookupRecord()
        record.SequenceIndex, record.LookupListIndex = slot, index
        table.SubstLookupRecord.append(record)
    table.SubstCount = len(records)
    return buildLookup([table], table='GSUB', extension=True)


def append_stage(font, slots, records):
    """Append one shared stage; return its lookup index and anchor coverage."""
    low = min(slot for slot, _ in records)
    high = max(slot for slot, _ in records)
    stage = context_lookup(font, slots[low:high+1], [(slot-low, index) for slot, index in records])
    lookups = font['GSUB'].table.LookupList.Lookup
    index = len(lookups)
    lookups.append(stage)
    return index, slots[low]


class Program:
    def __init__(self, glyphs):
        self.definitions = ['languagesystem DFLT dflt;', 'languagesystem latn dflt;']
        self.definitions += ['@marks = ' + glyph_class(glyphs) + ';',
                             'table GDEF { GlyphClassDef , , @marks, ; } GDEF;']
        self.helpers = []
        self.calls = []
        self.filters = {}
        self.stages = []
        self.stage_start = 0

    def lookup(self, rules, slot=None, exposed=None):
        name = f'L{len(self.helpers)}'
        flag = 'lookupflag 0;'
        if exposed is not None:
            members = tuple(sorted(set(exposed)))
            if members not in self.filters:
                filter_name = f'@F{len(self.filters)}'
                self.filters[members] = filter_name
                self.definitions.append(filter_name + ' = ' + glyph_class(members) + ';')
            flag = 'lookupflag UseMarkFilteringSet ' + self.filters[members] + ';'
        self.helpers.append(f'lookup {name} useExtension {{\n{flag}\n' +
                            '\n'.join(rules) + f'\n}} {name};')
        if slot is not None:
            self.calls.append((slot, name))
        return name

    def stage(self, name, guard, anchor=None):
        """Finish a semantic stage; later edits cannot change its clock guard."""
        if self.stage_start == len(self.calls):
            raise ValueError(f'Empty GSUB stage: {name}')
        self.stages.append((name, self.stage_start, len(self.calls), guard, anchor))
        self.stage_start = len(self.calls)

    def attach(self, font, tape, init, finalizers, turns):
        if self.stage_start != len(self.calls):
            raise ValueError('GSUB instructions remain outside an explicit stage')
        feature = 'feature liga { lookup ' + init + '; } liga;'
        builder = Builder(font, StringIO('\n'.join(self.definitions + self.helpers + [feature])))
        builder.build()
        indices = {name: lookup.lookup_index for name, lookup in builder.named_lookups_.items()}
        table = font['GSUB'].table
        lookups = table.LookupList.Lookup
        records = [(slot, indices[name]) for slot, name in self.calls]
        filters = font['GDEF'].table.MarkGlyphSetsDef
        stages = []
        for name, first, last, guard, anchor in self.stages:
            index, coverage = append_stage(font, tape.slots, records[first:last])
            coverage = coverage if anchor is None else anchor
            filtering = len(filters.Coverage)
            filters.Coverage.append(buildCoverage(coverage + guard, font.getReverseGlyphMap()))
            stages.append((index, coverage, guard, filtering))
        filters.MarkSetCount = len(filters.Coverage)
        liga = next(record.Feature for record in table.FeatureList.FeatureRecord if record.FeatureTag == 'liga')
        liga.LookupListIndex = [indices[init]]
        # Shapers sort and deduplicate physical indices. Only these small,
        # distinct clocks repeat; the helper and stage programs stay shared.
        for _ in range(turns):
            for index, coverage, guard, filtering in stages:
                clock = context_lookup(font, [coverage, guard], [(0, index)])
                clock.LookupFlag, clock.MarkFilteringSet = 16, filtering
                liga.LookupListIndex.append(len(lookups))
                lookups.append(clock)
        for coverage, name in finalizers:
            liga.LookupListIndex.append(len(lookups))
            lookups.append(context_lookup(font, [coverage], [(0, indices[name])]))
        liga.LookupCount = len(liga.LookupListIndex)
        table.LookupList.LookupCount = len(lookups)
        return indices, records
