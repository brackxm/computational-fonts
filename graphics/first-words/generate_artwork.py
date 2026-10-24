#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Generate original first-words SVG illustrations and review sheets. No font build."""

from pathlib import Path
from html import escape
import argparse
import json
import math
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

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


def clothes_and_toys(base):
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
    add('Clothing and toys', 'ball', base['ball'])
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


def svg_art(art, label):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160" role="img" aria-labelledby="title">
<!-- Original artwork. SPDX-License-Identifier: CC0-1.0 -->
<title id="title">{escape(label)}</title>
<g fill="none" stroke="{P['ink']}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">{art}</g>
</svg>\n'''


def sheet(words, title, columns=5, compact=False):
    cell = 194 if compact else 212
    card_h = 178 if compact else 210
    row_step = card_h + 16
    width = 40 + columns * cell
    rows = math.ceil(len(words) / columns)
    height = 112 + rows * row_step
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             f'<rect width="{width}" height="{height}" fill="#F6F4EE"/>',
             f'<text x="28" y="43" font-family="Arial" font-size="28" font-weight="bold" fill="{P["ink"]}">{escape(title)}</text>',
             '<text x="28" y="72" font-family="Arial" font-size="15" fill="#626770">Original first-words illustrations · editable vectors · CC0</text>']
    for i, name in enumerate(words):
        x, y = 24 + (i % columns) * cell, 92 + (i // columns) * row_step
        art_size = 130 if compact else 156
        art_x = x + (cell - 14 - art_size) / 2
        parts.append(f'<rect x="{x}" y="{y}" width="{cell-14}" height="{card_h}" rx="14" fill="#FFFDF8" stroke="#E2DED4"/>')
        parts.append(f'<g transform="translate({art_x},{y+8}) scale({art_size/160})" fill="none" stroke="{P["ink"]}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">{ART[name]}</g>')
        parts.append(f'<text x="{x+(cell-14)/2}" y="{y+card_h-19}" text-anchor="middle" font-family="Arial" font-size="{16 if compact else 18}" fill="{P["ink"]}">{escape(name.replace("-", " "))}</text>')
    parts.append('</svg>')
    return '\n'.join(parts)


def gallery():
    cards = []
    for category, words in CATEGORIES.items():
        for name in words:
            label = name.replace('-', ' ')
            art = svg_art(ART[name], label).replace('aria-labelledby="title"', f'aria-label="{label}"').replace('<title id="title">', '<title>')
            cards.append(f'<button class="card" data-word="{label}" data-file="{name}" data-category="{category}">{art}<span>{label}</span></button>')
    categories = ''.join(f'<option>{escape(c)}</option>' for c in CATEGORIES)
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>First words — 100 original drawings</title><style>
:root{color-scheme:light;font-family:system-ui,sans-serif;color:#314047;background:#f6f4ee}*{box-sizing:border-box}body{margin:0;padding:36px;max-width:1440px;margin-inline:auto}h1{font-size:clamp(26px,4vw,44px);letter-spacing:-.04em;margin:0 0 12px}p{max-width:800px;line-height:1.55}header{margin-bottom:28px}.tools{display:flex;gap:12px;flex-wrap:wrap;margin:22px 0}input,select{font:inherit;padding:12px 16px;border:1px solid #d4d6ce;border-radius:10px;background:#fffdf8;color:inherit}input{width:min(360px,100%)}#status{margin-left:auto;align-self:center;color:#626770}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:16px}.card{font:inherit;color:inherit;border:1px solid #e2ded4;background:#fffdf8;border-radius:16px;display:flex;flex-direction:column;align-items:center;padding:15px 12px 20px;gap:8px;cursor:pointer}.card:hover,.card:focus-visible{outline:3px solid #89b9cc;outline-offset:2px}.card svg{width:144px;max-width:100%;height:144px}.card span{font-weight:500}a{color:#275f71}dialog{border:1px solid #e2ded4;border-radius:20px;padding:24px;max-width:min(94vw,480px);width:480px;background:#fffdf8;color:#314047}dialog::backdrop{background:#31404788}.large svg{width:100%;height:300px}dialog h2{text-align:center;font-size:28px;margin:8px}dialog .actions{display:flex;justify-content:space-between;align-items:center;margin-top:24px}.close{font:inherit;border:1px solid #d4d6ce;border-radius:8px;background:white;padding:8px 14px;cursor:pointer}footer{font-size:14px;margin-top:36px;color:#626770}[hidden]{display:none!important}@media(max-width:550px){body{padding:24px 16px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.card svg{height:124px}.tools input{width:100%}#status{margin-left:0}}
</style></head><body><header><h1>First words</h1><p>100 original drawings with a shared palette and rounded outlines. Select a drawing to inspect it and download its editable SVG.</p><div class="tools"><input id="search" type="search" placeholder="Find a word…" aria-label="Find a drawing"><select id="category" aria-label="Category"><option value="">All categories</option>''' + categories + '''</select><span id="status" aria-live="polite">100 drawings</span></div></header><main class="grid">''' + ''.join(cards) + '''</main><dialog id="detail"><div class="large"></div><h2></h2><div class="actions"><a class="download" download>Download SVG</a><button class="close">Close</button></div></dialog><footer><p>Original artwork released under <a href="LICENSE.txt">CC0 1.0 Universal</a>. No external images or fonts. Labels are ordinary text; the drawings are not a font.</p><p>This is a curated first vocabulary, not a measured frequency ranking. <a href="manifest.json">Vocabulary and palette</a> · <a href="first-words-100-svg.zip">Download all 100 SVGs</a></p></footer><script>
const search=document.querySelector('#search'),category=document.querySelector('#category'),cards=[...document.querySelectorAll('.card')],status=document.querySelector('#status'),detail=document.querySelector('#detail');
function filter(){const q=search.value.trim().toLowerCase(),c=category.value;let n=0;for(const card of cards){card.hidden=!(card.dataset.word.includes(q)&&(!c||card.dataset.category===c));if(!card.hidden)n++;}status.textContent=n+' drawing'+(n===1?'':'s');}
search.addEventListener('input',filter);category.addEventListener('change',filter);
for(const card of cards)card.addEventListener('click',()=>{detail.querySelector('.large').replaceChildren(card.querySelector('svg').cloneNode(true));detail.querySelector('h2').textContent=card.dataset.word;detail.querySelector('.download').href='artwork/'+card.dataset.file+'.svg';detail.showModal();});
detail.querySelector('.close').addEventListener('click',()=>detail.close());detail.addEventListener('click',e=>{if(e.target===detail){const r=detail.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)detail.close();}});
</script></body></html>'''


