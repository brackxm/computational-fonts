# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Pack the large Sim error table into bounded class-context subtables."""
from fontTools.otlLib.builder import buildCoverage
from fontTools.ttLib.tables import otTables as ot


def partition(sets):
    """Glyphs with identical rule membership can share an OpenType class."""
    membership = {}
    for index, glyphs in enumerate(sets):
        for glyph in glyphs:
            membership.setdefault(glyph, []).append(index)
    classes, signatures = {}, {}
    for glyph, signature in membership.items():
        signature = tuple(signature)
        classes[glyph] = signatures.setdefault(signature, len(signatures)+1)
    definition = ot.ClassDef()
    definition.classDefs = classes
    return definition, [{classes[g] for g in glyphs} for glyphs in sets]


def class_context(rules, glyph_map):
    for rule in rules:
        assert rule.Format == 3 and rule.BacktrackGlyphCount == rule.InputGlyphCount == 1
        assert rule.LookAheadGlyphCount == 0
    table = ot.ChainContextSubst()
    table.Format = 2
    back = [r.BacktrackCoverage[0].glyphs for r in rules]
    inputs = [r.InputCoverage[0].glyphs for r in rules]
    table.BacktrackClassDef, back_classes = partition(back)
    table.InputClassDef, input_classes = partition(inputs)
    table.LookAheadClassDef = ot.ClassDef()
    table.LookAheadClassDef.classDefs = {}
    table.Coverage = buildCoverage(set(g for source in inputs for g in source), glyph_map)
    table.ChainSubClassSet = [ot.ChainSubClassSet() for _ in range(1+max(table.InputClassDef.classDefs.values()))]
    for item in table.ChainSubClassSet:
        item.ChainSubClassRule = []
    for source, backs, sources in zip(rules, back_classes, input_classes):
        for input_class in sorted(sources):
            for back_class in sorted(backs):
                rule = ot.ChainSubClassRule()
                rule.Backtrack, rule.Input, rule.LookAhead = [back_class], [], []
                rule.BacktrackGlyphCount, rule.InputGlyphCount, rule.LookAheadGlyphCount = 1, 1, 0
                rule.SubstLookupRecord = source.SubstLookupRecord
                rule.SubstCount = len(rule.SubstLookupRecord)
                table.ChainSubClassSet[input_class].ChainSubClassRule.append(rule)
    for item in table.ChainSubClassSet:
        item.ChainSubClassRuleCount = len(item.ChainSubClassRule)
    table.ChainSubClassSetCount = len(table.ChainSubClassSet)
    return table


def pack_layout(font):
    lookups = font['GSUB'].table.LookupList.Lookup
    feature = next(r.Feature for r in font['GSUB'].table.FeatureList.FeatureRecord if r.FeatureTag == 'liga')
    wrapper = lookups[feature.LookupListIndex[3]].SubTable[0].ExtSubTable
    errors = lookups[wrapper.SubstLookupRecord[0].LookupListIndex]
    assert errors.LookupType == 6
    source = errors.SubTable
    errors.SubTable = [class_context(source[i:i+128], font.getReverseGlyphMap()) for i in range(0, len(source), 128)]
    errors.SubTableCount = len(errors.SubTable)
    # Explicit extensions also support the pinned compiler's GSUB exporter.
    for lookup in lookups:
        if lookup.LookupType == 7:
            continue
        wrapped = []
        for table in lookup.SubTable:
            extension = ot.ExtensionSubst()
            extension.Format, extension.ExtensionLookupType = 1, lookup.LookupType
            extension.ExtSubTable = table
            wrapped.append(extension)
        lookup.LookupType, lookup.SubTable = 7, wrapped
        lookup.SubTableCount = len(wrapped)
