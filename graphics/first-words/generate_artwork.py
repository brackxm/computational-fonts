#!/usr/bin/env python3
# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Generate original first-words SVG illustrations and review sheets. No font build."""

from pathlib import Path
from html import escape
import argparse
import json
import math
import xml.etree.ElementTree as ET
from bundles import write_bundle
from word_labels import spellings, validate_labels

HERE = Path(__file__).resolve().parent
P = dict(ink='#314047', red='#EF7469', yellow='#F2CB67', green='#79AD86',
         blue='#89B9CC', brown='#A78062', cream='#F7DFBB', white='#FFF8E9',
         pink='#EFAB9F', purple='#A99AC6', orange='#ECA46B', gray='#B9C3C5',
         palegreen='#B6CCA0', darkbrown='#7E6150', highlight='#FFE5CE', ochre='#C89943')
ART = {}
CATEGORIES = {}


def attrs(values):
    return ' '.join(f'{k.replace("_", "-")}="{escape(str(P.get(v, v)), quote=True)}"'
                    for k, v in values.items() if v is not None)


def path(d, fill='none', **kw):
    return f'<path {attrs(dict(d=d, fill=fill, **kw))}/>'


def circle(x, y, r, fill='none', **kw):
    return f'<circle {attrs(dict(cx=x, cy=y, r=r, fill=fill, **kw))}/>'


def ellipse(x, y, rx, ry, fill='none', **kw):
    return f'<ellipse {attrs(dict(cx=x, cy=y, rx=rx, ry=ry, fill=fill, **kw))}/>'


def rect(x, y, w, h, fill='none', rx=4, **kw):
    return f'<rect {attrs(dict(x=x, y=y, width=w, height=h, rx=rx, fill=fill, **kw))}/>'


def line(d, **kw):
    return path(d, **kw)


def eye(x, y, r=3):
    return circle(x, y, r, 'ink', stroke='none')


def group(contents, transform='', **kw):
    return f'<g {attrs(dict(transform=transform or None, **kw))}>{contents}</g>'


def add(category, name, art):
    assert name not in ART, name
    ART[name] = art
    CATEGORIES.setdefault(category, []).append(name)


def wheel(x, y, r=12):
    return circle(x, y, r, 'ink') + circle(x, y, r * .38, 'white', stroke='none')


def food(base):
    for name in ('apple', 'banana'):
        add('Food', name, base[name])
    add('Food', 'pear',
        line('M80 43Q78 27 88 19') +
        path('M86 34Q100 17 116 26Q108 43 86 34Z', 'green') +
        path('M80 43C65 39 60 51 61 66C62 78 34 91 39 113C43 141 117 141 121 113C126 91 98 78 99 66C100 51 95 39 80 43Z', 'yellow') +
        line('M52 102Q48 113 58 119', stroke='white'))
    add('Food', 'orange', circle(80, 87, 48, 'orange') +
        line('M80 39V26') + path('M82 31Q98 13 119 27Q107 46 82 37Z', 'green') +
        line('M48 79Q45 92 51 101', stroke='white') +
        ''.join(circle(x,y,1.7,'brown',stroke='none') for x,y in [(105,98),(110,87),(101,111),(90,118)]))
    add('Food', 'lemon',
        path('M29 78Q28 70 39 67C54 30 108 29 123 66Q140 69 131 82C132 115 83 141 53 119Q30 105 29 88Q19 85 29 78Z','yellow') +
        line('M48 76Q65 52 86 54',stroke='white'))
    add('Food', 'strawberry',
        path('M39 61C24 83 57 133 80 140C103 133 136 83 121 61C111 43 49 43 39 61Z','red') +
        path('M80 56L60 34L62 56L35 49L52 69L79 62L106 69L125 49L98 56L100 34Z','green') +
        ''.join(line(f'M{x} {y}l1 5',stroke='cream',stroke_width=3) for x,y in [(54,81),(79,80),(104,81),(64,102),(90,104),(79,122)]))
    add('Food', 'cherry',
        line('M58 90Q50 49 88 25Q83 59 106 90') +
        path('M87 29Q106 15 125 30Q110 48 87 29Z','green') +
        circle(53,109,26,'red') + circle(108,111,26,'red') +
        line('M42 100l-1 7M97 102l-1 7',stroke='white'))
    add('Food', 'grapes',
        line('M80 40Q80 27 89 19') +
        path('M85 34Q97 14 121 29L111 43L95 47Z','green') +
        ''.join(circle(x,y,16,'purple') for x,y in [(61,57),(91,57),(47,83),(77,83),(107,83),(62,109),(92,109),(77,134)]))
    add('Food', 'watermelon',
        path('M23 47H137A57 86 0 0 1 23 47Z','green') +
        path('M32 48H128C124 93 103 121 80 121C57 121 36 93 32 48Z','red',stroke='none') +
        line('M23 47H137') +
        ''.join(ellipse(x,y,2.5,5,'ink',stroke='none') for x,y in [(52,67),(79,70),(107,67),(65,92),(94,92)]))
    add('Food', 'pineapple',
        path('M80 51L44 26L55 58L80 69L105 58L116 26L87 44L82 15L68 21Z','green') +
        rect(44,54,72,88,'yellow',rx=32) +
        path('M49 74L106 131M44 96L90 142M63 57L116 110M110 73L54 132M116 95L70 142M96 57L44 109',stroke='brown',stroke_width=3,fill='none'))
    add('Food', 'carrot',
        path('M76 48Q58 18 49 30L69 56Q43 38 38 51L66 67Z','green') +
        path('M69 53C84 40 111 55 110 72C107 94 62 131 35 141C32 111 47 70 69 53Z','orange') +
        line('M61 73l15 9M48 95l13 8M83 61l12 9'))
    add('Food', 'tomato',
        ellipse(80,92,51,43,'red') +
        path('M80 58L60 37L65 59L41 60L65 71L80 63L95 72L119 59L97 58L100 38Z','green') +
        line('M80 57Q80 35 89 26') + line('M45 88Q42 100 50 107',stroke='white'))
    add('Food', 'potato',
        path('M35 72C38 43 69 44 88 34C115 20 137 50 127 78C118 103 121 130 88 137C56 144 25 123 29 98Z','cream') +
        ''.join(line(f'M{x-3} {y}q3-3 6 0',stroke='brown',stroke_width=3) for x,y in [(61,66),(103,58),(48,98),(91,95),(77,120)]))
    add('Food', 'broccoli',
        path('M70 86L65 137H96L90 88L106 69L89 68L80 85L67 67L54 73Z','palegreen') +
        path('M41 88C16 82 20 55 39 50C36 30 61 22 75 34C89 15 114 28 115 47C140 46 144 77 122 88C113 101 96 96 82 91C65 102 52 99 41 88Z','green') +
        line('M51 61Q58 51 68 59M92 54Q105 48 113 61',stroke='palegreen',stroke_width=4))
    add('Food', 'mushroom',
        path('M68 86L61 130Q80 143 99 130L92 86Z','cream') +
        path('M24 81C29 42 56 25 80 25C104 25 131 42 136 81Q80 104 24 81Z','red') +
        ''.join(circle(x,y,r,'white',stroke='none') for x,y,r in [(57,60,9),(92,46,8),(108,73,8),(78,79,6)]))
    add('Food', 'bread',
        path('M43 63C16 55 24 26 50 26H110C136 26 144 55 117 63V132H43Z','brown') +
        path('M51 60C30 56 35 37 53 37H107C125 37 130 56 109 60V121H51Z','cream',stroke='none') +
        ''.join(circle(x,y,2,'brown',stroke='none') for x,y in [(66,72),(94,78),(77,104)]))
    add('Food', 'cheese',
        path('M29 76L103 33L133 91L61 132L29 110Z','yellow') +
        path('M29 76L61 96L133 57V91L61 132V96Z','yellow') +
        path('M29 76L103 33L133 57L61 96Z','cream') +
        ellipse(79,66,9,5,'yellow',stroke='none') +
        circle(82,105,7,'orange',stroke='none') + circle(114,83,5,'orange',stroke='none') +
        circle(43,101,5,'orange',stroke='none'))
    add('Food', 'egg',
        path('M80 23C58 23 34 69 34 97C34 124 54 138 80 138C106 138 126 124 126 97C126 69 102 23 80 23Z','white') +
        line('M55 76Q49 88 51 98',stroke='cream',stroke_width=7))
    add('Food', 'cake',
        rect(34,75,92,59,'cream') + rect(34,98,92,13,'pink',rx=0,stroke='none') +
        path('M28 75Q80 58 132 75V89Q121 100 111 88Q102 106 91 88Q80 104 69 88Q57 103 48 88Q37 100 28 89Z','pink') +
        line('M80 68V40') +
        path('M80 17C67 31 67 39 80 40C93 39 93 31 80 17Z','yellow'))
    add('Food', 'ice-cream',
        path('M49 80L80 142L111 80Z','cream') +
        line('M59 97l30 21M72 91l25 17M102 98l-29 21',stroke='brown',stroke_width=3) +
        path('M40 74C30 56 41 41 53 40C50 19 80 14 90 32C113 25 129 45 118 62C138 77 119 94 102 83Q91 99 80 84Q65 101 54 84Q39 90 40 74Z','pink'))