def export(out):
    assert len(ART) == 100, f'Expected 100 illustrations, got {len(ART)}'
    expected = [20, 20, 20, 10, 10, 10, 10]
    assert list(map(len, CATEGORIES.values())) == expected
    out.mkdir(parents=True, exist_ok=True)
    assets, previews = out / 'artwork', out / 'previews'
    assets.mkdir(exist_ok=True)
    previews.mkdir(exist_ok=True)
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
    manifest = dict(title='First words — 100 original vector illustrations', version=1,
                    license='CC0-1.0', language='en', selection='curated; not a corpus-derived frequency ranking',
                    viewBox=[0,0,160,160], outline_width=5, palette=P,
                    count=len(ART), categories={c:len(w) for c,w in CATEGORIES.items()},
                    drawings=[dict(id=n, label=n.replace('-', ' '), category=c,
                                   file=f'artwork/{n}.svg', svg_bytes=counts[n])
                              for c, words in CATEGORIES.items() for n in words])
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (previews / 'all-100.svg').write_text(sheet(list(ART), 'First words — all 100 drawings', columns=10, compact=True))
    for category, words in CATEGORIES.items():
        slug = category.lower().replace(' ', '-')
        (previews / f'{slug}.svg').write_text(sheet(words, category))
    (out / 'index.html').write_text(gallery())
    license_text = '''First words — original vector artwork and generator

SPDX-License-Identifier: CC0-1.0

To the extent possible under law, copyright and related rights in the original
SVG artwork, source geometry, previews, vocabulary annotations, approved_samples.json
and generate_artwork.py
in this collection are waived under Creative Commons CC0 1.0 Universal.

https://creativecommons.org/publicdomain/zero/1.0/legalcode

The artwork was generated directly as SVG geometry with assistance from OpenAI
Codex. No third-party illustrations, raster images or icon libraries were used.
The six original approved studies are retained in approved_samples.json.

The font builder, SVG-to-font conversion code, font playground, tests and
compiled fonts are licensed separately under Apache-2.0; see FONT_LICENSE.txt
and FONT_NOTICE.txt. The compiled fonts retain Roboto's Apache-2.0 notices.
'''
    (out / 'LICENSE.txt').write_text(license_text)
    with ZipFile(out / 'first-words-100-svg.zip', 'w', ZIP_DEFLATED) as archive:
        for file in sorted(assets.glob('*.svg')):
            archive.write(file, str(file.relative_to(out)))
        for file in sorted(previews.glob('*.svg')):
            archive.write(file, str(file.relative_to(out)))
        for name in ('LICENSE.txt', 'manifest.json'):
            archive.write(out / name, name)
        for name in ('generate_artwork.py', 'approved_samples.json', 'readme.md'):
            archive.write(HERE / name, name)
        archive.writestr('index.html', gallery().replace(' · <a href="first-words-100-svg.zip">Download all 100 SVGs</a>', ''))
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
    clothes_and_toys(base)
    transport()
    nature()
    body()
    export(args.output)


if __name__ == '__main__':
    main()
