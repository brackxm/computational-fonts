# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0

"""Add an ASCII prefix parser and visible output to the bounded GSUB machine."""
import copy
import hashlib
import json
from pathlib import Path
import sys

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from .config import ROOT, DEFAULT_FONT, DISPLAY_FONT
from .layout import VALUES, paths, validate
from .outputs import font_artifacts, overlap, validate_outputs

sys.path.insert(0, str(ROOT.parents[1] / 'decoders'))
from shared.font_metadata import DEFAULT_BASE, load_base_font, mark_modified_font, replace_font_names


def _validate_visible_paths(output):
    validate_outputs(output, (DEFAULT_BASE,))
    if overlap(font_artifacts(output), font_artifacts(DEFAULT_FONT, timing=True)):
        raise ValueError('Visible output requires a different path from the bundled machine artifacts')


def validate_visible_output(output, depth, rounds):
    """Keep the bundled fonts compatible with the runner, playground and specimen."""
    validate(depth, rounds)
    _validate_visible_paths(output)
    if (depth, rounds) != (5, 32) and overlap(font_artifacts(output), font_artifacts(DISPLAY_FONT)):
        raise ValueError('Custom visible configurations require --output to a different path; '
                         'the bundled playground font requires depth 5 and 32 rounds')


def build_visible(machine_path, output):
    """Compile preprocessing, reductions, and rendering into one rlig schedule.

    Input is SKI[optional fuel];PREFIX!. No host reducer or encoder is needed.
    The source machine's generated .fea and .json must be alongside its .ttf.
    """
    machine_path, output = Path(machine_path), Path(output)
    _validate_visible_paths(output)
    validate_outputs(output, (*font_artifacts(machine_path), DEFAULT_BASE))
    base = load_base_font(DEFAULT_BASE, output)
    font = TTFont(machine_path)
    try:
        meta = json.loads(machine_path.with_suffix('.json').read_text())
        depth, rounds = meta['depth'], meta['rounds']
        validate_visible_output(output, depth, rounds)
        ps = paths(depth)
        n, ix = len(ps), {p: i for i, p in enumerate(ps)}
        order = list(font.getGlyphOrder())
        old_classes = dict(font['GDEF'].table.GlyphClassDef.classDefs)
        marks = [name for name in order if old_classes.get(name) == 3]
        bases = [name for name in order if old_classes.get(name) == 1]
        display = {}
        glyph_set = base.getGlyphSet()
        base_cmap = base.getBestCmap()
        scale = 1000 / base['head'].unitsPerEm

        def add(name, text='', mark=False):
            name = 'ski.' + name
            pen, x = TTGlyphPen(None), 0
            for char in text:
                original = base_cmap[ord(char)]
                recording = DecomposingRecordingPen(glyph_set)
                glyph_set[original].draw(recording)
                recording.replay(TransformPen(pen, (scale, 0, 0, scale, x, 0)))
                x += base['hmtx'][original][0] * scale
            glyph = pen.glyph()
            font['glyf'][name] = glyph
            glyph.recalcBounds(font['glyf'])
            font['hmtx'][name] = (round(x), getattr(glyph, 'xMin', 0))
            order.append(name)
            (marks if mark else bases).append(name)
            if text:
                display[name] = text
            return name

        raw = {chr(i): add(f'input{i}', mark=i != ord('!')) for i in range(32, 127)}
        header = [add(f'header{f}') for f in range(rounds + 1)]
        parsing = [add(f'parse{f}') for f in range(rounds + 1)]
        cursor = [add(f'cursor{j}', mark=True) for j in range(n)]
        done, over = add('complete', mark=True), add('too_deep', mark=True)
        written = {(j, v): add(f'written{j}_{v}', mark=True)
                   for j in range(n) for v in VALUES if v != 'E'}
        tokens = {(j, v): add(f'token{j}_{v}', mark=True)
                  for j in range(n) for v in VALUES if v != 'E'}
        fuel_unset, end, bad_end = (add(k) for k in ('fuel_unset', 'end', 'bad_end'))
        syntax, input_overflow = add('syntax'), add('input_overflow')
        hidden = add('hidden', mark=True)
        rendered = {}
        for j, path in enumerate(ps):
            space = ' ' if path.endswith('1') else ''
            closing = len(path) - len(path.rstrip('1'))
            for value in VALUES:
                if value == 'E':
                    rendered[j, value] = hidden
                else:
                    text = space + ('(' if value == 'A' else value + ')' * closing)
                    rendered[j, value] = add(f'output{j}_{value}', text)
        status_names = {
            'normal': 'NORMAL  ', 'budget': 'STEP LIMIT  ', 'overflow': 'DEPTH LIMIT  ',
            'seek': 'INCOMPLETE  ', syntax: 'SYNTAX ERROR', input_overflow: 'INPUT TOO DEEP',
        }
        status = {name: add('status_' + name.replace('.', '_'), text)
                  for name, text in status_names.items()}
        fuel_display = [add(f'remaining{f}', f'  [fuel {f}]') for f in range(rounds + 1)]
        font.setGlyphOrder(order)
        for table in font['cmap'].tables:
            if table.isUnicode():
                table.cmap.update({ord(c): g for c, g in raw.items()})

        fea, initialization, finalization = [], [], []

        def cls(name, names):
            fea.append('@' + name + ' = [' + ' '.join(names) + '];')
            return '@' + name

        def lookup(name, rules, flag='', phase=initialization):
            fea.extend([f'lookup {name} useExtension {{',
                        'lookupflag ' + flag + ';' if flag else '',
                        *rules, f'}} {name};'])
            if phase is not None:
                phase.append(name)

        cls('VISIBLE_BASE', bases)
        cls('VISIBLE_MARK', marks)
        core = machine_path.with_suffix('.fea').read_text()
        core = core.replace('GlyphClassDef @BASE, , @MARK, ;',
                            'GlyphClassDef @VISIBLE_BASE, , @VISIBLE_MARK, ;')
        core, cycle_feature = core.rsplit('feature calt {', 1)
        cycle_names = [line.split()[1].rstrip(';') for line in cycle_feature.splitlines()
                       if line.strip().startswith('lookup ')]
        # Keep all machine helper definitions and mark-filter sets intact.
        fea.append(core)
        parse_class = cls('PARSE', parsing)
        errors = cls('INPUT_ERRORS', [syntax, input_overflow])
        cls('FUEL', [f'f{f}' for f in range(rounds + 1)])
        cls('INPUT_CHECK', [*cursor, done, over, *raw.values(),
                            *[f'n0_{v}' for v in VALUES]])
        cls('ANY_GLYPH', order)
        ghosts = cls('PARSE_GHOST', [*cursor, done, over, *written.values()])
        lookup('V_SPACE', [f'sub {raw[c]} by NULL;' for c in ' .'])
        headers = [('SKI' + str(f) + ';', header[f]) for f in range(rounds + 1)]
        headers.append(('SKI;', header[rounds]))
        lookup('V_HEADER', ['sub ' + ' '.join(raw[c] for c in source) + ' by ' + target + ';'
                            for source, target in sorted(headers, key=lambda item: -len(item[0]))])
        unframed = cls('UNFRAMED', [*raw.values(), '.notdef'])
        lookup('V_BAD_HEADER', [f"ignore sub @ANY_GLYPH {unframed}';",
                                f"sub {unframed}' by {syntax};"])
        lookup('V_INIT', [f'sub {header[f]} by {parsing[f]} {cursor[0]};' for f in range(rounds + 1)])
        tape = [f'n{j}_E' for j in range(n)]
        for j in range(n):
            tape.extend((f't{j}', f'q{j}'))
        lookup('V_ALLOCATE', [f'sub {raw["!"]} by ' + ' '.join(tape + [fuel_unset, end]) + ';'], phase=None)
        lookup('V_SEED', [f"sub {parse_class} {raw['!']}' lookup V_ALLOCATE;"], 'IgnoreMarks')
        lookup('V_FUEL', [f"sub {parsing[f]} {fuel_unset}' by f{f};" for f in range(rounds + 1)], 'IgnoreMarks')
        consume, advance = [], []
        for j, path in enumerate(ps):
            after = path.rstrip('1')
            following = cursor[ix[after[:-1] + '1']] if after else done
            for value in VALUES:
                if value == 'E':
                    continue
                next_cursor = (cursor[j + 1] if len(path) < depth else over) if value == 'A' else following
                consume.append(f'sub {cursor[j]} {raw["@" if value == "A" else value]} '
                               f'by {tokens[j, value]};')
                advance.append(f'sub {tokens[j, value]} by {written[j, value]} {next_cursor};')
        lookup('V_CONSUME', consume)
        lookup('V_ADVANCE', advance)
        # Distinct lookup indices below run this parser at most N times.
        # Depth-six trees need shared write helpers to keep lookup headers
        # within 16-bit offsets. Preserve the smaller fonts' existing layout.
        if depth == 6:
            for value in VALUES:
                if value != 'E':
                    lookup(f'V_PUT_{value}', [f'sub n{j}_E by n{j}_{value};' for j in range(n)],
                           phase=None)
        for j in range(n):
            visible = cls(f'PWRITE{j}', [*[written[j, v] for v in VALUES if v != 'E'],
                                        *[f'n{j}_{v}' for v in VALUES]])
            lookup(f'V_WRITE{j}', [f"sub {written[j, v]} n{j}_E' " +
                                  (f'lookup V_PUT_{v};' if depth == 6 else f'by n{j}_{v};')
                                  for v in VALUES if v != 'E'], 'UseMarkFilteringSet ' + visible)
        lookup('V_END_CHECK', [f"sub {end}' @ANY_GLYPH by {bad_end};"])
        lookup('V_VALIDATE', [f"sub {parse_class}' {over} by {input_overflow};",
                              f"sub {parse_class}' {done} @N0 @FUEL {end} by seek;",
                              f"sub {parse_class}' by {syntax};"], 'UseMarkFilteringSet @INPUT_CHECK')
        lookup('V_CLEAN', [f'sub {ghosts} by NULL;'])
        for j in range(n):
            lookup(f'V_ERROR_CLEAR{j}', [f"sub {errors} @N{j}' by {hidden};"],
                   f'UseMarkFilteringSet @N{j}', finalization)
        lookup('V_ERROR_FUEL', [f"sub {errors} @FUEL' by {hidden};"], 'IgnoreMarks', finalization)
        lookup('V_RENDER', [*[f'sub n{j}_{v} by {rendered[j, v]};' for j in range(n) for v in VALUES],
                            *[f'sub {source} by {target};' for source, target in status.items()],
                            *[f'sub f{f} by {fuel_display[f]};' for f in range(rounds + 1)]], phase=finalization)
        fea.extend(['feature ss01 {', *['lookup ' + k + ';' for k in initialization], '} ss01;',
                    'feature calt {', *['lookup ' + k + ';' for k in cycle_names], '} calt;',
                    'feature ss02 {', *['lookup ' + k + ';' for k in finalization], '} ss02;'])
        source = '\n'.join(fea)
        addOpenTypeFeaturesFromString(font, source)
        gsub = font['GSUB'].table
        features = {r.FeatureTag: r for r in gsub.FeatureList.FeatureRecord}
        prefix = list(features['ss01'].Feature.LookupListIndex)
        cycle = list(features['calt'].Feature.LookupListIndex)
        suffix = list(features['ss02'].Feature.LookupListIndex)
        consume_index = prefix[initialization.index('V_CONSUME')]
        offset = prefix.index(consume_index)
        advance_index = prefix[initialization.index('V_ADVANCE')]
        prefix[offset:offset + 2] = [consume_index, advance_index] * n
        sequence = prefix + cycle * rounds + cycle[:2] + suffix
        active = []
        for index in sequence:
            active.append(len(gsub.LookupList.Lookup))
            gsub.LookupList.Lookup.append(copy.copy(gsub.LookupList.Lookup[index]))
        gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)
        record = features['calt']
        record.FeatureTag = 'rlig'
        record.Feature.LookupListIndex, record.Feature.LookupCount = active, len(active)
        gsub.FeatureList.FeatureRecord, gsub.FeatureList.FeatureCount = [record], 1
        for script in gsub.ScriptList.ScriptRecord:
            script.Script.DefaultLangSys.FeatureIndex = [0]
            script.Script.DefaultLangSys.FeatureCount = 1
        for name_id in (0, 7, 8, 9, 11, 13, 14):
            value = base['name'].getDebugName(name_id)
            if value:
                font['name'].setName(value, name_id, 3, 1, 0x409)
                font['name'].setName(value, name_id, 1, 0, 0)
        replace_font_names(font, {1: 'SKI Evaluator', 2: 'Regular', 3: f'SKI-Visible-D{depth}-B{rounds}',
                                 4: 'SKI Evaluator Regular', 6: f'SKIEvaluator-D{depth}-B{rounds}',
                                 10: 'SKI prefix parser, bounded GSUB evaluator and visible output.'})
        font._decoder_base_digest = hashlib.sha256(DEFAULT_BASE.read_bytes()).digest()
        font['OS/2'].fsType = 0
        mark_modified_font(font, 'SKI evaluator', kind='interpreter')
        font.recalcTimestamp = False
        output.parent.mkdir(parents=True, exist_ok=True)
        font.save(output)
        report = {'schema': 'ski-visible-1', 'depth': depth, 'rounds': rounds, 'capacity': n,
                  'font_bytes': output.stat().st_size, 'glyphs': len(order), 'lookups': gsub.LookupList.LookupCount,
                  'font_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                  'base_sha256': font._decoder_base_digest.hex(), 'display': display}
        output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
        output.with_suffix('.fea').write_text(source)
        print({k: v for k, v in report.items() if k != 'display'}, flush=True)
        return report
    finally:
        base.close()
        font.close()


def serialize(source, fuel=32, depth=5, rounds=32):
    """Serialize syntax plus fixed workspace; never perform a reduction."""
    from .layout import validate
    from .syntax import parse, prefix, height
    validate(depth, rounds)
    if type(fuel) is not int or not 0 <= fuel <= rounds:
        raise ValueError('fuel outside compiled range')
    tree = parse(source)
    if height(tree) > depth:
        raise ValueError('input exceeds the visible font depth')
    return f'SKI{fuel};{prefix(tree)}!' + '.' * (3 * (2 ** (depth + 1) - 1) + 2)