def animals(base):
    for name in ('cat', 'dog'):
        add('Animals', name, base[name])
    add('Animals', 'rabbit',
        ellipse(58,48,14,35,'white') + ellipse(102,48,14,35,'white') +
        ellipse(58,45,5,22,'pink',stroke='none') + ellipse(102,45,5,22,'pink',stroke='none') +
        ellipse(80,101,43,36,'white') + eye(63,94) + eye(97,94) +
        path('M74 108Q80 103 86 108L80 114Z','pink') +
        line('M80 114V119M52 112L30 107M52 120L31 124M108 112L130 107M108 120L129 124'))
    add('Animals', 'mouse',
        circle(42,51,25,'gray') + circle(118,51,25,'gray') +
        circle(42,51,13,'pink',stroke='none') + circle(118,51,13,'pink',stroke='none') +
        path('M42 91C33 48 127 48 118 91L94 128Q80 145 66 128Z','gray') +
        eye(63,86) + eye(97,86) + circle(80,118,6,'pink') +
        line('M61 109L30 103M62 119L30 124M99 109L130 103M98 119L130 124'))
    add('Animals', 'bear',
        circle(43,46,20,'brown') + circle(117,46,20,'brown') +
        circle(43,46,9,'cream',stroke='none') + circle(117,46,9,'cream',stroke='none') +
        ellipse(80,90,52,47,'brown') + eye(59,78) + eye(101,78) +
        ellipse(80,109,24,19,'cream',stroke='none') +
        path('M71 102Q80 97 89 102Q87 111 80 112Q73 111 71 102Z','ink') +
        line('M80 112V118Q72 125 67 119M80 118Q88 125 93 119'))
    add('Animals', 'fox',
        path('M36 82L29 24L67 47Q80 41 93 47L131 24L124 82L136 90L101 126L80 140L59 126L24 90Z','orange') +
        path('M40 46L46 70L60 57Z','darkbrown',stroke='none') +
        path('M120 46L114 70L100 57Z','darkbrown',stroke='none') +
        path('M33 90Q55 87 80 120Q105 87 127 90L101 126L80 140L59 126Z','white',stroke='none') +
        eye(59,82) + eye(101,82) + path('M72 120H88L80 129Z','ink'))
    add('Animals', 'pig',
        path('M39 64L27 32Q57 24 68 52M121 64L133 32Q103 24 92 52','pink') +
        ellipse(80,89,51,47,'pink') + eye(59,76) + eye(101,76) +
        ellipse(80,105,25,19,'red') +
        ellipse(70,105,3,5,'ink',stroke='none') + ellipse(90,105,3,5,'ink',stroke='none'))
    add('Animals', 'cow',
        path('M47 52Q24 48 19 67Q39 81 55 68M113 52Q136 48 141 67Q121 81 105 68','cream') +
        path('M52 48Q34 29 48 19L64 45M108 48Q126 29 112 19L96 45','white') +
        path('M48 59C45 35 115 35 112 59L119 104Q116 135 80 138Q44 135 41 104Z','white') +
        path('M48 59Q63 44 75 53Q77 68 64 75Q53 78 46 71Z','brown',stroke='none') +
        eye(61,82) + eye(99,82) + ellipse(80,113,35,23,'pink') +
        ellipse(63,112,3,5,'ink',stroke='none') + ellipse(97,112,3,5,'ink',stroke='none'))
    add('Animals', 'horse',
        path('M50 56L43 19L65 25L72 47M108 56L116 19L94 25L88 47','brown') +
        path('M55 45C35 56 51 79 45 97C40 128 59 140 80 140C101 140 120 128 115 97C109 79 125 56 105 45Z','brown') +
        path('M58 43Q78 20 103 40L94 62L83 50L68 65Z','darkbrown') +
        eye(61,80) + eye(99,80) + ellipse(80,118,30,19,'cream') +
        eye(65,116,2.5) + eye(95,116,2.5))
    add('Animals', 'sheep',
        path('M47 75Q25 59 21 78Q31 96 48 89M113 75Q135 59 139 78Q129 96 112 89','gray') +
        ellipse(80,93,35,43,'gray') +
        path('M41 66C26 51 37 32 53 35C59 17 78 18 87 31C104 17 125 33 119 48C138 61 123 83 107 75C94 89 79 78 73 75C59 86 40 81 41 66Z','white') +
        eye(65,96) + eye(95,96) +
        path('M74 113H86L80 119Z','ink') + line('M80 119V125'))
    add('Animals', 'goat',
        path('M59 51Q29 24 43 15Q50 36 69 42M101 51Q131 24 117 15Q110 36 91 42','brown') +
        path('M48 63Q23 49 21 71Q31 85 47 77M112 63Q137 49 139 71Q129 85 113 77','cream') +
        path('M48 67Q50 39 80 43Q110 39 112 67L104 106Q99 126 80 131Q61 126 56 106Z','cream') +
        path('M70 126L80 145L90 126','white') + eye(63,78) + eye(97,78) +
        path('M74 106H86L80 112Z','brown') + line('M80 112V118'))
    add('Animals', 'duck',
        path('M33 87Q18 76 22 98C25 127 62 139 99 123C121 113 128 88 111 72C126 48 109 27 90 30C65 32 65 60 75 74Q57 72 48 87Z','yellow') +
        path('M113 48L139 56L113 65Z','orange') + eye(99,45) +
        path('M49 94Q67 81 88 91Q83 113 57 112','yellow') + line('M25 137H134',stroke='blue'))
    add('Animals', 'chicken',
        path('M75 42C59 20 76 14 84 29C88 10 105 13 103 30C121 18 129 32 114 43Z','red') +
        path('M32 88L18 64L42 70L41 48L60 70C66 56 73 48 88 44C113 34 132 59 118 82C142 120 103 139 68 128C43 122 32 108 32 88Z','white') +
        path('M120 58L139 68L119 75Z','yellow') + eye(105,57) +
        path('M119 78Q134 91 121 98Q109 95 119 78Z','red') +
        path('M52 91Q64 80 81 91Q76 112 58 111','cream') +
        line('M66 129V143M98 129V143M57 143H75M89 143H107',stroke='brown',stroke_width=4))
    add('Animals', 'bird',
        path('M43 88L22 77L27 105L48 111C64 141 118 128 117 91C129 60 108 36 85 43C64 44 61 65 65 73Z','blue') +
        path('M116 57L139 67L117 75Z','yellow') + eye(101,57) +
        path('M58 88Q73 75 91 85Q89 108 69 111','green') +
        line('M76 128V141M97 125V141M69 142H105',stroke='brown',stroke_width=4))
    add('Animals', 'fish',
        path('M47 66L20 45V115L47 94Z','yellow') +
        path('M78 58L91 35L109 61M78 102L91 125L109 99','yellow') +
        path('M41 80Q77 28 124 57L142 80Q124 112 88 111Q61 112 41 80Z','orange') +
        path('M101 52Q84 80 101 108',fill='none') + eye(121,73,4) +
        line('M64 80l13-10v20Z',stroke_width=4))
    add('Animals', 'turtle',
        ellipse(53,112,10,17,'green') + ellipse(107,112,10,17,'green') +
        path('M36 98L21 91L24 106L39 109Z','green') +
        ellipse(129,87,18,16,'palegreen') + eye(134,82,2.5) +
        path('M32 101C31 37 119 37 120 101Z','green') +
        path('M66 61L92 61L104 82L91 102H65L53 82Z','palegreen') +
        line('M53 82L34 80M104 82L117 80M66 61L61 53M92 61L98 53',stroke_width=4))
    add('Animals', 'frog',
        ellipse(44,120,24,14,'green') + ellipse(116,120,24,14,'green') +
        ellipse(80,98,38,39,'green') +
        circle(54,54,23,'green') + circle(106,54,23,'green') +
        circle(54,53,13,'white') + circle(106,53,13,'white') + eye(56,53,5) + eye(104,53,5) +
        ellipse(80,110,22,23,'palegreen',stroke='none') +
        line('M50 82Q80 103 110 82M55 107L49 135M105 107L111 135'))
    add('Animals', 'butterfly',
        path('M74 70C55 16 14 26 23 63C16 91 44 99 74 84Z','purple') +
        path('M86 70C105 16 146 26 137 63C144 91 116 99 86 84Z','purple') +
        path('M75 83C44 69 24 113 48 127C62 136 77 115 80 99C83 115 98 136 112 127C136 113 116 69 85 83Z','yellow') +
        line('M77 62Q63 36 54 43M83 62Q97 36 106 43') +
        rect(73,60,14,52,'brown',rx=7) +
        circle(44,63,8,'pink',stroke='none') + circle(116,63,8,'pink',stroke='none'))
    add('Animals', 'bee',
        ellipse(67,51,20,26,'white',transform='rotate(-30 67 51)') +
        ellipse(97,51,20,26,'white',transform='rotate(30 97 51)') +
        path('M117 87L140 99L118 106Z','ink') +
        ellipse(84,95,44,29,'yellow') +
        path('M76 68Q64 94 76 122M96 68Q85 95 96 122',stroke_width=12) +
        circle(43,88,19,'yellow') + eye(37,84,3) +
        line('M35 71L26 57M48 70L53 54',stroke_width=4))
    add('Animals', 'snail',
        path('M23 125Q39 107 87 113L103 109L108 73Q109 64 117 65Q127 66 127 77L130 115L140 125Q87 145 23 125Z','palegreen') +
        circle(70,86,37,'brown') +
        path('M83 105C55 114 40 90 50 73C61 54 91 62 92 82C93 96 73 102 65 90C60 81 72 75 78 81',stroke='cream') +
        line('M111 68L106 47M122 68L131 47') + eye(106,46,4) + eye(131,46,4))


def home(base):
    add('Home', 'house', base['house'])
    add('Home', 'door',
        rect(36,20,88,121,'brown') + rect(46,29,68,112,'cream',rx=2) +
        rect(57,42,46,35,'white',rx=2) + rect(57,90,46,36,'white',rx=2) +
        circle(101,85,5,'yellow') + line('M25 141H135'))
    add('Home', 'window',
        rect(29,27,102,104,'cream') + rect(40,38,80,82,'blue',rx=1) +
        line('M80 38V120M40 79H120',stroke='cream',stroke_width=9) +
        line('M52 52l13-1M52 61l21-1',stroke='white',stroke_width=4) +
        rect(22,130,116,10,'brown',rx=2))
    add('Home', 'bed',
        rect(22,51,17,88,'brown',rx=3) + rect(120,85,17,54,'brown',rx=3) +
        rect(38,75,82,42,'cream') + rect(41,62,30,24,'white',rx=8) +
        path('M74 70H120V114H74Z','blue') +
        rect(28,109,103,13,'brown',rx=2))
    add('Home', 'chair',
        rect(42,23,76,63,'brown',rx=8) + rect(53,34,54,33,'cream',rx=4) +
        line('M47 80V139M113 80V139',stroke='brown',stroke_width=10) +
        rect(33,78,94,21,'blue',rx=5))
    add('Home', 'table',
        path('M41 75L35 137H48L56 75M104 75L112 137H125L119 75','brown') +
        rect(21,57,118,23,'cream',rx=5) + line('M27 80H133',stroke='brown'))
    add('Home', 'sofa',
        rect(34,41,92,68,'blue',rx=17) + line('M80 46V90') +
        rect(31,113,15,20,'brown',rx=2) + rect(114,113,15,20,'brown',rx=2) +
        rect(28,86,104,33,'blue',rx=8) +
        rect(19,72,23,45,'blue',rx=8) + rect(118,72,23,45,'blue',rx=8) +
        line('M46 91H114',stroke_width=4))
    add('Home', 'lamp',
        line('M80 75V127',stroke='brown',stroke_width=9) +
        path('M51 127H109L118 139H42Z','brown') +
        path('M52 26H108L131 82H29Z','yellow') +
        line('M109 84V103',stroke_width=3) + circle(109,107,4,'brown') +
        line('M62 38L50 68',stroke='white',stroke_width=4))
    add('Home', 'clock',
        circle(80,80,57,'blue') + circle(80,80,46,'white') +
        line('M80 42V48M118 80H112M80 118V112M42 80H48',stroke_width=4) +
        line('M80 80V54M80 80L101 96',stroke_width=6) + circle(80,80,5,'red'))
    add('Home', 'key',
        path('M62 73H137V91H126V104H111V91H99V104H85V91H62Z','yellow') +
        circle(44,82,29,'yellow') + circle(44,82,11,'white'))
    add('Home', 'cup',
        path('M111 59C150 51 146 101 111 99','cream') +
        path('M35 48H114V108Q113 133 80 133H69Q35 132 35 108Z','blue') +
        line('M36 49H113') + line('M51 65V99',stroke='white',stroke_width=4))
    add('Home', 'plate',
        circle(80,80,57,'white') + circle(80,80,44,'blue',stroke_width=3) +
        circle(80,80,33,'white',stroke_width=3) +
        line('M49 44Q57 37 69 36',stroke='white',stroke_width=4))
    add('Home', 'bowl',
        ellipse(80,66,57,15,'white') +
        path('M23 66C28 110 48 127 80 127C112 127 132 110 137 66Q80 87 23 66Z','blue') +
        line('M42 88Q47 106 58 112',stroke='white',stroke_width=4) +
        line('M61 130H99',stroke_width=4))
    add('Home', 'spoon',
        path('M73 69H87L90 132Q80 145 70 132Z','gray') +
        ellipse(80,47,25,33,'gray') + line('M68 32Q61 44 66 54',stroke='white',stroke_width=4))
    add('Home', 'fork',
        path('M55 22V62Q55 79 73 82L70 133Q80 144 90 133L87 82Q105 79 105 62V22H94V58H85V22H75V58H66V22Z','gray') +
        line('M80 93V126',stroke='white',stroke_width=3))
    add('Home', 'bottle',
        path('M65 34V55L45 76V132Q45 141 55 141H105Q115 141 115 132V76L95 55V34Z','blue') +
        rect(62,21,36,18,'brown',rx=3) + rect(46,88,68,33,'cream',rx=0) +
        line('M58 77V82',stroke='white',stroke_width=4))
    add('Home', 'book',
        path('M39 23H124V131H39Q23 131 23 115V39Q23 23 39 23Z','blue') +
        path('M39 108H124V131H39Q23 131 23 120Q23 108 39 108Z','cream') +
        line('M43 32V98M61 48H106M61 65H97',stroke_width=4) +
        line('M43 118H114',stroke='brown',stroke_width=3))
    add('Home', 'pencil', group(
        rect(64,34,32,88,'yellow',rx=1) + rect(64,20,32,20,'pink',rx=4) +
        rect(64,38,32,8,'gray',rx=0) +
        path('M64 122L80 144L96 122Z','cream') + path('M74 136L80 144L86 136Z','ink',stroke='none') +
        line('M80 49V116',stroke='white',stroke_width=3), 'rotate(35 80 80)'))
    add('Home', 'scissors',
        path('M71 95L123 23Q135 46 91 102Z','gray') +
        path('M89 95L37 23Q25 46 69 102Z','gray') +
        ellipse(55,119,21,23,'red',transform='rotate(25 55 119)') +
        ellipse(105,119,21,23,'red',transform='rotate(-25 105 119)') +
        ellipse(55,119,9,11,'white',transform='rotate(25 55 119)',stroke_width=3) +
        ellipse(105,119,9,11,'white',transform='rotate(-25 105 119)',stroke_width=3) +
        circle(80,90,6,'brown'))
    add('Home', 'umbrella',
        line('M80 23V126Q80 149 60 139Q53 135 56 126',stroke='brown',stroke_width=6) +
        path('M21 83C24 48 49 28 80 28C111 28 136 48 139 83Q124 68 109 83Q94 68 80 83Q65 68 51 83Q35 68 21 83Z','red') +
        line('M80 29Q55 44 51 82M80 29Q105 44 109 82',stroke_width=3))


