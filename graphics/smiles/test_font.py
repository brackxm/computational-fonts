# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compare shaped diagrams with an independent graph parser."""
import json
import math
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
SHAPER = shutil.which('hb-shape')


def reference(source):
    if '.' in source:
        parts = [reference(fragment) for fragment in source.split('.')]
        return tuple(sorted(item for part in parts for item in part[index]) for index in (0,1))
    atoms, bonds, stack, rings = [], [], [], {}
    current, order, depth = None, 1, 0
    for token in re.findall(r'\[[^\]]+\]|Cl|Br|[A-Zbcnops]|[123()=#-]', source):
        if token[0].isalpha() or token[0]=='[':
            destination = (len(atoms), depth)
            element = 'bracket_'+re.match(r'\[(Cl|Br|[A-Za-z])',token)[1] if token[0]=='[' else token
            atoms.append(f'atom_{element}_{destination[0]}_{depth}')
            if current is not None:
                bonds.append(f'bond_{current[0]}_{current[1]}_{destination[0]}_{depth}_{order}_0')
            current, order = destination, 1
        elif token == '(':
            stack.append(current)
            depth += 1
        elif token == ')':
            current = stack.pop()
            depth -= 1
        elif token in '-=#':
            order = {'-':5, '=':2, '#':3}[token]
        elif token in rings:
            origin = rings.pop(token)
            bonds.append(f'bond_{origin[0]}_{origin[1]}_{current[0]}_{current[1]}_{order}_1')
            order = 1
        else:
            rings[token] = current
    return sorted(atoms), sorted(bonds)


def polygons_overlap(first, second):
    """Separating-axis check for convex painted bond/label bounds."""
    for polygon in (first,second):
        for a,b in zip(polygon,polygon[1:]+polygon[:1]):
            axis=(a[1]-b[1],b[0]-a[0])
            one=[p[0]*axis[0]+p[1]*axis[1] for p in first]
            two=[p[0]*axis[0]+p[1]*axis[1] for p in second]
            if max(one)<=min(two) or max(two)<=min(one):
                return False
    return True


