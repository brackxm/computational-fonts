# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Small direct GSUB assembler for the Gardner register machine."""
from fontTools.otlLib.builder import buildCoverage, buildLookup, buildSingleSubstSubtable, buildMultipleSubstSubtable
from fontTools.ttLib.tables import otTables as ot


class Program:
    def __init__(self, font):
        self.font = font
        self.specs = {}
        self.stubs = {}

    def add(self, name, kind, data):
        assert name not in self.specs
        stub = self.font.add('link_' + name)
        self.font.lookup(name, [f'sub {stub} by {stub};'], [stub])
        self.stubs[stub] = name
        self.specs[name] = kind, data
        return name

    def single(self, name, mapping):
        return self.add(name, 'single', mapping)

    def multiple(self, name, mapping):
        return self.add(name, 'multiple', mapping)

    def context(self, name, rules):
        # Rule = (input coverages, calls, backtrack[, lookahead]).
        return self.add(name, 'context', rules)

    def exact(self, name, rules):
        """Pack exact opening positions without a separate coverage per cell."""
        return self.add(name, 'exact', rules)

    def install(self, font, schedule):
        lookups = font['GSUB'].table.LookupList.Lookup
        indices = {}
        for i, lookup in enumerate(lookups):
            for sub in lookup.SubTable:
                sub = sub.ExtSubTable if lookup.LookupType == 7 else sub
                for source, target in getattr(sub, 'mapping', {}).items():
                    if source == target and source in self.stubs:
                        indices[self.stubs[source]] = i
        assert indices.keys() == self.specs.keys()
        names = font.getReverseGlyphMap()
        cache = {}

        def coverage(value):
            key = (value,) if isinstance(value, str) else tuple(value)
            if key not in cache:
                cache[key] = buildCoverage(key, names)
            return cache[key]

        for name, (kind, data) in self.specs.items():
            if kind == 'single':
                tables = [buildSingleSubstSubtable(data)]
            elif kind == 'multiple':
                tables, chunk, size = [], {}, 10
                for source, output in sorted(data.items(), key=lambda item:names[item[0]]):
                    cost = 6 + 2*len(output)
                    if chunk and size + cost > 56000:
                        tables.append(buildMultipleSubstSubtable(chunk))
                        chunk, size = {}, 10
                    chunk[source] = output
                    size += cost
                if chunk:
                    tables.append(buildMultipleSubstSubtable(chunk))
            elif kind == 'exact':
                # All rules have the same first glyph. Chunking keeps the
                # rule-set's 16-bit offsets small; extension offsets are 32-bit.
                tables = []
                for start in range(0, len(data), 400):
                    chunk = data[start:start+400]
                    sub = ot.ChainContextSubst()
                    sub.Format = 1
                    sub.Coverage = coverage(chunk[0][0][0])
                    entry = ot.ChainSubRuleSet()
                    entry.ChainSubRule = []
                    for inputs, target in chunk:
                        rule = ot.ChainSubRule()
                        rule.Backtrack = []
                        rule.BacktrackGlyphCount = 0
                        rule.Input = inputs[1:]
                        rule.InputGlyphCount = len(inputs)
                        rule.LookAhead = []
                        rule.LookAheadGlyphCount = 0
                        rec = ot.SubstLookupRecord()
                        rec.SequenceIndex = 0
                        rec.LookupListIndex = indices[target]
                        rule.SubstLookupRecord = [rec]
                        rule.SubstCount = 1
                        entry.ChainSubRule.append(rule)
                    entry.ChainSubRuleCount = len(entry.ChainSubRule)
                    sub.ChainSubRuleSet = [entry]
                    sub.ChainSubRuleSetCount = 1
                    tables.append(sub)
            else:
                tables = []
                for rule in data:
                    inputs, calls, back = rule[:3]
                    ahead = rule[3] if len(rule) == 4 else ()
                    sub = ot.ChainContextSubst()
                    sub.Format = 3
                    sub.BacktrackCoverage = [coverage(v) for v in reversed(back)]
                    sub.BacktrackGlyphCount = len(back)
                    sub.InputCoverage = [coverage(v) for v in inputs]
                    sub.InputGlyphCount = len(inputs)
                    sub.LookAheadCoverage = [coverage(v) for v in ahead]
                    sub.LookAheadGlyphCount = len(ahead)
                    sub.SubstLookupRecord = []
                    for position, target in calls:
                        rec = ot.SubstLookupRecord()
                        rec.SequenceIndex = position
                        rec.LookupListIndex = indices[target]
                        sub.SubstLookupRecord.append(rec)
                    sub.SubstCount = len(calls)
                    tables.append(sub)
            lookups[indices[name]] = buildLookup(tables, table='GSUB', extension=True)
        feature = next(r.Feature for r in font['GSUB'].table.FeatureList.FeatureRecord if r.FeatureTag == 'liga')
        feature.LookupListIndex = [indices[n] for n in schedule]
        feature.LookupCount = len(schedule)
        print('GSUB header bytes', 2+2*len(lookups)+sum(6+2*len(l.SubTable) for l in lookups),
              'extension records', sum(len(l.SubTable) for l in lookups), flush=True)
        return len(lookups)


def order_lookups(font, schedule):
    """HarfBuzz executes feature lookups in physical LookupList order."""
    table = font['GSUB'].table.LookupList
    order = [*schedule, *[i for i in range(len(table.Lookup)) if i not in schedule]]
    assert len(order) == len(set(order)) == len(table.Lookup)
    remap = {old:new for new,old in enumerate(order)}
    table.Lookup = [table.Lookup[i] for i in order]
    seen = set()

    def visit(value):
        if id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, ot.SubstLookupRecord):
            value.LookupListIndex = remap[value.LookupListIndex]
        elif isinstance(value, dict):
            for child in value.values():visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:visit(child)
        elif hasattr(value, '__dict__'):
            for child in vars(value).values():visit(child)
    visit(table.Lookup)
    for record in font['GSUB'].table.FeatureList.FeatureRecord:
        feature = record.Feature
        feature.LookupListIndex = [remap[i] for i in feature.LookupListIndex]
