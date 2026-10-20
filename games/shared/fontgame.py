# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Small OpenType toolkit for stateful game fonts; no game rules live here."""
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.otlLib.builder import buildCoverage, buildLookup
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables import otTables

START, END = '\ue000', '\ue001'
PIXELS = dict(zip('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', (
    '111101101101111','010110010010111','111001111100111','111001111001111',
    '101101111001001','111100111001111','111100111101111','111001010010010',
    '111101111101111','111101111001111','010101111101101','110101110101110',
    '111100100100111','110101101101110','111100110100111','111100110100100',
    '111100101101111','101101111101101','111010010010111','001001001101111',
    '101101110101101','100100100100111','101111111101101','101111111111101',
    '111101101101111','111101110100100','111101101111001','110101110101101',
    '111100111001111','111010010010010','101101101101111','101101101101010',
    '101101111111101','101101010101101','101101010010010','111001010100111')))


def rect(pen,x,y,w,h):
    pen.moveTo((x,y)); pen.lineTo((x+w,y)); pen.lineTo((x+w,y+h)); pen.lineTo((x,y+h)); pen.closePath()


def lettering(pen,text,x,y,size=7):
    for char in text:
        for i,pixel in enumerate(PIXELS.get(char,'0'*15)):
            if pixel == '1':
                rect(pen,x+(i%3)*size,y+(4-i//3)*size,size,size)
        x += 4*size


def centered_lettering(pen,text,center_x,y,size=9):
    lettering(pen,text,center_x-2*size*len(text),y,size)


def circle(pen,x,y,r,reverse=False):
    sign=-1 if reverse else 1
    pen.moveTo((x+r,y))
    for control,end in (((x+r,y+sign*r),(x,y+sign*r)),((x-r,y+sign*r),(x-r,y)),
                        ((x-r,y-sign*r),(x,y-sign*r)),((x+r,y-sign*r),(x+r,y))):
        pen.qCurveTo(control,end)
    pen.closePath()


def components(names):
    """Group positioned glyphs without applying the overlay translation twice."""
    names=tuple(names)
    def draw(pen,shift):
        for name in names:pen.addComponent(name,(1,0,0,1,0,0))
    return draw


def group(names):
    return '['+' '.join(names)+']'


def clock_wrapper(font,index,names):
    context = otTables.ContextSubst()
    context.Format, context.GlyphCount = 3,1
    context.Coverage = [buildCoverage(names,font.getReverseGlyphMap())]
    record = otTables.SubstLookupRecord()
    record.SequenceIndex, record.LookupListIndex = 0,index
    context.SubstLookupRecord, context.SubstCount = [record],1
    return buildLookup([context],table='GSUB',extension=True)


class GameFont:
    def __init__(self,family,width=1800,height=1000):
        self.family,self.width,self.height = family,width,height
        self.palette=('30484c','246b72','ae4a3c','bd872a')
        self.glyphs,self.metrics,self.layers,self.order = {},{},{},[]
        self.definitions,self.lookups,self.coverages = [],[],{}
        for name in ('.notdef','hidden','begin','end'):
            self.add(name)
        self.raw = {chr(c):self.add(f'input_{c}') for c in range(32,128)}

    def add(self,name,draw=None,advance=0,color=None,overlay=True):
        if name in self.glyphs:
            raise ValueError('Duplicate glyph: '+name)
        pen = TTGlyphPen(self.glyphs)
        if draw:
            draw(pen,-self.width if overlay else 0)
        self.glyphs[name] = pen.glyph()
        self.metrics[name] = (advance,0)
        self.order.append(name)
        if color is not None:
            self.layers[name] = [(name,color)]
        return name

    def lookup(self,name,rules,coverage,expose=None):
        if not rules or name in self.coverages:
            raise ValueError('Empty or duplicate lookup: '+name)
        flag = 'lookupflag 0;'
        if expose is not None:
            self.definitions.append(f'@filter_{name} = {group(expose)};')
            flag = f'lookupflag UseMarkFilteringSet @filter_{name};'
        self.lookups.append(f'lookup {name} useExtension {{\n{flag}\n'+'\n'.join(rules)+f'\n}} {name};')
        self.coverages[name] = coverage

    def forward_program(self,initial,states,lasts,stopped,transitions,finish,*,inputs=None,preprocess=()):
        """Read a finite-state cursor program in one forward GSUB pass.

        Each transition replaces the current input token with its new
        cursor and optional last-move mark. It leaves the previous cursor as
        context for this lookup; cleanup deletes all but the latest values.
        No clock or turn limit is added. Optional preprocessors tokenize source
        after whitespace removal. Callers supply complete transitions/inputs.
        """
        if not states or not lasts or not stopped:
            raise ValueError('Forward programs require cursor, last-move, and stopped states')
        raw=list(self.raw.values()) if inputs is None else list(inputs)
        preprocess=tuple(preprocess)
        freeze=f'sub {group(stopped)} {group(raw)}\' by NULL;'
        self.lookup('SPACE',[f'sub {self.raw[" "]} by NULL;'],[self.raw[' ']])
        for name,rules,coverage in preprocess:self.lookup(name,rules,coverage)
        self.lookup('INIT',['sub begin by '+' '.join(initial)+';'],['begin'])
        self.lookup('TRANSITION',[freeze,*transitions],raw,states)
        self.lookup('FINISH',finish,['end'],states)
        self.lookup('LAST_CLEAN',[f'sub {group(lasts)}\' {group(lasts)} by NULL;'],lasts,lasts)
        self.lookup('STATE_CLEAN',[f'sub {group(states)}\' {group(states)} by NULL;'],states,states)
        return ['SPACE',*[name for name,_,_ in preprocess],'INIT','TRANSITION','FINISH','LAST_CLEAN','STATE_CLEAN']

    def save(self,output,before,stages,after,passes):
        fb = FontBuilder(1000,isTTF=True)
        fb.setupGlyphOrder(self.order)
        cmap = {ord(c):name for c,name in self.raw.items()}
        cmap.update({0xe100+ord(c):name for c,name in self.raw.items()})
        cmap.update({ord(START):'begin',ord(END):'end',9:self.raw[' '],10:self.raw[' '],13:self.raw[' ']})
        fb.setupCharacterMap(cmap)
        for name,glyph in self.glyphs.items():
            glyph.recalcBounds(self.glyphs)
            self.metrics[name] = (self.metrics[name][0],getattr(glyph,'xMin',0))
        fb.setupGlyf(self.glyphs); fb.setupHorizontalMetrics(self.metrics)
        fb.setupHorizontalHeader(ascent=self.height,descent=-30)
        psname = ''.join(c for c in self.family if c.isalnum())+'-Regular'
        fb.setupNameTable({'familyName':self.family,'styleName':'Regular',
            'fullName':self.family+' Regular','psName':psname,'uniqueFontIdentifier':psname+'-1.0',
            'version':'Version 1.0','copyright':'Copyright 2026 Michael Brackx',
            'licenseDescription':'Licensed under the Apache License, Version 2.0',
            'licenseInfoURL':'https://www.apache.org/licenses/LICENSE-2.0'})
        fb.setupOS2(sTypoAscender=self.height,sTypoDescender=-30,usWinAscent=self.height,usWinDescent=30,fsType=0)
        fb.setupPost(); fb.setupMaxp(); fb.setupCOLR(self.layers,version=0)
        fb.setupCPAL([[tuple(int(c[i:i+2],16)/255 for i in (0,2,4))+(1.,) for c in self.palette]])
        registers=[name for name in self.order if name.startswith('r_')]
        definitions=['languagesystem DFLT dflt;','languagesystem latn dflt;',
                     '@registers = '+group(registers)+';',
                     'table GDEF { GlyphClassDef , , @registers, ; } GDEF;',*self.definitions]
        schedule=[*before,*stages,*after]
        names=list(dict.fromkeys(schedule))
        if len(set(before)) != len(before) or set(names) != set(self.coverages):
            raise ValueError('Schedule every lookup; direct prelude lookups must be unique')
        feature='feature liga { '+' '.join('lookup '+name+';' for name in names)+' } liga;'
        font=fb.font
        addOpenTypeFeaturesFromString(font,'\n'.join(definitions+self.lookups+[feature]))
        liga=next(r.Feature for r in font['GSUB'].table.FeatureList.FeatureRecord if r.FeatureTag=='liga')
        if len(liga.LookupListIndex) != len(names):
            raise RuntimeError('Unexpected feature lookup grouping')
        indices=dict(zip(names,liga.LookupListIndex))
        lookups=font['GSUB'].table.LookupList
        liga.LookupListIndex=[indices[name] for name in before]
        for name in stages*passes+after:
            liga.LookupListIndex.append(len(lookups.Lookup))
            lookups.Lookup.append(clock_wrapper(font,indices[name],self.coverages[name]))
        liga.LookupCount=len(liga.LookupListIndex)
        lookups.LookupCount=len(lookups.Lookup)
        output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
        font.save(output)
        stats=(len(self.order),lookups.LookupCount,output.stat().st_size)
        print(f'Saved {output}: {stats[0]} glyphs, {stats[1]} lookups, {stats[2]:,} bytes')
        font.close()
        return stats