@unittest.skipUnless(SHAPER, 'requires hb-shape')
class FontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='smiles-font-tests-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.generated = Path(cls.temporary.name) / 'rebuilt.ttf'
        subprocess.run([sys.executable, str(HERE/'build.py'), '--output', str(cls.generated)],
                       check=True, capture_output=True, timeout=240)
        cls.fonts = [HERE/'smiles-font.ttf', cls.generated]

    def shape(self, source, font, features='liga=1,calt=0'):
        result = subprocess.run([SHAPER, str(font), source, '--output-format=json',
                                 '--features='+features], capture_output=True, text=True, check=True, timeout=15)
        return json.loads(result.stdout)

    def check_graph(self, source):
        for font in self.fonts:
            with self.subTest(source=source, font=font.name):
                result = self.shape('{'+source+'}', font)
                names = [g['g'] for g in result]
                self.assertEqual(sorted(g for g in names if g.startswith('atom_')), reference(source)[0])
                self.assertEqual(sorted(g for g in names if g.startswith('bond_')), reference(source)[1])
                self.assertTrue(all(g in ('hidden','end','origin') or g.startswith(('atom_','bond_','bracket_label_','bracket_node_','fragment_gap_')) for g in names), names)
                self.assertEqual(sum(g['ax'] for g in result), 2400*(source.count('.')+1))

    def test_graphs(self):
        for source in ('C','CCO','CC(=O)O','CC(C)CO','CC(C(O)N)O','ClCCBr','CC#N',
                       'C1CCCCC1','C1=CC=CC=C1','C1CCC=1','C12CC1CC2',
                       'C1CC1C1CC1','C1(C)CC1','C(C1CC1)O','C(C)(N)O','CCCCCCCCCC','c1ccccc1','c1ccncc1','Cc1ccccc1','c1cc-ccc1','c1ccccc-1'):
            self.check_graph(source)

    def test_random_chains_and_branches(self):
        rng = random.Random(921)
        elements = ['C','O','N','Cl','Br','S','P','F']
        for _ in range(24):
            source = rng.choice(elements)
            for _ in range(rng.randint(1,4)):
                if rng.choice([True,False]):
                    source += '('+rng.choice(['','=','#'])+rng.choice(elements)+')'
                source += rng.choice(['','=','#'])+rng.choice(elements)
            self.check_graph(source)

    def test_nested_branch_returns_and_clock_limit(self):
        cases=['C(C(C))','C(C(C))O','CC(C(C))O','C(C(C))(C)',
               'C(-C(-C)(C))(-C(-C))(-C)',
               'C(-C)(-C)(-C)C(-C)(-C)C(-C)(-C)',
               'C'+'(-C)'*9,'C(C'+'(-C)'*8+')',
               'C(C(C))O.[Cl-]']
        # Also exercise different source spellings of supported trees with
        # consecutive closes, sibling branches, and explicit branch bonds.
        rng=random.Random(834)
        while len(cases)<70:
            size=rng.randrange(3,11)
            children={n:[] for n in range(size)}
            for n in range(1,size):
                parent=rng.choice([i for i in range(n) if len(children[i])<(4 if i==0 else 3)])
                children[parent].append(n)
            def emit(node,depth=0):
                return rng.choice(['C','N','O'])+''.join(
                    '('+rng.choice(['','-','=','#'])+emit(child,depth+1)+')'
                    for child in children[node])
            source=emit(0)
            depth=maximum=0
            for char in source:
                depth+=int(char=='(')-int(char==')')
                maximum=max(maximum,depth)
            if maximum<=2:
                cases.append(source)
        for source in cases:
            self.check_graph(source)
            for path in self.fonts:
                rendered=self.shape('{'+source+'}',path,'liga=1,calt=1')
                self.assertTrue(any(g['g'].startswith(('end','layout_')) for g in rendered),source)
                self.assertFalse(any(g['g'].startswith(('s_','p_','saved_','pop_','input_','closed_branch')) for g in rendered),source)

    def test_ligatures_are_required_and_input_remains_visible(self):
        for font in self.fonts:
            self.assertFalse(any(g['g'].startswith('atom_') for g in self.shape('{CCO}',font,'liga=0')))
            bare = self.shape('CCO',font)
            self.assertEqual(len(bare),3)
            self.assertGreater(sum(g['ax'] for g in bare),1000)

    def test_incomplete_input_has_no_complete_clean_diagram(self):
        for source in ('{C', '{C(}', '{C=}', '{CCCCCCCCCCC}', '{C1CC}', '{C()}', '{C.}', '{.C}', '{C..O}', '{C=.O}'):
            names = [g['g'] for g in self.shape(source,self.fonts[0])]
            self.assertTrue(any(g not in ('end','hidden') and not g.startswith(('atom_','bond_','bracket_label_','bracket_node_')) for g in names), names)

    def test_metadata_and_color_fallback(self):
        for path in self.fonts:
            with TTFont(path) as font:
                self.assertEqual(font['name'].getDebugName(1),'SMILES Diagrams')
                self.assertIn('Google',font['name'].getDebugName(0))
                self.assertIn('Michael Brackx',font['name'].getDebugName(0))
                self.assertEqual(font['OS/2'].fsType,0)
                self.assertIn('COLR',font)
                for name in ('atom_O_2_0','bond_0_0_1_0_1_0'):
                    self.assertTrue(font['glyf'][name].getCoordinates(font['glyf'])[1])
                    self.assertEqual(font['hmtx'][name][0],0)
                    self.assertIn(name,font['COLR'].ColorLayers)

    def test_regular_and_connected_ring_geometry(self):
        from layout import graph, scaffolds
        layouts = scaffolds()
        cases = ['C1'+'C'*(n-1)+'1' for n in range(3,11)]
        cases += ['C1=CC=CC=C1','C12CC1CC2','C1CC1C1CC1','C12(CCC1)CCC2',
                  'C1CC2(C1)CCC2','CC1CCCCC1','C1CCCCC1C','C1CC(C)CCC1',
                  'C1CCC2CCCCC2C1','CC(C)C','CC(C)CC','CC(C(C)C)C']
        for source in cases:
            _,edges = graph(source)
            signature = [(e.a,e.b,bool(e.ring)) for e in edges]
            index,layout = next((i,l) for i,l in enumerate(layouts)
                                if [(e.a,e.b,bool(e.ring)) for e in l[2]] == signature)
            positions = layout[3]
            for path in self.fonts:
                with self.subTest(source=source,font=path.name), TTFont(path) as font:
                    shaped = self.shape('{'+source+'}',path,'liga=1,calt=1')
                    names = [g['g'] for g in shaped]
                    self.assertIn('layout_'+str(index),names)
                    drawn = [n for n in names if n.startswith('chemical_bond_')]
                    joined = [n for n in names if n.startswith('joined_ring_')]
                    if joined:
                        self.assertEqual(joined,['joined_ring_'+str(index)])
                        self.assertEqual(len(drawn),0)
                        self.assertEqual(sum(n.startswith('ring_inner_') for n in names),source.count('='))
                    else:
                        self.assertEqual(len(drawn),len(edges))
                    for name,edge in zip(drawn,edges):
                        glyph = font['glyf'][name]
                        coordinates,ends,_ = glyph.getCoordinates(font['glyf'])
                        self.assertEqual(ends[0],3)
                        start = tuple((coordinates[0][j]+coordinates[3][j])/2 for j in range(2))
                        end = tuple((coordinates[1][j]+coordinates[2][j])/2 for j in range(2))
                        # A skeletal edge reaches its vertices. Parallel strokes
                        # on a multiple bond may have a small normal offset.
                        self.assertLess(math.dist(start,positions[edge.a[0]]),23)
                        self.assertLess(math.dist(end,positions[edge.b[0]]),23)
                    self.assertEqual(sum(g['ax'] for g in shaped),2400)

    def test_heteroatom_labels_and_bond_clearance(self):
        for path in self.fonts:
            with TTFont(path) as font:
                shaped = self.shape('{O1CCNCC1}',path,'liga=1,calt=1')
                labels = [g['g'] for g in shaped if g['g'].startswith('chemical_label_')]
                self.assertEqual(len(labels),2)
                self.assertTrue(any(n.startswith('chemical_label_O_') for n in labels))
                self.assertTrue(any(n.startswith('chemical_label_N_') for n in labels))
                for name in labels:
                    self.assertTrue(font['glyf'][name].getCoordinates(font['glyf'])[1])
                self.assertEqual(font['glyf']['atom_C_0_0'].numberOfContours,0)
                self.assertIn('isolated_carbon',[g['g'] for g in self.shape('{C}',path,'liga=1,calt=1')])

    def test_painted_bonds_clear_single_and_multi_letter_labels(self):
        cases=['O1CCNCC1','ClCCBr','BrCBr','C1CCC1CBr','C1CCC1CCCBr',
               'CC1CCC1CBr','Clc1ccccc1','c1cc(Br)ccc1','N=O','N#N']
        for path in self.fonts:
            with TTFont(path) as font:
                for source in cases:
                    with self.subTest(source=source,font=path.name):
                        shaped=self.shape('{'+source+'}',path,'liga=1,calt=1')
                        labels=[]
                        bonds=[]
                        for item in shaped:
                            name=item['g']
                            glyph=font['glyf'][name]
                            if glyph.numberOfContours and name.startswith(('atom_','chemical_label_')):
                                # Retain at least four font units of visible air,
                                # including the painted edge of the bond stroke.
                                x0,y0,x1,y1=glyph.xMin-4,glyph.yMin-4,glyph.xMax+4,glyph.yMax+4
                                labels.append((name,[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]))
                            if glyph.numberOfContours and name.startswith(('bond_','chemical_bond_')):
                                points,ends,_=glyph.getCoordinates(font['glyf'])
                                start=0
                                for end in ends:
                                    bonds.append((name,list(points[start:end+1])))
                                    start=end+1
                        self.assertTrue(labels)
                        self.assertTrue(bonds)
                        for bond,polygon in bonds:
                            for label,rectangle in labels:
                                self.assertFalse(polygons_overlap(polygon,rectangle),(source,bond,label))

    def test_aromatic_bonds_and_explicit_overrides(self):
        cases = [
            ('c1ccccc1',6,0,0),('c1ccncc1',6,0,0),('c1ccoc1',5,0,0),
            ('c1ccsc1',5,0,0),('b1ccccc1',6,0,0),('p1ccccc1',6,0,0),
            ('Cc1ccccc1',6,1,0),('Oc1ccccc1',6,1,0),('Clc1ccccc1',6,1,0),
            ('c1ccccc1C',6,1,0),('c1cc(-C)ccc1',6,1,0),
            ('c1cc-ccc1',5,1,0),('c1ccccc-1',5,1,0),('c1cc=ccc1',5,0,1),
            ('c1cc1-c1cc1',6,1,0),('c1ccc2ccccc2c1',11,0,0),
            ('C1CCCCC1',0,6,0),('C1=CC=CC=C1',0,3,3),
            ('c1ccc2CCCCc2c1',6,5,0),('C1CCc2ccccc2C1',6,5,0),
        ]
        for source,aromatic,single,double in cases:
            for path in self.fonts:
                with self.subTest(source=source,font=path.name), TTFont(path) as font:
                    shaped = self.shape('{'+source+'}',path,'liga=1,calt=1')
                    names = [g['g'] for g in shaped]
                    self.assertTrue(any(n.startswith('layout_') for n in names),names)
                    self.assertFalse(any('aromatic_start' in n or n.startswith('aromatic_input') for n in names),names)
                    bonds = [font['glyf'][n] for n in names if n.startswith('chemical_bond_')]
                    joined = [font['glyf'][n] for n in names if n.startswith('joined_ring_')]
                    inner = [font['glyf'][n] for n in names if n.startswith('ring_inner_')]
                    outer_edges = sum((g.endPtsOfContours[0]+1) for g in joined)
                    self.assertEqual(sum(g.numberOfContours==1 for g in bonds)+outer_edges-len(inner),aromatic+single)
                    self.assertEqual(sum(g.numberOfContours==2 for g in bonds)+len(inner),double)
                    self.assertEqual(len(bonds)+outer_edges,aromatic+single+double)
                    circles = [n for n in names if n.startswith('aromatic_circle_')]
                    expected = (0 if not aromatic or source in ('c1cc-ccc1','c1ccccc-1','c1cc=ccc1')
                                else 2 if source in ('c1cc1-c1cc1','c1ccc2ccccc2c1') else 1)
                    self.assertEqual(len(circles),expected)
                    self.assertEqual(len(set(circles)),len(circles))
                    for name in circles:
                        glyph = font['glyf'][name]
                        self.assertEqual(glyph.numberOfContours,2)
                        self.assertAlmostEqual(glyph.xMax-glyph.xMin,glyph.yMax-glyph.yMin,delta=1)
                        self.assertEqual(font['hmtx'][name][0],0)
                        self.assertIn(name,font['COLR'].ColorLayers)
                    self.assertEqual(sum(g['ax'] for g in shaped),2400)
        for source,symbol in [('c1ccncc1','N'),('c1ccoc1','O'),('c1ccsc1','S'),('b1ccccc1','B'),('p1ccccc1','P')]:
            names = [g['g'] for g in self.shape('{'+source+'}',self.fonts[0],'liga=1,calt=1')]
            self.assertEqual(sum(n.startswith('chemical_label_'+symbol+'_') for n in names),1)

    def test_joined_ring_corners(self):
        from layout import scaffolds
        from fontTools.pens.pointInsidePen import PointInsidePen
        for path in self.fonts:
            with TTFont(path) as font:
                for size in range(3,11):
                    source='C1'+'C'*(size-1)+'1'
                    positions=next(p for s,_,_,p in scaffolds() if s==source)
                    result=self.shape('{'+source+'}',path,'liga=1,calt=1')
                    joined=[g['g'] for g in result if g['g'].startswith('joined_ring_')]
                    self.assertEqual(len(joined),1)
                    outline=font['glyf'][joined[0]]
                    coordinates,ends,flags=outline.getCoordinates(font['glyf'])
                    self.assertEqual(list(ends),[size-1,2*size-1])
                    self.assertTrue(all(flag&1 for flag in flags))
                    # A hollow polygon is one continuous outline, with no bond
                    # rectangles left underneath it and opposite contour winding.
                    self.assertFalse(any(g['g'].startswith('chemical_bond_') for g in result))
                    outer=list(coordinates[:size])
                    inner=list(coordinates[size:])
                    def area(points):
                        return sum(p[0]*q[1]-p[1]*q[0] for p,q in zip(points,points[1:]+points[:1]))
                    self.assertLess(area(outer)*area(inner),0)
                    center=tuple(sum(p[i] for p in positions.values())/size for i in (0,1))
                    pen=PointInsidePen(font['glyf'],center)
                    outline.draw(pen,font['glyf'])
                    self.assertFalse(pen.getResult())
                    for i in range(size):
                        p,q=positions[i],positions[(i+1)%size]
                        midpoint=tuple((p[j]+q[j])/2 for j in (0,1))
                        pen=PointInsidePen(font['glyf'],midpoint)
                        outline.draw(pen,font['glyf'])
                        self.assertTrue(pen.getResult())
                        # Every outer and inner side lies half a stroke width
                        # from its bond centerline, including the closing side.
                        for contour in (outer,inner):
                            distance=min(abs((q[0]-p[0])*((a[1]+b[1])/2-p[1])-
                                             (q[1]-p[1])*((a[0]+b[0])/2-p[0]))/math.dist(p,q)
                                         for a,b in zip(contour,contour[1:]+contour[:1]))
                            self.assertAlmostEqual(distance,4.5,delta=.8)
                    self.assertIn(joined[0],font['COLR'].ColorLayers)
                for source in ('c1ccncc1','[cH]1ccccc1','[nH]1cccc1'):
                    result=self.shape('{'+source+'}',path,'liga=1,calt=1')
                    self.assertFalse(any(g['g'].startswith('joined_ring_') for g in result))
                benzene=self.shape('{c1ccccc1}',path,'liga=1,calt=1')
                self.assertEqual(sum(g['g'].startswith('joined_ring_') for g in benzene),1)
                self.assertEqual(sum(g['g'].startswith('aromatic_circle_') for g in benzene),1)
                kekule=self.shape('{C1=CC=CC=C1}',path,'liga=1,calt=1')
                self.assertEqual(sum(g['g'].startswith('ring_inner_') for g in kekule),3)

    def test_bracket_atoms_and_charges(self):
        cases = ['[nH]1cccc1','c1cc[nH]c1','[NH4+]','[O-]','CC(=O)[O-]',
                 '[CH3][NH3+]','[nH]1c[nH]cc1','[C]'*10,'[C]','[Cl-]','[N+2]','[N++]','[N---]',
                 '[NH0+1]','[nH+]1ccccc1','[CH]1CCCCC1','C[NH2+]C']
        for source in cases:
            self.check_graph(source)
            for path in self.fonts:
                with self.subTest(source=source,font=path.name), TTFont(path) as font:
                    shaped = self.shape('{'+source+'}',path,'liga=1,calt=1')
                    names = [g['g'] for g in shaped]
                    labels = [g for g in shaped if g['g'].startswith('bracket_label_')]
                    self.assertEqual(len(labels),source.count('['))
                    self.assertFalse(any(n.startswith(('bracket_token_','bracket_input_','s_','p_')) for n in names),names)
                    self.assertEqual(sum(g['ax'] for g in shaped),2400)
                    for label in labels:
                        self.assertTrue(font['glyf'][label['g']].getCoordinates(font['glyf'])[1])
                        self.assertNotEqual((label['dx'],label['dy']),(0,0))
                        self.assertIn(label['g'],font['COLR'].ColorLayers)
                    if '1' in source and source.startswith(('[nH]','c1','[nH+]')):
                        self.assertEqual(sum(n.startswith('aromatic_circle_') for n in names),1)
        for path in self.fonts:
            # Charge magnitude aliases have the same native label and position.
            for a,b in [('[N++]','[N+2]'),('[N+++]','[N+3]'),('[NH]','[NH1]'),('[N]','[NH0]')]:
                left = self.shape('{'+a+'}',path,'liga=1,calt=1')
                right = self.shape('{'+b+'}',path,'liga=1,calt=1')
                self.assertEqual([(g['g'],g['dx'],g['dy']) for g in left],[(g['g'],g['dx'],g['dy']) for g in right])
            # The parser moves both labels behind its final state. Their
            # independent anchors must still identify the first and second atoms.
            pair = self.shape('{[CH3][NH3+]}',path,'liga=1,calt=1')
            pen,positions = 0,[]
            for glyph in pair:
                if glyph['g'].startswith('bracket_label_'):
                    positions.append((pen+glyph['dx'],glyph['dy']))
                pen += glyph['ax']
            self.assertEqual(positions,[(110,790),(275,885)])
            bare = self.shape('[NH4+]',path)
            self.assertFalse(any(g['g'].startswith('bracket_label_') for g in bare))
            self.assertGreater(sum(g['ax'] for g in bare),1000)
            ammonium = self.shape('{[NH4+]}',path,'liga=1,calt=1')
            self.assertIn('bracket_label_N_4_4_R',[g['g'] for g in ammonium])
            ring = self.shape('{[nH]1cccc1}',path,'liga=1,calt=1')
            self.assertTrue(any(g['g']=='bracket_label_n_1_3_L' for g in ring))
            with TTFont(path) as font:
                # Counts sit below the baseline; charges rise above the letters.
                neutral = font['glyf']['bracket_label_N_4_3_R']
                positive = font['glyf']['bracket_label_N_4_4_R']
                self.assertLess(neutral.yMin,-45)
                self.assertGreater(positive.yMax,neutral.yMax+20)

    def test_bracket_charges_clear_painted_bonds(self):
        from fontTools.pens.pointInsidePen import PointInsidePen
        cases=['C[NH+](C)C','C[NH+2](C)C','C[NH-3](C)C',
               'C1CC[NH+](C)C1','[N+]12(CCC1)CCC2',
               '[N+]12(CC1)CCC2','[N+]12(CCCC1)CCC2',
               'C1C[N+]2(C1)CCC2','C[NH2+]C','CC(=O)[O-]',
               '[nH+]1ccccc1','C[NH+](C)C.[Cl-]']
        for path in self.fonts:
            with TTFont(path) as font:
                glyphs=font.getGlyphSet()
                for source in cases:
                    with self.subTest(source=source,font=path.name):
                        labels,bonds=[],[]
                        pen=0
                        for item in self.shape('{'+source+'}',path,'liga=1,calt=1'):
                            name=item['g']
                            outline=font['glyf'][name]
                            x,y=pen+item['dx'],item['dy']
                            pen+=item['ax']
                            if name.startswith('bracket_label_'):
                                labels.append((name,x,y,(outline.xMin+x,outline.yMin+y,outline.xMax+x,outline.yMax+y)))
                            elif name.startswith(('chemical_bond_','bond_')):
                                points,ends,_=outline.getCoordinates(font['glyf'])
                                start=0
                                for end in ends:
                                    bonds.append((name,[(a+x,b+y) for a,b in points[start:end+1]]))
                                    start=end+1
                        self.assertEqual(len(labels),source.count('['))
                        self.assertTrue(bonds)
                        for bond,quad in bonds:
                            p=tuple((quad[0][i]+quad[3][i])/2 for i in (0,1))
                            q=tuple((quad[1][i]+quad[2][i])/2 for i in (0,1))
                            length=math.dist(p,q)
                            steps=max(2,math.ceil(length/2))
                            for label,x,y,(x0,y0,x1,y1) in labels:
                                # Check actual label ink, including charges,
                                # on the stroke and just outside its edges.
                                # The empty space between stacked N/H labels
                                # must not count as a painted collision.
                                for i in range(steps+1):
                                    for offset in (-8,-4,0,4,8):
                                        px=p[0]+(q[0]-p[0])*i/steps-(q[1]-p[1])*offset/length
                                        py=p[1]+(q[1]-p[1])*i/steps+(q[0]-p[0])*offset/length
                                        if not (x0<=px<=x1 and y0<=py<=y1):
                                            continue
                                        inside=PointInsidePen(glyphs,(px-x,py-y))
                                        glyphs[label].draw(inside)
                                        self.assertFalse(inside.getResult(),(source,bond,label,px,py))
                # Without H, even a nominally downward label keeps its
                # formal charge above the element rather than as a subscript.
                charged=font['glyf']['bracket_label_N_0_4_D']
                self.assertGreater(charged.yMax,80)

    def test_disconnected_fragments(self):
        cases = ['[NH4+].[Cl-]', '[Cl-].[NH4+]', 'C.C', 'CCO.CN', 'c1ccccc1.[Cl-]',
                 'CC(=O)[O-].[NH4+]', '[nH]1cccc1.[Cl-]', 'C1CC1.C1CC1',
                 'C1CC1.[NH4+].CCO', 'CC(C(O)N)O.[Cl-]', 'C.C.C.C.C.C.C.C.C.C']
        for source in cases:
            self.check_graph(source)
            for path in self.fonts:
                with self.subTest(source=source,font=path.name), TTFont(path) as font:
                    shaped = self.shape('{'+source+'}',path,'liga=1,calt=1')
                    parts,part = [],[]
                    for glyph in shaped:
                        if glyph['g'].startswith('fragment_gap_'):
                            parts.append(part)
                            part=[]
                        else:
                            part.append(glyph)
                    parts.append(part)
                    self.assertEqual(len(parts),source.count('.')+1)
                    # A component must shape exactly as it does alone, including
                    # aromatic circles and charge attachment, without a bond to
                    # its neighbor. The separator alone supplies the spacing.
                    previous_right = None
                    pen = 0
                    for fragment,component in zip(source.split('.'),parts):
                        standalone = self.shape('{'+fragment+'}',path,'liga=1,calt=1')
                        self.assertEqual([(g['g'],g['dx'],g['dy'],g['ax']) for g in component],
                                         [(g['g'],g['dx'],g['dy'],g['ax']) for g in standalone])
                    for i,component in enumerate(parts):
                        left,right = float('inf'),float('-inf')
                        for glyph in component:
                            outline=font['glyf'][glyph['g']]
                            if outline.numberOfContours:
                                left=min(left,pen+glyph['dx']+outline.xMin)
                                right=max(right,pen+glyph['dx']+outline.xMax)
                            pen += glyph['ax']
                        if previous_right is not None:
                            self.assertGreater(left-previous_right,60)
                        previous_right=right
                        if i<len(parts)-1:
                            gap=[g for g in shaped if g['g'].startswith('fragment_gap_')][i]
                            self.assertLess(gap['ax'],0)
                            pen += gap['ax']
                    # Remove the otherwise-unused right side of every canvas.
                    self.assertLess(sum(g['ax'] for g in shaped),2400*len(parts))
        for path in self.fonts:
            self.assertEqual(sum(g['g']=='aromatic_circle_50' for g in self.shape('{[nH]1cccc1.[Cl-]}',path,'liga=1,calt=1')),1)
            bare=self.shape('[NH4+].[Cl-]',path,'liga=1,calt=1')
            self.assertFalse(any(g['g']=='origin' for g in bare))
            self.assertTrue(any(g['g']=='u002E' for g in bare))

    def test_reproducibility(self):
        self.assertEqual(self.fonts[0].read_bytes(),self.fonts[1].read_bytes())


if __name__ == '__main__':
    unittest.main()