def clothes_and_toys():
    add('Clothing and toys', 'shoe',
        path('M35 59L59 53L73 78L101 87L128 90Q141 94 137 120H25V86Q25 69 35 59Z','blue') +
        path('M26 112H137V125H25Z','white') +
        line('M55 78L67 72M63 88L76 81M38 67V94',stroke='white',stroke_width=4))
    add('Clothing and toys', 'sock',
        path('M70 24H111V91Q121 100 115 116Q110 129 92 132L52 142Q28 146 25 125Q23 111 41 103L70 90Z','pink') +
        path('M70 24H111V43H70Z','white') +
        path('M101 94Q90 108 113 116M41 103Q60 111 52 142','none',stroke_width=4))
    add('Clothing and toys', 'hat',
        path('M42 93L52 49Q78 30 108 49L118 93Z','yellow') +
        path('M45 78H115L118 94H42Z','red') +
        ellipse(80,102,61,17,'yellow') + line('M39 97Q80 107 121 97',stroke_width=3))
    add('Clothing and toys', 'shirt',
        path('M55 28L31 40L14 68L39 84L49 68V137H111V68L121 84L146 68L129 40L105 28Q80 46 55 28Z','blue') +
        path('M63 31Q80 55 97 31','none',stroke='white',stroke_width=5))
    add('Clothing and toys', 'trousers',
        path('M45 22H115L126 140H88L80 76L72 140H34Z','blue') +
        line('M45 38H115M80 39V64M48 43Q48 62 39 63M112 43Q112 62 121 63',stroke_width=4) +
        line('M40 126H72M88 126H120',stroke='white',stroke_width=3))
    add('Clothing and toys', 'dress',
        path('M59 23L43 34L34 59L52 69L61 57L63 78L31 137H129L97 78L99 57L108 69L126 59L117 34L101 23Q80 42 59 23Z','pink') +
        path('M63 75H97V85H63Z','red') +
        line('M64 97L53 121M96 97L107 121',stroke='white',stroke_width=4))
    add('Clothing and toys', 'coat',
        path('M58 25L34 39L18 101L40 110L49 73L44 139H116L111 73L120 110L142 101L126 39L102 25Z','green') +
        path('M61 25L80 48L65 65L52 38Z','palegreen') +
        path('M99 25L80 48L95 65L108 38Z','palegreen') +
        line('M80 49V139M51 106H65M95 106H109',stroke_width=4) +
        circle(87,82,2,'ink',stroke='none') + circle(87,104,2,'ink',stroke='none'))
    # Each coloured panel carries its own outline. Shared seams use the exact
    # same Bezier, reversed as necessary, so fills and strokes cannot diverge.
    add('Clothing and toys', 'ball',
        path('M80 26A54 54 0 0 0 80 134C40 110 40 50 80 26Z','blue') +
        path('M80 26C40 50 40 110 80 134C100 110 100 50 80 26Z','yellow') +
        path('M80 26A54 54 0 0 1 80 134C100 110 100 50 80 26Z','red') +
        circle(80,80,54) + line('M44 55Q34 68 35 82',stroke='white',stroke_width=4))
    add('Clothing and toys', 'kite',
        path('M78 19L122 66L78 109L34 66Z','blue') +
        path('M78 19V66H122Z','red') + path('M34 66H78V109Z','yellow') +
        line('M78 19V109M34 66H122',stroke_width=3) +
        line('M78 109C57 123 100 134 80 146',stroke_width=3) +
        path('M74 119L62 113L63 125Z','pink') + path('M85 135L98 129L96 142Z','pink'))
    add('Clothing and toys', 'teddy-bear',
        ellipse(80,108,30,30,'brown') + circle(47,91,16,'brown') + circle(113,91,16,'brown') +
        ellipse(55,137,18,13,'brown') + ellipse(105,137,18,13,'brown') +
        circle(49,34,15,'brown') + circle(111,34,15,'brown') + circle(80,58,37,'brown') +
        ellipse(80,72,18,13,'cream',stroke='none') + ellipse(80,112,18,20,'cream',stroke='none') +
        eye(65,54) + eye(95,54) + path('M74 66H86L80 73Z','ink') +
        line('M80 73V77Q74 81 70 77M80 77Q86 81 90 77',stroke_width=3))


def transport():
    add('Transport', 'car',
        path('M26 85L44 52Q49 43 61 43H100Q110 43 115 54L132 86Q143 89 143 103V116H17V101Q17 87 26 85Z','red') +
        path('M53 53H76V80H39Z','blue') + path('M85 53H99Q103 53 106 59L117 80H85Z','blue') +
        rect(20,94,12,9,'yellow',rx=2) + rect(128,94,12,9,'yellow',rx=2) +
        wheel(47,116,15) + wheel(114,116,15))
    add('Transport', 'bus',
        rect(17,40,126,83,'yellow',rx=11) +
        ''.join(rect(x,52,19,27,'blue',rx=3) for x in (27,53,79)) +
        rect(107,52,25,62,'blue',rx=3) + line('M119 53V114M108 83H131',stroke_width=3) +
        line('M21 92H101',stroke_width=4) + wheel(43,123,14) + wheel(115,123,14))
    add('Transport', 'truck',
        rect(17,41,77,70,'red',rx=5) +
        path('M94 64H120L143 88V114H94Z','blue') +
        path('M104 73H117L131 89H104Z','white') +
        line('M24 112H142',stroke='brown',stroke_width=8) +
        wheel(43,117,15) + wheel(119,117,15))
    add('Transport', 'train',
        rect(25,76,73,40,'blue',rx=8) + rect(86,42,48,74,'red',rx=3) +
        rect(98,54,24,25,'blue',rx=2) + rect(78,35,62,11,'brown',rx=3) +
        rect(42,51,18,25,'brown',rx=1) + rect(37,43,28,11,'brown',rx=2) +
        path('M25 99L14 123H31Z','yellow') +
        wheel(45,119,13) + wheel(80,119,13) + wheel(116,119,13) +
        line('M15 140H145',stroke_width=4) +
        circle(48,27,7,'gray',stroke_width=3) + circle(32,17,5,'gray',stroke_width=3))
    add('Transport', 'bicycle',
        circle(42,111,25,'white') + circle(120,111,25,'white') +
        path('M42 111L65 65L84 111H42L101 65L120 111','none',stroke='red',stroke_width=6) +
        line('M63 65L58 53M49 53H70M101 65L96 43H113',stroke_width=5) +
        circle(84,111,5,'brown') + line('M84 111L93 122H102',stroke_width=4))
    add('Transport', 'boat',
        path('M22 106H140L120 132H44Z','brown') +
        line('M79 22V106',stroke='brown',stroke_width=6) +
        path('M72 31L31 92H72Z','blue') + path('M87 45L128 93H87Z','yellow') +
        line('M18 143Q34 133 50 143Q66 153 82 143Q98 133 114 143Q130 153 145 143',stroke='blue',stroke_width=4))
    add('Transport', 'airplane',
        path('M71 40C71 14 89 14 89 40V66L142 94V107L89 92V121L107 135V144L80 136L53 144V135L71 121V92L18 107V94L71 66Z','white') +
        path('M73 42Q80 36 87 42V53H73Z','blue',stroke_width=3) +
        line('M29 96L65 78M131 96L95 78',stroke='red',stroke_width=4))
    add('Transport', 'helicopter',
        line('M77 43V26M26 26H132',stroke_width=6) +
        path('M102 74L136 57L143 65L134 95L106 96Z','yellow') +
        path('M34 65Q52 46 81 48Q111 50 111 84Q110 109 82 111H48Q19 112 19 90Q18 76 34 65Z','blue') +
        path('M41 64Q54 56 67 58V83H26Q29 72 41 64Z','white') +
        line('M48 112V129M88 112V129M28 129H109',stroke_width=5) +
        line('M136 49V85',stroke_width=4))
    add('Transport', 'rocket',
        path('M61 95L36 116L31 137L64 125M99 95L124 116L129 137L96 125','red') +
        path('M67 126Q63 143 80 151Q97 143 93 126Z','yellow') +
        path('M80 16C54 40 52 79 61 124H99C108 79 106 40 80 16Z','white') +
        path('M80 16Q98 33 102 52H58Q62 33 80 16Z','red') +
        circle(80,76,15,'blue') + line('M61 111H99',stroke_width=4))
    add('Transport', 'tractor',
        rect(28,40,44,57,'green',rx=3) + rect(37,49,25,29,'blue',rx=2) +
        rect(22,33,57,10,'green',rx=3) + rect(69,73,62,41,'green',rx=5) +
        rect(103,47,9,27,'brown',rx=2) + line('M122 83V104M113 83V104',stroke_width=3) +
        wheel(51,115,25) + wheel(124,122,16) + circle(51,115,12,'yellow',stroke_width=3) +
        circle(124,122,7,'yellow',stroke_width=3))


def nature():
    add('Nature', 'sun',
        ''.join(line(f'M{80+45*math.cos(a):.2f} {80+45*math.sin(a):.2f}L{80+60*math.cos(a):.2f} {80+60*math.sin(a):.2f}',stroke='yellow',stroke_width=7)
                for a in [i*math.pi/6 for i in range(12)]) + circle(80,80,34,'yellow'))
    add('Nature', 'moon',
        path('M107 24C59 18 29 56 39 95C49 135 98 151 130 117C86 120 59 75 80 43Q89 29 107 24Z','yellow'))
    add('Nature', 'star',
        path('M80 20L98 58L140 64L110 95L117 138L80 117L43 138L50 95L20 64L62 58Z','yellow'))
    add('Nature', 'cloud',
        path('M40 120C11 118 12 82 38 78C29 45 69 28 89 51C118 38 142 64 128 87C154 100 140 125 119 122Z','white') +
        line('M43 88Q40 100 48 105',stroke='blue',stroke_width=4))
    add('Nature', 'rainbow',
        path('M20 131C20 29 140 29 140 131H121C121 54 39 54 39 131Z','red') +
        path('M39 131C39 54 121 54 121 131H103C103 80 57 80 57 131Z','yellow') +
        path('M57 131C57 80 103 80 103 131H85C85 111 75 111 75 131Z','blue'))
    add('Nature', 'tree',
        path('M69 83L63 141H98L91 83Z','brown') +
        path('M34 91C16 80 24 54 42 52C38 27 65 16 81 33C100 14 125 33 119 55C141 58 146 83 125 95C109 111 92 103 80 99C60 112 41 107 34 91Z','green') +
        line('M80 89V126M80 110L63 95M80 102L96 88',stroke='brown',stroke_width=5))
    add('Nature', 'flower',
        line('M80 84V142',stroke='green',stroke_width=7) +
        path('M78 123Q48 126 43 101Q65 96 78 123Z','green') +
        path('M82 112Q109 118 119 93Q97 88 82 112Z','green') +
        ''.join(ellipse(80+23*math.cos(a),59+23*math.sin(a),15,19,'pink',transform=f'rotate({i*60+90} {80+23*math.cos(a)} {59+23*math.sin(a)})')
                for i,a in enumerate([i*math.pi/3 for i in range(6)])) + circle(80,59,17,'yellow'))
    add('Nature', 'leaf',
        path('M32 128C18 52 81 19 133 27C138 83 105 143 32 128Z','green') +
        line('M24 139L114 47M51 110L48 82M51 110L82 114M77 84L76 58M77 84L107 86',stroke_width=4))
    add('Nature', 'mountain',
        path('M16 136L65 34L116 136Z','blue') +
        path('M70 136L109 62L146 136Z','gray') +
        path('M44 78L65 34L87 79L70 70L60 82L52 69Z','white') +
        path('M94 91L109 62L125 94L109 86Z','white'))
    snow=''
    for i in range(6):
        snow += group(line('M80 80V23M80 45L66 33M80 45L94 33M80 62L69 53M80 62L91 53',stroke='blue',stroke_width=5),f'rotate({60*i} 80 80)')
    add('Nature', 'snowflake', snow + circle(80,80,5,'white',stroke='blue'))


