# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Extract complete short poems from pinned public-domain editions, offline.

These parsers target the exact snapshots in sources.json, not arbitrary HTML.
Run: python3 literature/poem-oracle/collect.py
"""

import gzip
import hashlib
from html import unescape
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
MAX_LINES, MAX_WORDS = 16, 120


def plain(fragment):
    """Preserve explicit verse/stanza breaks, ignoring HTML source wrapping."""
    fragment = re.sub(r'<span class="pagenum">.*?</span>', '', fragment, flags=re.S)
    fragment = re.sub(r'<br\s*/?>', '\n', fragment)
    fragment = re.sub(r'</p\s*>', '\n\n', fragment)
    fragment = re.sub(r'<[^>]+>', '', fragment)
    # Source newlines are whitespace, whereas inserted breaks are significant.
    return unescape(fragment)


def verse(fragment):
    # Protect explicit breaks before removing source formatting whitespace.
    fragment = re.sub(r'\s+', ' ', fragment)
    lines = [' '.join(line.split()) for line in plain(fragment).splitlines()]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def dickinson(body):
    body = body.split('<a id="Index_of_First_Lines"')[0]
    for match in re.finditer(r'<a id="([^"]+)">\s*</a>(.*?)(?=<hr|\Z)', body, re.S):
        anchor, fragment = match.groups()
        if anchor.startswith('Series_'):
            continue
        lines = verse(fragment).splitlines()
        while lines and (not lines[0] or re.fullmatch(r'[IVXLCDM]+\.', lines[0])):
            lines.pop(0)
        title = ''
        while lines and (not lines[0] or lines[0].isupper()):
            if lines[0]:
                title += (' ' if title else '') + lines[0]
            lines.pop(0)
        # The first poem has a bracketed publication note before its first line.
        if lines and lines[0].startswith('['):
            while lines and ']' not in lines.pop(0):
                pass
        text = '\n'.join(lines).strip()
        if text:
            yield anchor, title or text.splitlines()[0], text


def rossetti(body):
    # Each illustration marks the start of a complete poem, with one or more p's.
    matches = list(re.finditer(r'<img\b[^>]*\bid="([^"]+)"[^>]*>', body))
    for i, match in enumerate(matches):
        if match.group(1).startswith('img_'):
            continue
        end = matches[i+1].start() if i+1 < len(matches) else len(body)
        paragraphs = re.findall(r'<p\b[^>]*>(.*?)</p>', body[match.end():end], re.S)
        text = '\n\n'.join(verse(p) for p in paragraphs if '<br' in p)
        if text:
            yield match.group(1), text.splitlines()[0], text


def blake(body):
    for chapter in re.split(r'<div class="chapter">', body)[1:]:
        heading = re.search(r'<h2>(.*?)</h2>', chapter, re.S)
        stanzas = re.findall(r'<p class="poem">(.*?)</p>', chapter, re.S)
        if not heading or not stanzas:
            continue
        anchor = re.search(r'id="([^"]+)"', heading[1])[1]
        yield anchor, verse(heading[1]), '\n\n'.join(verse(p) for p in stanzas)


def stevenson(body):
    # Heading boundaries retain complete poems; no excerpts of longer ones.
    for match in re.finditer(r'<h3>(.*?)</h3>(.*?)(?=<h[23]\b|\Z)', body, re.S):
        heading, fragment = match.groups()
        # Balance nested divs so illustration captions after a poem cannot leak
        # into its text. Several captions precede the following heading/rule.
        stanzas = [verse(p) for p in div_contents(fragment, 'poem')]
        if not stanzas:
            continue
        text = '\n\n'.join(stanzas)
        title = verse(heading)
        anchor = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        yield anchor, title, text


def div_contents(fragment, class_name):
    """Read balanced containers, including editions with a div per verse line."""
    depth, start = 0, None
    for tag in re.finditer(r'</?div\b[^>]*>', fragment):
        if tag[0].startswith('</'):
            if depth:
                depth -= 1
                if not depth:
                    yield fragment[start:tag.start()]
        elif depth:
            depth += 1
        elif f'class="{class_name}"' in tag[0]:
            depth, start = 1, tag.end()


def teasdale(body):
    body = body.split('<h2 id="id00042"')[1].split('<p id="id00386"')[0]
    yield from paragraph_poems(body)


def paragraph_poems(body):
    title = anchor = None
    stanzas = []
    for match in re.finditer(r'<p\b([^>]*)>(.*?)</p>', body, re.S):
        attrs, fragment = match.groups()
        if '<br' in fragment:
            if title:
                stanzas.append(verse(fragment))
        else:
            if stanzas:
                yield anchor, title, '\n\n'.join(stanzas)
            title, stanzas = verse(fragment), []
            anchor = re.search(r'id="([^"]+)"', attrs)[1]
    if stanzas:
        yield anchor, title, '\n\n'.join(stanzas)


def teasdale_love(body):
    body = body[body.index('<p id="id00025"'):].split('<p id="id00274"')[0]
    yield from paragraph_poems(body)


def millay(body):
    body = body[body.index('<p id="id00007"'):]
    main, sonnets = body.split('<p id="id00087"', 1)
    yield from paragraph_poems(main)
    for match in re.finditer(r'<h4[^>]*>.*?</h4>\s*<p id="([^"]+)"[^>]*>(.*?)</p>', sonnets, re.S):
        text = verse(match[2])
        yield match[1], text.splitlines()[0], text


def housman(body):
    for fragment in re.findall(r'<pre>(.*?)</pre>', body, re.S):
        fragment = re.sub(r'<[^>]+>', '', fragment)
        lines = [line.strip() for line in unescape(fragment).splitlines()]
        while lines and not lines[0]:
            lines.pop(0)
        if not lines or not re.fullmatch('[IVXLCDM]+', lines[0]):
            continue
        number = lines.pop(0)
        while lines and not lines[0]:
            lines.pop(0)
        if lines and (lines[0].isupper() or lines[0].isdigit()):
            lines.pop(0)
        text = '\n'.join(lines).strip()
        if text:
            yield number, text.splitlines()[0], text


def dunbar(body):
    for fragment in div_contents(body, 'poem'):
        heading = re.search(r'<h4>(.*?)</h4>', fragment, re.S)
        stanzas = list(div_contents(fragment, 'stanza'))
        if not heading or not stanzas:
            continue
        title = verse(heading[1])
        anchor = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        yield anchor, title, '\n\n'.join(verse(p) for p in stanzas)


def headed_paragraph_poems(body, tag):
    """A heading and its complete verse paragraphs, excluding dated notes."""
    for match in re.finditer(fr'<{tag}\b([^>]*)>(.*?)</{tag}>(.*?)(?=<h[1-6]\b|\Z)', body, re.S):
        attrs, heading, fragment = match.groups()
        paragraphs = re.findall(r'<p\b[^>]*>(.*?)</p>', fragment, re.S)
        stanzas = [verse(p) for p in paragraphs if '<br' in p]
        if stanzas:
            anchor = re.search(r'id="([^"]+)"', attrs)[1]
            yield anchor, verse(heading), '\n\n'.join(stanzas)


def teasdale_rivers(body):
    body = body[body.index('<h2 id="id00018"'):]
    # This edition encodes the final verse line of The Flight as a heading.
    # Restore its role before using headings as poem boundaries.
    body = re.sub(r'</p>\s*<h5 id="id00026">(.*?)</h5>', r'\1<br></p>', body, flags=re.S)
    # Numbered movements of Vignettes Overseas/Sappho are not standalone poems.
    for anchor, title, text in headed_paragraph_poems(body, 'h[2-5]'):
        if not re.fullmatch('[IVXLCDM]+', title):
            yield anchor, title, text


def crapsey(body):
    body = body[body.index('<h2 id="id00038"'):]
    yield from headed_paragraph_poems(body, 'h3')


def anchored_pre_poems(body):
    anchors = list(re.finditer(r'<a id="(link2H_4_\d+)"', body))
    for i, anchor in enumerate(anchors):
        end = anchors[i+1].start() if i+1 < len(anchors) else len(body)
        fragment = body[anchor.end():end]
        heading = re.search(r'<h2\b[^>]*>(.*?)</h2>', fragment, re.S)
        pres = re.findall(r'<pre>(.*?)</pre>', fragment, re.S)
        if not heading or not pres:
            continue
        title = verse(heading[1])
        # Keep complete multipart works together. The explicitly numbered
        # sonnets are individual poems rather than movements of one poem.
        if len(pres) != 1 and title != 'SONNETS':
            continue
        for pre in pres:
            text = '\n'.join(line.strip() for line in plain(pre).splitlines()).strip()
            poem_title = re.sub(r'^[IVXLCDM]+\.\s*', '', title)
            poem_anchor = anchor[1]
            if title == 'SONNETS':
                number, text = text.split('\n', 1)
                if not re.fullmatch('[IVXLCDM]+', number):
                    raise ValueError('Expected a numbered sonnet')
                text = text.strip()
                poem_title = 'Sonnet '+number
                # All sonnets share their section's actual HTML anchor.
                poem_anchor += '-'+number
            elif not poem_title or re.fullmatch(r'[IVXLCDM]+\.?', poem_title):
                poem_title = text.splitlines()[0]
            yield poem_anchor, poem_title, text


def shakespeare(body):
    for chapter in re.split(r'<div class="chapter">', body)[1:]:
        heading = re.search(r'<h2>([IVXLCDM]+)</h2>', chapter)
        paragraphs = re.findall(r'<p class="poem">(.*?)</p>', chapter, re.S)
        if heading and paragraphs:
            yield heading[1], 'Sonnet '+heading[1], '\n\n'.join(verse(p) for p in paragraphs)


def headed_stanza_poems(body):
    for match in re.finditer(r'<h2\b[^>]*>(.*?)</h2>(.*?)(?=<h2\b|\Z)', body, re.S):
        heading, fragment = match.groups()
        title = verse(heading)
        if title == 'NOTES':
            break
        containers = list(div_contents(fragment, 'poem'))
        if len(containers) != 1:
            continue
        stanzas = list(div_contents(containers[0], 'stanza'))
        if not stanzas:
            continue
        identity = re.search(r'id="([^"]+)"', heading)
        anchor = identity[1] if identity else re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        yield anchor, title, '\n\n'.join(verse(p) for p in stanzas)


def heading_sections(body, tag):
    for match in re.finditer(fr'<{tag}\b([^>]*)>(.*?)</{tag}>(.*?)(?=<{tag}\b|\Z)', body, re.S):
        attrs, heading, fragment = match.groups()
        title = ' '.join(verse(heading).split())
        identity = re.search(r'id="([^"]+)"', attrs+' '+heading)
        anchor = identity[1] if identity else re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        yield anchor, title, fragment


def herrick(body):
    for anchor, title, fragment in heading_sections(body, 'h3'):
        # Only numbered original poems: omit biography, editorial notes and
        # the verse quotations scattered through the commentary/appendices.
        if not re.fullmatch(r'id_[12]\.[pne]\d+', anchor):
            continue
        fragment = re.sub(r'<a\b[^>]*class="fnanchor[^\"]*"[^>]*>.*?</a>',
                          '', fragment, flags=re.S)
        containers = list(div_contents(fragment, 'poem'))
        if len(containers) != 1:
            continue
        stanzas = list(div_contents(containers[0], 'stanza'))
        if stanzas:
            title = re.sub(r'^\d+\.\s*', '', title)
            yield anchor, title, '\n\n'.join(verse(p) for p in stanzas)


def lear(body):
    for match in re.finditer(r'<p class="rhyme" id="(rhyme1_\d+)">(.*?)</p>', body, re.S):
        text = verse(match[2])
        yield match[1], text.splitlines()[0], text


def rossetti_poems(body):
    for anchor, title, fragment in heading_sections(body, 'h4'):
        pres = re.findall(r'<pre\b[^>]*>(.*?)</pre>', fragment, re.S)
        stanzas = []
        for pre in pres:
            text = '\n'.join(line.strip() for line in plain(pre).splitlines()).strip()
            if text:
                stanzas.append(text)
        if stanzas:
            yield anchor, title, re.sub(r'\n{3,}', '\n\n', '\n\n'.join(stanzas))


def browning(body):
    for anchor, title, fragment in heading_sections(body, 'h2'):
        if not re.fullmatch('[IVXLCDM]+', title):
            continue
        paragraphs = re.findall(r'<p class="poetry">(.*?)</p>', fragment, re.S)
        if paragraphs:
            yield title, 'Sonnet '+title, '\n\n'.join(verse(p) for p in paragraphs)


def masters(body):
    for anchor, title, fragment in heading_sections(body, 'h2'):
        if not anchor.startswith('chap'):
            continue
        paragraphs = re.findall(r'<p class="noindent">(.*?)</p>', fragment, re.S)
        if paragraphs:
            yield anchor, title, '\n\n'.join(verse(p) for p in paragraphs)


def teasdale_moon(body):
    for anchor, title, fragment in heading_sections(body, 'h2'):
        stanzas = list(div_contents(fragment, 'stanza'))
        if stanzas:
            # Modern HTML transcriptions encode verse lines as nested divs
            # without br tags. Convert those explicit line ends before verse().
            text = '\n\n'.join(verse(p.replace('</div>', '<br>')) for p in stanzas)
            yield anchor, title, text


def underwoods(body):
    body = body.split('<h2>Footnotes</h2>')[0]
    body = re.sub(r'<a\b[^>]*class="citation[^\"]*"[^>]*>.*?</a>',
                  '', body, flags=re.S)
    for anchor, title, fragment in heading_sections(body, 'h3'):
        paragraphs = re.findall(r'<p class="poetry">(.*?)</p>', fragment, re.S)
        if not paragraphs:
            continue
        text = '\n\n'.join(verse(p) for p in paragraphs)
        title = re.sub(r'^[IVXLCDM]+[—.]\s*', '', title)
        if re.fullmatch('[IVXLCDM]+', title):
            title = text.splitlines()[0]
        yield anchor, title, text


def yeats_swans(body):
    yield from headed_stanza_poems(body.split('<h2>NOTE</h2>')[0])


def renascence(body):
    for anchor, title, fragment in heading_sections(body, 'h3'):
        paragraphs = re.findall(r'<p class="poem">(.*?)</p>', fragment, re.S)
        if paragraphs:
            yield anchor, title, '\n\n'.join(verse(p) for p in paragraphs)


PARSERS = dict(dickinson=dickinson, rossetti=rossetti, blake=blake,
               stevenson=stevenson, teasdale=teasdale, housman=housman,
               millay=millay, dunbar=dunbar, shakespeare=shakespeare,
               crapsey=crapsey, mckay=headed_stanza_poems, yeats=headed_stanza_poems,
               herrick=herrick, lear=lear, browning=browning, masters=masters,
               **{'teasdale-love': teasdale_love, 'teasdale-rivers': teasdale_rivers,
                  'millay-april': anchored_pre_poems, 'housman-last': anchored_pre_poems,
                  'rossetti-poems': rossetti_poems, 'yeats-swans': yeats_swans,
                  'stevenson-underwoods': underwoods, 'teasdale-moon': teasdale_moon,
                  'millay-renascence': renascence})


def collect():
    sources = json.loads((ROOT/'sources.json').read_text())
    poems, seen, counts, ids = [], set(), {}, {}
    for source in sources:
        raw = gzip.decompress((ROOT/source['snapshot']).read_bytes())
        if hashlib.sha256(raw).hexdigest() != source['sha256']:
            raise ValueError('Source checksum mismatch: '+source['id'])
        body = raw.decode('utf-8').split('</header>', 1)[1].split('<footer', 1)[0]
        total = kept = 0
        for anchor, title, text in PARSERS[source['id']](body):
            total += 1
            # A heading may wrap a dedication onto another printed line.
            # Font titles are one line; verse/stanza breaks remain untouched.
            title = ' '.join(title.split())
            line_count = sum(bool(line.strip()) for line in text.splitlines())
            word_count = len(text.split())
            if not (2 <= line_count <= MAX_LINES and word_count <= MAX_WORDS):
                continue
            fingerprint = re.sub(r'\W', '', text).casefold()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            base_id = source['id']+'-'+anchor
            ids[base_id] = ids.get(base_id, 0) + 1
            poem_id = base_id + (f'-{ids[base_id]}' if ids[base_id] > 1 else '')
            poems.append(dict(id=poem_id, title=title,
                              author=source['author'], text=text,
                              line_count=line_count, word_count=word_count,
                              source_id=source['id'], source_anchor=anchor))
            kept += 1
        counts[source['id']] = dict(complete_poems=total, selected=kept)
    return poems, counts


def main():
    poems, counts = collect()
    (ROOT/'poems.json').write_text(json.dumps(poems, ensure_ascii=False, indent=2)+'\n')
    summary = dict(poems=len(poems), max_lines=MAX_LINES, max_words=MAX_WORDS,
                   sources=counts)
    (ROOT/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
