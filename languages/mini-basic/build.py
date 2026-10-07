#!/usr/bin/env python3
# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Build the bounded Mini BASIC interpreter in OpenType GSUB."""

import argparse
from pathlib import Path
import sys

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.otlLib.builder import buildCoverage, buildLigatureSubstSubtable, buildLookup, buildMultipleSubstSubtable
from fontTools.ttLib.tables import otTables

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'decoders'))
from shared.font_metadata import DEFAULT_BASE, load_base_font, mark_modified_font, replace_font_names

MAX_STEPS, MAX_LINES, OUTPUT_ROWS, STRING_LENGTH = 128, 16, 8, 24
PRINT_ITEMS = 4
CALL_DEPTH = 4
WIDTH, HEIGHT, CELL = 13000, 6000, 500
VARS = 'ABCD'
CHARS = ''.join(chr(n) for n in range(32, 127))
STRING_CHARS = CHARS.replace('"', '')
ARITHMETIC = {'+': 'add', '-': 'sub', '*': 'multiply', '/': 'divide', 'MOD': 'modulo'}


def build_font(output):
    font = load_base_font(DEFAULT_BASE, output)
    try:
        cmap = font.getBestCmap()
        glyphs, metrics = font['glyf'], font['hmtx']
        order = list(font.getGlyphOrder())
        if any(name.startswith('basic.') for name in order):
            raise ValueError('Base contains reserved basic. glyph names')
        generated, stages, fea, filters = [], [], [], {}

        def add(name, components=(), advance=0):
            name = 'basic.' + name
            if name in glyphs:
                raise ValueError('Duplicate glyph: ' + name)
            pen = TTGlyphPen(glyphs)
            for original, x, y, scale in components:
                pen.addComponent(original, (scale, 0, 0, scale, x, y))
            glyph = pen.glyph()
            glyph.recalcBounds(glyphs)
            glyphs[name] = glyph
            metrics[name] = (advance, getattr(glyph, 'xMin', 0))
            order.append(name)
            generated.append(name)
            return name

        def text_parts(text, x, y, cell=CELL, scale=.25):
            return [(cmap[ord(char)], x - WIDTH + i * cell, y, scale)
                    for i, char in enumerate(text) if char != ' ']

        def cls(name, names):
            fea.append('@' + name + ' = [' + ' '.join(names) + '];')
            return '@' + name

        def lookup(name, rules, visible=None, stage=True):
            flag = ''
            if visible is not None:
                key = tuple(dict.fromkeys(visible))
                if key not in filters:
                    filters[key] = cls('FILTER_' + str(len(filters)), key)
                flag = 'lookupflag UseMarkFilteringSet ' + filters[key] + ';'
            extension = ' useExtension' if name == 'ACTIVATE' else ''
            fea.extend([f'lookup {name}{extension} {{', flag, *rules, f'}} {name};'])
            if stage:
                stages.append(name)
            return name

        raw = {char: add(f'input_{ord(char):02x}') for char in CHARS}
        outside = {char: add(f'outside_{ord(char):02x}') for char in sorted(set(c.upper() for c in CHARS))}
        quoted = {char: add(f'quoted_{ord(char):02x}') for char in STRING_CHARS}
        open_quote, close_quote = add('quote_open'), add('quote_close')
        comment_start, comment = add('comment_start'), add('comment')
        root, end, eof = [add(n) for n in ('parse_root', 'statement_end', 'eof')]
        initializers = {':': add('init'), ';': add('init_legacy')}
        separator_modes = {c: add('separator_mode_' + str(ord(c))) for c in ':;'}
        raw_ends = {c: add('raw_end_' + str(ord(c))) for c in ':;'}
        statement_separator = add('statement_separator')
        parse_ghost = add('parse_ghost')
        syntax, arithmetic, output_error, division_error, loop_error, stack_error, return_error, width_error = [add('error_' + n) for n in ('syntax', 'arithmetic', 'output', 'division', 'loop', 'stack', 'return', 'width')]

        frame_name = add('frame', text_parts('MINI BASIC', 500, HEIGHT - 450, cell=350, scale=.18), WIDTH)
        # The terminal's frame is the only advancing glyph. Every other glyph
        # is a GDEF mark, so filter sets can address distant machine components.
        title = add('title', text_parts('MINI BASIC', 500, HEIGHT - 450, cell=350, scale=.18))
        pen = TTGlyphPen(glyphs)
        for x, y, w, h in ((0, 0, WIDTH, 25), (0, HEIGHT-25, WIDTH, 25),
                           (0, 0, 25, HEIGHT), (WIDTH-25, 0, 25, HEIGHT)):
            pen.moveTo((x,y)); pen.lineTo((x+w,y)); pen.lineTo((x+w,y+h)); pen.lineTo((x,y+h)); pen.closePath()
        glyphs[frame_name] = pen.glyph()
        glyphs[frame_name].recalcBounds(glyphs)
        metrics[frame_name] = (WIDTH, 0)

        const = {v: add(f'const_{v}') for v in range(100)}
        labels = {v: add(f'line_{v}') for v in range(1, 100)}
        active = {v: add(f'active_{v}') for v in labels}
        target = {v: add(f'target_{v}') for v in range(100)}
        else_target = {v: add(f'else_target_{v}') for v in range(100)}
        pc = {v: add(f'pc_{v}') for v in labels}
        seen = {v: add(f'seen_{v}') for v in labels}
        statuses = {
            'done': 'DONE', 'limit': 'STEP LIMIT', 'syntax': 'SYNTAX ERROR',
            'arithmetic': 'ARITHMETIC RANGE ERROR', 'output': 'OUTPUT LIMIT', 'missing': 'MISSING LINE',
            'division': 'DIVISION BY ZERO', 'loop': 'LOOP ERROR',
            'stack': 'CALL STACK FULL', 'return': 'RETURN WITHOUT GOSUB',
            'width': 'PRINT WIDTH ERROR',
        }
        halted = {key: add('halt_' + key, text_parts(text, 500, 300, cell=350, scale=.18))
                  for key, text in statuses.items()}
        boot = add('pc_boot')
        jump = {v: add(f'jump_{v}') for v in target}
        jump_next, jump_done = add('jump_next'), add('jump_done')
        call_next = add('call_next')
        depths = {i: add(f'call_depth_{i}') for i in range(CALL_DEPTH+1)}
        popping = {i: add(f'call_pop_{i}') for i in range(1,CALL_DEPTH+1)}
        return_targets = [*labels, None]
        save_return = {n: add(f'save_return_{n}') for n in return_targets}
        returns = {(i,n): add(f'return_{i}_{n}') for i in range(CALL_DEPTH) for n in return_targets}
        dest = {var: add('dest_' + var) for var in VARS}
        write = {(var, v): add(f'write_{var}_{v}') for var in VARS for v in range(100)}
        roles = ('reg', 'left', 'right')
        refs = {(role, var, v): add(f'{role}_{var}_{v}')
                for role in roles for var in VARS for v in range(100)}
        # Raw references exist only at parse time; they never hold VM values.
        refs.update({('ref',var,0): add(f'ref_{var}_0') for var in VARS})
        # Header register values draw the final machine state; operand copies
        # remain invisible and are synchronized after each assignment.
        for i, var in enumerate(VARS):
            for v in range(100):
                name = refs['reg', var, v]
                pen = TTGlyphPen(glyphs)
                for original, x, y, scale in text_parts(f'{var}={v:02}', 500+i*3000, 950, cell=350, scale=.18):
                    pen.addComponent(original, (scale,0,0,scale,x,y))
                glyphs[name] = pen.glyph()
                glyphs[name].recalcBounds(glyphs)
                metrics[name] = (0, getattr(glyphs[name], 'xMin', 0))
        values = {(role, v): add(f'{role}_const_{v}') for role in ('left', 'right') for v in const}
        left = {v: add(f'value_left_{v}') for v in const}
        right = {v: add(f'value_right_{v}') for v in const}
        result = {v: add(f'result_{v}') for v in const}
        emit_string, acknowledged = add('emit_string'), add('printed')
        empty_rows = {r: add(f'row_empty_{r}') for r in range(OUTPUT_ROWS)}
        active_rows = {r: add(f'row_active_{r}') for r in empty_rows}
        used_rows = {r: add(f'row_used_{r}') for r in empty_rows}
        literal = {(i,c): add(f'literal_{i}_{ord(c):02x}') for i in range(STRING_LENGTH) for c in STRING_CHARS}
        fresh_literal = {(i,c): add(f'literal_active_{i}_{ord(c):02x}') for i,c in literal}
        tagged = {(r,i,c): add(f'literal_tag_{r}_{i}_{ord(c):02x}')
                  for r in empty_rows for i,c in literal}
        characters = {(r,i,c): add(f'output_char_{r}_{i}_{ord(c):02x}',
                                  text_parts(c, 500+i*CELL, HEIGHT-1000-r*500)) for r,i,c in tagged}
        string_cursor = {i: add(f'string_cursor_{i}') for i in range(STRING_LENGTH+1)}
        string_temp = {(i,c): add(f'string_temp_{i}_{ord(c):02x}') for i,c in literal}
        literal_end = add('literal_end')
        print_chars = {c: add(f'print_char_{ord(c):02x}') for c in STRING_CHARS}
        print_cursors = {i: add(f'print_column_{i}') for i in range(STRING_LENGTH+1)}
        print_pending = {i: add(f'print_pending_{i}') for i in range(1,PRINT_ITEMS)}
        print_joins = {i: add(f'print_join_{i}') for i in print_pending}
        print_active = {i: add(f'print_join_active_{i}') for i in print_pending}
        keywords = {k: add('keyword_' + k) for k in ('LET','PRINT','IF','THEN','ELSE','GOTO','GOSUB','RETURN','END','REM','MOD','FOR','TO','NEXT','STEP','AND','OR','NOT','WHILE','WEND')}
        logic = {op: add('logic_'+op) for op in ('AND','OR')}
        logic_active = {op: add('logic_active_'+op) for op in logic}
        negate = add('logic_NOT')
        logic_results = {(op,b): add(f'logic_result_{op}_{int(b)}') for op in logic for b in (False,True)}
        codes = {k: add('code_' + k) for k in ('LET','LIST','IF','GOTO','GOSUB','RETURN','END','REM','FOR','NEXT','WHILE','WEND')}
        executing = {k: add('execute_' + k) for k in codes}
        for_active = add('code_FOR_active')
        for_illegal, next_illegal = add('execute_FOR_illegal'), add('execute_NEXT_illegal')
        while_active = add('code_WHILE_active')
        while_illegal, wend_illegal = add('execute_WHILE_illegal'), add('execute_WEND_illegal')
        while_results = {b: add('while_condition_'+str(int(b))) for b in (False,True)}
        loop_vars = {a: add('loop_var_'+a) for a in VARS}
        loop_bounds = {v: add('loop_bound_'+str(v)) for v in const}
        loop_steps = {v: add('loop_step_'+str(v)) for v in range(1,100)}
        body_labels = {n: add('loop_body_'+str(n)) for n in labels}
        after_labels = {n: add('loop_after_'+str(n)) for n in labels}
        body_pending, bound_pending, skip_pending = [add(n) for n in ('body_pending','bound_pending','skip_pending')]
        step_pending = add('step_pending')
        skip = {n: add('loop_skip_'+str(n)) for n in labels}
        skip_done = add('loop_skip_done')
        for_enter, for_skip = add('for_enter'), add('for_skip')
        operators = {op: add('operator_' + name) for op,name in
                     (('+','add'),('-','subtract'),('*','multiply'),('/','divide'),('MOD','modulo'),('FOR','for'),('NEXT','next'),('FOR_DOWN','for_down'),('NEXT_DOWN','next_down'),('=','equal'),('<>','unequal'),('<','less'),
                      ('<=','less_equal'),('>','greater'),('>=','greater_equal'))}
        op_source = {op: add('compare_' + str(i)) for i,op in enumerate(('=','<>','<','<=','>','>='))}
        outcomes = {(op,v): add(f'arithmetic_{name}_{v}')
                    for op,name in ARITHMETIC.items() for v in range(102)}
        for_results = {(v,enter): add(f'for_result_{v}_{int(enter)}') for v in const for enter in (False,True)}
        for_down_results = {(v,enter): add(f'for_down_result_{v}_{int(enter)}') for v in const for enter in (False,True)}
        next_increments = {v: add(f'next_increment_{v}') for v in const}
        next_decrements = {v: add(f'next_decrement_{v}') for v in const}
        truths = {b: add('condition_' + str(int(b))) for b in (False, True)}
        comparisons = {(op,b): add(f'comparison_{i}_{int(b)}') for i,op in enumerate(op_source) for b in truths}
        counted = {(i,n): add(f'counted_{i}_{n}') for i in range(1,MAX_LINES+1) for n in labels}
        count_start = add('count_start')

        fea.extend(['languagesystem DFLT dflt;', 'languagesystem latn dflt;'])
        raw_cls = cls('RAW', raw.values())
        outside_cls = cls('OUTSIDE', [outside[c.upper()] for c in CHARS])
        quoted_cls = cls('QUOTED', [quoted[c] for c in STRING_CHARS])
        inside = cls('INSIDE', [open_quote, *quoted.values()])
        pc_alive = cls('PC_ALIVE', [boot,*pc.values(),*seen.values()])
        pc_running = cls('PC_RUNNING', pc.values())
        pc_seen = cls('PC_SEEN', seen.values())
        label_cls, active_cls = cls('LABEL', labels.values()), cls('ACTIVE', active.values())
        const_cls, target_cls = cls('CONST', const.values()), cls('TARGET', target.values())
        else_target_cls = cls('ELSE_TARGET', else_target.values())
        positive_const = cls('POSITIVE_CONST', [const[v] for v in loop_steps])
        ref_raw = cls('REF', [refs['ref',v,0] for v in VARS])
        operands = cls('OPERAND', [*const.values(), *[refs['ref',v,0] for v in VARS]])
        dest_cls = cls('DEST', dest.values())
        lhs = cls('LEFT', [*[values['left',v] for v in const], *[refs['left',a,v] for a in VARS for v in const]])
        rhs = cls('RIGHT_WITH_LOOP', [*[values['right',v] for v in const], *[refs['right',a,v] for a in VARS for v in const], *loop_bounds.values(),*loop_steps.values()])
        litcols = {i: cls('LIT_'+str(i), [literal[i,c] for c in STRING_CHARS]) for i in range(STRING_LENGTH)}
        litactive = cls('LIT_ACTIVE', fresh_literal.values())
        emits = cls('EMIT', [emit_string])

        # Explicit envelopes keep PRINT joins distinct from legacy separators.
        lookup('START_ACTION', ['sub ' + ' '.join(raw[c] for c in 'RUN'+separator) + ' by ' + initializer + ';'
                               for separator,initializer in initializers.items()], stage=False)
        init_guard = cls('INIT_GUARD', [*raw.values(), frame_name])
        start_tail = f'{raw["U"]} {raw["N"]} [{raw[":"]} {raw[";"]}]'
        lookup('START', [f'ignore sub {init_guard} {raw["R"]}\' {start_tail};',
                         f'sub {raw["R"]}\' lookup START_ACTION {start_tail};'])
        lookup('INITIALIZE', [f'sub {initializer} by ' + ' '.join([frame_name, title, *[refs['reg',a,0] for a in VARS],
                             depths[0], *[empty_rows[r] for r in reversed(empty_rows)], separator_modes[separator], count_start, boot, root]) + ';'
                             for separator,initializer in initializers.items()])
        for separator in initializers:
            lookup('SELECT_SEPARATOR_' + str(ord(separator)),
                   [f"sub [{separator_modes[separator]} {raw_ends[separator]}] {raw[separator]}' by {raw_ends[separator]};"],
                   visible=[*separator_modes.values(), raw_ends[separator], raw[separator]])
        raw_end_cls = cls('RAW_END', raw_ends.values())
        quoted_end_cls = cls('QUOTED_END', [quoted[c] for c in raw_ends])
        lookup('LEX', [f'sub [{comment_start} {comment}] {raw_end_cls}\' by {statement_separator};',
                       f'sub {inside} {raw_end_cls}\' by {quoted_end_cls};',
                       f'sub {raw_end_cls}\' by {statement_separator};',
                       f'sub [{comment_start} {comment}] {raw_cls}\' by {comment};',
                       f'sub {inside} {raw[chr(34)]}\' by {close_quote};',
                       f'sub {inside} ['+' '.join(raw[c] for c in STRING_CHARS)+f']\' by {quoted_cls};',
                       f'sub {outside["R"]} {outside["E"]} [{raw["M"]} {raw["m"]}]\' by {comment_start};',
                       f'sub {raw[chr(34)]}\' by {open_quote};',
                       f'sub {raw_cls}\' by {outside_cls};'],
               # Skip spaces already normalized outside strings when finding
               # REM, while retaining quoted spaces and statement boundaries.
               visible=[*raw.values(), *[name for c,name in outside.items() if c != ' '],
                        *quoted.values(), open_quote, close_quote, comment_start, comment,
                        *raw_ends.values(), statement_separator])
        lookup('TRIM', [f'sub {outside[" "]} by NULL;', f'sub {comment} by NULL;',
                        f'sub {statement_separator} by {end} {root};'])
        lookup('LEX_CONTROLS', [f'sub {outside["!"]} by {eof};',
                        f'sub {open_quote} by {string_cursor[0]};'])
        lookup('STRING_TAKE', [f'sub {string_cursor[i]} {quoted[c]} by {string_temp[i,c]};' for i,c in literal])
        lookup('STRING_ADVANCE', [f'sub {string_temp[i,c]} by {literal[i,c]} {string_cursor[i+1]};' for i,c in literal])
        lookup('STRING_CLOSE', [f'sub {cursor} {close_quote} by {literal_end};' for cursor in string_cursor.values()])
        lookup('NUMBER_PAIR', [f'sub {outside[str(v//10)]} {outside[str(v%10)]} by {const[v]};' for v in const])
        lookup('NUMBER_SINGLE', [f'sub {outside[str(v)]} by {const[v]};' for v in range(10)])
        lookup('WORDS', [f'sub '+ ' '.join(outside[c] for c in word) + f' by {name};'
                         for word,name in keywords.items() if word != 'REM'] +
                        [f'sub {outside["R"]} {outside["E"]} {comment_start} by {keywords["REM"]};'])
        lookup('VARIABLES', [f'sub {outside[a]} by {refs["ref",a,0]};' for a in VARS])
        lookup('COMPARE_PAIRS', [f'sub '+ ' '.join(outside[c] for c in op) + f' by {op_source[op]};'
                                  for op in ('<>','<=','>=')])
        lookup('COMPARE_SINGLE', [f'sub {outside[op]} by {op_source[op]};' for op in ('=','<','>')])
        lookup('LABELS', [f'sub {root} {const_cls}\' by [' + ' '.join([syntax,*labels.values()]) + '];'])

        lookup('TO_DEST', [f'sub {refs["ref",a,0]} by {dest[a]};' for a in VARS], stage=False)
        lookup('INFER_LET_ACTION', [f'sub {refs["ref",a,0]} by {keywords["LET"]} {refs["ref",a,0]};' for a in VARS], stage=False)
        lookup('INFER_LET', [f"sub {root} {label_cls} {ref_raw}' lookup INFER_LET_ACTION;"])
        lookup('TO_LOOP_VAR', [f'sub {refs["ref",a,0]} by {loop_vars[a]};' for a in VARS], stage=False)
        lookup('TO_LOOP_BOUND', [f'sub {const[v]} by {loop_bounds[v]};' for v in const], stage=False)
        lookup('TO_DEFAULT_BOUND', [f'sub {const[v]} by {loop_bounds[v]} {loop_steps[1]};' for v in const], stage=False)
        lookup('TO_LOOP_STEP', [f'sub {const[v]} by {loop_steps[v]};' for v in loop_steps], stage=False)
        lookup('NEXT_OPERANDS', [f'sub {refs["ref",a,0]} by {loop_vars[a]} {refs["left",a,0]} {operators["NEXT"]} {step_pending} {bound_pending} {body_pending};' for a in VARS], stage=False)
        for role in ('left','right'):
            lookup('TO_'+role.upper(), [f'sub {const[v]} by {values[role,v]};' for v in const] +
                   [f'sub {refs["ref",a,0]} by {refs[role,a,0]};' for a in VARS], stage=False)
        lookup('TO_TARGET', [f'sub {const[v]} by {target[v]};' for v in const], stage=False)
        lookup('TO_ELSE_TARGET', [f'sub {const[v]} by {else_target[v]};' for v in const], stage=False)
        lookup('DROP', [f'sub {name} by {parse_ghost};' for name in [op_source['='],keywords['THEN'],keywords['ELSE'],keywords['GOTO'],keywords['STEP'],outside['-']]], stage=False)
        compare_source = cls('COMPARISON_SOURCE', op_source.values())
        logic_source = cls('LOGIC_SOURCE', [keywords[op] for op in logic])
        lookup('TO_COMPARISON', [f'sub {name} by {operators[op]};' for op,name in op_source.items()], stage=False)
        lookup('TO_LOGIC', [f'sub {keywords[op]} by {name};' for op,name in logic.items()], stage=False)
        lookup('TO_NOT', [f'sub {keywords["NOT"]} by {negate};'], stage=False)
        for key in codes:
            original = keywords['PRINT' if key=='LIST' else key]
            extra = ' '+body_pending if key=='WEND' else ''
            lookup('TO_CODE_'+key, [f'sub {original} by {codes[key]}{extra};'], stage=False)
        # Comparisons share TO_COMPARISON; NEXT_OPERANDS inserts its operator.
        # Only the arithmetic and FOR parser rules need individual helpers.
        for op in [*ARITHMETIC,'FOR']:
            source = outside[op] if op in '+-*/' else keywords['TO' if op=='FOR' else op]
            lookup('TO_OP_'+str(list(operators).index(op)), [f'sub {source} by {operators[op]};'], stage=False)
        lookup('TO_FOR_DOWN', [f'sub {keywords["TO"]} by {operators["FOR_DOWN"]};'], stage=False)
        for i in print_pending:
            lookup('TO_PRINT_JOIN_'+str(i), [f'sub {outside[";"]} by {print_pending[i]};'], stage=False)
            lookup('VALIDATE_PRINT_JOIN_'+str(i), [f'sub {print_pending[i]} by {print_joins[i]};'], stage=False)
        parser = []
        # Whole-statement patterns prevent valid prefixes of malformed source
        # from becoming executable instructions.
        for op in ARITHMETIC:
            op_input = keywords[op] if op=='MOD' else outside[op]
            parser.append(f'sub {root} {label_cls} {keywords["LET"]}\' lookup TO_CODE_LET '
                          f'{ref_raw}\' lookup TO_DEST {op_source["="]}\' lookup DROP '
                          f'{operands}\' lookup TO_LEFT {op_input}\' lookup TO_OP_{list(operators).index(op)} '
                          f'{operands}\' lookup TO_RIGHT {end};')
        parser.append(f'sub {root} {label_cls} {keywords["LET"]}\' lookup TO_CODE_LET '
                      f'{ref_raw}\' lookup TO_DEST {op_source["="]}\' lookup DROP {operands}\' lookup TO_LEFT {end};')
        # Validate each complete PRINT item with a bounded position marker.
        # A separator stays pending until the following item has been parsed;
        # malformed tails therefore reject the whole program before execution.
        for i in range(PRINT_ITEMS):
            prefix = (f'{root} {label_cls} {keywords["PRINT"]}\' lookup TO_CODE_LIST ' if i==0 else
                      f'{print_pending[i]}\' lookup VALIDATE_PRINT_JOIN_{i} ')
            suffixes = [f'{end}']
            if i+1 < PRINT_ITEMS:
                suffixes.append(f'{outside[";"]}\' lookup TO_PRINT_JOIN_{i+1}')
            items = [f'{operands}\' lookup TO_LEFT ']
            for op in ARITHMETIC:
                op_input = keywords[op] if op=='MOD' else outside[op]
                items.append(f'{operands}\' lookup TO_LEFT {op_input}\' lookup TO_OP_{list(operators).index(op)} '
                             f'{operands}\' lookup TO_RIGHT ')
            items += [' '.join(litcols[j]+"'" for j in range(length))+f" {literal_end}' "
                      for length in range(STRING_LENGTH+1)]
            parser += [f'sub {prefix}{item}{suffix};' for item in items for suffix in suffixes]
        parser.append(f'sub {root} {label_cls} {keywords["FOR"]}\' lookup TO_CODE_FOR '
                      f'{ref_raw}\' lookup TO_LOOP_VAR {op_source["="]}\' lookup DROP '
                      f'{const_cls}\' lookup TO_LEFT {keywords["TO"]}\' lookup TO_FOR_DOWN '
                      f'{const_cls}\' lookup TO_LOOP_BOUND {keywords["STEP"]}\' lookup DROP '
                      f'{outside["-"]}\' lookup DROP {positive_const}\' lookup TO_LOOP_STEP {end};')
        parser.append(f'sub {root} {label_cls} {keywords["FOR"]}\' lookup TO_CODE_FOR '
                      f'{ref_raw}\' lookup TO_LOOP_VAR {op_source["="]}\' lookup DROP '
                      f'{const_cls}\' lookup TO_LEFT {keywords["TO"]}\' lookup TO_OP_{list(operators).index("FOR")} '
                      f'{const_cls}\' lookup TO_LOOP_BOUND {keywords["STEP"]}\' lookup DROP '
                      f'{positive_const}\' lookup TO_LOOP_STEP {end};')
        parser.append(f'sub {root} {label_cls} {keywords["FOR"]}\' lookup TO_CODE_FOR '
                      f'{ref_raw}\' lookup TO_LOOP_VAR {op_source["="]}\' lookup DROP '
                      f'{const_cls}\' lookup TO_LEFT {keywords["TO"]}\' lookup TO_OP_{list(operators).index("FOR")} '
                      f'{const_cls}\' lookup TO_DEFAULT_BOUND {end};')
        parser.append(f'sub {root} {label_cls} {keywords["NEXT"]}\' lookup TO_CODE_NEXT {ref_raw}\' lookup NEXT_OPERANDS {end};')
        def comparison_pattern(inverted):
            return (f'{keywords["NOT"]}\' lookup TO_NOT ' if inverted else '') + \
                   f'{operands}\' lookup TO_LEFT {compare_source}\' lookup TO_COMPARISON {operands}\' lookup TO_RIGHT '
        for inverted in (False,True):
            first = comparison_pattern(inverted)
            conditions = [first] + [first + f'{logic_source}\' lookup TO_LOGIC ' + comparison_pattern(second)
                                    for second in (False,True)]
            for condition in conditions:
                parser.append(f'sub {root} {label_cls} {keywords["WHILE"]}\' lookup TO_CODE_WHILE {condition}{end};')
                for long_form in (False,True):
                    goto = f'{keywords["GOTO"]}\' lookup DROP ' if long_form else ''
                    prefix = (f'sub {root} {label_cls} {keywords["IF"]}\' lookup TO_CODE_IF '
                              f'{condition}{keywords["THEN"]}\' lookup DROP {goto}{const_cls}\' lookup TO_TARGET ')
                    parser.append(prefix + f'{end};')
                    for else_long in (False,True):
                        else_goto = f'{keywords["GOTO"]}\' lookup DROP ' if else_long else ''
                        parser.append(prefix + f'{keywords["ELSE"]}\' lookup DROP {else_goto}{const_cls}\' lookup TO_ELSE_TARGET {end};')
        for key in ('GOTO','GOSUB'):
            parser.append(f'sub {root} {label_cls} {keywords[key]}\' lookup TO_CODE_{key} {const_cls}\' lookup TO_TARGET {end};')
        for key in ('END','REM','RETURN','WEND'):
            parser.append(f'sub {root} {label_cls} {keywords[key]}\' lookup TO_CODE_{key} {end};')
        lookup('PARSE', parser)
        lookup('REMOVE_PARSE_GHOST', [f'sub {parse_ghost} by NULL;'])
        # Pair both loop types in source order. Mixed or same-type nesting,
        # mismatched closers and unclosed loops are syntax errors.
        loop_var_class = cls('LOOP_VAR', loop_vars.values())
        loop_start = cls('LOOP_START', [codes['FOR'],codes['WHILE']])
        loop_checks = [f"ignore sub {codes['FOR']}' {loop_var_class} {codes['NEXT']};",
                       f"ignore sub {codes['WHILE']}' {codes['WEND']};",
                       f"sub {loop_start}' by {syntax};"]
        loop_checks += [f"ignore sub {codes['FOR']} {loop_vars[a]} {codes['NEXT']} {loop_vars[a]}';" for a in VARS]
        loop_checks += [f"sub {codes['NEXT']} {loop_var_class}' by {syntax};",
                        f"ignore sub {codes['WHILE']} {codes['WEND']}';",
                        f"sub {codes['WEND']}' by {syntax};"]
        lookup('CHECK_LOOPS', loop_checks, visible=[codes[k] for k in ('FOR','NEXT','WHILE','WEND')]+list(loop_vars.values()))
        lookup('LOOP_DIRECTION', [f"sub {operators['FOR_DOWN']} {operators['NEXT']}' by {operators['NEXT_DOWN']};"],
               visible=[operators[k] for k in ('FOR','FOR_DOWN','NEXT','NEXT_DOWN')])
        lookup('LOOP_VARS', [f'sub {name} by {dest[a]};' for a,name in loop_vars.items()])
        # Insert WHILE's exit placeholder after parsing its operands: expanding
        # the keyword inside PARSE would shift that rule's later lookup targets.
        lookup('LOOP_PREPARE', [f'sub {loop_bounds[v]} by {loop_bounds[v]} {skip_pending};' for v in const] +
               [f'sub {codes["WHILE"]} by {codes["WHILE"]} {skip_pending};'])
        # Keep captured labels in the filter set so subsequent labels cannot
        # become additional body/exit targets during this forward pass.
        lookup('CAPTURE_BODY', [f"sub {codes['FOR']} {label_cls}' by ["+' '.join(body_labels.values())+'];'],
               visible=[codes['FOR'],*labels.values(),*body_labels.values()])
        all_labels = cls('LABEL_WITH_BODY', [*labels.values(),*body_labels.values()])
        lookup('CAPTURE_AFTER', [f"sub [{codes['NEXT']} {codes['WEND']}] {all_labels}' by ["+' '.join(list(after_labels.values())*2)+'];'],
               visible=[codes['NEXT'],codes['WEND'],*labels.values(),*body_labels.values(),*after_labels.values()])
        # Bounds and steps share value setters for their distinct placeholders.
        for v in const:
            lookup('SET_LOOP_VALUE_'+str(v), [f'sub {bound_pending} by {loop_bounds[v]};'] +
                   ([f'sub {step_pending} by {loop_steps[v]};'] if v in loop_steps else []), stage=False)
        lookup('COPY_BOUND', [f"sub {loop_bounds[v]} {bound_pending}' lookup SET_LOOP_VALUE_{v};" for v in const],
               visible=[*loop_bounds.values(),bound_pending])
        lookup('COPY_STEP', [f"sub {loop_steps[v]} {step_pending}' lookup SET_LOOP_VALUE_{v};" for v in loop_steps],
               visible=[*loop_steps.values(),step_pending])
        lookup('COPY_SKIP', [f"sub {skip_pending}' {after_labels[n]} by {skip[n]};" for n in labels] +
               [f"sub {skip_pending}' by {skip_done};"], visible=[skip_pending,*after_labels.values()])
        # A WHILE header can also be the preceding loop's exit. Copy exits
        # before reusing that label as the WHILE return address.
        while_labels = cls('LABEL_FOR_WHILE', [*labels.values(),*body_labels.values(),*after_labels.values()])
        lookup('CAPTURE_WHILE_HEAD', [f"sub {while_labels}' {codes['WHILE']} by ["+' '.join(list(body_labels.values())*3)+'];'],
               visible=[codes['WHILE'],*labels.values(),*body_labels.values(),*after_labels.values()])
        lookup('COPY_BODY', [f"sub {body_labels[n]} {body_pending}' by {target[n]};" for n in labels],
               visible=[*body_labels.values(),body_pending])
        lookup('RESTORE_LOOP_LABELS', [f'sub {name} by {labels[n]};' for mapping in (body_labels,after_labels) for n,name in mapping.items()])
        lookup('CHECK_STATEMENTS', [f'ignore sub {label_cls}\' ['+' '.join(codes.values())+'];', f'sub {label_cls}\' by {syntax};'])
        lookup('CHECK_ORDER', [f'sub {labels[n]} ['+' '.join(labels[m] for m in labels if m<=n)+f']\' by {syntax};'
                               for n in labels], visible=labels.values())
        counting = [f'sub {count_start} {label_cls}\' by ['+' '.join(counted[1,n] for n in labels)+'];']
        for i in range(1,MAX_LINES):
            prev = cls('COUNT_'+str(i), [counted[i,n] for n in labels])
            counting.append(f'sub {prev} {label_cls}\' by ['+' '.join(counted[i+1,n] for n in labels)+'];')
        counting.append(f'sub ['+' '.join(counted[MAX_LINES,n] for n in labels)+f'] {label_cls}\' by {syntax};')
        lookup('COUNT_LINES', counting, visible=[count_start,*labels.values(),*counted.values()])
        lookup('RELEASE_COUNT', [f'sub {name} by {labels[n]};' for (i,n),name in counted.items()])
        # The terminator must immediately follow a fresh statement root. Once
        # consumed, any remaining EOF or raw tokens cause a syntax error.
        lookup('FINISH_SOURCE', [f'sub {root} {eof} by {add("source_finished")};'])
        allowed_eof = generated[-1]
        all_glyphs = cls("ALL_GLYPHS", order)
        lookup("CHECK_FINISH_LAST", [f"sub {allowed_eof}' {all_glyphs} by {syntax};"])
        lookup('CHECK_ROOTS', [f'ignore sub {root}\' {label_cls};', f'sub {root}\' by {syntax};'])
        lookup('CHECK_EOF', [f'sub {eof} by {syntax};'])
        invalid = [*outside.values(),*const.values(),*[refs['ref',a,0] for a in VARS],
                   *quoted.values(),open_quote,close_quote,*string_cursor.values(),*keywords.values(),
                   *op_source.values(),comment_start,body_pending,bound_pending,step_pending,*print_pending.values()]
        lookup('REJECT_UNPARSED', [f'sub {name} by {syntax};' for name in invalid])
        # Require a terminator: an EOF acknowledgement is the only route out
        # of boot. Missing/truncated input never executes a partial program.
        lookup('ACK_SOURCE', [f'sub {boot}\' {allowed_eof} by {add("pc_validated")};'], visible=[boot,allowed_eof])
        validated = generated[-1]
        lookup('MISSING_EOF', [f'sub {boot} by {halted["syntax"]};', f'sub {validated} by {boot};'])
        lookup('SYNTAX_STOP', [f'sub {pc_alive}\' {syntax} by {halted["syntax"]};'], visible=[boot,*pc.values(),*seen.values(),syntax])
        lookup('RESET_PC', [f'sub {name} by {boot};' for name in [*pc.values(),*seen.values()]], stage=False)
        for n in labels:
            lookup('SET_PC_'+str(n), [f'sub {boot} by {pc[n]};'], stage=False)
        lookup('BOOT', [f"sub {boot}' lookup SET_PC_{n} {name};" for n,name in labels.items()], visible=[boot,*labels.values()])
        lookup('EMPTY_PROGRAM', [f'sub {boot} by {halted["done"]};'])
        lookup('REMOVE_PARSER', [f'sub {name} by NULL;' for name in [root,end,allowed_eof,count_start,syntax]])
        initialization = list(stages)
        stages.clear()

        # Each clock tick activates exactly one retained statement. Header
        # registers and all operand copies are separate, synchronized glyphs.
        lookup('ACTIVATE', [f'sub {pc[n]} ' + ' '.join([label_cls]*offset) +
               f' {labels[n]}\' by {active[n]};' for n in labels for offset in range(MAX_LINES)],
               visible=[*pc.values(),*labels.values()])
        lookup('SEEN_LINE', [f'sub {pc_running}\' {active_cls} by {pc_seen};'], visible=[*pc.values(),*active.values()])
        lookup('MISSING_LINE', [f'sub {pc_running} by {halted["missing"]};'])
        loop_heads = [codes['FOR'],for_active,codes['WHILE'],while_active]
        all_loop_codes = cls('ALL_LOOP_CODES', loop_heads)
        active_loop_codes = cls('ACTIVE_LOOP_CODES', [for_active,while_active])
        for key,illegal in (('FOR',for_illegal),('WHILE',while_illegal)):
            guard = []
            for offset in range(MAX_LINES):
                between = ' '.join([all_loop_codes]*offset)
                guard += [f"sub {active_loop_codes} {between} {codes[key]}' by {illegal};",
                          f"sub {codes[key]}' {between} {active_loop_codes} by {illegal};"]
            guard.append(f"sub {codes[key]}' by {executing[key]};")
            lookup('GUARD_'+key, guard, visible=loop_heads, stage=False)
        for key,head,illegal in (('NEXT',for_active,next_illegal),('WEND',while_active,wend_illegal)):
            lookup('GUARD_'+key, [f"sub {head} {codes[key]}' by {executing[key]};",
                   f"sub {codes[key]}' by {illegal};"],
                   visible=[*loop_heads,codes['NEXT'],codes['WEND']], stage=False)
        lookup('DISPATCH', [f'sub {active_cls} {name}\' by {executing[key]};' for key,name in codes.items() if key not in ('FOR','NEXT','WHILE','WEND')] +
               [f"sub {active_cls} {codes['FOR']}' lookup GUARD_FOR;",
                f"sub {active_cls} {codes['NEXT']}' lookup GUARD_NEXT;",
                f"sub {active_cls} {codes['WHILE']}' lookup GUARD_WHILE;",
                f"sub {active_cls} {codes['WEND']}' lookup GUARD_WEND;",
                f"sub {active_cls} {for_active}' by {for_illegal};",
                f"sub {active_cls} {while_active}' by {executing['WHILE']};"],
               visible=[*labels.values(),*active.values(),*codes.values(),for_active,while_active])
        logic_class = cls('LOGIC', logic.values())
        logic_exec = cls('LOGIC_ACTIVE', logic_active.values())
        joins = cls('PRINT_JOINS', print_joins.values())
        active_joins = cls('PRINT_ACTIVE_JOINS', print_active.values())
        lookup('ACTIVATE_LOGIC', [f"sub [{executing['IF']} {executing['WHILE']}] {logic_class}' by {logic_exec};",
               f"sub [{executing['LIST']} {active_joins}] {joins}' by {active_joins};"],
               visible=[*codes.values(),*executing.values(),*print_joins.values(),*print_active.values(),*logic.values(),*logic_active.values(),*labels.values(),*active.values()])
        for role, value_map in (('left',left),('right',right)):
            lookup('READ_'+role.upper(), [f'sub {name} by {name} {value_map[v]};'
                     for v in const for name in [values[role,v],*[refs[role,a,v] for a in VARS],
                        *([loop_bounds[v],*([loop_steps[v]] if v in loop_steps else [])] if role=='right' else [])]], stage=False)
            if role == 'left':
                rules = [f'sub ['+' '.join(executing[key] for key in ('LET','FOR','NEXT'))+f'] {dest_cls} {lhs}\' lookup READ_LEFT;',
                         f'sub [{executing["IF"]} {executing["WHILE"]} {executing["LIST"]} {active_joins} '+' '.join(logic_active.values())+f'] {lhs}\' lookup READ_LEFT;']
            else:
                rules = [f'sub ['+' '.join(left.values())+'] ['+' '.join(operators.values())+f'] {rhs}\' lookup READ_RIGHT;']
            # Ignore output outlines, but retain labels as barriers between
            # instructions and PRINT joins as barriers between its items.
            lookup('LOAD_'+role.upper(), rules,
                   visible=[*left.values(),*operators.values(),*[values['right',v] for v in const],
                            *[refs['right',a,v] for a in VARS for v in const],*loop_bounds.values(),*loop_steps.values(),
                            *labels.values(),*active.values()] if role=='right' else
                           [*codes.values(),*executing.values(),for_active,while_active,*dest.values(),
                            *[values['left',v] for v in const],*[refs['left',a,v] for a in VARS for v in const],
                            *logic.values(),*logic_active.values(),*print_joins.values(),*print_active.values(),*labels.values(),*active.values()])
        calc = {}
        compare = {'=':lambda a,b:a==b, '<>':lambda a,b:a!=b, '<':lambda a,b:a<b,
                   '<=':lambda a,b:a<=b, '>':lambda a,b:a>b, '>=':lambda a,b:a>=b}
        for a in const:
            for b in const:
                arithmetic_values = {'+': a+b, '-': a-b, '*': a*b,
                                     '/': a//b if b else 101, 'MOD': a%b if b else 101}
                for op, value in arithmetic_values.items():
                    slot = 101 if op in ('/', 'MOD') and b==0 else value if 0<=value<100 else 100
                    calc[left[a], operators[op], right[b]] = outcomes[op,slot]
                calc[left[a], operators['FOR'],right[b]] = for_results[a,a<=b]
                calc[left[a], operators['FOR_DOWN'],right[b]] = for_down_results[a,a>=b]
                calc[left[a], operators['NEXT'],right[b]] = next_increments[a+b] if a+b<100 else outcomes['+',100]
                calc[left[a], operators['NEXT_DOWN'],right[b]] = next_decrements[a-b] if a>=b else outcomes['-',100]
                for op,fn in compare.items():
                    calc[left[a], operators[op], right[b]] = comparisons[op,fn(a,b)]
        lookup('CALCULATE', [f'sub {left[0]} {operators["+"]} {right[0]} by {outcomes["+",0]};'],
               visible=[*left.values(),*right.values(),*operators.values()])
        lookup('RESULT', [f'sub {name} by {operators[op]} {result[v] if v<100 else division_error if v==101 else arithmetic};'
                          for (op,v),name in outcomes.items()] +
                         [f'sub {name} by {operators[op]} {truths[b]};' for (op,b),name in comparisons.items()] +
                         [f'sub {name} by {operators["FOR"]} {result[v]} {for_enter if enter else for_skip};' for (v,enter),name in for_results.items()] +
                         [f'sub {name} by {operators["FOR_DOWN"]} {result[v]} {for_enter if enter else for_skip};' for (v,enter),name in for_down_results.items()] +
                         [f'sub {name} by {operators["NEXT"]} {result[v]} {left[v]} {operators["<="]};' for v,name in next_increments.items()] +
                         [f'sub {name} by {operators["NEXT_DOWN"]} {result[v]} {left[v]} {operators[">="]};' for v,name in next_decrements.items()])
        # NEXT first adds its constant step, then compares the updated value to
        # the bound. Both passes share the arithmetic/comparison table, avoiding
        # a separate transition for every counter/bound/step combination.
        current_left = cls('CURRENT_LEFT', left.values())
        bound_class = cls('LOOP_BOUND', loop_bounds.values())
        lookup('LOAD_NEXT_BOUND', [f"sub {current_left} [{operators['<=']} {operators['>=']}] {bound_class}' lookup READ_RIGHT;"],
               visible=[*left.values(),operators['<='],operators['>='],*loop_bounds.values(),*labels.values(),*active.values()])
        lookup('CALCULATE_NEXT_BOUND', [f'sub {left[0]} {operators["<="]} {right[0]} by {comparisons["<=",True]};'],
               visible=[*left.values(),*right.values(),*operators.values()])
        lookup('RESULT_NEXT_BOUND', [f'sub {comparisons[op,b]} by {truths[b]};' for op in ('<=','>=') for b in truths])
        # NOT applies to one comparison. Labels and joins isolate its result
        # from the following comparison or a neighboring instruction.
        lookup('NEGATE', [f"sub {negate} {truths[b]}' by {truths[not b]};" for b in truths],
               visible=[negate,*truths.values(),*logic.values(),*logic_active.values(),*labels.values(),*active.values()])
        lookup('COMBINE_LOGIC', [f'sub {truths[a]} {logic_active[op]} {truths[b]} by '
               f'{logic_results[op,a and b if op=="AND" else a or b]};'
               for op in logic for a in truths for b in truths],
               visible=[*truths.values(),*logic_active.values(),*labels.values(),*active.values()])
        lookup('LOGIC_RESULT', [f'sub {name} by {logic[op]} {truths[b]};' for (op,b),name in logic_results.items()])
        lookup('RESULT_LITERAL', [f'sub {left[v]} by {result[v]};' for v in const])
        lookup('FOR_RUNNING', [f'sub {executing["FOR"]} by {for_active} {jump_next};'], stage=False)
        skip_tokens = cls('SKIP_TOKENS', [*skip.values(),skip_done])
        lookup('EMIT_SKIP', [f'sub {name} by {name} {jump[n]};' for n,name in skip.items()] +
               [f'sub {skip_done} by {skip_done} {jump_done};'], stage=False)
        lookup('WHILE_DECISION', [f"sub {executing['WHILE']} {skip_tokens} {truths[b]}' by {while_results[b]};" for b in truths],
               visible=[executing['WHILE'],*skip.values(),skip_done,*truths.values(),*labels.values(),*active.values()])
        lookup('WHILE_RUNNING', [f'sub {executing["WHILE"]} by {while_active} {jump_next};'], stage=False)
        lookup('WHILE_CONTROL', [f"sub [{executing['WHILE']} {codes['WHILE']}] {skip_tokens}' lookup EMIT_SKIP {while_results[False]};",
               f"sub {executing['WHILE']}' {skip_tokens} {while_results[False]} by {codes['WHILE']};",
               f"sub {executing['WHILE']}' lookup WHILE_RUNNING {skip_tokens} {while_results[True]};"],
               visible=[executing['WHILE'],codes['WHILE'],*skip.values(),skip_done,*while_results.values(),*labels.values(),*active.values()])
        lookup('LOOP_CONTROL', [f"sub {executing['FOR']}' lookup FOR_RUNNING {for_enter};",
               f"sub {executing['FOR']}' {for_skip} by {codes['FOR']};",
               f"sub {for_active}' {skip_tokens} {executing['NEXT']} {truths[False]} by {codes['FOR']};",
               f"sub {for_skip} {skip_tokens}' lookup EMIT_SKIP;"],
               visible=[executing['FOR'],for_active,executing['NEXT'],truths[False],for_enter,for_skip,*skip.values(),skip_done])
        # Target the result glyph, whose distinct values can share one mapping
        # per variable. The canonical destination stays in the stored program.
        results = cls('RESULTS', result.values())
        for a in VARS:
            lookup('WRITE_'+a, [f'sub {result[v]} by {write[a,v]};' for v in const], stage=False)
        lookup('EMIT_RESULT', [f'sub {result[v]} by '+' '.join(print_chars[c] for c in str(v))+';' for v in const], stage=False)
        lookup('ASSIGN', [f"sub {dest[a]} {results}' lookup WRITE_{a};" for a in VARS] +
               [f"sub [{executing['LIST']} {active_joins}] {results}' lookup EMIT_RESULT;"],
               visible=[*dest.values(),*result.values(),*codes.values(),*executing.values(),*print_joins.values(),*print_active.values(),*labels.values(),*active.values()])

        headers = {a: cls('HEADER_'+a, [refs['reg',a,v] for v in const]) for a in VARS}
        # Contexts reset only their selected glyph before setting its new value.
        # Sharing the reset maps avoids repeating every old value in every setter,
        # while retaining the variable and operand role.
        operand_roles = ('left', 'right')
        lookup('RESET_HEADER', [f'sub {refs["reg",a,old]} by {refs["reg",a,0]};'
               for a in VARS for old in const], stage=False)
        lookup('RESET_REFERENCES', [f'sub {refs[role,a,old]} by {refs[role,a,0]};'
               for role in operand_roles for a in VARS for old in const], stage=False)
        for v in const:
            lookup('SET_HEADER_'+str(v), [f'sub {refs["reg",a,0]} by {refs["reg",a,v]};'
                   for a in VARS], stage=False)
            lookup('SET_REFERENCES_'+str(v), [f'sub {refs[role,a,0]} by {refs[role,a,v]};'
                   for role in operand_roles for a in VARS], stage=False)
        header_rules = []
        for i, a in enumerate(VARS):
            following = ' '.join(headers[b] for b in VARS[i+1:])
            for v in const:
                header_rules.append(f"sub {headers[a]}' lookup RESET_HEADER lookup SET_HEADER_{v} {following} {write[a,v]};")
        lookup('HEADER_UPDATE', header_rules,
               visible=[*[refs['reg',a,v] for a in VARS for v in const], *write.values()])
        for a in VARS:
            all_refs = [refs[role,a,v] for role in operand_roles for v in const]
            all_cls = cls('ALL_'+a, all_refs)
            rules_forward = []
            for v in const:
                same = cls(f'SAME_{a}_{v}', [write[a,v],*[refs[role,a,v] for role in roles]])
                rules_forward.append(f"sub {same} {all_cls}' lookup RESET_REFERENCES lookup SET_REFERENCES_{v};")
            lookup('BROADCAST_FORWARD_'+a, rules_forward,
                   visible=[*all_refs,*[refs['reg',a,v] for v in const],*[write[a,v] for v in const]])
        # Emit the jump beside its preserved operand rather than specializing
        # a preceding control glyph for each of the 100 possible destinations.
        lookup('EMIT_TARGET', [f'sub {name} by {name} {jump[n]};' for mapping in (target,else_target) for n,name in mapping.items()], stage=False)
        lookup('BRANCH', [f"sub {truths[True]} {target_cls}' lookup EMIT_TARGET;",
                         f"sub {truths[False]} {target_cls} {else_target_cls}' lookup EMIT_TARGET;"],
               visible=[*truths.values(),*target.values(),*else_target.values(),*labels.values(),*active.values()])
        lookup('GOTO', [f"sub [{executing['GOTO']} {executing['GOSUB']} {executing['WEND']}] {target_cls}' lookup EMIT_TARGET;"],
               visible=[executing['GOTO'],executing['GOSUB'],executing['WEND'],*target.values(),*labels.values(),*active.values()])
        lookup('TRANSFERS', [f"ignore sub {truths[False]}' {target_cls} {else_target_cls};",
                             f"sub {truths[False]}' by {jump_next};"],
               visible=[*truths.values(),*target.values(),*else_target.values(),*labels.values(),*active.values()])
        # Source characters stay canonical. Temporary characters from strings
        # and evaluated numbers form one stream, then receive actual columns.
        chars = cls('PRINT_CHARS', print_chars.values())
        source_chars = cls('SOURCE_CHARS', literal.values())
        lookup('COPY_PRINT_TEXT', [f'sub {name} by {name} {print_chars[c]};' for (i,c),name in literal.items()], stage=False)
        lookup('PRINT_TEXT', [f"sub [{executing['LIST']} {active_joins} {chars}] {source_chars}' lookup COPY_PRINT_TEXT;"],
               visible=[executing['LIST'],*print_active.values(),*literal.values(),*print_chars.values(),literal_end,*labels.values(),*active.values()])
        lookup('PRINT_CURSOR', [f"ignore sub {executing['LIST']}' [{arithmetic} {division_error}];",
               f"sub {executing['LIST']}' by {executing['LIST']} {emit_string} {print_cursors[0]};"],
               visible=[executing['LIST'],arithmetic,division_error,*labels.values(),*active.values()])
        for i in range(STRING_LENGTH):
            lookup('PLACE_PRINT_CHAR_'+str(i), [f'sub {print_chars[c]} by {fresh_literal[i,c]} {print_cursors[i+1]};' for c in STRING_CHARS], stage=False)
        lookup('PRINT_COLUMNS', [f"sub {print_cursors[i]} {chars}' lookup PLACE_PRINT_CHAR_{i};" for i in range(STRING_LENGTH)] +
               [f"sub {print_cursors[STRING_LENGTH]} {chars}' by {width_error};"],
               visible=[*print_cursors.values(),*print_chars.values(),*labels.values(),*active.values(),width_error])
        # Validate the complete row before allocation or painting, so a late
        # arithmetic or width error cannot leave a partially printed row.
        lookup('VALIDATE_PRINT', [f"sub {emit_string}' [{arithmetic} {division_error} {width_error}] by NULL;"],
               visible=[emit_string,arithmetic,division_error,width_error,*labels.values(),*active.values()])
        lookup('FINISH_INSTRUCTION', [f'sub {executing[key]} by {codes[key]} {jump_next};' for key in ('LET','LIST','REM')] +
                [f'sub {for_illegal} by {for_active} {loop_error};',
                 f'sub {next_illegal} by {codes["NEXT"]} {loop_error};',
                 f'sub {while_illegal} by {codes["WHILE"]} {loop_error};',
                 f'sub {wend_illegal} by {codes["WEND"]} {loop_error};',
                 f'sub {executing["END"]} by {codes["END"]} {jump_done};',
                 f'sub {executing["GOSUB"]} by {codes["GOSUB"]} {call_next};'])
        # Return addresses live beside source labels, indexed by call depth.
        # Filtering skips older entries; labels remain barriers for dispatch.
        lookup('EMIT_RETURN_ADDRESS', [f'sub {labels[n]} by {labels[n]} {save_return[n]};' for n in labels], stage=False)
        lookup('CAPTURE_RETURN_ADDRESS', [f"ignore sub {call_next}' {label_cls};",
               f"sub {call_next}' by {save_return[None]};",
               f"sub {call_next} {label_cls}' lookup EMIT_RETURN_ADDRESS;"], visible=[call_next,*labels.values()])
        saves = cls('SAVE_RETURN', save_return.values())
        lookup('CHECK_CALL_DEPTH', [f"sub {depths[CALL_DEPTH]} {saves}' by {stack_error};"],
               visible=[*depths.values(),*save_return.values()])
        lookup('ADVANCE_CALL_DEPTH', [f"sub {depths[i]}' {saves} by {depths[i+1]};" for i in range(CALL_DEPTH)],
               visible=[*depths.values(),*save_return.values()])
        return_classes = {i: cls('RETURN_'+str(i), [returns[i,n] for n in return_targets]) for i in range(CALL_DEPTH)}
        lookup('PUSH_RETURN', [f"sub {depths[i+1]} {saves}' by {return_classes[i]};" for i in range(CALL_DEPTH)],
               visible=[*depths.values(),*save_return.values()])
        lookup('REQUEST_RETURN', [f"sub {depths[0]} {executing['RETURN']}' by {return_error};"] +
               [f"sub {depths[i]}' {executing['RETURN']} by {popping[i]};" for i in popping],
               visible=[*depths.values(),executing['RETURN']])
        lookup('POP_RETURN_VALUE', [f'sub {name} by {jump_done if n is None else jump[n]};'
               for (i,n),name in returns.items()], stage=False)
        saved = cls('SAVED_RETURNS', returns.values())
        lookup('POP_RETURN', [f"sub {popping[i]} " + ' '.join([saved]*offset) +
               f" {return_classes[i-1]}' lookup POP_RETURN_VALUE;" for i in popping for offset in range(CALL_DEPTH)],
               visible=[*popping.values(),*returns.values()])
        lookup('RETREAT_CALL_DEPTH', [f'sub {popping[i]} by {depths[i-1]};' for i in popping])
        lookup('SELECT_OUTPUT_ROW', [f'sub {name}\' {emits} by {active_rows[r]};' for r,name in empty_rows.items()],
               visible=[*empty_rows.values(),emit_string])
        string_output_rules = []
        for r in empty_rows:
            painted = cls('TAGGED_'+str(r), [tagged[r,i,c] for i,c in literal])
            mapping = cls('PAINT_'+str(r), [tagged[r,i,c] for i,c in literal])
            string_output_rules.append(f'sub [{active_rows[r]} {painted}] {litactive}\' by {mapping};')
        lookup('OUTPUT_STRING', string_output_rules,
               visible=[*active_rows.values(),*fresh_literal.values(),*tagged.values()])
        fresh = cls('FRESH_ROWS', active_rows.values())
        lookup('ACK_PRINT', [f'sub {fresh} {emits}\' by {acknowledged};', f'sub {emits}\' by {output_error};'],
               visible=[*active_rows.values(),emit_string])
        errors = {arithmetic:'arithmetic',output_error:'output',division_error:'division',loop_error:'loop',stack_error:'stack',return_error:'return',width_error:'width'}
        lookup('STOP_ERRORS', [f"sub {pc_alive}' {error} by {halted[key]};" for error,key in errors.items()],
               visible=[boot,*pc.values(),*seen.values(),*errors])
        lookup('CLEAN_OUTPUT', [f'sub {name} by {characters[r,i,c]};' for (r,i,c),name in tagged.items()])
        lookup('CLEAN_OUTPUT_SINGLE', [f'sub {name} by {used_rows[r]};' for r,name in active_rows.items()] +
               [f'sub {executing[key]} by {codes[key]};' for key in ('IF','NEXT','GOTO','RETURN','WEND')] +
               [f'sub {name} by {print_joins[i]};' for i,name in print_active.items()] +
               [f'sub {name} by NULL;' for name in [*fresh_literal.values(),*print_chars.values(),*print_cursors.values()]])
        lookup('RESTORE_LINES', [f'sub {name} by {labels[n]};' for n,name in active.items()])
        # Preserve the following line label and emit its jump beside it. One
        # multiple-substitution helper replaces 99 constant-target setters.
        lookup('EMIT_NEXT_LINE', [f'sub {name} by {name} {jump[n]};' for n,name in labels.items()], stage=False)
        lookup('NEXT_LINE', [f"ignore sub {jump_next}' {label_cls};",
                            f"sub {jump_next}' by {jump_done};",
                            f"sub {jump_next} {label_cls}' lookup EMIT_NEXT_LINE;"],
               visible=[jump_next,*labels.values()])
        lookup('UPDATE_PC', [f"sub {pc_alive}' lookup RESET_PC lookup SET_PC_{n} {name};" for n,name in jump.items() if n in pc] +
               [f"sub {pc_alive}' {jump[0]} by {halted['missing']};",
                f"sub {pc_alive}' {jump_done} by {halted['done']};"],
               visible=[boot,*pc.values(),*seen.values(),*jump.values(),jump_done])
        lookup('CLEAN_TICK', [f'sub {name} by NULL;' for name in
               [*jump.values(),jump_next,jump_done,call_next,*write.values(),acknowledged,*errors,for_enter,for_skip,*while_results.values(),*result.values(),*truths.values()]])
        execution = list(stages)
        stages.clear()
        lookup('EXECUTION_LIMIT', [f'sub {name} by {halted["limit"]};' for name in [*pc.values(),*seen.values()]])
        final = list(stages)

        font.setGlyphOrder(order)
        for table in font['cmap'].tables:
            table.cmap = {ord(char):raw[char] for char in CHARS}
        for tag in ('GSUB','GPOS','GDEF','DSIG'):
            if tag in font:
                del font[tag]
        fea.append('table GDEF { GlyphClassDef ['+frame_name+'], , ['+' '.join(n for n in generated if n!=frame_name)+'], ; } GDEF;')
        sequence = initialization + execution + final
        fea += ['feature rlig {', *[f'lookup {name};' for name in sequence], '} rlig;']
        print(f'Compiling {len(order)} glyphs and interpreter rules...', flush=True)
        addOpenTypeFeaturesFromString(font, '\n'.join(fea))
        print('Substitution tables compiled.', flush=True)
        gsub = font['GSUB'].table
        feature = next(r.Feature for r in gsub.FeatureList.FeatureRecord if r.FeatureTag=='rlig')
        # A clock uses distinct lookup indices while sharing the actual tables.
        indices = feature.LookupListIndex
        index_by_name = dict(zip(sequence, indices))
        # Small extension subtables keep arithmetic's internal 16-bit offsets
        # bounded, without repeatedly invoking overflow repair while saving.
        calculation = gsub.LookupList.Lookup[index_by_name['CALCULATE']]
        subtables = [buildLigatureSubstSubtable({key:value for key,value in calc.items()
                     if key[0] in {left[i],left[i+1]}}) for i in range(0,100,2)]
        shared_calculation = buildLookup(
            subtables, flags=calculation.LookupFlag, markFilterSet=calculation.MarkFilteringSet,
            table='GSUB', extension=True)
        for name in ('CALCULATE','CALCULATE_NEXT_BOUND'):
            gsub.LookupList.Lookup[index_by_name[name]] = shared_calculation
        # The literal-output copier has many mappings. Split it explicitly,
        # then give every shared lookup extension offsets before serialization.
        # This avoids hundreds of full-table overflow-repair iterations.
        for shared in gsub.LookupList.Lookup:
            kind = shared.LookupType
            if kind == 2:
                subtables = []
                for table in shared.SubTable:
                    items = list(table.mapping.items())
                    subtables.extend(buildMultipleSubstSubtable(dict(items[i:i+2048]))
                                     for i in range(0,len(items),2048))
                shared.SubTable = subtables
                shared.SubTableCount = len(subtables)
            if kind != 7:
                extensions = []
                for table in shared.SubTable:
                    extension = otTables.ExtensionSubst()
                    extension.Format, extension.ExtensionLookupType = 1, kind
                    extension.ExtSubTable = table
                    extensions.append(extension)
                shared.LookupType, shared.SubTable = 7, extensions
        top, wrappers = [], {}
        def append_pass(name):
            # Keep distinct indices: shaping clients deduplicate repeated feature
            # indices. The indices can still point to the same wrapper object.
            if name in wrappers:
                top.append(len(gsub.LookupList.Lookup))
                gsub.LookupList.Lookup.append(wrappers[name])
                return
            original = gsub.LookupList.Lookup[index_by_name[name]]
            wrapper = otTables.Lookup()
            wrapper.LookupFlag = 0
            names = set()
            for subtable in original.SubTable:
                kind = original.LookupType
                if kind == 7:
                    kind, subtable = subtable.ExtensionLookupType, subtable.ExtSubTable
                if kind in (1,2):
                    names.update(subtable.mapping)
                elif kind == 4:
                    names.update(subtable.ligatures)
                elif kind == 6 and subtable.Format == 3:
                    names.update(subtable.InputCoverage[0].glyphs)
                else:
                    names.update(subtable.Coverage.glyphs)
            context = otTables.ChainContextSubst()
            context.Format = 3
            context.BacktrackCoverage, context.LookAheadCoverage = [], []
            context.BacktrackGlyphCount = context.LookAheadGlyphCount = 0
            context.InputCoverage = [buildCoverage(names, font.getReverseGlyphMap())]
            context.InputGlyphCount = context.SubstCount = 1
            record = otTables.SubstLookupRecord()
            record.SequenceIndex, record.LookupListIndex = 0, index_by_name[name]
            context.SubstLookupRecord = [record]
            extension = otTables.ExtensionSubst()
            extension.Format, extension.ExtensionLookupType, extension.ExtSubTable = 1, 6, context
            wrapper.LookupType, wrapper.SubTable, wrapper.SubTableCount = 7, [extension], 1
            wrappers[name] = wrapper
            top.append(len(gsub.LookupList.Lookup))
            gsub.LookupList.Lookup.append(wrapper)
        for name in initialization:
            if name in ('STRING_TAKE','STRING_ADVANCE'):
                continue
            if name == 'STRING_CLOSE':
                for _ in range(STRING_LENGTH):
                    append_pass('STRING_TAKE'); append_pass('STRING_ADVANCE')
            if name == 'PARSE':
                for _ in range(PRINT_ITEMS-1): append_pass(name)
            append_pass(name)
        for _ in range(MAX_STEPS):
            for name in execution:
                append_pass(name)
        # Resolve a jump made on the last tick before reporting the step limit.
        for name in ("ACTIVATE", "SEEN_LINE", "MISSING_LINE", "RESTORE_LINES", *final):
            append_pass(name)
        feature.LookupListIndex, feature.LookupCount = top, len(top)
        gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)
        # Repeated indices share serialized headers. Count unique objects as
        # a conservative bound; serializers may merge additional equal tables.
        unique_lookups = {id(item):item for item in gsub.LookupList.Lookup}.values()
        header_size = 2 + 2*len(gsub.LookupList.Lookup) + sum(
            6 + 2*lookup.SubTableCount + (2 if lookup.LookupFlag & 16 else 0)
            for lookup in unique_lookups)
        print(f'{len(gsub.LookupList.Lookup)} lookup indices, {len(wrappers)} shared clock wrappers, '
              f'{header_size} lookup-header bytes (upper bound).', flush=True)
        if header_size > 65535:
            raise ValueError('Clock lookup headers exceed OpenType offsets')
        font['hhea'].ascent, font['hhea'].descent = HEIGHT, 0
        font['OS/2'].sTypoAscender, font['OS/2'].sTypoDescender = HEIGHT, 0
        font['OS/2'].usWinAscent, font['OS/2'].usWinDescent = HEIGHT, 0
        font['OS/2'].fsType = 0
        replace_font_names(font, {1:'Mini BASIC',2:'Regular',3:'MiniBASIC',4:'Mini BASIC Regular',
                                6:'MiniBASIC-Regular',16:'Mini BASIC',17:'Regular'})
        print('Computing font identity...', flush=True)
        mark_modified_font(font, 'mini-basic', kind='interpreter')
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        print('Saving font...', flush=True)
        font.save(output)
        print(f'Saved {output}: {len(order)} glyphs, {MAX_STEPS} instructions')
    finally:
        font.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().with_name('mini-basic-font.ttf'))
    args = parser.parse_args()
    try:
        build_font(args.output)
    except Exception as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