def body():
    add('Body', 'eye',
        path('M20 80Q80 19 140 80Q80 141 20 80Z','white') +
        circle(80,80,25,'green') + circle(80,80,12,'ink') +
        circle(87,73,4,'white',stroke='none'))
    add('Body', 'ear',
        path('M116 77C140 23 75 9 48 40C30 59 44 83 58 93C68 102 62 123 77 134C94 147 115 130 108 115C102 102 107 94 116 77Z','cream') +
        path('M62 66C55 38 99 31 106 57C111 75 89 81 86 93Q70 82 67 99',fill='none') +
        line('M86 94Q89 113 79 118',stroke_width=4))
    add('Body', 'nose',
        path('M71 28C70 57 53 77 39 99C32 110 43 123 58 117Q79 135 101 118C116 125 130 111 118 98Q99 78 97 57',fill='cream') +
        line('M55 109Q62 101 69 109M93 109Q100 101 107 109',stroke_width=4))
    add('Body', 'mouth',
        path('M22 79Q46 61 64 69Q80 55 96 69Q114 61 138 79Q118 124 80 124Q42 124 22 79Z','pink') +
        path('M30 80Q80 94 130 80Q110 108 80 108Q50 108 30 80Z','white') +
        line('M23 79Q80 89 137 79',stroke_width=4))
    add('Body', 'hand',
        path('M53 86V39Q53 29 62 29Q71 29 71 39V73V23Q71 13 80 13Q89 13 89 23V72V30Q89 20 98 20Q107 20 107 30V77V46Q107 36 116 36Q125 36 125 46V104Q125 133 99 139H75Q58 136 49 122L24 88Q17 77 26 71Q35 66 43 77L53 91Z','cream') +
        line('M66 105Q83 98 98 106',stroke='brown',stroke_width=3))
    add('Body', 'foot',
        path('M64 141C53 123 48 110 44 91C38 73 44 58 62 55L100 52C117 78 109 100 99 118L96 141Z','cream') +
        circle(44,48,12,'cream') + ellipse(65,37,10,12,'cream') + ellipse(84,36,9,11,'cream') +
        ellipse(102,43,8,10,'cream') + ellipse(115,57,7,9,'cream') +
        line('M65 101Q72 107 70 120',stroke='brown',stroke_width=3))
    add('Body', 'tooth',
        path('M80 39C52 16 24 39 36 73C45 98 42 140 58 140C71 140 66 107 80 103C94 107 89 140 102 140C118 140 115 98 124 73C136 39 108 16 80 39Z','white') +
        line('M55 50Q51 60 55 69',stroke='blue',stroke_width=4))
    add('Body', 'heart',
        path('M80 139C57 121 21 96 21 62C21 27 62 20 80 48C98 20 139 27 139 62C139 96 103 121 80 139Z','red') +
        line('M44 52Q38 58 39 68',stroke='pink',stroke_width=5))
    add('Body', 'bone', group(
        path('M65 55C38 61 32 33 48 27C48 9 77 10 80 31C83 10 112 9 112 27C128 33 122 61 95 55V105C122 99 128 127 112 133C112 151 83 150 80 129C77 150 48 151 48 133C32 127 38 99 65 105Z','white'), 'rotate(42 80 80)'))
    add('Body', 'face',
        ellipse(80,85,49,55,'cream') +
        path('M33 69C26 30 55 15 84 20C115 16 137 39 127 72Q111 60 101 41Q76 63 42 52Z','brown') +
        eye(62,82,4) + eye(99,82,4) +
        path('M80 87L75 103H83',fill='none',stroke_width=4) +
        line('M62 113Q80 129 99 113',stroke_width=4))


