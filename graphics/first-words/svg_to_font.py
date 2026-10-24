# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Convert the collection's SVG fills and rounded strokes into ordered vector layers."""

from copy import deepcopy
import math
import re
import xml.etree.ElementTree as ET

import pathops
from fontTools.misc.transform import Identity, Transform
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import SVGPath

STYLE = {'fill': 'black', 'stroke': 'none', 'stroke-width': '1',
         'stroke-linecap': 'butt', 'stroke-linejoin': 'miter', 'stroke-miterlimit': '4'}
CAPS = dict(butt=pathops.LineCap.BUTT_CAP, round=pathops.LineCap.ROUND_CAP,
            square=pathops.LineCap.SQUARE_CAP)
JOINS = dict(miter=pathops.LineJoin.MITER_JOIN, round=pathops.LineJoin.ROUND_JOIN,
             bevel=pathops.LineJoin.BEVEL_JOIN)
SHAPES = {'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon'}


def parse_transform(value):
    transform = Identity
    remainder = re.sub(r'([A-Za-z]+)\s*\(([^)]*)\)', '', value).strip(' ,\t\r\n')
    if remainder:
        raise ValueError(f'Invalid SVG transform: {value}')
    for command, raw in re.findall(r'([A-Za-z]+)\s*\(([^)]*)\)', value):
        args = [float(v) for v in re.split(r'[\s,]+', raw.strip()) if v]
        if command == 'matrix' and len(args) == 6:
            operation = Transform(*args)
        elif command == 'translate' and len(args) in (1, 2):
            operation = Identity.translate(args[0], args[1] if len(args) == 2 else 0)
        elif command == 'scale' and len(args) in (1, 2):
            operation = Identity.scale(args[0], args[1] if len(args) == 2 else args[0])
        elif command == 'rotate' and len(args) in (1, 3):
            x, y = args[1:] if len(args) == 3 else (0, 0)
            operation = Identity.translate(x, y).rotate(math.radians(args[0])).translate(-x, -y)
        else:
            raise ValueError(f'Unsupported SVG transform: {command}({raw})')
        transform = transform.transform(operation)
    return transform


def close_fill(source):
    """SVG implicitly closes open subpaths for fills, but leaves strokes open."""
    result = pathops.Path()
    pen = result.getPen()
    class FillPen:
        def __getattr__(self, name):
            return pen.closePath if name == 'endPath' else getattr(pen, name)
    source.draw(FillPen())
    return result


def layers_from_svg(filename, units_per_em):
    root = ET.parse(filename).getroot()
    if root.get('viewBox') != '0 0 160 160':
        raise ValueError(f'{filename}: expected the collection\'s 160 × 160 viewBox')
    # One em of artwork, 0.06 em side padding, with y=144 near the baseline.
    scale = units_per_em / 160
    font_transform = Transform(scale, 0, 0, -scale, .06 * units_per_em, .9 * units_per_em)
    result = []

    def emit(shape, color, role, transform):
        if not color or color == 'none':
            return
        if not re.fullmatch(r'#[0-9A-Fa-f]{6}', color):
            raise ValueError(f'{filename}: unsupported paint {color}')
        total = font_transform.transform(transform)
        shape = shape.transform(*total)
        shape.convertConicsToQuads(.15)
        shape = pathops.simplify(shape, clockwise=True)
        if shape:
            result.append((shape, color.lower(), role))

    def walk(element, inherited, parent):
        tag = element.tag.rsplit('}', 1)[-1]
        style = {**inherited, **{key: element.get(key) for key in STYLE if key in element.attrib}}
        transform = parent.transform(parse_transform(element.get('transform', '')))
        if tag in SHAPES:
            # SVGPath parses geometry, while this walker supplies SVG paint order,
            # inheritance, group transforms and expansion of strokes before scaling.
            leaf = deepcopy(element)
            leaf.attrib.pop('transform', None)
            for key in list(leaf.attrib):
                if key in STYLE:
                    del leaf.attrib[key]
            wrapper = ET.Element('svg')
            wrapper.append(leaf)
            geometry = pathops.Path()
            SVGPath.fromstring(ET.tostring(wrapper)).draw(geometry.getPen())
            geometry.convertConicsToQuads(.01)
            if style['fill'] != 'none':
                emit(close_fill(geometry), style['fill'], 'fill', transform)
            if style['stroke'] != 'none' and float(style['stroke-width']) > 0:
                outline = pathops.Path(geometry)
                outline.stroke(float(style['stroke-width']), CAPS[style['stroke-linecap']],
                               JOINS[style['stroke-linejoin']], float(style['stroke-miterlimit']))
                emit(outline, style['stroke'], 'stroke', transform)
        elif tag not in {'svg', 'g', 'title', 'desc'}:
            raise ValueError(f'{filename}: unsupported SVG element {tag}')
        for child in element:
            walk(child, style, transform)

    walk(root, STYLE, Identity)
    if not result:
        raise ValueError(f'{filename}: drawing has no painted geometry')
    return result


def glyph_from_path(shape):
    pen = TTGlyphPen(None)
    shape.draw(Cu2QuPen(pen, max_err=.7, reverse_direction=False))
    return pen.glyph()


def monochrome_path(layers, ink='#314047'):
    """Keep visible outlines and details, with later fills knocking out earlier ink."""
    result = pathops.Path()
    for shape, color, role in layers:
        operation = pathops.PathOp.UNION if role == 'stroke' or color == ink else pathops.PathOp.DIFFERENCE
        result = pathops.op(result, shape, operation, clockwise=True)
    return result
