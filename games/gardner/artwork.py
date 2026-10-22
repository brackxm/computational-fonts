# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Original geometric chess artwork for the Gardner font."""
from fontgame import rect,circle


def polygon(p,points,reverse=False):
    points=list(reversed(points)) if reverse else points
    p.moveTo(points[0])
    for point in points[1:]:p.lineTo(point)
    p.closePath()


def draw_piece(p,x,y,piece):
    """White pieces have inset holes; Black pieces use filled silhouettes."""
    kind=piece.upper();outlined=piece.isupper()
    def poly(points,hole=False):polygon(p,[(x+a,y+b) for a,b in points],hole)
    def box(a,b,w,h,hole=False):poly([(a,b),(a+w,b),(a+w,b+h),(a,b+h)],hole)
    def orb(a,b,r,hole=False):circle(p,x+a,y+b,r,hole)
    box(-38,-57,76,12)
    if outlined:box(-32,-53,64,4,True)
    if kind=='P':
        poly([(-29,-43),(29,-43),(14,0),(-14,0)])
        orb(0,26,22)
        if outlined:
            poly([(-21,-37),(21,-37),(10,-6),(-10,-6)],True);orb(0,26,16,True)
    elif kind=='R':
        points=[(-28,-43),(28,-43),(23,22),(37,22),(37,54),(21,54),(21,41),(8,41),(8,54),(-8,54),(-8,41),(-21,41),(-21,54),(-37,54),(-37,22),(-23,22)]
        poly(points)
        if outlined:poly([(-21,-37),(21,-37),(16,28),(-16,28)],True)
    elif kind=='N':
        points=[(-32,-43),(32,-43),(23,-23),(28,9),(24,33),(14,48),(1,52),(-11,62),(-10,45),(-28,30),(-37,9),(-18,7),(-9,-6),(-23,-19)]
        poly(points);orb(1,33,3,True)
        if outlined:poly([(-19,-37),(22,-37),(15,-23),(20,7),(17,24),(11,32),(3,35),(-10,26),(-20,17),(-9,15),(0,-5),(-14,-22)],True)
    elif kind=='B':
        poly([(-30,-43),(30,-43),(14,-5),(23,17),(18,34),(0,59),(-18,34),(-23,17),(-14,-5)])
        poly([(-5,12),(0,7),(15,27),(11,32)],True)
        if outlined:poly([(-21,-37),(21,-37),(8,-7),(-8,-7)],True)
    elif kind=='Q':
        poly([(-30,-43),(30,-43),(23,-18),(37,40),(18,20),(0,49),(-18,20),(-37,40),(-23,-18)])
        for a,b in ((-37,44),(0,53),(37,44)):orb(a,b,6)
        if outlined:poly([(-21,-37),(21,-37),(15,-19),(-15,-19)],True)
    elif kind=='K':
        poly([(-31,-43),(31,-43),(17,-5),(23,23),(14,33),(-14,33),(-23,23),(-17,-5)])
        box(-6,36,12,31);box(-19,46,38,10)
        if outlined:poly([(-22,-37),(22,-37),(10,-6),(15,20),(9,26),(-9,26),(-15,20),(-10,-6)],True)
    else:raise ValueError(piece)