def additional_words():
    """Extend the first collection with familiar animals and everyday objects."""
    add('Food', 'peach',
        path('M80 51C55 28 22 53 29 89C33 118 61 140 80 130C99 140 127 118 131 89C138 53 105 28 80 51Z','pink') +
        line('M80 51Q65 78 80 119') + line('M80 49Q81 28 91 23') +
        path('M88 32Q101 13 122 24Q112 43 88 38Z','green'))
    add('Food', 'plum',
        ellipse(80,91,43,48,'purple') + line('M83 47Q76 29 87 19') +
        path('M85 30Q102 18 119 32Q103 46 85 36Z','green') +
        line('M54 77Q48 93 55 104',stroke='white'))
    add('Food', 'coconut',
        circle(80,86,53,'brown') + circle(80,86,42,'white') +
        circle(80,86,26,'cream') + line('M32 119l10 10M117 125l9-10',stroke='darkbrown',stroke_width=3))
    add('Food', 'avocado',
        path('M80 20C57 20 54 52 37 78C13 117 44 143 80 143C116 143 147 117 123 78C106 52 103 20 80 20Z','green') +
        path('M80 32C65 32 65 59 48 86C31 115 54 132 80 132C106 132 129 115 112 86C95 59 95 32 80 32Z','palegreen',stroke='none') +
        circle(80,104,24,'brown') + line('M68 97Q73 88 83 90',stroke='cream',stroke_width=3))
    add('Food', 'cucumber', group(
        rect(53,20,54,121,'green',rx=27) +
        line('M67 46V113M81 38V124M95 47V111',stroke='palegreen',stroke_width=3), 'rotate(30 80 80)'))
    add('Food', 'corn',
        rect(52,25,56,105,'yellow',rx=28) +
        line('M70 36V119M89 36V119M55 52H105M53 70H107M53 88H107M55 106H105',stroke='ochre',stroke_width=3) +
        path('M80 141Q30 126 27 65Q62 80 80 141Z','green') +
        path('M80 141Q130 126 133 65Q98 80 80 141Z','palegreen'))
    add('Food', 'peas',
        path('M25 109Q38 30 133 34Q124 123 25 109Z','green') +
        path('M34 105Q67 66 125 42',stroke='palegreen',stroke_width=3) +
        circle(53,88,17,'palegreen') + circle(83,72,17,'palegreen') + circle(111,53,16,'palegreen'))
    add('Food', 'onion',
        path('M69 45L61 19L79 28L91 16L91 45C114 60 135 83 128 106C119 141 41 141 32 106C25 83 46 60 69 45Z','cream') +
        line('M71 49Q40 94 60 125M89 49Q120 94 100 125M80 49V129',stroke='brown',stroke_width=3) +
        line('M70 133l-5 10M80 134v12M90 133l5 10',stroke='brown',stroke_width=3))
    add('Food', 'pizza',
        path('M35 30Q80 13 131 47L61 143Z','yellow') +
        path('M35 30Q80 13 131 47L124 60Q81 31 41 45Z','brown') +
        circle(68,61,11,'red') + circle(96,70,10,'red') + circle(68,103,10,'red') +
        line('M52 77l7 5M94 94l-5 7',stroke='green',stroke_width=5))
    add('Food', 'cookie',
        path('M74 25Q95 20 105 34Q126 33 130 53Q145 66 134 86Q138 108 118 117Q108 138 86 134Q65 146 49 129Q28 126 28 105Q13 89 25 70Q21 48 42 41Q51 22 74 25Z','cream') +
        ''.join(circle(x,y,r,'darkbrown',stroke='none') for x,y,r in [(56,59,7),(96,49,6),(111,89,7),(75,89,6),(51,110,6),(89,119,5)]))

    def cat_face(fill):
        return (path('M41 66L30 26L66 48Q80 43 94 48L130 26L119 66Q137 117 100 134Q80 144 60 134Q23 117 41 66Z',fill) +
                eye(59,84) + eye(101,84) + ellipse(80,112,25,18,'cream') +
                path('M73 105H87L80 113Z','ink') + line('M80 113V120M70 122Q80 127 90 122',stroke_width=3))
    add('Animals', 'lion',
        path('M80 15L96 25L115 21L122 40L140 49L135 70L145 89L133 106L130 127L108 132L94 146L75 139L55 145L43 129L23 123L25 102L14 85L26 65L23 46L43 38L53 21L71 25Z','brown') +
        circle(80,83,44,'yellow') + eye(64,77) + eye(96,77) +
        ellipse(80,103,23,19,'cream') + path('M72 94H88L80 104Z','darkbrown') + line('M80 104V114'))
    add('Animals', 'tiger', cat_face('orange') +
        path('M67 50L76 69L79 48M93 50L85 69L82 48M40 80L54 91L38 97M120 80L106 91L122 97','ink',stroke='none'))
    add('Animals', 'elephant',
        ellipse(44,84,28,43,'gray') + ellipse(116,84,28,43,'gray') +
        ellipse(80,78,39,48,'gray') +
        path('M68 95V126Q67 144 86 143Q107 144 109 125L94 121Q95 131 84 129L91 95Z','gray') +
        eye(62,78) + eye(98,78) +
        path('M57 101Q48 119 60 122L67 104M103 101Q112 119 100 122L93 104','white') +
        line('M77 111H87M77 120H87',stroke_width=3))
    add('Animals', 'giraffe',
        path('M59 82L55 140H105L101 82Z','yellow') +
        path('M49 60Q26 39 21 60Q31 77 49 70M111 60Q134 39 139 60Q129 77 111 70','yellow') +
        line('M63 44V23M97 44V23',stroke='brown',stroke_width=8) +
        circle(63,21,6,'brown') + circle(97,21,6,'brown') +
        rect(48,41,64,57,'yellow',rx=26) + ellipse(80,90,32,18,'cream') +
        eye(64,64) + eye(96,64) + eye(69,89,2) + eye(91,89,2) +
        path('M61 111L74 107L77 121L60 126M89 126L102 120L103 136H89','brown',stroke='none'))
    add('Animals', 'zebra',
        path('M51 56L44 20L64 24L72 48M109 56L116 20L96 24L88 48','white') +
        path('M52 48Q80 28 108 48L116 111Q113 139 80 139Q47 139 44 111Z','white') +
        path('M71 42L80 65L89 42M48 67L66 78L46 87M112 67L94 78L114 87M45 94L64 102L45 111M115 94L96 102L115 111','ink',stroke='none') +
        eye(64,84) + eye(96,84) + ellipse(80,119,29,18,'gray') + eye(68,118,2) + eye(92,118,2))
    add('Animals', 'monkey',
        circle(32,81,19,'brown') + circle(128,81,19,'brown') +
        circle(32,81,10,'pink',stroke='none') + circle(128,81,10,'pink',stroke='none') +
        circle(80,82,51,'brown') +
        path('M80 57C49 34 35 75 51 94C33 122 61 138 80 132C99 138 127 122 109 94C125 75 111 34 80 57Z','cream') +
        eye(63,78) + eye(97,78) + ellipse(80,102,8,5,'brown',stroke='none') +
        line('M65 117Q80 130 95 117') + line('M69 32Q59 17 79 18Q95 19 88 32'))
    add('Animals', 'panda',
        circle(43,41,22,'ink') + circle(117,41,22,'ink') + ellipse(80,87,53,49,'white') +
        ellipse(58,80,16,20,'ink',transform='rotate(25 58 80)') +
        ellipse(102,80,16,20,'ink',transform='rotate(-25 102 80)') +
        circle(60,76,4,'white',stroke='none') + circle(100,76,4,'white',stroke='none') +
        ellipse(80,109,10,7,'ink') + line('M80 116V122M70 123Q80 129 90 123',stroke_width=3))
    add('Animals', 'penguin',
        path('M48 72Q21 87 24 116L47 106M112 72Q139 87 136 116L113 106','ink') +
        path('M63 127L43 141H76V125M97 127L117 141H84V125','orange') +
        ellipse(80,81,40,56,'ink') +
        path('M80 64C60 44 49 72 51 96Q52 127 80 128Q108 127 109 96C111 72 100 44 80 64Z','white',stroke='none') +
        eye(67,69) + eye(93,69) + path('M69 82H91L80 94Z','orange'))
    add('Animals', 'whale',
        path('M109 74L125 53L139 56L136 74L145 89L129 99L112 88C110 123 76 139 44 121C9 101 19 58 48 55C78 49 96 59 109 74Z','blue') +
        path('M27 98Q61 119 104 98Q90 132 51 125Q32 120 27 98Z','white',stroke='none') +
        path('M65 102Q70 129 89 128L90 109','blue') + eye(44,79) + line('M30 94Q39 99 48 94',stroke_width=3) +
        line('M64 43V24M64 30Q51 16 42 27M64 30Q77 16 86 27',stroke='blue',stroke_width=5))
    add('Animals', 'octopus',
        path('M44 94Q18 96 21 116Q27 132 40 117Q35 144 54 141Q64 138 61 117Q69 149 80 141Q91 149 99 117Q96 138 106 141Q125 144 120 117Q133 132 139 116Q142 96 116 94Z','purple') +
        path('M43 94V64C43 13 117 13 117 64V94Q80 115 43 94Z','purple') +
        eye(64,73) + eye(96,73) + line('M70 88Q80 98 90 88',stroke_width=3))

    add('Home', 'toothbrush', group(
        rect(66,59,23,84,'blue',rx=11) + rect(58,20,39,47,'white',rx=10) +
        line('M68 25V57M78 25V57M88 25V57',stroke='blue',stroke_width=3), 'rotate(20 80 80)'))
    add('Home', 'comb',
        rect(23,45,114,18,'orange',rx=8) +
        ''.join(rect(x,61,7,53,'orange',rx=3) for x in range(28,132,14)))
    add('Home', 'brush', group(
        rect(69,91,22,54,'brown',rx=9) + ellipse(80,61,36,45,'brown') +
        ellipse(80,61,27,35,'cream') +
        ''.join(line(f'M{x} {y}v9',stroke_width=3) for x in (67,80,93) for y in (42,60,78)), 'rotate(20 80 80)'))
    add('Home', 'mirror',
        rect(69,104,22,40,'brown',rx=8) + ellipse(80,64,44,49,'brown') +
        ellipse(80,64,34,39,'blue') + line('M60 65L85 40M69 80L96 53',stroke='white',stroke_width=5))
    add('Home', 'towel',
        line('M21 35H139',stroke='gray',stroke_width=8) + rect(40,27,80,108,'cream',rx=5) +
        rect(40,100,80,15,'blue',rx=0,stroke='none') +
        line('M40 135H120M51 135V143M66 135V143M81 135V143M96 135V143M111 135V143',stroke_width=3))
    add('Home', 'soap',
        rect(25,71,110,62,'pink',rx=24) + ellipse(80,93,33,13,'pink') +
        circle(47,47,13,'white') + circle(88,29,10,'white') + circle(117,51,16,'white') +
        line('M43 111H96',stroke='white',stroke_width=3))
    add('Home', 'bath',
        line('M38 120l-5 19M122 120l5 19',stroke_width=7) +
        path('M24 80H136L125 112Q121 127 104 127H56Q39 127 35 112Z','white') +
        rect(18,69,124,14,'blue',rx=6) +
        path('M37 68V41Q37 22 53 22Q69 22 69 40',stroke='gray',stroke_width=8) +
        circle(92,58,11,'white') + circle(111,47,8,'white'))
    add('Home', 'toilet',
        rect(79,25,49,60,'white',rx=5) + rect(88,39,16,6,'gray',rx=2) +
        path('M44 92Q43 113 71 116L66 138H111L99 111Q125 102 128 88Z','white') +
        ellipse(76,87,52,16,'white') + ellipse(76,85,35,8,'blue'))
    add('Home', 'sink',
        path('M66 108L60 140H100L94 108Z','white') +
        path('M23 70H137L124 98Q119 111 80 111Q41 111 36 98Z','white') +
        ellipse(80,70,57,18,'white') + ellipse(80,72,39,9,'blue') +
        path('M86 59V34Q86 21 74 21Q62 21 62 34V41',stroke='gray',stroke_width=8) +
        line('M104 49V40M95 43H113',stroke_width=4))
    add('Home', 'fridge',
        rect(40,16,80,127,'white',rx=8) + line('M40 60H120') +
        rect(49,32,5,17,'gray',rx=2,stroke='none') + rect(49,77,5,28,'gray',rx=2,stroke='none') +
        line('M48 144H57M103 144H112',stroke_width=5))
    add('Home', 'oven',
        rect(28,28,104,114,'white',rx=7) + rect(40,67,80,62,'blue',rx=5) +
        line('M49 76H111',stroke_width=6) +
        ''.join(circle(x,47,6,'gray') for x in (48,80,112)) +
        line('M42 19H68M92 19H118M54 15V25M106 15V25',stroke_width=4))
    add('Home', 'pan',
        rect(106,70,39,17,'brown',rx=6) + circle(62,79,45,'gray') + circle(62,79,34,'ink') +
        line('M43 60Q55 49 69 53',stroke='gray',stroke_width=4))
    add('Home', 'kettle',
        path('M104 55Q142 37 140 78Q139 100 118 103',stroke='brown',stroke_width=10) +
        path('M43 80L20 63L25 101L45 110','blue') +
        path('M49 48H105L124 117Q127 134 110 135H48Q31 134 34 117Z','blue') +
        ellipse(77,48,30,8,'blue') + circle(77,35,8,'brown') +
        line('M55 71L48 102',stroke='white',stroke_width=4))
    add('Home', 'broom', group(
        rect(74,15,12,83,'brown',rx=5) +
        path('M57 90H103L120 141H40Z','yellow') + rect(55,89,50,13,'orange',rx=3) +
        line('M64 109L57 140M80 109V140M96 109L103 140',stroke='brown',stroke_width=3), 'rotate(12 80 80)'))
    add('Home', 'basket',
        path('M43 71Q43 18 80 18Q117 18 117 71',stroke='brown',stroke_width=9) +
        path('M23 65H137L122 136H38Z','cream') +
        line('M27 85H133M31 105H129M36 125H124M48 69L57 133M69 69L72 133M91 69L88 133M112 69L103 133',stroke='brown',stroke_width=3) +
        rect(20,61,120,13,'brown',rx=5))

    add('Clothing and toys', 'glove',
        path('M53 91L31 71Q20 62 19 76L37 114Q42 126 59 127H112Q130 123 130 104V59Q130 46 119 48V40Q119 27 108 29V31Q108 18 97 22Q97 10 86 14Q79 16 79 28V80L67 50Q61 38 52 45Q47 50 52 61Z','yellow') +
        rect(52,123,63,21,'orange',rx=4) + line('M97 29V76M108 34V78M119 51V82',stroke_width=3))
    add('Clothing and toys', 'scarf',
        path('M45 60L37 134H67L83 63Z','blue') +
        path('M80 58L96 137H125L114 48Z','blue') +
        path('M33 40Q80 18 128 40L119 68Q80 48 41 68Z','blue') +
        line('M41 109H71M94 111H121',stroke='white',stroke_width=7) +
        line('M40 135V143M51 135V144M63 135V143M99 137V145M111 137V145M122 137V145',stroke_width=3))
    add('Clothing and toys', 'boot',
        path('M51 25H104V95L127 106Q139 110 137 132H26V113Q26 99 51 96Z','yellow') +
        rect(26,127,111,13,'brown',rx=3) + rect(48,22,60,14,'yellow',rx=4) +
        line('M65 47V85',stroke='white',stroke_width=4))
    add('Clothing and toys', 'crown',
        path('M34 119L20 45L57 72L80 24L103 72L140 45L126 119Z','yellow') +
        rect(34,111,92,23,'yellow',rx=4) +
        circle(80,91,10,'red') + circle(48,95,6,'blue') + circle(112,95,6,'blue'))
    add('Clothing and toys', 'drum',
        path('M31 64V122Q80 150 129 122V64Z','red') +
        path('M34 77L56 126L80 80L104 126L126 77',stroke='cream',stroke_width=4) +
        ellipse(80,64,49,18,'cream') + path('M31 119Q80 144 129 119V129Q80 154 31 129Z','blue') +
        line('M40 25L91 62M120 24L83 58',stroke='brown',stroke_width=6) +
        circle(39,24,5,'brown') + circle(120,24,5,'brown'))

    add('Transport', 'scooter',
        wheel(39,125,14) + wheel(122,125,14) +
        path('M39 120H92L117 98',stroke='blue',stroke_width=7) +
        line('M122 123L104 30M87 30H119',stroke='blue',stroke_width=7) +
        line('M87 30H96M113 30H123',stroke='ink',stroke_width=8))
    add('Transport', 'motorcycle',
        wheel(36,116,23) + wheel(124,116,23) +
        path('M36 115L60 78L91 115H36L78 84H105',stroke='red',stroke_width=7) +
        path('M82 75Q95 61 111 73L104 88H79Z','red') +
        line('M124 116L106 56L117 49M47 76H76',stroke_width=7) +
        circle(118,65,7,'yellow') + rect(64,102,30,21,'gray',rx=5))
    def van(fill):
        return (path('M20 70L33 44H99L126 71H138V117H20Z',fill) +
                path('M40 53H68V76H30Z','blue') + path('M79 53H95L117 76H79Z','blue') +
                line('M75 80V115M83 88H94',stroke_width=3) + wheel(45,117,17) + wheel(116,117,17))
    add('Transport', 'taxi', van('yellow') + rect(60,30,39,14,'yellow',rx=3) +
        ''.join(rect(x,88,8,8,'ink',rx=0,stroke='none') for x in (24,40,56,104,120)))
    add('Transport', 'ambulance', van('white') + rect(73,29,25,13,'red',rx=4) +
        path('M48 82H58V91H67V101H58V110H48V101H39V91H48Z','red',stroke='none'))
    add('Transport', 'canoe',
        path('M16 92Q80 121 144 92L122 125Q80 144 38 125Z','orange') +
        ellipse(80,92,62,16,'cream') + ellipse(80,91,45,8,'brown') +
        line('M49 40L110 116',stroke='brown',stroke_width=7) +
        path('M104 99Q119 101 129 118L135 133L117 129Q101 115 104 99Z','brown'))

    add('Nature', 'rock',
        path('M24 105L40 62L71 38L111 47L137 101L123 128H42Z','gray') +
        line('M40 62L68 79L71 38M68 79L106 88L111 47M106 88L123 128',stroke_width=3))
    add('Nature', 'shell',
        path('M66 132L30 99C10 80 22 57 39 62C34 36 59 25 72 45C79 14 106 27 104 48C130 30 147 56 130 77C153 87 138 110 113 114L94 132Z','pink') +
        path('M61 124L99 124L104 139H56Z','cream') +
        line('M67 120L35 75M75 119L55 48M83 119L89 43M91 119L120 62M98 121L130 94',stroke='brown',stroke_width=3))
    add('Nature', 'feather',
        path('M35 119C21 89 53 36 126 20C139 72 111 111 59 121Z','blue') +
        line('M26 141L119 30M44 119L39 95M60 100L56 73M77 80L75 53M62 99L90 101M80 77L107 78M96 58L120 58',stroke_width=3))
    add('Nature', 'nest',
        ellipse(80,95,61,26,'brown') +
        ellipse(59,81,16,23,'white',transform='rotate(-20 59 81)') +
        ellipse(94,77,17,24,'blue',transform='rotate(12 94 77)') +
        path('M19 91Q80 129 141 91L131 119Q80 152 29 119Z','brown') +
        line('M29 104L111 128M48 129L129 105M24 117L103 137M47 101L134 121',stroke='cream',stroke_width=3))
    add('Nature', 'fire',
        path('M57 128C18 114 30 76 46 58Q44 81 58 85C54 44 82 33 80 15Q115 42 111 74Q121 65 124 53C153 110 121 144 85 144Z','orange') +
        path('M80 135C52 128 62 105 80 81Q80 102 95 103Q112 127 80 135Z','yellow'))

    add('Food', 'sandwich',
        path('M25 108L106 43L139 114L55 139Z','cream') +
        path('M25 91L106 26L139 97L55 122Z','cream') +
        path('M25 99L55 130L139 105V115L55 140L25 110Z','brown') +
        path('M25 92L55 121L139 98L132 109L56 132L30 110Z','green') +
        path('M25 86L106 21L139 92L55 118Z','cream') +
        path('M37 85L102 34L125 86L58 105Z','white',stroke='none'))
    add('Food', 'burger',
        path('M27 72C29 14 131 14 133 72Z','brown') +
        ''.join(line(f'M{x} {y}l4-2',stroke='cream',stroke_width=3) for x,y in [(50,50),(75,40),(103,48),(84,59)]) +
        rect(24,95,112,26,'darkbrown',rx=12) +
        path('M24 91H136L109 109L84 100L57 110L24 100Z','yellow') +
        path('M22 77Q35 69 47 79Q59 69 72 79Q86 69 99 79Q113 69 138 77L133 91H27Z','green') +
        path('M25 119H135Q132 141 110 141H50Q28 141 25 119Z','brown'))
    def ring(radius, inner):
        return (f'M{80-radius} 80A{radius} {radius} 0 1 1 {80+radius} 80A{radius} {radius} 0 1 1 {80-radius} 80Z'
                f'M{80-inner} 80A{inner} {inner} 0 1 0 {80+inner} 80A{inner} {inner} 0 1 0 {80-inner} 80Z')
    add('Food', 'doughnut', path(ring(55,19),'brown') + path(ring(47,26),'pink',stroke_width=3) +
        line('M51 51l7 3M99 47l-4 6M116 83l-7-2M90 116l-4-6M45 98l7-3',stroke='white',stroke_width=3))
    add('Food', 'pancake',
        ellipse(80,129,63,17,'white') +
        rect(31,88,98,37,'brown',rx=15) + line('M33 105H127',stroke='cream',stroke_width=4) +
        ellipse(80,87,49,16,'cream') +
        path('M45 82Q80 63 115 82V104Q105 117 99 97Q89 108 84 94Q73 104 65 92L45 94Z','ochre') +
        path('M63 68L93 62L105 75L74 83Z','yellow') + line('M74 83V90L105 82V75',stroke_width=3))
    add('Food', 'popcorn',
        path('M36 70L47 140H113L124 70Z','red') +
        path('M51 73L59 137H72L68 73M92 73L88 137H101L109 73','cream',stroke='none') +
        path('M31 73C15 64 21 45 35 44C29 27 49 19 60 30C65 10 89 12 94 30C111 16 131 30 125 45C145 47 144 70 128 74Z','white') +
        line('M46 48Q49 37 60 42M78 34Q91 35 88 47M104 53Q116 47 121 58',stroke='cream',stroke_width=4) +
        line('M36 76H124'))
    add('Food', 'pumpkin',
        path('M70 48L69 22L88 18L91 45Z','green') +
        ellipse(80,90,60,47,'orange') + ellipse(80,90,39,47,'orange') +
        ellipse(80,90,17,47,'orange') + line('M88 34Q113 23 119 38Q120 48 111 48',stroke='green',stroke_width=4))
    add('Food', 'cabbage',
        circle(80,83,53,'palegreen') +
        path('M80 133Q19 139 22 88Q49 77 80 133Z','green') +
        path('M80 133Q141 139 138 88Q111 77 80 133Z','green') +
        path('M43 72Q48 40 78 45Q108 43 117 70Q95 67 80 100Q65 68 43 72Z','palegreen') +
        line('M36 101L76 130M124 101L84 130M80 58V90',stroke='white',stroke_width=3))
    add('Food', 'lettuce',
        path('M64 125L66 141H96L99 123Z','cream') +
        path('M79 133C57 140 38 119 44 103C17 103 12 77 31 64C15 45 36 22 54 31C61 11 87 12 94 31C115 14 139 35 126 55C149 64 145 92 124 98C135 119 111 139 94 130Z','green') +
        line('M80 133V49M80 101L48 70M80 113L114 77M80 78L100 55',stroke='palegreen',stroke_width=4))
    add('Food', 'radish',
        path('M77 55Q43 37 45 18Q72 17 80 49Q81 15 107 20Q113 39 86 57Z','green') +
        path('M80 53C32 47 28 100 54 117Q72 125 80 143Q84 123 103 116C133 99 126 47 80 53Z','red') +
        path('M54 117Q72 125 80 143Q84 123 103 116Q80 126 54 117Z','white',stroke='none') +
        path('M80 53C32 47 28 100 54 117Q72 125 80 143Q84 123 103 116C133 99 126 47 80 53Z') +
        line('M80 142l-2 6',stroke_width=3) + line('M53 76Q48 87 53 94',stroke='white',stroke_width=4))
    add('Food', 'blueberry',
        circle(103,62,30,'blue') + circle(54,91,32,'blue') + circle(104,111,29,'blue') +
        path('M103 44L108 55L119 55L111 63L113 74L103 68L93 74L95 63L87 55H98Z','purple',stroke_width=3) +
        path('M54 73L59 84H70L62 92L64 103L54 97L44 103L46 92L38 84H49Z','purple',stroke_width=3) +
        path('M104 96L108 105H118L111 112L113 122L104 117L95 122L97 112L90 105H100Z','purple',stroke_width=3))

    add('Animals', 'crocodile',
        path('M24 97L17 66L44 84L62 68L76 77L91 64L103 78L121 76L140 90L136 117H58Z','green') +
        path('M54 115L49 137H69L76 119M104 118L110 137H130L121 112','green') +
        path('M78 80Q70 56 84 55Q101 53 103 80','green') + eye(87,68) +
        line('M68 101H136',stroke_width=3) + path('M84 102L90 113L96 102M111 102L117 113L123 102','white',stroke_width=3))
    add('Animals', 'snake',
        path('M43 138C13 132 16 94 45 91L101 94C120 95 119 77 103 77L70 77C32 76 33 29 72 29L110 32V56L73 53C57 52 57 57 72 58L105 58C149 59 151 116 104 117L46 114Q33 116 45 122Q56 128 43 138Z','green') +
        ellipse(116,44,25,19,'green') + eye(119,37) +
        line('M139 47L149 50M149 50L153 45M149 50L153 55',stroke='red',stroke_width=3) +
        line('M46 101l-1 9M69 103l-1 9M86 63l-1 9',stroke='palegreen',stroke_width=4))
    add('Animals', 'spider',
        line('M55 70L30 45L18 61M52 86L23 77L15 94M54 103L26 111L20 132M65 115L48 135L49 146M105 70L130 45L142 61M108 86L137 77L145 94M106 103L134 111L140 132M95 115L112 135L111 146',stroke_width=5) +
        ellipse(80,85,30,37,'purple') + circle(80,55,23,'purple') +
        circle(71,51,7,'white') + circle(89,51,7,'white') + eye(72,52,2) + eye(88,52,2) +
        line('M74 67Q80 73 86 67',stroke_width=3))
    add('Animals', 'ant',
        line('M59 75L33 58L21 74M60 88L32 90L20 107M64 101L45 123L46 140M98 75L124 58L137 74M100 88L127 90L140 107M96 101L115 123L114 140',stroke_width=4) +
        ellipse(80,111,23,27,'brown') + ellipse(80,81,19,21,'brown') +
        line('M67 41L51 24L43 31M93 41L109 24L117 31',stroke_width=4) +
        circle(80,51,25,'brown') + eye(70,49) + eye(90,49) + line('M73 62Q80 68 87 62',stroke_width=3))
    add('Animals', 'ladybird',
        line('M45 71L29 60M41 93H23M48 114L30 127M115 71L131 60M119 93H137M112 114L130 127M68 39L57 22M92 39L103 22',stroke_width=4) +
        circle(80,52,24,'ink') + ellipse(80,94,43,48,'red') + line('M80 48V140') +
        ''.join(circle(x,y,7,'ink',stroke='none') for x,y in [(58,77),(54,103),(65,122),(102,77),(106,103),(95,122)]) +
        circle(72,43,3,'white',stroke='none') + circle(88,43,3,'white',stroke='none'))
    add('Animals', 'dragonfly',
        ellipse(48,63,33,13,'blue',transform='rotate(25 48 63)') +
        ellipse(112,63,33,13,'blue',transform='rotate(-25 112 63)') +
        ellipse(47,91,31,12,'palegreen',transform='rotate(-15 47 91)') +
        ellipse(113,91,31,12,'palegreen',transform='rotate(15 113 91)') +
        rect(72,53,16,86,'green',rx=8) + line('M73 86H87M73 103H87M73 120H87',stroke_width=3) +
        circle(80,44,16,'green') + eye(73,40) + eye(87,40))
    add('Animals', 'bat',
        path('M65 74L21 38Q25 71 15 101Q34 89 45 109Q59 100 70 124H90Q101 100 115 109Q126 89 145 101Q135 71 139 38L95 74Z','purple') +
        path('M65 73L61 35L78 48L99 35L95 73V107Q80 130 65 107Z','purple') +
        eye(73,65) + eye(87,65) + line('M72 85Q80 92 88 85M27 57L64 94M133 57L96 94',stroke_width=3))
    add('Animals', 'owl',
        path('M42 59L34 22L66 38Q80 32 94 38L126 22L118 59Q140 126 80 141Q20 126 42 59Z','brown') +
        path('M43 85Q29 103 44 124L61 113M117 85Q131 103 116 124L99 113','brown') +
        circle(59,65,23,'cream') + circle(101,65,23,'cream') + eye(59,65,7) + eye(101,65,7) +
        path('M72 88H88L80 100Z','yellow') +
        line('M65 111l6 5M89 116l6-5M72 128l8 5l8-5M59 139H71M89 139H101',stroke_width=3))
    add('Animals', 'hedgehog',
        path('M37 116L24 98L32 84L25 69L44 62L45 44L63 46L72 28L88 39L104 28L111 48L131 49L127 69L143 80L132 98L137 116Z','brown') +
        path('M24 119L49 90Q63 83 72 102Q81 77 99 91Q113 82 124 101L134 119Q81 139 24 119Z','cream') +
        circle(22,118,5,'ink') + eye(54,109) + line('M55 132H65M105 132H115',stroke_width=5))
    add('Animals', 'crab',
        line('M47 95L23 89L14 105M47 109L24 116L22 131M113 95L137 89L146 105M113 109L136 116L138 131M51 78L31 62M109 78L129 62',stroke_width=12) +
        line('M47 95L23 89L14 105M47 109L24 116L22 131M113 95L137 89L146 105M113 109L136 116L138 131M51 78L31 62M109 78L129 62',stroke='orange',stroke_width=7) +
        path('M28 67C7 61 10 35 25 29L27 48L43 37C54 52 43 68 28 67Z','orange') +
        path('M132 67C153 61 150 35 135 29L133 48L117 37C106 52 117 68 132 67Z','orange') +
        ellipse(80,99,37,30,'orange') + line('M66 74V58M94 74V58',stroke_width=6) +
        circle(66,55,7,'white') + circle(94,55,7,'white') + eye(66,55,2) + eye(94,55,2) +
        line('M70 105Q80 116 90 105',stroke_width=3))

    add('Home', 'phone',
        rect(46,16,68,128,'gray',rx=12) + rect(53,31,54,91,'blue',rx=3) +
        line('M70 24H90',stroke_width=3) + circle(80,133,4,'white') +
        line('M64 55L88 39M65 74L98 51',stroke='white',stroke_width=4))
    add('Home', 'camera',
        path('M25 53H49L58 36H100L109 53H135V131H25Z','gray') +
        rect(32,43,18,10,'gray',rx=2) + circle(82,89,31,'ink') + circle(82,89,22,'blue') +
        line('M71 83Q76 73 86 76',stroke='white',stroke_width=4) + rect(114,63,12,9,'white',rx=2))
    add('Home', 'computer',
        rect(24,22,112,81,'gray',rx=7) + rect(33,31,94,61,'blue',rx=3) +
        path('M71 103V119H89V103','gray') +
        path('M28 120H132L142 139H18Z','gray') +
        line('M39 126H121M32 132H128M58 125V133M78 125V133M98 125V133',stroke_width=2) +
        line('M44 55L66 39M45 72L85 43',stroke='white',stroke_width=4))
    add('Home', 'television',
        line('M49 24L76 43L102 22M46 128L39 141M114 128L121 141',stroke_width=5) +
        rect(18,43,124,85,'brown',rx=12) + rect(27,53,83,65,'blue',rx=9) +
        circle(126,67,7,'cream') + circle(126,91,7,'cream') +
        line('M120 111H132M41 76L58 62',stroke='cream',stroke_width=3))
    add('Home', 'radio',
        line('M116 53L136 17',stroke_width=5) +
        path('M53 56V39Q80 24 107 39V56',stroke='brown',stroke_width=8) +
        rect(20,55,120,82,'red',rx=11) + circle(59,96,26,'cream') +
        ''.join(line(f'M{x} 78V114',stroke='brown',stroke_width=3) for x in (46,55,64,73)) +
        rect(96,68,32,12,'cream',rx=2) + circle(111,105,12,'cream') + line('M111 105l5-6',stroke_width=3))
    add('Home', 'candle',
        ellipse(80,135,47,11,'gray') + rect(59,65,42,70,'cream',rx=4) +
        path('M59 65Q69 56 80 65Q91 56 101 65V84Q91 98 87 77Q76 91 72 77Q63 91 59 80Z','white') +
        line('M80 64V47',stroke_width=3) +
        path('M80 18C59 38 61 53 80 53C99 53 101 38 80 18Z','yellow'))
    add('Home', 'hammer', group(
        rect(71,56,19,88,'brown',rx=6) +
        path('M32 30H102L127 45L120 64L97 55H60V66H32Z','gray') +
        line('M77 77V123',stroke='cream',stroke_width=3), 'rotate(20 80 80)'))
    add('Home', 'saw',
        path('M51 52L140 107L133 116L124 110L119 119L110 113L105 122L96 116L91 125L82 119L77 128L47 107Z','gray') +
        path('M23 38L60 52L49 112L17 98Z','brown') +
        path('M31 55L46 61L40 91L28 86Z','white') + circle(53,69,3,'ink',stroke='none'))
    add('Home', 'ladder',
        rect(42,17,13,126,'brown',rx=3) + rect(105,17,13,126,'brown',rx=3) +
        ''.join(rect(55,y,50,9,'cream',rx=2) for y in (35,60,85,110)))
    add('Home', 'bucket',
        path('M39 71Q34 17 80 17Q126 17 121 71',stroke='gray',stroke_width=7) +
        path('M30 65H130L115 140H45Z','blue') + ellipse(80,65,50,12,'blue') +
        line('M46 85L53 121',stroke='white',stroke_width=4))
    add('Home', 'watering-can',
        path('M102 56Q145 34 143 80Q142 106 117 103',stroke='green',stroke_width=9) +
        path('M47 100L21 64L29 52L64 83Z','green') +
        path('M16 53L31 42L38 56L22 68Z','green') +
        rect(50,65,69,70,'green',rx=16) + ellipse(84,65,34,10,'palegreen') +
        path('M73 58V44H96V58','green') + line('M65 89V115',stroke='palegreen',stroke_width=4))
    add('Home', 'backpack',
        path('M63 32V21Q80 13 97 21V32',stroke='brown',stroke_width=7) +
        path('M42 52Q17 66 30 119M118 52Q143 66 130 119',stroke='brown',stroke_width=8) +
        rect(38,31,84,111,'blue',rx=23) + path('M40 55Q80 41 120 55',stroke_width=3) +
        rect(52,86,56,40,'blue',rx=8) + line('M54 98H106M101 98V107',stroke_width=3) +
        path('M67 31H93V68L80 77L67 68Z','cream'))
    add('Home', 'bag',
        path('M52 57V43Q52 15 80 15Q108 15 108 43V57',stroke='brown',stroke_width=8) +
        path('M37 51H123L134 140H26Z','pink') +
        line('M52 50V65M108 50V65',stroke='brown',stroke_width=6) +
        path('M61 95Q80 78 99 95Q80 114 61 95Z','white',stroke_width=3))
    add('Home', 'envelope',
        rect(19,40,122,86,'cream',rx=5) +
        path('M20 42L80 87L140 42M21 123L62 84M139 123L98 84',stroke_width=4))
    add('Home', 'ruler', group(
        rect(19,60,122,40,'yellow',rx=3) +
        ''.join(line(f'M{x} 61V{80 if i%2==0 else 72}',stroke_width=3) for i,x in enumerate(range(30,133,10))) +
        circle(30,90,3,'white',stroke_width=2), 'rotate(-25 80 80)'))

    add('Clothing and toys', 'balloon',
        line('M80 112Q106 125 83 143Q70 150 77 154',stroke_width=3) +
        path('M75 108L68 120H92L85 108Z','red') +
        ellipse(80,64,44,51,'red') + line('M55 46Q47 60 52 75',stroke='white',stroke_width=5))
    add('Clothing and toys', 'doll',
        path('M58 128L56 143H72L77 124M102 128L104 143H88L83 124','cream') +
        path('M58 82L30 111L37 121L63 106M102 82L130 111L123 121L97 106','cream') +
        path('M63 72H97L113 130H47Z','pink') +
        circle(80,45,28,'cream') +
        path('M53 46Q43 20 65 17Q80 6 97 20Q117 22 107 48L93 29L76 38L65 28Z','brown') +
        eye(70,45,2) + eye(90,45,2) + line('M73 57Q80 63 87 57',stroke_width=3) +
        path('M65 74L80 87L95 74','white'))
    add('Clothing and toys', 'puzzle',
        path('M27 28H70V43C55 38 54 62 70 57V79H48C56 95 32 98 36 80H27Z','blue') +
        path('M78 28H132V70H117C123 55 99 53 103 70H78V57C95 62 94 38 78 43Z','yellow') +
        path('M27 88H38C32 105 57 104 52 88H70V108C54 103 53 127 70 122V140H27Z','green') +
        path('M78 79H103C98 96 122 95 117 79H132V140H78V122C94 128 95 103 78 108Z','red'))
    add('Clothing and toys', 'guitar', group(
        path('M69 70C49 59 35 79 43 94C16 119 40 146 68 134C93 141 110 119 91 98C101 79 91 63 78 70Z','brown') +
        rect(68,35,12,68,'cream',rx=2) + rect(62,14,24,31,'brown',rx=5) +
        circle(67,107,15,'darkbrown') + rect(52,125,29,7,'cream',rx=2) +
        line('M72 27V128M77 27V128',stroke='white',stroke_width=1.5) +
        line('M58 23H62M86 23H90M58 35H62M86 35H90',stroke_width=4), 'rotate(20 80 80)'))
    add('Clothing and toys', 'cap',
        path('M29 90C25 28 121 24 128 87Z','blue') +
        path('M78 44Q102 52 105 87',stroke_width=3) +
        path('M27 88Q80 79 111 88L143 105Q111 126 59 112L27 103Z','blue') +
        circle(78,40,5,'blue') + line('M40 62Q48 51 59 49',stroke='white',stroke_width=4))

    add('Transport', 'hot-air-balloon',
        path('M46 95L64 126M114 95L96 126',stroke='brown',stroke_width=4) +
        path('M80 15C23 15 18 68 46 95L62 111H98L114 95C142 68 137 15 80 15Z','blue') +
        path('M80 15C48 34 50 78 62 111H98C110 78 112 34 80 15Z','yellow') +
        path('M80 15C67 46 68 83 73 111H87C92 83 93 46 80 15Z','red') +
        rect(61,124,38,23,'brown',rx=4) + line('M63 132H97',stroke='cream',stroke_width=3))
    add('Transport', 'skateboard',
        circle(47,119,12,'gray') + circle(113,119,12,'gray') +
        path('M17 79Q30 98 80 98Q130 98 143 79L145 98Q129 115 80 115Q31 115 15 98Z','brown') +
        path('M17 79Q30 93 80 93Q130 93 143 79L145 90Q129 105 80 105Q31 105 15 90Z','blue') +
        line('M38 94l4 1M118 95l4-1',stroke_width=3))
    add('Transport', 'submarine',
        path('M61 56V28H92V43H78V57','yellow') +
        path('M123 69L143 55V110L123 96Z','yellow') +
        rect(18,56,111,62,'yellow',rx=31) +
        circle(48,86,14,'blue') + circle(88,86,14,'blue') +
        line('M38 126H114',stroke='blue',stroke_width=3))
    add('Transport', 'fire-engine',
        path('M18 65H100L121 85H141V123H18Z','red') +
        path('M102 72L115 87H94V72Z','blue') + rect(69,72,17,16,'blue',rx=2) +
        rect(24,77,36,32,'gray',rx=2) + line('M26 88H58M26 98H58',stroke_width=3) +
        rect(33,41,96,10,'gray',rx=2) + rect(33,57,96,8,'gray',rx=2) +
        line('M44 44V63M63 44V63M82 44V63M101 44V63M120 44V63',stroke_width=3) +
        rect(87,57,16,9,'blue',rx=3) + wheel(43,124,16) + wheel(118,124,16))
    add('Transport', 'traffic-light',
        rect(72,119,16,26,'gray',rx=3) + rect(53,15,54,110,'gray',rx=10) +
        path('M52 33H36L52 48M108 33H124L108 48M52 67H36L52 82M108 67H124L108 82M52 101H36L52 116M108 101H124L108 116','gray') +
        circle(80,36,12,'red') + circle(80,70,12,'yellow') + circle(80,104,12,'green') +
        line('M58 146H102',stroke_width=5))

    add('Nature', 'acorn',
        path('M44 71Q40 120 80 143Q120 120 116 71Z','brown') +
        path('M80 45Q77 24 92 18',stroke='brown',stroke_width=8) +
        path('M33 71Q37 39 80 39Q123 39 127 71Z','cream') +
        line('M47 56L57 68M64 48L81 68M86 47L106 68M60 47L44 68M82 47L65 68M105 52L88 68',stroke='brown',stroke_width=3) +
        line('M57 88Q56 107 70 119',stroke='cream',stroke_width=4))
    add('Nature', 'pinecone',
        path('M80 24C49 24 34 72 39 108Q43 137 80 144Q117 137 121 108C126 72 111 24 80 24Z','brown') +
        line('M80 24V15',stroke_width=5) +
        path('M61 42L80 60L99 42M47 63L64 82L80 65L96 82L113 63M40 89L59 108L80 88L101 108L120 89M44 115L62 132L80 113L98 132L116 115',stroke='cream',stroke_width=3))
    add('Nature', 'cactus',
        path('M68 119V76H45Q24 76 24 55V41Q24 27 38 27Q50 27 50 41V52H68V30Q68 14 82 14Q96 14 96 30V71H112V56Q112 42 125 42Q138 42 138 56V78Q138 97 116 97H96V119Z','green') +
        path('M51 117H111L103 145H59Z','brown') +
        line('M80 31V107M35 40V57M124 55V79',stroke='palegreen',stroke_width=3))
    add('Nature', 'raindrop',
        path('M80 16C69 45 32 75 32 103C32 158 128 158 128 103C128 75 91 45 80 16Z','blue') +
        line('M54 93Q45 115 65 126',stroke='white',stroke_width=6))
    add('Nature', 'snowman',
        circle(80,110,37,'white') + circle(80,58,27,'white') +
        line('M44 100L20 79M22 81L18 67M116 100L140 79M138 81L142 67',stroke='brown',stroke_width=4) +
        path('M57 77Q80 88 103 77V89Q80 101 57 89Z','red') + rect(91,88,12,28,'red',rx=2) +
        rect(57,18,46,22,'ink',rx=3) + rect(45,37,70,8,'ink',rx=2) +
        eye(70,56,2.5) + eye(90,56,2.5) + path('M78 62L106 68L78 72Z','orange',stroke_width=3) +
        ''.join(circle(80,y,3,'ink',stroke='none') for y in (104,119,133)))


