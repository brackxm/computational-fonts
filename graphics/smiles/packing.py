# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Share idempotent substitution maps without merging interpreter clock ticks."""
from fontTools.ttLib.tables import otTables


def compact_maps(font):
    table=font['GSUB'].table
    classes=font['GDEF'].table.GlyphClassDef.classDefs
    kept,indices,shared=[],{},{}
    direct={index for record in table.FeatureList.FeatureRecord
            for index in record.Feature.LookupListIndex}
    state_maps=[]
    for index,lookup in enumerate(table.LookupList.Lookup):
        subtables=[getattr(sub,'ExtSubTable',sub) for sub in lookup.SubTable]
        single=lookup.LookupType==1 or (lookup.LookupType==7 and all(
            sub.ExtensionLookupType==1 for sub in lookup.SubTable))
        key=None
        if single:
            mappings=[sub.mapping for sub in subtables]
            # Mark-filter flags cannot affect maps whose inputs are all
            # unclassified parser states. FEA creates separate copies of
            # these helpers for each ring's mark-filter set.
            if lookup.LookupFlag in (8,16) and all(
                    classes.get(name,0)==0 for mapping in mappings for name in mapping):
                lookup.LookupFlag=0
                if hasattr(lookup,'MarkFilteringSet'):
                    del lookup.MarkFilteringSet
            # Direct feature passes and context wrappers retain distinct
            # indices, so every interpreter tick still executes.
            combined={name:target for mapping in mappings for name,target in mapping.items()}
            if index not in direct and all(combined.get(target,target)==target for target in combined.values()):
                key=(lookup.LookupFlag,getattr(lookup,'MarkFilteringSet',None),
                     tuple(tuple(sorted(mapping.items())) for mapping in mappings))
        # Inline RESET/POP helpers are called by contexts that enumerate
        # their complete state inputs. Compatible helpers can share a union
        # map: no other input can reach that nested lookup. Never expand a
        # directly applied feature lookup or a drawing/mark substitution.
        merged=None
        state_map=single and index not in direct and lookup.LookupFlag==0 and len(mappings)==1 and combined and all(
            name.startswith('s_') and value.startswith('s_') for name,value in combined.items())
        if state_map:
            for target,mapping in state_maps:
                if any(name in mapping and mapping[name]!=value for name,value in combined.items()):
                    continue
                union=mapping|combined
                if all(union.get(value,value)==value for value in union.values()):
                    mapping.update(combined)
                    merged=target
                    break
        if merged is not None:
            indices[index]=merged
        elif key is not None and key in shared:
            indices[index]=shared[key]
        else:
            indices[index]=len(kept)
            if key is not None:
                shared[key]=len(kept)
            kept.append(lookup)
            if state_map:
                state_maps.append((indices[index],mappings[0]))
    visited=set()
    def rewrite(value):
        if id(value) in visited:
            return
        visited.add(id(value))
        if isinstance(value,otTables.SubstLookupRecord):
            value.LookupListIndex=indices[value.LookupListIndex]
        elif isinstance(value,(list,tuple)):
            for item in value:
                rewrite(item)
        elif hasattr(value,'__dict__'):
            for item in vars(value).values():
                rewrite(item)
    for lookup in kept:
        rewrite(lookup)
    for record in table.FeatureList.FeatureRecord:
        record.Feature.LookupListIndex=[indices[i] for i in record.Feature.LookupListIndex]
    table.LookupList.Lookup=kept
    table.LookupList.LookupCount=len(kept)
