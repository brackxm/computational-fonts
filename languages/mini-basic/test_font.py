# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Compare actual Mini BASIC shaping with a separate small interpreter."""
import importlib.util
import json
from pathlib import Path
import random
import re
import shutil
import subprocess
import struct
import sys
import tempfile
import unittest
from zipfile import ZipFile

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.otBase import USE_HARFBUZZ_REPACKER

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHAPER = shutil.which('hb-shape')
spec = importlib.util.spec_from_file_location('basic_builder', HERE / 'build.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def encode(program):
    return 'RUN:' + (':'.join(program.splitlines()) + ':' if program else '') + '!'


def interpret(program):
    """Regex-based reference; it shares no parser or transition code with GSUB."""
    statements, pairs, open_loop = [], {}, None
    zero = dict.fromkeys('ABCD', 0)
    operand = r'(?:[A-D]|[0-9]{1,2})'
    expression = operand + r'(?:(?:[+*/-]|MOD)' + operand + r')?'
    comparison = r'(?:NOT)?' + operand + r'(?:<>|<=|>=|=|<|>)' + operand
    condition = comparison + r'(?:(?:AND|OR)' + comparison + r')?'
    for line in program.splitlines():
        line = ''.join(part if part.startswith('"') else re.sub(r'\s+', '', part.upper())
                       for part in re.findall(r'"[^"\n]*"|[^"\n]+|"',line))
        match = re.fullmatch(r'\s*([0-9]{1,2})\s*(.*?)\s*', line)
        if not match or not 1 <= int(match[1]) <= 99:
            return [], zero, 'syntax'
        number, text = int(match[1]), match[2]
        if statements and number <= statements[-1][0]: return [], zero, 'syntax'
        if match := re.fullmatch(r'(?:LET)?([A-D])=(' + expression + ')', text):
            instruction = ('let', *match.groups())
        elif match := re.fullmatch(r'PRINT(.+)', text):
            items = re.split(r';(?=(?:[^"\n]*"[^"\n]*")*[^"\n]*$)',match[1])
            item_pattern = r'(?:"[^"\n]{0,'+str(builder.STRING_LENGTH)+r'}"|'+expression+')'
            if len(items)>builder.PRINT_ITEMS or any(not re.fullmatch(item_pattern,item) for item in items):
                return [],zero,'syntax'
            instruction = ('print', items)
        elif match := re.fullmatch(r'IF(' + condition + r')THEN(?:GOTO)?([0-9]{1,2})(?:ELSE(?:GOTO)?([0-9]{1,2}))?', text):
            instruction = ('if', *match.groups())
        elif match := re.fullmatch(r'GOTO([0-9]{1,2})', text): instruction = ('goto', int(match[1]))
        elif match := re.fullmatch(r'GOSUB([0-9]{1,2})', text): instruction = ('gosub', int(match[1]))
        elif text == 'RETURN': instruction = ('return',)
        elif match := re.fullmatch(r'FOR([A-D])=([0-9]{1,2})TO([0-9]{1,2})(?:STEP(-?[0-9]{1,2}))?', text):
            step = int(match[4]) if match[4] is not None else 1
            if open_loop is not None or step==0: return [], zero, 'syntax'
            open_loop = ('for', len(statements), match[1])
            instruction = ('for', match[1], int(match[2]), int(match[3]), step)
        elif match := re.fullmatch(r'NEXT([A-D])', text):
            if open_loop is None or open_loop[0] != 'for' or open_loop[2] != match[1]: return [], zero, 'syntax'
            start = open_loop[1]
            pairs[start], pairs[len(statements)] = len(statements), start
            open_loop = None
            instruction = ('next', match[1])
        elif match := re.fullmatch(r'WHILE(' + condition + ')', text):
            if open_loop is not None: return [], zero, 'syntax'
            open_loop = ('while', len(statements), None)
            instruction = ('while', match[1])
        elif text == 'WEND':
            if open_loop is None or open_loop[0] != 'while': return [], zero, 'syntax'
            start = open_loop[1]
            pairs[start], pairs[len(statements)] = len(statements), start
            open_loop = None
            instruction = ('wend',)
        elif text == 'END': instruction = ('end',)
        elif text.startswith('REM'): instruction = ('rem',)
        else: return [], zero, 'syntax'
        statements.append((number, instruction))
    if len(statements) > builder.MAX_LINES or open_loop is not None: return [], zero, 'syntax'
    variables, output, active_loop, calls = dict.fromkeys('ABCD', 0), [], None, []
    by_number = {n:i for i,(n,_) in enumerate(statements)}
    index = 0
    def value(token): return variables[token] if token in variables else int(token)
    def evaluate(text):
        parts = re.fullmatch(r'([A-D]|[0-9]{1,2})(?:([+*/-]|MOD)([A-D]|[0-9]{1,2}))?', text)
        a = value(parts[1])
        if parts[2]:
            b, op = value(parts[3]), parts[2]
            if op in ('/', 'MOD') and b == 0: return None, 'division'
            a = a+b if op=='+' else a-b if op=='-' else a*b if op=='*' else a//b if op=='/' else a%b
        return (a, None) if 0 <= a <= 99 else (None, 'arithmetic')
    def evaluate_condition(text):
        parts = re.split(r'(AND|OR)',text)
        def evaluate_comparison(part):
            match = re.fullmatch(r'(NOT)?([A-D]|[0-9]{1,2})(<>|<=|>=|=|<|>)([A-D]|[0-9]{1,2})',part)
            a,b = value(match[2]),value(match[4])
            result = {'=':a==b,'<>':a!=b,'<':a<b,'<=':a<=b,'>':a>b,'>=':a>=b}[match[3]]
            return not result if match[1] else result
        first = evaluate_comparison(parts[0])
        if len(parts)==1: return first
        second = evaluate_comparison(parts[2])
        return first and second if parts[1]=='AND' else first or second
    for _ in range(builder.MAX_STEPS):
        if index == len(statements): return output, variables, 'done'
        instruction = statements[index][1]
        kind = instruction[0]
        next_index = index + 1
        if kind == 'let':
            number, error = evaluate(instruction[2])
            if error: return output, variables, error
            variables[instruction[1]] = number
        elif kind == 'print':
            pieces = []
            for item in instruction[1]:
                if item.startswith('"'): pieces.append(item[1:-1])
                else:
                    number,error = evaluate(item)
                    if error: return output,variables,error
                    pieces.append(str(number))
            row = ''.join(pieces)
            if len(row)>builder.STRING_LENGTH: return output,variables,'width'
            if len(output) == builder.OUTPUT_ROWS: return output, variables, 'output'
            output.append(row)
        elif kind in ('goto','if','gosub'):
            take = kind != 'if'
            if kind == 'if':
                take = evaluate_condition(instruction[1])
            if take or kind=='if' and instruction[3] is not None:
                if kind == 'gosub' and len(calls) == builder.CALL_DEPTH: return output, variables, 'stack'
                line = int(instruction[2] if take else instruction[3]) if kind=='if' else instruction[1]
                if line not in by_number: return output, variables, 'missing'
                if kind == 'gosub': calls.append(next_index)
                next_index = by_number[line]
        elif kind == 'return':
            if not calls: return output, variables, 'return'
            next_index = calls.pop()
        elif kind == 'for':
            if active_loop is not None: return output, variables, 'loop'
            variables[instruction[1]] = instruction[2]
            if (instruction[2] > instruction[3] if instruction[4]>0 else instruction[2] < instruction[3]): next_index = pairs[index] + 1
            else: active_loop = index
        elif kind == 'next':
            if active_loop != pairs[index]: return output, variables, 'loop'
            variable = instruction[1]
            incremented = variables[variable] + statements[active_loop][1][4]
            if not 0<=incremented<=99: return output, variables, 'arithmetic'
            variables[variable] = incremented
            step,limit = statements[active_loop][1][4],statements[active_loop][1][3]
            if (variables[variable] <= limit if step>0 else variables[variable] >= limit): next_index = active_loop + 1
            else: active_loop = None
        elif kind == 'while':
            if active_loop is not None and active_loop != index: return output, variables, 'loop'
            if evaluate_condition(instruction[1]): active_loop = index
            else:
                active_loop = None
                next_index = pairs[index] + 1
        elif kind == 'wend':
            if active_loop != pairs[index]: return output, variables, 'loop'
            next_index = pairs[index]
        elif kind == 'end': return output, variables, 'done'
        index = next_index
    return output, variables, 'done' if index==len(statements) else 'limit'


class BasicFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.fresh = Path(cls.temp.name) / 'fresh.ttf'
        result = subprocess.run([sys.executable, str(HERE / 'build.py'), '--output', str(cls.fresh)],
                                capture_output=True, text=True, timeout=180)
        if result.returncode: raise RuntimeError(result.stdout + result.stderr)
        cls.paths = [HERE / 'mini-basic-font.ttf', cls.fresh]

    def shape(self, path, programs):
        result = subprocess.run([SHAPER,str(path),'--text-file=-','--output-format=json','--features=kern=0'],
                input='\n'.join(programs)+'\n', capture_output=True, text=True, check=True, timeout=60)
        return [json.loads(line) for line in result.stdout.splitlines()]

    def state(self, rows):
        output, variables, status = {}, {}, []
        for row in rows:
            name = row['g']
            if match := re.fullmatch(r'basic\.output_number_(\d+)_(\d+)', name):
                output[int(match[1])] = str(int(match[2]))
            elif match := re.fullmatch(r'basic\.output_char_(\d+)_(\d+)_([a-f0-9]+)', name):
                output.setdefault(int(match[1]), {})[int(match[2])] = chr(int(match[3],16))
            elif match := re.fullmatch(r'basic\.row_used_(\d+)', name):
                output.setdefault(int(match[1]), {})
            elif match := re.fullmatch(r'basic\.reg_([A-D])_(\d+)', name):
                variables[match[1]] = int(match[2])
            elif name.startswith('basic.halt_'): status.append(name.removeprefix('basic.halt_'))
        self.assertEqual(len(status), 1, rows)
        self.assertEqual(sum(row['ax'] for row in rows), builder.WIDTH)
        self.assertEqual(sorted(output), list(range(len(output))))
        values = [v if isinstance(v,str) else ''.join(v[i] for i in sorted(v)) for _,v in sorted(output.items())]
        return values, variables, status[0]

    def check(self, programs):
        for path in self.paths:
            actual = self.shape(path, [encode(p) for p in programs])
            for program, rows in zip(programs, actual):
                with self.subTest(font=path.name,program=program):
                    self.assertEqual(self.state(rows), interpret(program))

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_backward_loop_and_independent_variables(self):
        self.check(['10 LET A=1\n20 PRINT A\n30 LET A=A+1\n40 IF A<=5 THEN GOTO 20\n50 END',
                    '10 LET A=12\n20 LET B=A+7\n30 LET C=B-A\n40 LET D=C\n50 PRINT D\n60 END',
                    '10 PRINT A\n20 PRINT B\n30 PRINT C\n40 PRINT D', ''])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_output_order_literals_case_and_repeat_execution(self):
        self.check(['10 PRINT "Hello;  BASIC!"\n20 PRINT ""\n30 PRINT 99\n40 END',
                    '10 let a=2\n20 print "MiXeD"\n30 print A\n40 let A=A-1\n50 if A>0 then goto 20\n60 END',
                    '10 GOTO 30\n20 PRINT "SECOND"\n25 END\n30 PRINT "FIRST"\n40 GOTO 20',
                    '10 REM comment with "quotes"\n20 PRINT "  spaces  "\n30 END'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_errors_and_whole_statement_validation(self):
        self.check(['10 LET A=99+1\n20 PRINT A', '10 LET A=0-1\n20 END', '10 GOTO 90',
                    '10 GOTO 10', '10 PRINT 1\n20 GOTO 10', '10 LET A=1+2+3\n20 END',
                    '10 PRINT 100\n20 END', '0 END', '10 END\n10 PRINT 1', '20 END\n10 END',
                    '10 LET E=1', '10 PRINT "'+ 'x'*25 +'"', '10 PRINT 1 garbage',
                    '\n'.join(f'{i} REM x' for i in range(1,18)), '10', '10 PRINT "unfinished'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_all_relations_and_generated_arithmetic(self):
        cases = []
        for op in ('=','<>','<','<=','>','>='):
            for a,b in ((0,0),(1,2),(99,0)):
                cases.append(f'10 LET A={a}\n20 LET B={b}\n30 IF A{op}B THEN GOTO 50\n40 PRINT 0\n45 END\n50 PRINT 1')
        rng = random.Random(127)
        for _ in range(30):
            a,b = rng.randrange(100),rng.randrange(100)
            op = rng.choice('+-')
            cases.append(f'10 LET A={a}\n20 LET B={b}\n30 LET C=A{op}B\n40 PRINT C\n50 END')
        self.check(cases)

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_exact_language_bounds(self):
        self.check(['10 PRINT "'+ 'x'*24 +'"',
                    '\n'.join(f'{i} REM x' for i in range(1,17)),
                    '\n'.join(f'{i} PRINT {i}' for i in range(1,9)),
                    '10 LET A=0\n20 LET A=A+1\n30 IF A<63 THEN GOTO 20\n40 END',
                    '10 LET A=0\n20 LET A=A+1\n30 IF A<64 THEN GOTO 20\n40 END',
                    '10 LET A=0\n20 LET A=A+1\n30 IF A<63 THEN GOTO 20\n40 GOTO 99'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_new_arithmetic_and_print_expressions(self):
        cases = ['10 A=7\n20 B=A*3\n30 PRINT B/2\n40 PRINT B MOD 2\n50 PRINT A+2\n60 PRINT B-A',
                 '10 PRINT 7*0', '10 A=12\n20 B=3\n30 B=A/B\n40 PRINT B',
                 '10 A=8\n20 A=A MOD 3\n30 PRINT A',
                 '10 A=9\n20 PRINT A*12', '10 A=8\n20 A=A/0', '10 PRINT 8 MOD 0', '10 PRINT 0/0', '10 PRINT 0 MOD 0',
                 '10 PRINT 99/1\n20 PRINT 0/99\n30 PRINT 99 MOD 1\n40 PRINT 99 MOD 99',
                 '10 A=0\n20 A=12/A', '10 A=0\n20 A=12 MOD A',
                 '10 PRINT 1+2*3', '10 PRINT (1+2)', '10 LET A=9\n20 A=99*99',
                 '10 PRINT "MOD / * FOR NEXT"', '10 print 99 mod 8']
        rng = random.Random(921)
        for op in ('+', '-', '*', '/', 'MOD'):
            for _ in range(15):
                a,b = rng.randrange(100),rng.randrange(100)
                cases.append(f'10 A={a}\n20 B={b}\n30 C=A{op}B\n40 PRINT C')
        self.check(cases)

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_counted_loops_and_control_flow(self):
        self.check(['10 FOR A=1 TO 5\n20 PRINT A*2\n30 NEXT A\n40 END',
                    '10 FOR B=3 TO 1\n20 PRINT B\n30 NEXT B\n40 PRINT B',
                    '10 FOR D=2 TO 2\n20 PRINT D\n30 NEXT D',
                    '10 FOR A=1 TO 2\n20 PRINT A\n30 NEXT A\n40 FOR B=3 TO 4\n50 PRINT B\n60 NEXT B',
                    '10 FOR A=0 TO 98\n20 NEXT A',
                    '10 FOR A=98 TO 99\n20 PRINT A\n30 NEXT A',
                    '10 FOR A=0 TO 98\n20 REM slow loop\n30 NEXT A',
                    '10 FOR A=1 TO 2\n20 GOTO 10\n30 NEXT A',
                    '10 GOTO 30\n20 FOR A=1 TO 2\n30 NEXT A',
                    '10 FOR A=1 TO 2\n20 GOTO 50\n30 NEXT A\n40 FOR B=1 TO 2\n50 NEXT B',
                    '10 FOR A=1 TO 2\n20 GOTO 40\n30 NEXT A\n40 FOR B=1 TO 2\n50 NEXT B',
                    '10 A=0\n20 FOR B=1 TO 2\n30 A=A+B\n40 NEXT B\n50 IF A<6 THEN GOTO 20\n60 PRINT A',
                    '10 FOR A=1 TO 3\n20 IF A=2 THEN GOTO 40\n30 PRINT A\n40 NEXT A',
                    '10 FOR A=1 TO 3\n20 A=7\n30 NEXT A\n40 PRINT A',
                    '10 FOR A=5 TO 3\n20 NEXT A',
                    '10 FOR A=3 TO 1\n20 NEXT A\n30 FOR B=1 TO 2\n40 PRINT B\n50 NEXT B',
                    '10 FOR A=1 TO 1\n20 NEXT A\n30 FOR B=1 TO 2\n40 GOTO 10\n50 NEXT B',
                    '10 FOR A=1 TO 1\n20 NEXT A\n30 FOR B=1 TO 2\n40 GOTO 20\n50 NEXT B',
                    '10 FOR A=1 TO 1\n20 NEXT A\n30 PRINT 8\n40 GOTO 20'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_malformed_counted_loops(self):
        self.check(['10 FOR A=1 TO 2', '10 NEXT A',
                    '10 FOR A=1 TO 2\n20 NEXT B',
                    '10 FOR A=1 TO 2\n20 FOR B=1 TO 2\n30 NEXT B\n40 NEXT A',
                    '10 FOR A=1 TO B\n20 NEXT A', '10 FOR A=1+1 TO 3\n20 NEXT A',
                    '10 FOR A=1 TO 3 STEP 0\n20 NEXT A',
                    '10 FOR A=1 TO 3\n20 NEXT A garbage',
                    '10 NEXT A\n20 FOR A=1 TO 3\n30 NEXT A'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_counted_loop_steps(self):
        cases = ['10 FOR A=1 TO 9 STEP 2\n20 PRINT A\n30 NEXT A',
                 '10 FOR B=2 TO 8 STEP 3\n20 PRINT B\n30 NEXT B\n40 PRINT B',
                 '10 FOR C=0 TO 0 STEP 99\n20 PRINT C\n30 NEXT C\n40 PRINT C',
                 '10 FOR D=1 TO 1 STEP 98\n20 PRINT D\n30 NEXT D',
                 '10 FOR A=3 TO 1 STEP 99\n20 PRINT 0\n30 NEXT A\n40 PRINT A',
                 '10 FOR A=0 TO 99 STEP 99\n20 PRINT A\n30 NEXT A',
                 '10 FOR A=90 TO 90 STEP 20\n20 PRINT A\n30 NEXT A',
                 '10 FOR A=1 TO 5 STEP 2\n20 A=98\n30 NEXT A',
                 '10 FOR A=1 TO 1 STEP 1\n20 NEXT A\n30 FOR A=1 TO 4 STEP 3\n40 PRINT A\n50 NEXT A',
                 '10 FOR B=3 TO 1 STEP 9\n20 NEXT B\n30 FOR D=1 TO 3\n40 PRINT D\n50 NEXT D',
                 '10 FOR A=1 TO 5 STEP 2\n20 GOSUB 60\n30 NEXT A\n40 END\n60 PRINT A*A\n70 RETURN',
                 '10 for b=01 to 05 step 02\n20 print b\n30 next b',
                 '10 FOR A=0 TO 98 STEP 2\n20 NEXT A',
                 '10 PRINT "STEP -2 0"']
        for i,variable in enumerate('ABCD'):
            for step in range(1,100):
                start = i
                limit = min(99,start+2*step)
                cases.append(f'10 FOR {variable}={start} TO {limit} STEP {step}\n20 NEXT {variable}\n30 PRINT {variable}')
        self.check(cases)

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_malformed_steps(self):
        self.check(['10 A=7\n20 FOR A=1 TO 3 STEP 0\n30 NEXT A',
                    '10 FOR A=1 TO 3 STEP 00\n20 NEXT A',
                    '10 FOR A=1 TO 3 STEP -0\n20 NEXT A',
                    '10 FOR A=1 TO 3 STEP -100\n20 NEXT A',
                    '10 FOR A=1 TO 3 STEP A\n20 NEXT A',
                    '10 FOR A=1 TO 3 STEP 1+1\n20 NEXT A',
                    '10 FOR A=1 TO 3 STEP 100\n20 NEXT A',
                    '10 FOR A=1 TO 3 STEP\n20 NEXT A',
                    '10 FOR A=1 TO 3 STEP 2 STEP 3\n20 NEXT A',
                    '10 FOR A=1 TO 3 STEP +2\n20 NEXT A',
                    '10 FOR A=1 TO 3 STEP 2.5\n20 NEXT A'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_subroutines_and_return_stack(self):
        self.check(['10 A=3\n20 GOSUB 70\n30 PRINT A\n40 GOSUB 70\n50 PRINT A\n60 END\n70 A=A*2\n80 RETURN',
                    '10 GOSUB 30\n20 END\n30 GOSUB 50\n40 RETURN\n50 GOSUB 70\n60 RETURN\n70 GOSUB 90\n80 RETURN\n90 PRINT 4\n99 RETURN',
                    '10 GOSUB 10', '10 A=A+1\n20 GOSUB 10',
                    '10 RETURN', '10 A=8\n20 PRINT A\n30 RETURN',
                    '10 GOSUB 99', '10 GOSUB 0',
                    '10 GOSUB 30\n20 END\n30 PRINT "Hello"\n40 END',
                    '10 GOSUB 30\n20 PRINT 9\n25 END\n30 RETURN',
                    '10 GOTO 30\n20 RETURN\n30 GOSUB 20',
                    '10 GOSUB 30\n20 RETURN\n30 RETURN',
                    '10 FOR B=1 TO 3\n20 GOSUB 60\n30 NEXT B\n40 END\n60 PRINT B*2\n70 RETURN',
                    '10 GOTO 60\n20 A=A+1\n30 IF A<3 THEN 50\n40 RETURN\n50 GOSUB 20\n55 RETURN\n60 GOSUB 20\n70 PRINT A\n80 END',
                    '10 GOSUB 40\n20 PRINT 1\n30 END\n40 IF A=0 THEN 70\n50 PRINT 2\n60 RETURN\n70 A=1\n80 GOSUB 40\n90 RETURN'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_short_if_and_malformed_subroutines(self):
        self.check(['10 A=3\n20 PRINT A\n30 A=A-1\n40 IF A>0 THEN 20\n50 END',
                    '10 IF 0=1 THEN 99\n20 PRINT 5', '10 IF 1=1 THEN 0',
                    '10 GOSUB A', '10 GOSUB 1+2', '10 GOSUB 20 garbage\n20 RETURN',
                    '10 RETURN 20', '10 IF 1=1 THEN GOSUB 20\n20 RETURN',
                    '10 IF 1=1 THEN RETURN', '10 IF 1=1 THEN 2+3',
                    '10 print "GOSUB RETURN THEN"', '10 gosub 30\n20 end\n30 return'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_logical_combinations_and_negation(self):
        cases = []
        ops = ['=','<>','<','<=','>','>=']
        for i,op in enumerate(ops):
            for join in ('AND','OR'):
                for first_not in ('','NOT '):
                    for second_not in ('','NOT '):
                        for a,b in ((0,0),(0,1),(1,0),(1,1),(2,2)):
                            condition = f'{first_not}A{op}1 {join} {second_not}B{ops[(i+1)%6]}1'
                            cases.append(f'10 A={a}\n20 B={b}\n30 IF {condition} THEN GOTO 60\n40 PRINT 0\n50 END\n60 PRINT 1')
            for a in (0,1,2):
                cases.append(f'10 A={a}\n20 IF NOT A{op}1 THEN 50\n30 PRINT 0\n40 END\n50 PRINT 1')
        self.check(cases)

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_logical_conditions_repeat_and_boundaries(self):
        self.check(['10 A=0\n20 IF NOT A>=3 AND A<5 THEN 40\n30 END\n40 PRINT A\n50 A=A+1\n60 GOTO 20',
                    '10 A=0\n20 IF A=0 OR NOT A=3 THEN 40\n30 END\n40 PRINT A\n50 A=A+1\n60 GOTO 20',
                    '10 A=0\n20 B=4\n30 IF NOT A<2 OR NOT B=4 THEN 60\n40 A=A+1\n50 GOTO 30\n60 PRINT A',
                    '10 IF 0=1 AND 1=1 THEN 99\n20 PRINT 7',
                    '10 IF NOT 0=0 OR 0=1 THEN 99\n20 PRINT 7',
                    '10 IF 1=1 AND 1=1 THEN 99',
                    '10 PRINT 3\n20 END\n30 IF 1=1 OR 1=1 THEN 0',
                    '10 IF 1=1 THEN 30\n20 IF NOT 0=0 AND 1=1 THEN 0\n30 PRINT 5',
                    '10 C=0\n20 D=3\n30 IF C<D AND NOT D=0 THEN 50\n40 PRINT C\n45 END\n50 C=C+1\n60 D=D-1\n70 GOTO 30',
                    '10 A=0\n20 A=A+1\n30 IF A<63 AND NOT B<>0 THEN 20\n40 END',
                    '10 A=0\n20 A=A+1\n30 IF A<64 AND NOT B<>0 THEN 20\n40 END',
                    '10 FOR A=1 TO 5 STEP 2\n20 GOSUB 60\n30 NEXT A\n40 END\n60 IF NOT A=3 AND A<5 THEN 80\n70 RETURN\n80 PRINT A\n90 RETURN',
                    '10 PRINT "NOT AND OR"',
                    '10 if not a<>0 and not b>0 then 30\n20 end\n30 print 5'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_malformed_logical_conditions(self):
        self.check(['10 IF NOT NOT A=0 THEN 20\n20 END',
                    '10 IF A=0 AND B=0 AND C=0 THEN 20\n20 END',
                    '10 IF A=0 AND B=0 OR C=0 THEN 20\n20 END',
                    '10 IF A=0 AND THEN 20\n20 END', '10 IF AND A=0 THEN 20\n20 END',
                    '10 IF NOT A THEN 20\n20 END', '10 IF A=0 NOT B=0 THEN 20\n20 END',
                    '10 IF (A=0 OR B=0) THEN 20\n20 END',
                    '10 IF A+1=1 AND B=0 THEN 20\n20 END',
                    '10 IF A=0 OR OR B=0 THEN 20\n20 END',
                    '10 A=NOT B', '10 PRINT NOT A=0',
                    '10 A=7\n20 IF NOT A=7 AND B=0 THEN 30 garbage\n30 END'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_while_retesting_and_conditions(self):
        cases = ['10 WHILE 0=1\n20 PRINT 9\n30 WEND',
                 '10 WHILE 0=1\n20 PRINT 9\n30 WEND\n40 PRINT 7',
                 '10 A=0\n20 WHILE A<3\n30 PRINT A\n40 A=A+1\n50 WEND\n60 PRINT A',
                 '10 WHILE 1=1\n20 WEND',
                 '10 WHILE 1=1\n20 PRINT 7\n30 WEND',
                 '10 A=0\n20 WHILE A<42\n30 A=A+1\n40 WEND',
                 '10 A=0\n20 WHILE A<43\n30 A=A+1\n40 WEND',
                 '10 A=0\n20 WHILE A<2\n30 A=A+1\n40 GOTO 20\n50 WEND\n60 PRINT A',
                 '10 A=0\n20 WHILE A<3 AND NOT B=1\n30 A=A+1\n40 B=A MOD 2\n50 WEND\n60 PRINT A',
                 '10 A=0\n20 WHILE NOT A>=3 OR B<>0\n30 A=A+1\n40 WEND\n50 PRINT A',
                 '10 while not a>=2\n20 a=a+1\n30 wend\n40 print a',
                 '10 PRINT "WHILE WEND"']
        for variable in 'ABCD':
            cases.append(f'10 {variable}=0\n20 WHILE {variable}<3\n30 PRINT {variable}\n40 {variable}={variable}+1\n50 WEND')
        for op in ('=','<>','<','<=','>','>='):
            for join in ('AND','OR'):
                for negation in ('','NOT '):
                    for start in (0,1,2):
                        cases.append(f'10 A={start}\n20 WHILE {negation}A{op}1 {join} NOT B=0\n30 A=A+1\n40 WEND\n50 PRINT A')
        self.check(cases)

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_while_loop_state_and_subroutines(self):
        self.check(['10 A=0\n20 WHILE A<2\n30 A=A+1\n40 WEND\n50 FOR B=1 TO 2\n60 PRINT B\n70 NEXT B',
                    '10 FOR B=2 TO 1\n20 PRINT 9\n30 NEXT B\n40 WHILE A<B\n50 A=A+1\n60 WEND\n70 PRINT A',
                    '10 WHILE 0=1\n20 PRINT 9\n30 WEND\n40 WHILE B<2\n50 B=B+1\n60 WEND\n70 PRINT B',
                    '10 FOR B=1 TO 2\n20 PRINT B\n30 NEXT B\n40 WHILE A<B\n50 A=A+1\n60 WEND\n70 PRINT A',
                    '10 WHILE A<2\n20 A=A+1\n30 WEND\n40 WHILE B<A\n50 B=B+1\n60 WEND\n70 PRINT B',
                    '10 GOTO 30\n20 WHILE A<2\n30 WEND',
                    '10 WHILE A<2\n20 GOTO 50\n30 WEND\n40 WHILE B<2\n50 WEND',
                    '10 WHILE A<2\n20 GOTO 40\n30 WEND\n40 WHILE B<2\n50 WEND',
                    '10 WHILE A<2\n20 GOTO 40\n30 WEND\n40 FOR B=1 TO 2\n50 NEXT B',
                    '10 FOR B=1 TO 2\n20 GOTO 40\n30 NEXT B\n40 WHILE A<2\n50 WEND',
                    '10 WHILE A<2\n20 GOSUB 70\n30 WEND\n40 PRINT A\n50 END\n70 A=A+1\n80 RETURN',
                    '10 GOSUB 50\n20 PRINT A\n30 END\n50 WHILE A<2\n60 A=A+1\n70 WEND\n80 RETURN',
                    '10 WHILE A<2\n20 A=A+1\n30 GOTO 50\n40 WEND\n50 GOTO 10'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_malformed_while_loops(self):
        self.check(['10 WEND', '10 WHILE A<2', '10 WHILE A<2\n20 NEXT A',
                    '10 FOR A=0 TO 2\n20 WEND',
                    '10 WHILE A<2\n20 WHILE B<2\n30 WEND\n40 WEND',
                    '10 WHILE A<2\n20 FOR B=0 TO 2\n30 NEXT B\n40 WEND',
                    '10 FOR A=0 TO 2\n20 WHILE B<2\n30 WEND\n40 NEXT A',
                    '10 A=7\n20 END\n30 WHILE A<2',
                    '10 WHILE\n20 WEND', '10 WHILE A\n20 WEND',
                    '10 WHILE A<2 THEN 30\n20 WEND\n30 END',
                    '10 WHILE A+1<2\n20 WEND', '10 WHILE NOT NOT A<2\n20 WEND',
                    '10 WHILE A=0 AND B=0 OR C=0\n20 WEND',
                    '10 WHILE A=0 AND\n20 WEND', '10 WHILE (A<2)\n20 WEND',
                    '10 WHILE A<2 garbage\n20 WEND', '10 WHILE A<2\n20 WEND A'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_else_branches_and_conditions(self):
        cases = []
        for first_goto in ('','GOTO '):
            for second_goto in ('','GOTO '):
                for value in (0,1,2):
                    cases.append(f'10 A={value}\n20 IF A=1 THEN {first_goto}50 ELSE {second_goto}70\n30 PRINT 9\n40 END\n50 PRINT "YES"\n60 END\n70 PRINT "NO"')
        for target in range(100):
            cases.append(f'1 IF 0=1 THEN 99 ELSE {target}' + (f'\n{target} PRINT 7' if target>1 else ''))
        for op in ('=','<>','<','<=','>','>='):
            for join in ('AND','OR'):
                for first_not in ('','NOT '):
                    for second_not in ('','NOT '):
                        for a,b in ((0,0),(0,1),(1,0),(1,1),(2,2)):
                            condition = f'{first_not}A{op}1 {join} {second_not}B<>1'
                            cases.append(f'10 A={a}\n20 B={b}\n30 IF {condition} THEN 60 ELSE 80\n40 PRINT 9\n50 END\n60 PRINT 1\n70 END\n80 PRINT 0')
        self.check(cases)

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_else_targets_control_flow_and_limits(self):
        self.check(['10 IF 1=1 THEN 30 ELSE 99\n20 PRINT 9\n30 PRINT 7',
                    '10 IF 0=1 THEN 99 ELSE 30\n20 PRINT 9\n30 PRINT 7',
                    '10 PRINT 5\n20 IF 1=1 THEN 99 ELSE 30\n30 END',
                    '10 PRINT 5\n20 IF 0=1 THEN 30 ELSE 99\n30 END',
                    '10 IF 1=1 THEN 20 ELSE 0\n20 END',
                    '10 IF 0=1 THEN 0 ELSE 20\n20 END',
                    '10 IF 0=1 THEN 20 ELSE 0\n20 END',
                    '10 IF 1=1 THEN 0 ELSE 20\n20 END',
                    '10 IF 0=1 THEN 10 ELSE 10',
                    '10 A=0\n20 A=A+1\n30 IF A<63 THEN 20 ELSE 40\n40 END',
                    '10 A=0\n20 A=A+1\n30 IF A<64 THEN 20 ELSE 40\n40 END',
                    '10 A=0\n20 IF A<3 THEN 40 ELSE 70\n30 END\n40 PRINT A\n50 A=A+1\n60 GOTO 20\n70 PRINT "DONE"',
                    '10 FOR A=1 TO 3\n20 GOSUB 60\n30 NEXT A\n40 END\n60 IF A=2 THEN 90 ELSE 80\n70 END\n80 RETURN\n90 PRINT A\n99 RETURN',
                    '10 WHILE A<3\n20 IF A=1 THEN 40 ELSE 30\n30 PRINT A\n40 A=A+1\n50 WEND\n60 PRINT A',
                    '10 if not a<>0 then goto 30 else 20\n20 end\n30 print "ELSE"',
                    '10 IF A=0 THEN 30 ELSE 40\n20 IF A=1 THEN 99 ELSE 98\n30 END\n40 END'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_malformed_else_branches(self):
        self.check(['10 IF A=0 THEN 20 ELSE\n20 END',
                    '10 IF A=0 THEN ELSE 20\n20 END',
                    '10 IF A=0 THEN 20 ELSE GOTO\n20 END',
                    '10 IF A=0 THEN 20 ELSE A\n20 END',
                    '10 IF A=0 THEN 20 ELSE 2+3\n20 END',
                    '10 IF A=0 THEN 20 ELSE PRINT 7\n20 END',
                    '10 IF A=0 THEN 20 ELSE GOSUB 20\n20 END',
                    '10 IF A=0 THEN 20 ELSE RETURN\n20 END',
                    '10 IF A=0 THEN 20 ELSE 20 ELSE 20\n20 END',
                    '10 IF A=0 THEN 20 ELSE IF A=1 THEN 20\n20 END',
                    '10 ELSE 20\n20 END', '10 GOTO 20 ELSE 20\n20 END',
                    '10 WHILE A<2 ELSE 20\n20 WEND',
                    '10 A=7\n20 END\n30 IF A=0 THEN 20 ELSE 20 garbage',
                    '10 IF A=0 THEN 20 ELSE 100\n20 END'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_print_lists_and_numeric_columns(self):
        cases = ['10 PRINT "A=";A', '10 PRINT 7;" Hello";3+4',
                 '10 PRINT "";"";"";""', '10 PRINT 1;2;3;4',
                 '10 PRINT "a;:!";0;" b";99',
                 '10 A=7\n20 B=3\n30 PRINT "A=";A;", B=";B\n40 PRINT A+B;" ";A-B',
                 '10 PRINT "x";"y"\n20 PRINT "z";"q"',
                 '10 FOR A=8 TO 11\n20 PRINT "A=";A;"!"\n30 NEXT A',
                 '10 A=0\n20 WHILE A<3\n30 PRINT A;":";A*A\n40 A=A+1\n50 WEND',
                 '10 PRINT 99/2;" remainder ";99 MOD 2',
                 '10 print "MiXeD ";01;" End"',
                 '10 GOSUB 40\n20 GOSUB 40\n30 END\n40 PRINT "A=";A\n50 A=A+1\n60 RETURN']
        for variable in 'ABCD':
            for value in range(100):
                cases.append(f'10 {variable}={value}\n20 PRINT "{variable}=";{variable};"/";{variable}+0')
        self.check(cases)

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_print_list_bounds_and_atomic_errors(self):
        self.check(['10 PRINT "'+ 'x'*22 +'";99',
                    '10 PRINT "'+ 'x'*23 +'";9',
                    '10 A=7\n20 PRINT "prior"\n30 PRINT "'+ 'x'*23 +'";99',
                    '10 PRINT "'+ 'x'*24 +'";""',
                    '10 PRINT "'+ 'x'*24 +'";1',
                    '10 A=7\n20 PRINT "prior"\n30 PRINT "x=";1/0',
                    '10 PRINT "'+ 'x'*24 +'";1;1/0',
                    '10 PRINT 1/0;99+1', '10 PRINT 99+1;1/0',
                    '10 PRINT "ok"\n20 PRINT 1;99+1',
                    '\n'.join(f'{i} PRINT "row=";{i}' for i in range(1,10)),
                    '10 PRINT "";""\n20 GOTO 10'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_malformed_print_lists(self):
        self.check(['10 PRINT', '10 PRINT ;A', '10 PRINT A;',
                    '10 PRINT "x";;A', '10 PRINT 1;2;3;4;5',
                    '10 PRINT "x";"y";"z";"q";"r"',
                    '10 PRINT "x";"y" garbage', '10 PRINT "x";"unterminated',
                    '10 PRINT "x";A+1+2', '10 PRINT "x",A',
                    '10 PRINT "x";E', '10 PRINT "x";100',
                    '10 A=7\n20 END\n30 PRINT "x";A;',
                    '10 PRINT "x";"'+ 'y'*25 +'"'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_generated_print_item_boundaries(self):
        rng = random.Random(412)
        items = ['A', 'B', '0', '99', 'A+B', 'B-A', '99+1', '1/0',
                 'A MOD B', '""', '"a;:!"', '" PRINT END "', '"'+ 'x'*24 +'"']
        cases = []
        for _ in range(80):
            statement = '20 PRINT ' + ';'.join(rng.choice(items) for _ in range(rng.randrange(1,7)))
            cases.append('10 A=3\n15 B=4\n'+statement+'\n30 PRINT "after"')
            position = rng.randrange(len(statement))
            malformed = statement[:position]+rng.choice(';0129+-*/"ABCDEFG!')+statement[position:]
            cases.append('10 A=3\n15 B=4\n'+malformed+'\n30 PRINT "after"')
        self.check(cases)

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_descending_loops_and_every_step(self):
        cases = ['10 FOR A=3 TO 1 STEP -1\n20 PRINT "A=";A\n30 NEXT A\n40 PRINT A',
                 '10 FOR B=9 TO 2 STEP -2\n20 PRINT B\n30 NEXT B\n40 PRINT B',
                 '10 FOR C=1 TO 3 STEP -1\n20 PRINT 9\n30 NEXT C\n40 PRINT C',
                 '10 FOR D=0 TO 0 STEP -1\n20 PRINT D\n30 NEXT D',
                 '10 FOR A=3 TO 2 STEP -5\n20 PRINT A\n30 NEXT A',
                 '10 FOR A=5 TO 2 STEP -1\n20 A=0\n30 NEXT A',
                 '10 FOR A=99 TO 1 STEP -99\n20 NEXT A',
                 '10 FOR A=99 TO 0 STEP -99\n20 PRINT A\n30 NEXT A',
                 '10 for b=05 to 01 step -02\n20 print b\n30 next b',
                 '10 FOR A=99 TO 1 STEP -1\n20 NEXT A',
                 '10 PRINT "STEP -2"']
        for variable in 'ABCD':
            for step in range(1,100):
                cases.append(f'10 FOR {variable}=99 TO 2 STEP -{step}\n20 NEXT {variable}\n30 PRINT {variable}')
        self.check(cases)

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_descending_loop_state_and_print_lists(self):
        self.check(['10 FOR A=3 TO 1 STEP -1\n20 PRINT "down=";A\n30 NEXT A\n40 FOR B=1 TO 2\n50 PRINT "up=";B\n60 NEXT B',
                    '10 D=0\n20 FOR A=3 TO 1 STEP -1\n30 D=D+1\n40 NEXT A\n50 IF D<6 THEN 20\n60 PRINT D',
                    '10 D=0\n20 FOR A=1 TO 3 STEP -1\n30 PRINT 9\n40 NEXT A\n50 D=D+1\n60 IF D<2 THEN 20\n70 PRINT A',
                    '10 FOR A=1 TO 2\n20 NEXT A\n30 FOR B=4 TO 2 STEP -2\n40 PRINT "B=";B\n50 NEXT B',
                    '10 FOR A=4 TO 1 STEP -1\n20 GOSUB 70\n30 NEXT A\n40 END\n70 IF A=2 THEN 90 ELSE 80\n80 RETURN\n90 PRINT "A=";A\n99 RETURN',
                    '10 FOR A=4 TO 2 STEP -1\n20 NEXT A\n30 WHILE B<A\n40 B=B+1\n50 WEND\n60 PRINT "A=";A;",B=";B',
                    '10 GOTO 30\n20 FOR A=3 TO 1 STEP -1\n30 NEXT A',
                    '10 FOR A=3 TO 1 STEP -1\n20 GOTO 10\n30 NEXT A',
                    '10 FOR A=3 TO 1 STEP -1\n20 GOTO 40\n30 NEXT A\n40 FOR B=3 TO 1 STEP -1\n50 NEXT B',
                    '10 FOR A=1 TO 3 STEP -1\n20 NEXT A\n30 FOR B=3 TO 1 STEP -1\n40 PRINT "B=";B\n50 NEXT B',
                    '10 FOR A=3 TO 1 STEP -1\n20 PRINT "A=";A;", square=";A*A\n30 NEXT A'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_malformed_negative_steps(self):
        self.check(['10 FOR A=3 TO 1 STEP -0\n20 NEXT A',
                    '10 FOR A=3 TO 1 STEP -00\n20 NEXT A',
                    '10 FOR A=3 TO 1 STEP -100\n20 NEXT A',
                    '10 FOR A=3 TO 1 STEP -A\n20 NEXT A',
                    '10 FOR A=3 TO 1 STEP --1\n20 NEXT A',
                    '10 FOR A=3 TO 1 STEP -1+1\n20 NEXT A',
                    '10 FOR A=-3 TO 1 STEP -1\n20 NEXT A',
                    '10 FOR A=3 TO -1 STEP -1\n20 NEXT A'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_raw_envelope_and_parse_boundaries(self):
        invalid = ['RUN;10 END;', 'RUN;10 PRINT 1;;!', 'RUN;10 PRINT 1;!;!',
                   'RUN;10 LET A=3 junk;20 END;!', 'RUN;!10 END;!', 'RUN;!;!', 'RUN;10 END;20 PRINT "bad;!',
                   'RUN;10 PRINT "ok";20;!', 'RUN;10 PRINT "A=";A;20 END;!',
                   'RUN;10 PRINT 1:20 END:!', 'RUN:10 PRINT 1::!', 'RUN:!10 END:!', 'RUN:!;!']
        for path in self.paths:
            for rows in self.shape(path, invalid):
                self.assertEqual(self.state(rows), ([],dict.fromkeys('ABCD',0),'syntax'))
        source = ['10 PRINT 7\n20 END', '10 A=3\n20 PRINT A\n30 END',
                  '10 FOR A=3 TO 1 STEP -1\n20 PRINT A\n30 NEXT A',
                  '10 PRINT 1\n20 REM http://example\n30 PRINT 2',
                  '10 PRINT 1\n20 REM "quoted: comment"\n30 PRINT 2',
                  '10 PRINT ":;!"\n20 END', '']
        legacy = ['RUN;' + (';'.join(p.splitlines())+';' if p else '') + '!' for p in source]
        for path in self.paths:
            for program,rows in zip(source,self.shape(path,legacy)):
                self.assertEqual(self.state(rows),interpret(program))

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_spaces_and_comment_separators(self):
        self.check(['1 0 P R I N T " A=";0 7\n2 0 END',
                    '10 R E M ignored ;PRINT "unterminated\n20 PRINT 7',
                    '10 PRINT ""\n20 REM ;PRINT "ignored";!\n30 PRINT ":;"',
                    '10 FOR A=3 TO 1 STEP -1\n20 PRINT "A=";A\n30 NEXT A'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_shared_updates_for_every_variable_and_value(self):
        programs = []
        for i,variable in enumerate('ABCD'):
            other = 'ABCD'[(i+1)%4]
            for value in range(100):
                programs.append(f'10 {variable}={value}\n20 {other}={variable}+0\n30 PRINT {other}\n'
                                f'40 {variable}=0+{other}\n50 PRINT {variable}\n60 {variable}=0\n'
                                f'70 PRINT {variable}\n80 PRINT {other}\n90 {variable}={(value+37)%100}\n'
                                f'91 PRINT {variable}\n92 PRINT {other}\n93 {variable}={other}\n'
                                f'94 PRINT {variable}\n99 END')
        self.check(programs)

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_numbers_between_operands_and_instruction_boundaries(self):
        self.check(['10 A=7\n20 B=A*3\n30 PRINT A\n40 PRINT B',
                    '10 PRINT 7\n20 PRINT 9*2',
                    '10 A=5\n20 END\n30 B=A*3',
                    '10 FOR A=1 TO 3\n20 PRINT A*A\n30 NEXT A'])

    @unittest.skipUnless(SHAPER, 'Install hb-shape')
    def test_compact_tables_and_fonttools_only_serialization(self):
        programs = ['10 FOR A=1 TO 5 STEP 2\n20 GOSUB 70\n30 NEXT A\n40 PRINT 7/2\n50 END\n70 IF NOT A=3 AND A<5 THEN 90\n80 RETURN\n90 PRINT A*A\n99 RETURN',
                    '10 FOR A=6 TO 2 STEP -2\n20 GOSUB 70\n30 NEXT A\n40 PRINT "A=";A\n50 END\n70 IF NOT A=4 AND B=0 THEN 90 ELSE 80\n80 RETURN\n90 PRINT "A=";A;", square=";A*A\n99 RETURN',
                    '10 PRINT "'+ 'x'*22 +'";99',
                    '10 A=0\n20 WHILE A<3\n30 GOSUB 70\n40 A=A+1\n50 WEND\n60 END\n70 IF NOT A=1 AND B=0 THEN 90 ELSE 80\n80 RETURN\n90 PRINT A\n99 RETURN',
                    '10 WHILE NOT A>=3 AND B=0\n20 GOSUB 70\n30 WEND\n40 PRINT A\n50 END\n70 A=A+1\n80 RETURN',
                    '10 GOSUB 10', '10 RETURN',
                    '10 GOSUB 30\n20 END\n30 GOSUB 50\n40 RETURN\n50 GOSUB 70\n60 RETURN\n70 GOSUB 90\n80 RETURN\n90 PRINT 4\n99 RETURN']
        for i,path in enumerate(self.paths):
            with TTFont(path) as font:
                data = font.getTableData('GSUB')
                start = struct.unpack_from('>H',data,8)[0]
                count = struct.unpack_from('>H',data,start)[0]
                offsets = struct.unpack_from('>'+str(count)+'H',data,start+2)
                # Resource budgets leave room for additions while detecting a
                # return to thousands of specialized helper tables.
                self.assertLessEqual(len(set(offsets)),1000)
                # PRINT's row-layout stages add clock indices; the budget still
                # stays well below 16-bit offsets and caps helper proliferation.
                self.assertLessEqual(max(offsets),38000)
                font.cfg[USE_HARFBUZZ_REPACKER] = False
                font['GSUB'].compile(font)  # force serialization, not raw-table copying
                pure = Path(self.temp.name)/f'pure-{i}.ttf'
                font.save(pure)
            for program,rows in zip(programs,self.shape(pure,[encode(p) for p in programs])):
                self.assertEqual(self.state(rows),interpret(program))

    def test_font_metadata_geometry_and_source_protection(self):
        for path in self.paths:
            with TTFont(path) as font:
                self.assertEqual(font['name'].getBestFamilyName(), 'Mini BASIC')
                self.assertEqual(set(font.getBestCmap()),set(range(32,127)))
                self.assertEqual(font['OS/2'].fsType,0)
                self.assertIn('Apache',font['name'].getDebugName(13))
                self.assertIn('Interpreter modifications',font['name'].getDebugName(0))
                for name in font.getGlyphOrder():
                    if not name.startswith('basic.'): continue
                    glyph = font['glyf'][name]
                    self.assertEqual(font['hmtx'][name][0],builder.WIDTH if name=='basic.frame' else 0)
                    self.assertEqual(font['hmtx'][name][1], getattr(glyph, 'xMin', 0), name)
                    if glyph.numberOfContours:
                        self.assertGreaterEqual(glyph.yMin,0,name)
                        self.assertLessEqual(glyph.yMax,builder.HEIGHT,name)
                        if name!='basic.frame':
                            self.assertGreaterEqual(glyph.xMin,-builder.WIDTH,name)
                            self.assertLessEqual(glyph.xMax,0,name)
        with self.assertRaisesRegex(ValueError,'Output must differ'):
            builder.build_font(builder.DEFAULT_BASE)
        empty = Path(self.temp.name) / 'import'
        empty.mkdir()
        result = subprocess.run([sys.executable,'-c','import runpy; runpy.run_path('+repr(str(HERE/'build.py'))+')'],
                                cwd=empty, capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(list(empty.iterdir()),[])

    def test_specimen_embeds_the_current_fonts(self):
        with ZipFile(HERE/'mini-basic.odt') as odt:
            self.assertEqual(odt.read('Fonts/computational.ttf'), self.paths[0].read_bytes())
            self.assertEqual(odt.read('Fonts/Roboto-Regular.ttf'), builder.DEFAULT_BASE.read_bytes())


if __name__ == '__main__': unittest.main()