def svg_art(art, label):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160" role="img" aria-labelledby="title">
<!-- Copyright 2026 Michael Brackx. SPDX-License-Identifier: Apache-2.0 -->
<title id="title">{escape(label)}</title>
<g fill="none" stroke="{P['ink']}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">{art}</g>
</svg>\n'''


def stacked_art(art):
    # Two diagonal copies, with a small inset to fit even the widest drawings.
    return group(art, 'translate(36 2) scale(.78)') + group(art, 'translate(-2 32) scale(.78)')


def sheet(words, title, columns=5, compact=False, artwork=None, labels=None):
    artwork = ART if artwork is None else artwork
    cell = 194 if compact else 212
    card_h = 178 if compact else 210
    row_step = card_h + 16
    width = 40 + columns * cell
    rows = math.ceil(len(words) / columns)
    height = 112 + rows * row_step
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             f'<rect width="{width}" height="{height}" fill="#F6F4EE"/>',
             f'<text x="28" y="43" font-family="Arial" font-size="28" font-weight="bold" fill="{P["ink"]}">{escape(title)}</text>',
             '<text x="28" y="72" font-family="Arial" font-size="15" fill="#626770">Original first-words illustrations · editable vectors · Apache 2.0</text>']
    for i, name in enumerate(words):
        x, y = 24 + (i % columns) * cell, 92 + (i // columns) * row_step
        art_size = 130 if compact else 156
        art_x = x + (cell - 14 - art_size) / 2
        parts.append(f'<rect x="{x}" y="{y}" width="{cell-14}" height="{card_h}" rx="14" fill="#FFFDF8" stroke="#E2DED4"/>')
        parts.append(f'<g transform="translate({art_x},{y+8}) scale({art_size/160})" fill="none" stroke="{P["ink"]}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">{artwork[name]}</g>')
        label = labels[name] if labels else name.replace('-', ' ')
        parts.append(f'<text x="{x+(cell-14)/2}" y="{y+card_h-19}" text-anchor="middle" font-family="Arial" font-size="{16 if compact else 18}" fill="{P["ink"]}">{escape(label)}</text>')
    parts.append('</svg>')
    return '\n'.join(parts)


def gallery():
    cards = []
    aliases = json.loads((HERE / 'aliases.json').read_text())
    for category, words in CATEGORIES.items():
        for name in words:
            label = name.replace('-', ' ')
            art = svg_art(ART[name], label).replace('aria-labelledby="title"', f'aria-label="{label}"').replace('<title id="title">', '<title>')
            search = escape(' '.join(spellings(dict(id=name, label=label, aliases=aliases[name]))), quote=True)
            cards.append(f'<button class="card" data-word="{label}" data-search="{search}" data-file="{name}" data-category="{category}">{art}<span>{label}</span></button>')
    categories = ''.join(f'<option>{escape(c)}</option>' for c in CATEGORIES)
    return ('''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>First words — __DRAWING_COUNT__ original drawings</title><style>
