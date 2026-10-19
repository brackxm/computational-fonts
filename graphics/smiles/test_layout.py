# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Geometry checks independent of font substitution and outline generation."""
import math
import unittest
from layout import LENGTH, graph, regular, scaffolds


class LayoutTests(unittest.TestCase):
    def test_regular_polygons(self):
        for size in range(3,11):
            vertices = regular(size)
            for i,p in enumerate(vertices):
                self.assertAlmostEqual(math.dist(p,vertices[(i+1)%size]),LENGTH)
            area = abs(sum(p[0]*vertices[(i+1)%size][1]-p[1]*vertices[(i+1)%size][0]
                           for i,p in enumerate(vertices)))/2
            self.assertAlmostEqual(area,size*LENGTH**2/(4*math.tan(math.pi/size)))

    def test_aromatic_circle_geometry(self):
        from aromatic import circle_glyph,ring_circles
        expected_counts = {'C1CC1C1CC1':2,'C12CC1CC2':2,'C12(CCC1)CCC2':2,
                           'C1CCC2CCCCC2C1':2,'CC(C)C':0}
        for source,_,edges,positions in scaffolds():
            circles = ring_circles(edges,positions)
            if source in expected_counts:
                self.assertEqual(len(circles),expected_counts[source])
            for indices,center,radius in circles:
                self.assertGreater(radius,0)
                for index in indices:
                    edge = edges[index]
                    p,q = positions[edge.a[0]],positions[edge.b[0]]
                    distance = abs((q[0]-p[0])*(center[1]-p[1])-(q[1]-p[1])*(center[0]-p[0]))/math.dist(p,q)
                    self.assertLess(radius+4,distance)
                glyph = circle_glyph(center,radius)
                self.assertEqual(glyph.numberOfContours,2)
                coordinates,ends,_ = glyph.getCoordinates(None)
                # The inner contour must be a hole in monochrome renderers.
                signs,first = [],0
                for last in ends:
                    contour = coordinates[first:last+1]
                    signs.append(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(contour,contour[1:]+contour[:1])))
                    first=last+1
                self.assertLess(signs[0]*signs[1],0)

    def test_all_scaffold_edges_have_one_bond_length(self):
        signatures = set()
        for source,atoms,edges,positions in scaffolds():
            with self.subTest(source=source):
                self.assertEqual(len(atoms),len(positions))
                self.assertLessEqual(len(atoms),10)
                signature = tuple((e.a,e.b,bool(e.ring)) for e in edges)
                self.assertNotIn(signature,signatures)
                signatures.add(signature)
                for edge in edges:
                    self.assertAlmostEqual(math.dist(positions[edge.a[0]],positions[edge.b[0]]),LENGTH,delta=1.1)
                self.assertTrue(all(0<x<2400 and 0<y<1650 for x,y in positions.values()))


if __name__ == '__main__':
    unittest.main()