:root{color-scheme:light;font-family:system-ui,sans-serif;color:#314047;background:#f6f4ee}*{box-sizing:border-box}body{margin:0;padding:36px;max-width:1440px;margin-inline:auto}h1{font-size:clamp(26px,4vw,44px);letter-spacing:-.04em;margin:0 0 12px}p{max-width:800px;line-height:1.55}header{margin-bottom:28px}.tools{display:flex;gap:12px;flex-wrap:wrap;margin:22px 0}input,select{font:inherit;padding:12px 16px;border:1px solid #d4d6ce;border-radius:10px;background:#fffdf8;color:inherit}input{width:min(360px,100%)}#status{margin-left:auto;align-self:center;color:#626770}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:16px}.card{font:inherit;color:inherit;border:1px solid #e2ded4;background:#fffdf8;border-radius:16px;display:flex;flex-direction:column;align-items:center;padding:15px 12px 20px;gap:8px;cursor:pointer}.card:hover,.card:focus-visible{outline:3px solid #89b9cc;outline-offset:2px}.card svg{width:144px;max-width:100%;height:144px}.card span{font-weight:500}a{color:#275f71}dialog{border:1px solid #e2ded4;border-radius:20px;padding:24px;max-width:min(94vw,480px);width:480px;background:#fffdf8;color:#314047}dialog::backdrop{background:#31404788}.large svg{width:100%;height:300px}dialog h2{text-align:center;font-size:28px;margin:8px}dialog .actions{display:flex;justify-content:space-between;align-items:center;margin-top:24px}.close{font:inherit;border:1px solid #d4d6ce;border-radius:8px;background:white;padding:8px 14px;cursor:pointer}footer{font-size:14px;margin-top:36px;color:#626770}[hidden]{display:none!important}@media(max-width:550px){body{padding:24px 16px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.card svg{height:124px}.tools input{width:100%}#status{margin-left:0}}
</style></head><body><header><h1>First words</h1><p>__DRAWING_COUNT__ original drawings with a shared palette and rounded outlines. Select a drawing to inspect it and download its editable SVG.</p><div class="tools"><input id="search" type="search" placeholder="Find a word…" aria-label="Find a drawing"><select id="category" aria-label="Category"><option value="">All categories</option>''' + categories + '''</select><span id="status" aria-live="polite">__DRAWING_COUNT__ drawings</span></div></header><main class="grid">''' + ''.join(cards) + '''</main><dialog id="detail"><div class="large"></div><h2></h2><div class="actions"><a class="download" download>Download SVG</a><button class="close">Close</button></div></dialog><footer><p>Original artwork licensed under <a href="LICENSE.txt">Apache 2.0</a>. No external images or fonts. Labels are ordinary text; the drawings are not a font.</p><p>This is a curated first vocabulary, not a measured frequency ranking. <a href="manifest.json">Vocabulary and palette</a> · <a href="first-words-svg.zip">Download SVG set</a></p></footer><script>
const search=document.querySelector('#search'),category=document.querySelector('#category'),cards=[...document.querySelectorAll('.card')],status=document.querySelector('#status'),detail=document.querySelector('#detail');
function filter(){const q=search.value.trim().toLowerCase(),c=category.value;let n=0;for(const card of cards){card.hidden=!(card.dataset.search.includes(q)&&(!c||card.dataset.category===c));if(!card.hidden)n++;}status.textContent=n+' drawing'+(n===1?'':'s');}
search.addEventListener('input',filter);category.addEventListener('change',filter);
for(const card of cards)card.addEventListener('click',()=>{detail.querySelector('.large').replaceChildren(card.querySelector('svg').cloneNode(true));detail.querySelector('h2').textContent=card.dataset.word;detail.querySelector('.download').href='artwork/'+card.dataset.file+'.svg';detail.showModal();});
detail.querySelector('.close').addEventListener('click',()=>detail.close());detail.addEventListener('click',e=>{if(e.target===detail){const r=detail.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)detail.close();}});
</script></body></html>''').replace('__DRAWING_COUNT__', str(len(ART)))


def export(out):
    assert len(ART) == 200, f'Expected 200 illustrations, got {len(ART)}'
    expected = [40, 40, 50, 20, 20, 20, 10]
    assert list(map(len, CATEGORIES.values())) == expected
    aliases = json.loads((HERE / 'aliases.json').read_text())
    plurals = json.loads((HERE / 'plurals.json').read_text())
    assert set(aliases) == set(ART), 'Alias keys must match the drawing IDs'
    assert set(plurals) == set(ART), 'Plural keys must match the drawing IDs'
    drawings = [dict(id=n, label=n.replace('-', ' '), aliases=aliases[n], plurals=plurals[n], category=c,
                     plural_file=f'artwork/plurals/{n}.svg' if plurals[n] else None,
                     file=f'artwork/{n}.svg')
                for c, words in CATEGORIES.items() for n in words]
    validate_labels(drawings)
    out.mkdir(parents=True, exist_ok=True)
    assets, previews = out / 'artwork', out / 'previews'
    assets.mkdir(exist_ok=True)
    (assets / 'plurals').mkdir(exist_ok=True)
    previews.mkdir(exist_ok=True)
    expected_plurals = {f'{n}.svg' for n in ART if plurals[n]}
    for file in (assets / 'plurals').glob('*.svg'):
        if file.name not in expected_plurals:
            file.unlink()
    for name in ('all-100.svg', 'new-50.svg'):
        (previews / name).unlink(missing_ok=True)
    counts = {}
    for name, art in ART.items():
        svg = svg_art(art, name.replace('-', ' '))
        root = ET.fromstring(svg)
        assert root.attrib['viewBox'] == '0 0 160 160'
        for element in root.iter():
            assert element.tag.split('}')[-1] not in {'image', 'script', 'text', 'foreignObject'}
            for attr in ('fill', 'stroke'):
                value = element.get(attr, 'none')
                assert value == 'none' or value in P.values(), (name, attr, value)
        file = assets / f'{name}.svg'
        file.write_text(svg)
        counts[name] = len(svg.encode())
        if plurals[name]:
            (assets / 'plurals' / f'{name}.svg').write_text(svg_art(stacked_art(art), plurals[name][0]))
    for drawing in drawings:
        drawing['svg_bytes'] = counts[drawing['id']]
    manifest = dict(title=f'First words — {len(ART)} original vector illustrations', version=2,
                    license='Apache-2.0', language='en', selection='curated; not a corpus-derived frequency ranking',
                    viewBox=[0,0,160,160], outline_width=5, palette=P,
                    count=len(ART), plural_count=sum(bool(v) for v in plurals.values()),
                    plural_layout='two diagonal copies at 78% scale in the original canvas',
                    categories={c:len(w) for c,w in CATEGORIES.items()},
                    drawings=drawings)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (previews / 'all-words.svg').write_text(sheet(list(ART), f'First words — all {len(ART)} drawings', columns=10, compact=True))
    plural_art = {n:stacked_art(ART[n]) for n in ART if plurals[n]}
    (previews / 'plurals.svg').write_text(sheet(list(plural_art), 'First words — stacked plurals',
        columns=10, compact=True, artwork=plural_art, labels={n:plurals[n][0] for n in plural_art}))
    for category, words in CATEGORIES.items():
        slug = category.lower().replace(' ', '-')
        (previews / f'{slug}.svg').write_text(sheet(words, category))
    (out / 'index.html').write_text(gallery())
    for name in ('LICENSE.txt', 'NOTICE.txt'):
        (out / name).write_text((HERE / name).read_text())
    files = [out / d['file'] for d in drawings]
    files.extend(out / d['plural_file'] for d in drawings if d['plural_file'])
    files.extend(previews / name for name in ['all-words.svg', 'plurals.svg',
                 *(c.lower().replace(' ', '-')+'.svg' for c in CATEGORIES)])
    files.extend(out / name for name in ('LICENSE.txt', 'NOTICE.txt', 'manifest.json'))
    entries = [(file.relative_to(out).as_posix(), file.read_bytes()) for file in files]
    entries.extend((name, (HERE / name).read_bytes()) for name in
                   ('generate_artwork.py', 'approved_samples.json', 'aliases.json', 'plurals.json',
                    'word_labels.py', 'bundles.py', 'readme.md'))
    entries.append(('index.html', gallery().replace(' · <a href="first-words-svg.zip">Download SVG set</a>', '').encode()))
    write_bundle(out / 'first-words-svg.zip', entries)
    print(f'Generated {len(ART)} original SVGs; {sum(counts.values()):,} total SVG bytes.')
    print('Categories:', ', '.join(f'{c}: {len(w)}' for c,w in CATEGORIES.items()))
    print(f'Gallery: {out / "index.html"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE)
    args = parser.parse_args()
    base = json.loads((HERE / 'approved_samples.json').read_text())
    food(base)
    animals(base)
    home(base)
    clothes_and_toys()
    transport()
    nature()
    body()
    additional_words()
    export(args.output)


if __name__ == '__main__':
    main()
