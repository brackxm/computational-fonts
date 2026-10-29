# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Verified LLVM -> predicated, bounded SSA -> shared Boolean circuits -> GSUB.

Runtime arguments never enter this module. Every dynamic operation produces
wires, including control, poison, memory addressing and execution-limit flags.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import time

from llvmlite import binding as llvm
from fontcircuit.gsub.circuit import Circuit, Value, ResourceLimit, emit_font


class LLVMError(ValueError):
    """Invalid LLVM or an explicitly unsupported construct."""


MAX_SOURCE_BYTES = 1 << 20
MAX_ENTRY_INPUT_BITS = (65535-3)//2  # At least two glyphs per argument bit.


@dataclass(frozen=True)
class Limits:
    max_steps: int = 16  # basic-block transitions per invocation, including entry
    max_call_depth: int = 3
    max_memory_bytes: int = 64
    max_gates: int = 24000
    max_lowered_instructions: int = 20000
    max_indirect_targets: int = 16
    max_initializers: int = 32

    def __post_init__(self):
        for name, maximum in [('max_steps', 128), ('max_call_depth', 8),
                              ('max_memory_bytes', 4096), ('max_gates', 32000),
                              ('max_lowered_instructions', 1000000), ('max_indirect_targets',256),
                              ('max_initializers',256)]:
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise LLVMError(f'{name} must be between 1 and {maximum}')


@dataclass(frozen=True)
class Scalar:
    value: Value
    poison: int = 0
    provenance: PointerByte | None = None


@dataclass(frozen=True)
class Pointer:
    object: Value  # finite allocation identity; zero is null
    offset: Value  # signed, 64-bit byte offset
    poison: int = 0


@dataclass(frozen=True)
class PointerByte:
    """Opaque pointer payload carried by one byte of a typed pointer store."""
    pointer: Pointer
    lane: Value
    valid: int = 1


def split_top(text):
    """Split canonical LLVM syntax at commas outside nested types/values."""
    parts, start, depth, quoted, escape = [], 0, 0, False, False
    for i, char in enumerate(text):
        if quoted:
            if escape: escape = False
            elif char == '\\': escape = True
            elif char == '"': quoted = False
        elif char == '"': quoted = True
        elif char in '[{(<': depth += 1
        elif char in ']})>': depth -= 1
        elif char == ',' and depth == 0:
            parts.append(text[start:i].strip()); start = i+1
    parts.append(text[start:].strip())
    return parts


def integer_width(typ):
    match = re.fullmatch(r'i(1|8|16|32|64)', str(typ))
    if not match: raise LLVMError(f'unsupported integer type: {typ}')
    return int(match[1])


def named_symbol_key(name):
    """Keep ordinary names concise; quote names that could collide with slots."""
    if re.fullmatch(r'[-a-zA-Z$._][-a-zA-Z$._0-9]*',name): return name
    escaped = ''.join(chr(b) if 32<=b<127 and b not in (34,92) else f'\\{b:02X}' for b in name.encode('utf-8'))
    return '@"'+escaped+'"'


def symbol_spelling(key):
    return key if key.startswith('@') else '@'+key


def array_length(typ):
    # llvmlite 0.46's element_count uses LLVMGetArrayLength, which truncates
    # LLVM's 64-bit array lengths to 32 bits. Read the verified type spelling.
    return int(re.match(r'\[(\d+) x ',str(typ))[1])


def aggregate_elements(typ):
    if typ.is_array:
        count = array_length(typ)
        if count>256: raise ResourceLimit('aggregate exceeds 256 elements')
        return list(typ.elements)*count
    elements = list(typ.elements)
    if len(elements)>256: raise ResourceLimit('aggregate exceeds 256 elements')
    return elements


def callee_span(text):
    tokens = r'[@%](?:"(?:[^"\\]|\\.)*"|[-a-zA-Z$._0-9]+)|"(?:[^"\\]|\\.)*"|\b(?:null|poison|undef)\b'
    for token in re.finditer(tokens,text):
        if token[0].startswith('"'): continue
        opening = re.match(r'\s*\(',text[token.end():])
        if opening: return token.start(),token.end()+opening.end()
    raise LLVMError('unsupported call syntax')


def call_parts(inst):
    text = rhs_text(inst)
    callee_start,start = callee_span(text)
    depth,quoted,escape = 1,False,False
    for end in range(start,len(text)):
        if quoted:
            if escape: escape = False
            elif text[end]=='\\': escape = True
            elif text[end]=='"': quoted = False
            continue
        if text[end]=='"': quoted = True
        elif text[end]=='(': depth += 1
        elif text[end]==')': depth -= 1
        if depth==0:
            if re.search(r'(?:^|\s)\[',text[end+1:]): raise LLVMError('call operand bundles are unsupported')
            prefix = text[:callee_start]
            if '...' in syntax_text(prefix): raise LLVMError('variadic call sites are unsupported')
            return prefix,split_top(text[start:end]) if text[start:end].strip() else []
    raise LLVMError('unsupported call syntax')


def syntax_text(text):
    """Identifiers may legally be named %volatile, %noundef, @range, etc."""
    text = re.sub(r'[%@](?:"(?:[^"\\]|\\.)*"|[-a-zA-Z$._0-9]+)','',text)
    return mask_strings(text)


def mask_strings(text):
    """Hide string contents while preserving offsets into canonical LLVM text."""
    return re.sub(r'"(?:[^"\\]|\\.)*"',lambda match:' '*len(match[0]),text)


def rhs_text(inst):
    return re.sub(r'^\s*%(?:"(?:[^"\\]|\\.)*"|[-a-zA-Z$._0-9]+)\s*=\s*','',str(inst)).strip()


def metadata_tags(inst):
    return {part.split()[0] for part in split_top(rhs_text(inst)) if part.startswith('!')}


def calling_convention(text):
    syntax = syntax_text(text)
    match = re.search(r'\b(?:cc\s+\d+|[A-Za-z_][A-Za-z_0-9]*cc|(?:amdgpu|ptx|spir|spirv|aarch64|riscv|wasm)_[A-Za-z_0-9]+)\b',syntax)
    convention = match[0] if match else 'ccc'
    convention = {'cc 0':'ccc','cc 8':'fastcc'}.get(convention,convention)
    if convention not in ('ccc','fastcc'): raise LLVMError(f'unsupported calling convention: {convention}')
    return convention


def intrinsic_kind(name):
    if re.fullmatch(r'llvm\.(?:[su](?:min|max)|ctpop|ctlz|cttz|abs|fshl|fshr)\.i(?:1|8|16|32|64)',name): return 'scalar'
    if re.fullmatch(r'llvm\.[su](?:add|sub|mul)\.with\.overflow\.i(?:1|8|16|32|64)',name): return 'overflow'
    if re.fullmatch(r'llvm\.[su](?:add|sub|shl)\.sat\.i(?:1|8|16|32|64)',name): return 'saturation'
    if re.fullmatch(r'llvm\.lifetime\.(?:start|end)\.p0',name): return 'lifetime'
    if re.fullmatch(r'llvm\.(?:memcpy(?:\.inline)?|memmove)\.p0\.p0\.i(?:32|64)',name): return 'memory'
    if re.fullmatch(r'llvm\.memset(?:\.inline)?\.p0\.i(?:32|64)',name): return 'memory'
    return None


def abi_attribute(parameter):
    """Canonical pointee spelling is part of byval/sret call compatibility."""
    syntax = mask_strings(parameter)
    match = re.search(r'\b(byval|sret)\(([^()]*)\)',syntax)
    if not match: return None
    align = re.search(r'\balign (\d+)\b',syntax)
    pointee = parameter[match.start(2):match.end(2)]
    return match[1],pointee,int(align[1]) if align and match[1]=='byval' else None


def parse(source):
    if isinstance(source, Path):
        with source.open('rb') as stream: source = stream.read(MAX_SOURCE_BYTES+1)
    if len(source)>MAX_SOURCE_BYTES or len(source.encode('utf-8') if isinstance(source,str) else source)>MAX_SOURCE_BYTES:
        raise LLVMError('source exceeds 1 MiB')
    context = llvm.create_context()  # Keep named types stable across builds.
    module = None
    try:
        if isinstance(source, bytes):
            module = (llvm.parse_bitcode(source,context=context) if source.startswith((b'BC\xc0\xde', b'\xde\xc0\x17\x0b'))
                      else llvm.parse_assembly(source.decode('utf-8'),context=context))
        else: module = llvm.parse_assembly(source,context=context)
        module.verify()
        return module
    except (RuntimeError, UnicodeError) as error:
        if module is not None: module.close()
        context.close()
        raise LLVMError(f'LLVM parsing/verification failed: {error}') from None


class Lowering:
    def __init__(self, module, limits):
        self.module, self.limits = module, limits
        self.c = Circuit(limits.max_gates)
        self.flags = {}
        self.symbol_keys = {}
        self.functions = {self.symbol_key(f):f for f in module.functions}
        self.globals = {self.symbol_key(g):g for g in module.global_variables}
        # llvmlite does not expose alias/metadata iterators. Read their canonical,
        # LLVM-verified spelling; addresses still lower through ordinary pointers.
        self.aliases = {}
        self.used_aliases = set()
        self.metadata_nodes = {}
        for line in str(module).splitlines():
            alias = re.fullmatch(r'(@(?:"(?:[^"\\]|\\.)*"|[-a-zA-Z$._0-9]+)) = ((?:[a-z_]+(?:\([^)]*\))?\s+)*)alias (.*)',line)
            if alias: self.aliases[self.global_name(alias[1])] = (alias[2],split_top(alias[3]))
            node = re.fullmatch(r'!(\d+) = (?:distinct )?!\{(.*)\}',line)
            if node: self.metadata_nodes[node[1]] = split_top(node[2]) if node[2].strip() else []
        self.function_ids = {name:0x80000000+i for i,name in enumerate(self.functions,1)}
        self.function_headers = {}
        self.function_signatures = {}
        self.abi_types = {}
        self.source_types = {}
        self.store_sizes = {}
        self.frames = [[]]  # The outer ABI adapter owns entry/result storage.
        self.address_taken = set()
        self.indirect_calls = {}
        self.call_targets = {}
        self.callee_constraints = {}
        self.initializers = []
        self.global_pointers = {}
        self.global_initializing = set()
        self.mutable_globals = set()
        self.pointer_memory_used = False
        self.memory = {}  # allocation -> list[Scalar byte]; all values are wires
        self.object_sizes = {}  # Retain bounds after frame deallocation for pointer arithmetic.
        self.readonly = set()
        self.alive = {}
        self.lifetime_allocas = set()
        self.alloca_sizes = {}
        self.next_object = 1
        self.lowered = 0
        self.validated = set()
        self.type_modules = []
        layout = module.data_layout or 'e-p:64:64-i64:64-n8:16:32:64'
        if not layout.startswith('e') or re.search(r'(?:^|-)p(?:0)?:(?!64:)', layout):
            raise LLVMError('only little-endian layouts with 64-bit default pointers are supported')
        if re.search(r'(?:^|-)(?:ni:|A[1-9]|G[1-9]|P[1-9])', layout):
            raise LLVMError('non-default/non-integral pointer address spaces are unsupported')
        for pointer_layout in re.findall(r'(?:^|-)p(?:0)?:([0-9:]+)',layout):
            fields = pointer_layout.split(':')
            if len(fields)>3 and fields[3]!='64': raise LLVMError('only 64-bit pointer indices are supported')
        self.layout = llvm.create_target_data(layout)

    def flag(self, name, condition, active=1):
        self.flags[name] = self.c.OR(self.flags.get(name, 0), self.c.AND(active, condition))

    def any_poison(self, data):
        if isinstance(data, tuple):
            out = 0
            for element in data: out = self.c.OR(out, self.any_poison(element))
            return out
        return data.poison

    def mux(self, condition, yes, no):
        c = self.c
        if condition==0: return no
        if condition==1: return yes
        if isinstance(yes, tuple): return tuple(self.mux(condition, a, b) for a,b in zip(yes,no))
        poison = c.MUX(condition, yes.poison, no.poison)
        if isinstance(yes, Pointer):
            return Pointer(c.mux(condition, yes.object, no.object),
                           c.mux(condition, yes.offset, no.offset), poison)
        provenance = None
        if yes.provenance is not None or no.provenance is not None:
            empty = PointerByte(Pointer(c.const(0,32),c.const(0,64)),c.const(0,3),0)
            a,b = yes.provenance or empty,no.provenance or empty
            provenance = PointerByte(self.mux(condition,a.pointer,b.pointer),
                                     c.mux(condition,a.lane,b.lane),c.MUX(condition,a.valid,b.valid))
        return Scalar(c.mux(condition, yes.value, no.value), poison,provenance)

    def zero(self, typ, poison=0, _budget=None, _depth=0):
        if _budget is None: _budget = [0]
        _budget[0] += 1
        if _budget[0] > 4096 or _depth > 32: raise ResourceLimit('aggregate type exceeds size/depth budget')
        if str(typ) == 'void': return ()
        if typ.is_pointer:
            if str(typ) != 'ptr': raise LLVMError('non-default pointer address space')
            return Pointer(self.c.const(0,32), self.c.const(0,64), poison)
        if typ.is_struct or typ.is_array:
            if typ.is_struct and typ.is_opaque_struct: raise LLVMError('opaque structure')
            elements = aggregate_elements(typ)
            return tuple(self.zero(t, poison, _budget, _depth+1) for t in elements)
        return Scalar(self.c.const(0,integer_width(typ)), poison)

    def operand(self, operand, env):
        if operand in env: return env[operand]
        kind = operand.value_kind.name
        if kind=='function': return self.function_pointer(self.symbol_key(operand))
        if kind == 'constant_int': return Scalar(self.c.const(operand.get_constant_value(), integer_width(operand.type)))
        if kind in ('poison_value', 'undef_value', 'constant_aggregate_zero', 'constant_pointer_null'):
            # A fixed zero is a valid refinement of undef; poison stays distinct.
            return self.zero(operand.type, int(kind == 'poison_value'))
        if kind == 'global_variable': return self.global_pointer(self.symbol_key(operand))
        if kind == 'global_alias': return self.symbol_pointer(self.symbol_key(operand))
        if kind in ('constant_expr','constant_array','constant_data_array','constant_struct'):
            return self.constant(operand.type,self.untyped(operand.type,str(operand)))
        raise LLVMError(f'unsupported operand: {str(operand).strip()} ({kind})')

    @staticmethod
    def untyped(typ, text):
        spelling = str(typ).split(' = type ',1)[0]
        if not text.startswith(spelling+' '): raise LLVMError(f'unsupported constant spelling: {text}')
        return text[len(spelling)+1:].strip()

    def constant(self, typ, text, alias_path=()):
        """Decode LLVM-verified constants; never evaluate program input values."""
        zero = self.zero(typ)
        if text in ('zeroinitializer','undef','null'): return zero
        if text == 'poison': return self.zero(typ,1)
        if typ.is_pointer:
            if text.startswith('@'):
                return self.symbol_pointer(self.global_name(text),alias_path)
            match = re.fullmatch(r'getelementptr\s+((?:inbounds(?:\s+nuw)?|nuw|nusw)\s+)?\((.*)\)',text,re.S)
            if match:
                parts = split_top(match[2])
                args = []
                for part in parts[1:]:
                    # GEP constant indices are integers and the base is a pointer.
                    match_type = re.match(r'(ptr|i\d+)\s+',part)
                    if not match_type: raise LLVMError(f'unsupported constant GEP operand: {part}')
                    t = self.typed_source(match_type[1])
                    args.append(self.constant(t,part[match_type.end():],alias_path))
                return self.gep_text('getelementptr '+(match[1] or '')+', '.join(parts),args)
            raise LLVMError(f'unsupported pointer constant: {text}')
        if typ.is_array or typ.is_struct:
            elements = aggregate_elements(typ)
            if typ.is_array and text.startswith('c"') and text.endswith('"'):
                if str(next(iter(typ.elements)))!='i8': raise LLVMError('byte-string initializer requires i8 elements')
                data = self.llvm_bytes(text[2:-1])
                if len(data)!=len(elements): raise LLVMError('byte-string initializer has wrong length')
                return tuple(Scalar(self.c.const(x,8)) for x in data)
            opening,closing = ('[',']') if typ.is_array else ('<{','}>') if typ.is_packed_struct else ('{','}')
            if not text.startswith(opening) or not text.endswith(closing):
                raise LLVMError(f'unsupported aggregate constant: {text}')
            body = text[len(opening):-len(closing)].strip()
            fields = split_top(body) if body else []
            if len(fields)!=len(elements): raise LLVMError('aggregate initializer has wrong element count')
            return tuple(self.constant(t,self.untyped(t,part)) for t,part in zip(elements,fields))
        try: number = {'true':1,'false':0}[text] if text in ('true','false') else int(text)
        except ValueError: raise LLVMError(f'unsupported integer constant: {text}') from None
        return Scalar(self.c.const(number,integer_width(typ)))

    @staticmethod
    def llvm_bytes(text):
        result = bytearray()
        i = 0
        while i<len(text):
            if text[i]=='\\':
                if text[i:i+2]=='\\\\':
                    result.append(92); i += 2
                    continue
                pair = text[i+1:i+3]
                if not re.fullmatch(r'[0-9A-Fa-f]{2}',pair): raise LLVMError('unsupported LLVM string escape')
                result.append(int(pair,16)); i += 3
            else:
                result.append(ord(text[i])); i += 1
        return bytes(result)

    @classmethod
    def global_name(cls, text):
        if re.fullmatch(r'@\d+',text): return text
        if re.fullmatch(r'@[-a-zA-Z$._0-9]+',text): return named_symbol_key(text[1:])
        if text.startswith('@"') and text.endswith('"'):
            return named_symbol_key(cls.llvm_bytes(text[2:-1]).decode('utf-8'))
        raise LLVMError(f'unsupported global reference: {text}')

    def symbol_key(self, value):
        if value not in self.symbol_keys:
            if value.name: key = named_symbol_key(value.name)
            elif value.value_kind.name=='function':
                header = next(line for line in str(value).splitlines() if line.startswith(('define ','declare ')))
                start,end = callee_span(header)
                key = self.global_name(header[start:end-1].strip())
            else:
                spelling = re.match(r'(@(?:"(?:[^"\\]|\\.)*"|[-a-zA-Z$._0-9]+))\s*=',str(value))
                if not spelling: raise LLVMError('unsupported unnamed global symbol')
                key = self.global_name(spelling[1])
            self.symbol_keys[value] = key
        return self.symbol_keys[value]

    def function_header(self, function):
        key = self.symbol_key(function)
        if key not in self.function_headers:
            self.function_headers[key] = next(line for line in str(function).splitlines() if line.startswith(('define ','declare ')))
        return self.function_headers[key]

    def function_signature(self, function):
        key = self.symbol_key(function)
        if key not in self.function_signatures:
            typ = function.global_value_type
            self.function_signatures[key] = (typ.get_function_return(),tuple(typ.get_function_parameters()),
                calling_convention(self.function_header(function)),bool(typ.is_function_vararg),
                tuple(abi_attribute(' '.join(x.decode() for x in p.attributes)) for p in function.arguments))
        return self.function_signatures[key]

    def call_signature(self, inst):
        operands = list(inst.operands)
        prefix,parameters = call_parts(inst)
        return inst.type,tuple(x.type for x in operands[:-1]),calling_convention(prefix),False,tuple(map(abi_attribute,parameters))

    def abi_type(self, attribute):
        if attribute[1] not in self.abi_types:
            typ = self.typed_source(attribute[1])
            self.zero(typ)
            size = self.layout.get_abi_size(typ)
            if not size: raise LLVMError('zero-sized byval/sret storage is unsupported')
            if size>self.limits.max_memory_bytes: raise ResourceLimit('byval/sret type exceeds byte budget')
            self.abi_types[attribute[1]] = typ
        return self.abi_types[attribute[1]]

    def function_pointer(self, name):
        function = self.functions[name]
        if function.is_declaration or name.startswith('llvm.'):
            raise LLVMError(f'external/intrinsic function addresses are unsupported: {symbol_spelling(name)}')
        self.address_taken.add(name)
        return Pointer(self.c.const(self.function_ids[name],32),self.c.const(0,64))

    def symbol_pointer(self, name, path=()):
        if name in self.aliases:
            if name in path: raise LLVMError('cyclic global aliases are unsupported')
            if len(path)>=64: raise ResourceLimit('global alias graph exceeds depth 64')
            qualifiers,parts = self.aliases[name]
            if re.search(r'\b(?:weak|weak_odr|linkonce|linkonce_odr|available_externally|thread_local)\b',qualifiers):
                raise LLVMError(f'unsupported alias linkage/storage: {symbol_spelling(name)}')
            if len(parts)!=2 or not parts[1].startswith(('ptr ','getelementptr ')):
                raise LLVMError(f'only default-space aliases without partitions are supported: {symbol_spelling(name)}')
            self.used_aliases.add(name)
            target = parts[1][4:] if parts[1].startswith('ptr ') else parts[1]
            return self.constant(self.typed_source('ptr'),target,path+(name,))
        return self.function_pointer(name) if name in self.functions else self.global_pointer(name)

    def function_symbol(self, name):
        """Resolve a statically named callback/entry, including aliases, to code."""
        if name in self.functions: return self.functions[name]
        pointer = self.symbol_pointer(name)
        identity = self.c.known(pointer.object)
        if pointer.poison==0 and self.c.known(pointer.offset)==0:
            for target,code in self.function_ids.items():
                if code==identity: return self.functions[target]
        raise LLVMError(f'symbol is not a defined function base: {symbol_spelling(name)}')

    def callee_constraint(self, inst):
        attachment = next(part for part in split_top(rhs_text(inst)) if part.startswith('!callees '))
        match = re.fullmatch(r'!callees !(\d+)',attachment)
        if not match or match[1] not in self.metadata_nodes: raise LLVMError('unsupported !callees metadata node')
        names = set()
        for item in self.metadata_nodes[match[1]]:
            if not item.startswith('ptr @'): raise LLVMError('!callees requires defined function references')
            function = self.function_symbol(self.global_name(item[4:]))
            name = self.symbol_key(function)
            self.function_pointer(name)
            names.add(name)
        return names

    def global_definition(self, value):
        text = re.sub(r'^@(?:"(?:[^"\\]|\\.)*"|[-a-zA-Z$._0-9]+)\s*=\s*','',str(value))
        match = re.search(r'\b(constant|global)\s+(.*)',text,re.S)
        if value.is_declaration or not match: raise LLVMError(f'only defined globals are supported: {symbol_spelling(self.symbol_key(value))}')
        return text,match,split_top(self.untyped(value.global_value_type,match[2]))[0]

    def add_initializer(self, name, priority, source):
        function = self.function_symbol(name)
        result,args,convention,varargs,_ = self.function_signature(function)
        if function.is_declaration or str(result)!='void' or args or convention!='ccc' or varargs:
            raise LLVMError('constructors must be defined void() functions using ccc')
        self.initializers.append({'function':self.symbol_key(function),'priority':priority,'source':source})
        if len(self.initializers)>self.limits.max_initializers:
            raise ResourceLimit(f'max_initializers={self.limits.max_initializers} exceeded')

    def discover_initializers(self):
        for name,value in self.globals.items():
            text = str(value)
            # A section is a top-level attribute, never text inside the quoted
            # global name or initializer. split_top preserves quoted commas.
            section = ''
            for clause in split_top(text)[1:]:
                attribute = re.fullmatch(r'section "((?:[^"\\]|\\.)*)"',clause)
                if attribute:
                    try: section = self.llvm_bytes(attribute[1]).decode('utf-8')
                    except UnicodeError: raise LLVMError('unsupported section-name encoding') from None
            macho = [part.strip() for part in section.split(',')]
            known_macho = len(macho)>=2 and macho[0] in ('__DATA','__DATA_CONST') and macho[1] in ('__mod_init_func','__mod_term_func')
            extra_startup_flags = any(part in ('mod_init_funcs','mod_term_funcs','init_func_offsets') for part in macho[2:])
            if extra_startup_flags or (known_macho and section not in (
                    '__DATA,__mod_init_func','__DATA_CONST,__mod_init_func',
                    '__DATA,__mod_term_func','__DATA_CONST,__mod_term_func')):
                raise LLVMError(f'unsupported module initialization section: {section}')
            if section.startswith(('.ctors','.dtors','.preinit_array','.CRT$X')) or '__init_offsets' in section:
                raise LLVMError(f'unsupported module initialization section: {section}')
            if name=='llvm.global_dtors' or section in ('__DATA,__mod_term_func','__DATA_CONST,__mod_term_func') or section.startswith('.fini_array'):
                typ = value.global_value_type
                if not typ.is_array or array_length(typ): raise LLVMError('module destructors are unsupported')
                continue
            if name=='llvm.global_ctors':
                _,_,initializer = self.global_definition(value)
                typ = value.global_value_type
                if not typ.is_array: raise LLVMError('unsupported constructor array')
                if not array_length(typ): continue
                element = next(iter(typ.elements))
                fields = list(element.elements)
                if len(fields)!=3 or str(fields[0])!='i32' or any(str(t)!='ptr' for t in fields[1:]):
                    raise LLVMError('unsupported constructor entry type')
                if not initializer.startswith('[') or not initializer.endswith(']'): raise LLVMError('unsupported constructor initializer')
                for entry in split_top(initializer[1:-1]):
                    body = self.untyped(element,entry)
                    if not body.startswith('{') or not body.endswith('}'): raise LLVMError('unsupported constructor entry')
                    pieces = split_top(body[1:-1])
                    raw_priority = self.untyped(fields[0],pieces[0])
                    if not re.fullmatch(r'-?\d+',raw_priority): raise LLVMError('constructor priorities must be literal integers')
                    priority = int(raw_priority)&0xffffffff
                    callback = self.untyped(fields[1],pieces[1])
                    associated = self.untyped(fields[2],pieces[2])
                    if associated!='null':
                        symbol = self.global_name(associated)
                        if symbol in self.aliases:
                            pointer = self.symbol_pointer(symbol)
                            identity = self.c.known(pointer.object)
                            symbol = next((n for n,p in self.global_pointers.items() if self.c.known(p.object)==identity),
                                          next((n for n,code in self.function_ids.items() if code==identity),symbol))
                        definition = self.globals.get(symbol) or self.functions.get(symbol)
                        if definition is None or definition.is_declaration or definition.linkage.name not in ('external','internal','private'):
                            raise LLVMError('constructor associated symbols must be defined and retained in this module')
                    self.add_initializer(self.global_name(callback),priority,name)
            elif section in ('__DATA,__mod_init_func','__DATA_CONST,__mod_init_func') or section=='.init_array' or section.startswith('.init_array.'):
                definition,qualifier,initializer = self.global_definition(value)
                if qualifier[1]!='constant' or re.search(r'\b(?:externally_initialized|thread_local|addrspace)\b',definition[:qualifier.start()]):
                    raise LLVMError('initializer sections require immutable, default-space storage')
                typ = value.global_value_type
                priority = 65535
                if section.startswith('.init_array.'):
                    suffix = section[len('.init_array.'):]
                    if not suffix.isdecimal() or int(suffix)>0xffffffff: raise LLVMError('unsupported initializer section priority')
                    priority = int(suffix)
                if typ.is_pointer: callbacks = [initializer]
                elif typ.is_array and str(next(iter(typ.elements)))=='ptr':
                    if not array_length(typ): continue
                    if not initializer.startswith('['): raise LLVMError('unsupported initializer pointer array')
                    callbacks = [self.untyped(next(iter(typ.elements)),x) for x in split_top(initializer[1:-1])]
                else: raise LLVMError('initializer sections require function-pointer cells or arrays')
                for callback in callbacks: self.add_initializer(self.global_name(callback),priority,section)
        self.initializers.sort(key=lambda item:item['priority'])

    def prepare(self, entry):
        self.discover_initializers()
        for item in self.initializers: self.check_function(self.functions[item['function']])
        self.check_function(entry)
        # Address-taken functions and indirect call sites can introduce each
        # other through tables, parameters, globals and callbacks. Reach closure
        # before emitting any execution stages.
        while True:
            before = len(self.validated),len(self.address_taken),len(self.indirect_calls)
            for inst,signature in list(self.indirect_calls.items()):
                candidates = [self.functions[name] for name in self.functions if name in self.address_taken
                              and self.function_signature(self.functions[name])==signature
                              and (inst not in self.callee_constraints or name in self.callee_constraints[inst])]
                if len(candidates)>self.limits.max_indirect_targets:
                    raise ResourceLimit(f'max_indirect_targets={self.limits.max_indirect_targets} exceeded')
                self.call_targets[inst] = candidates
                for candidate in candidates: self.check_function(candidate)
            if before==(len(self.validated),len(self.address_taken),len(self.indirect_calls)): break

    def global_pointer(self, name):
        if name in ('llvm.global_ctors','llvm.global_dtors','llvm.used','llvm.compiler.used'):
            raise LLVMError('LLVM linker metadata globals cannot be used as runtime storage')
        if name in self.global_pointers: return self.global_pointers[name]
        if len(self.global_initializing)>=64: raise ResourceLimit('global initializer graph exceeds depth 64')
        if name not in self.globals: raise LLVMError(f'unsupported global/function reference: {symbol_spelling(name)}')
        global_value = self.globals[name]
        text = re.sub(r'^@(?:"(?:[^"\\]|\\.)*"|[-a-zA-Z$._0-9]+)\s*=\s*','',str(global_value))
        match = re.search(r'\b(constant|global)\s+(.*)',text,re.S)
        if global_value.is_declaration or not match:
            raise LLVMError(f'only defined globals are supported: {symbol_spelling(name)}')
        if re.search(r'\b(?:externally_initialized|thread_local|addrspace)\b',text[:match.start()]):
            raise LLVMError(f'unsupported global storage: {symbol_spelling(name)}')
        if any(part.startswith('!absolute_symbol') for part in split_top(text)):
            raise LLVMError(f'unsupported absolute-address global: {symbol_spelling(name)}')
        typ = global_value.global_value_type
        self.zero(typ)
        size = self.layout.get_abi_size(typ)
        self.reserve_memory(size)
        identity = self.next_object; self.next_object += 1
        self.memory[identity] = [Scalar(self.c.const(0,8)) for _ in range(size)]
        self.object_sizes[identity] = size
        pointer = Pointer(self.c.const(identity,32),self.c.const(0,64))
        # Install the object before following relocations, including self-links
        # and forward references in cyclic global initializer graphs.
        self.global_pointers[name] = pointer
        self.global_initializing.add(name)
        if match[1]=='constant': self.readonly.add(identity)
        else: self.mutable_globals.add(name)
        initializer = split_top(self.untyped(typ,match[2]))[0]
        data = self.constant(typ,initializer)
        packed = self.pack(data,typ)
        for i,cell in enumerate(packed):
            if cell is not None: self.memory[identity][i] = cell
        self.global_initializing.remove(name)
        return pointer

    def reserve_memory(self, size):
        if size < 1: raise LLVMError('zero-sized allocations/globals are unsupported')
        if sum(len(x) for x in self.memory.values())+size > self.limits.max_memory_bytes:
            raise ResourceLimit(f'allocations exceed max_memory_bytes={self.limits.max_memory_bytes}')

    def resize(self, value, width, signed=False):
        bits = value.bits
        return Value(bits[:width] + ((bits[-1] if signed else 0),)*max(0,width-len(bits)))

    def typed_source(self, text):
        """Read GEP/alloca's source element type via LLVM, including named structs."""
        if text in self.source_types: return self.source_types[text]
        definitions = '\n'.join(str(t) for t in self.module.struct_types if t.name)
        try:
            module = llvm.parse_assembly(definitions + '\n@__llvmfont_type = external global ' + text,context=llvm.create_context())
            self.type_modules.append(module)
            typ = module.get_global_variable('__llvmfont_type').global_value_type
            self.source_types[text] = typ
            return typ
        except RuntimeError as error: raise LLVMError(f'unsupported memory type {text}: {error}') from None

    def check_function(self, function):
        key = self.symbol_key(function)
        if key in self.validated: return
        self.validated.add(key)
        if function.is_declaration: raise LLVMError(f'external function: {symbol_spelling(key)}')
        if function.global_value_type.is_function_vararg: raise LLVMError('variadic functions are unsupported')
        header = self.function_header(function).rsplit('{',1)[0]
        header = syntax_text(header)
        if re.search(r'\b(?:personality|gc|prefix|prologue|byref|inalloca|preallocated|swiftself|swifterror|inreg|nest|nofpclass|alignstack)\b', header):
            raise LLVMError(f'unsupported ABI/semantic attribute on {symbol_spelling(key)}')
        calling_convention(header)
        for arg in function.arguments:
            self.zero(arg.type)
            attribute = abi_attribute(' '.join(x.decode() for x in arg.attributes))
            if attribute: self.abi_type(attribute)
        result_type = function.global_value_type.get_function_return()
        self.zero(result_type)
        blocks = list(function.blocks)
        instruction_map = {inst:inst for block in blocks for inst in block.instructions}
        if len(blocks)>256: raise ResourceLimit('function exceeds 256 basic blocks')
        allowed = {'add','sub','mul','udiv','sdiv','urem','srem','and','or','xor','shl','lshr','ashr',
                   'icmp','trunc','zext','sext','select','freeze','phi','br','switch','ret','unreachable',
                   'call','alloca','load','store','getelementptr','insertvalue','extractvalue'}
        for block in blocks:
            for inst in block.instructions:
                text = str(inst)
                syntax = syntax_text(text)
                if inst.opcode not in allowed: raise LLVMError(f'unsupported instruction: {text.strip()}')
                operands = list(inst.operands)
                for index,operand in enumerate(operands):
                    if operand.value_kind.name=='function' and not (inst.opcode=='call' and index==len(operands)-1):
                        self.function_pointer(self.symbol_key(operand))
                    if operand.value_kind.name in {'global_variable','global_alias','constant_expr','constant_array','constant_data_array','constant_struct'}:
                        self.operand(operand,{})
                        continue
                    if operand.value_kind.name not in {'argument','instruction','constant_int','poison_value',
                            'undef_value','constant_aggregate_zero','constant_pointer_null','basic_block','function'}:
                        raise LLVMError(f'unsupported operand: {str(operand).strip()} ({operand.value_kind.name})')
                if re.search(r'\b(?:volatile|atomic|musttail|inalloca|swifterror|addrspace|nusw|samesign)\b',syntax):
                    raise LLVMError(f'unsupported instruction modifier: {text.strip()}')
                tags = metadata_tags(inst)
                if tags & {'!range','!dereferenceable','!dereferenceable_or_null','!align','!absolute_symbol'} or (
                        tags & {'!noundef','!nonnull'} and inst.opcode!='load') or ('!callees' in tags and inst.opcode!='call'):
                    raise LLVMError(f'unsupported semantic metadata: {text.strip()}')
                if inst.opcode == 'alloca' and block != blocks[0]:
                    raise LLVMError('alloca must be in the entry block (no repeated allocations)')
                if inst.opcode == 'alloca' and list(inst.operands)[0].value_kind.name != 'constant_int':
                    raise LLVMError('dynamic alloca is unsupported')
                if inst.opcode == 'getelementptr' and re.search(r'\bnuw\b',syntax) and 'inbounds' not in syntax:
                    raise LLVMError('GEP nuw requires inbounds in this subset')
                if inst.opcode == 'br' and any(x == blocks[0] for x in inst.operands):
                    raise LLVMError('branches to entry are unsupported')
                if inst.opcode == 'call':
                    callee = operands[-1]
                    callee_name = self.symbol_key(callee) if callee.value_kind.name=='function' else ''
                    prefix,parameters = call_parts(inst)
                    direct = callee.value_kind.name=='function'
                    kind = intrinsic_kind(callee_name) if direct else None
                    prohibited = r'\b(?:byref|inalloca|preallocated|inreg|nest|swiftself|swifterror|nofpclass)\b'
                    if re.search(prohibited,syntax_text(prefix+' '+ ' '.join(parameters))):
                        raise LLVMError(f'unsupported call attribute: {text.strip()}')
                    convention = calling_convention(prefix)
                    for parameter in parameters:
                        attribute = abi_attribute(parameter)
                        if attribute: self.abi_type(attribute)
                    if '!callees' in tags:
                        if direct: raise LLVMError('!callees is supported only on indirect calls')
                        self.callee_constraints[inst] = self.callee_constraint(inst)
                    if not direct:
                        self.indirect_calls[inst] = self.call_signature(inst)
                        if str(inst.type)!='void': self.zero(inst.type)
                        continue
                    definition = self.functions.get(callee_name)
                    declaration = self.function_header(definition)
                    declaration = declaration[:callee_span(declaration)[0]]
                    if convention!=calling_convention(declaration): raise LLVMError('call/definition calling convention mismatch')
                    if callee_name.startswith('llvm.'):
                        if kind is None:
                            raise LLVMError(f'unsupported intrinsic: @{callee_name}')
                        if kind=='memory':
                            volatile = operands[-2]
                            if volatile.value_kind.name!='constant_int' or volatile.get_constant_value()!=0:
                                raise LLVMError('volatile memory intrinsics are unsupported')
                        if kind=='lifetime':
                            root = self.lifetime_root(operands[1],instruction_map)
                            if root is None: raise LLVMError('lifetime markers require a local alloca base (or all-zero GEP)')
                            size = operands[0]
                            if size.value_kind.name!='constant_int' or size.get_constant_value() not in (
                                    (1<<64)-1,self.allocation_size(root)):
                                raise LLVMError('lifetime markers require the complete allocation size or -1')
                            if '.start.' in callee_name: self.lifetime_allocas.add(root)
                    else:
                        if self.function_signature(definition)!=self.call_signature(inst):
                            raise LLVMError('call/definition signature mismatch')
                        self.check_function(self.functions[callee_name])
                if str(inst.type) != 'void': self.zero(inst.type)

    def lifetime_root(self, value, instructions):
        while (inst := instructions.get(value)) is not None:
            if inst.opcode=='alloca': return inst
            if inst.opcode!='getelementptr': return None
            operands = list(inst.operands)
            if not all(x.value_kind.name=='constant_int' and x.get_constant_value()==0 for x in operands[1:]): return None
            value = operands[0]
        return None

    def allocation_size(self, inst):
        if inst not in self.alloca_sizes:
            parts = split_top(rhs_text(inst)[len('alloca '):])
            typ = self.typed_source(parts[0])
            count = list(inst.operands)[0]
            if count.value_kind.name!='constant_int': raise LLVMError('dynamic alloca is unsupported')
            self.alloca_sizes[inst] = self.layout.get_abi_size(typ)*count.get_constant_value()
        return self.alloca_sizes[inst]

    def binary(self, inst, a, b, active):
        c, op = self.c, inst.opcode
        x, y = a.value, b.value
        width = x.width
        poison = c.OR(a.poison,b.poison)
        flags = set(syntax_text(str(inst)).split('=',1)[1].strip().split()[1:]) & {'nsw','nuw','exact'}
        if op in ('add','sub','mul'):
            compute = c.mul if op == 'mul' else lambda x,y: c.add(x,y,op == 'sub')
            result = compute(x,y)
            for flag in sorted(flags):
                wide = width*2 if op == 'mul' else width+1
                extended = compute(self.resize(x,wide,flag=='nsw'),self.resize(y,wide,flag=='nsw'))
                overflow = c.NOT(c.eq(extended,self.resize(result,wide,flag=='nsw')))
                poison = c.OR(poison,overflow)
        elif op in ('and','or','xor'):
            result = c.bitwise(op,x,y)
            if op=='or' and re.search(r'\bor disjoint\b',syntax_text(str(inst))):
                poison = c.OR(poison,c.nonzero(c.bitwise('and',x,y)))
        elif op in ('shl','lshr','ashr'):
            invalid = c.NOT(c.lt(y,c.const(width,width))) if width > 1 else c.nonzero(y)
            poison = c.OR(poison,invalid)
            result = c.shift({'shl':'shl','lshr':'shr_u','ashr':'shr_s'}[op],x,y)
            if 'exact' in flags:
                restored = c.shift('shl',result,y)
                poison = c.OR(poison,c.NOT(c.eq(restored,x)))
            for flag in sorted(flags & {'nsw','nuw'}):
                restored = c.shift('shr_s' if flag=='nsw' else 'shr_u',result,y)
                poison = c.OR(poison,c.NOT(c.eq(restored,x)))
        else:
            zero = c.const(0,width)
            bad = c.OR(b.poison,c.eq(y,zero))
            signed = op.startswith('s')
            if signed:
                bad = c.OR(bad,c.AND(c.eq(x,c.const(1<<(width-1),width)),c.eq(y,c.const(-1,width))))
                ax = c.add_subtract(zero,x,x.bits[-1])
                ay = c.add_subtract(zero,y,y.bits[-1])
                q,r = c.unsigned_divmod(ax,ay)
                q = c.add_subtract(zero,q,c.XOR(x.bits[-1],y.bits[-1]))
                r = c.add_subtract(zero,r,x.bits[-1])
            else: q,r = c.unsigned_divmod(x,y)
            self.flag('trap.undefined_behavior',bad,active)
            if 'exact' in flags: poison = c.OR(poison,c.nonzero(r))
            result = r if op.endswith('rem') else q
        return Scalar(result,poison)

    def intrinsic(self, name, args, active):
        c = self.c
        kind = intrinsic_kind(name)
        if kind=='memory': return self.memory_intrinsic(name,args,active)
        if kind=='lifetime': return self.lifetime(name,args,active)
        if kind=='saturation':
            a,b = args
            op = name.split('.')[1]
            signed = op[0]=='s'
            width = a.value.width
            poison = c.OR(a.poison,b.poison)
            if op[1:]=='shl':
                result = c.shift('shl',a.value,b.value)
                back = c.shift('shr_s' if signed else 'shr_u',result,b.value)
                overflow = c.NOT(c.eq(back,a.value))
                invalid = c.NOT(c.lt(b.value,c.const(width,width)))
                poison = c.OR(poison,invalid)
            else:
                result,flag = self.intrinsic(f'llvm.{op}.with.overflow.i{width}',args,active)
                result,overflow = result.value,flag.value.bits[0]
            if signed:
                clamp = c.mux(a.value.bits[-1],c.const(1<<(width-1),width),c.const((1<<(width-1))-1,width))
            else: clamp = c.const(0 if op=='usub' else (1<<width)-1,width)
            return Scalar(c.mux(overflow,clamp,result),poison)
        if kind=='overflow':
            a,b = args
            signed = name.split('.')[1][0]=='s'
            op = name.split('.')[1][1:]
            width = a.value.width
            wide = width*2 if op=='mul' else width+1
            x,y = self.resize(a.value,wide,signed),self.resize(b.value,wide,signed)
            extended = c.mul(x,y) if op=='mul' else c.add(x,y,op=='sub')
            result = Value(extended.bits[:width])
            overflow = c.NOT(c.eq(extended,self.resize(result,wide,signed)))
            poison = c.OR(a.poison,b.poison)
            return Scalar(result,poison),Scalar(Value((overflow,)),poison)
        op = name.split('.')[1]
        a = args[0]
        poison = self.any_poison(a)
        if op in ('fshl','fshr'):
            b,shift = args[1:]
            width = a.value.width
            distance = Value(shift.value.bits[:width.bit_length()-1]+(0,)*(width-width.bit_length()+1))
            negative = c.add(c.const(0,width),distance,True)
            if a.value.bits==b.value.bits:
                value = c.shift('rotl' if op=='fshl' else 'rotr',a.value,distance)
            else:
                left = c.shift('shl',a.value,distance if op=='fshl' else negative)
                right = c.shift('shr_u',b.value,negative if op=='fshl' else distance)
                value = c.bitwise('or',left,right)
                value = c.mux(c.nonzero(distance),value,a.value if op=='fshl' else b.value)
            return Scalar(value,c.OR(poison,c.OR(b.poison,shift.poison)))
        if op in ('smin','smax','umin','umax'):
            b = args[1]
            take = c.lt(a.value,b.value,op[0]=='s')
            if op.endswith('max'): take = c.NOT(take)
            return Scalar(c.mux(take,a.value,b.value),c.OR(poison,b.poison))
        if op == 'abs':
            value = c.add_subtract(c.const(0,a.value.width),a.value,a.value.bits[-1])
            bad = c.AND(args[1].value.bits[0],c.eq(a.value,c.const(1<<(a.value.width-1),a.value.width)))
            return Scalar(value,c.OR(c.OR(poison,args[1].poison),bad))
        value = c.count({'ctpop':'popcnt','ctlz':'clz','cttz':'ctz'}[op],a.value)
        if op != 'ctpop':
            poison = c.OR(c.OR(poison,args[1].poison),c.AND(args[1].value.bits[0],c.NOT(c.nonzero(a.value))))
        return Scalar(value,poison)

    def allocate(self, inst):
        return self.allocate_bytes(self.allocation_size(inst),int(inst not in self.lifetime_allocas))

    def allocate_bytes(self, size, alive=1):
        self.reserve_memory(size)
        identity = self.next_object; self.next_object += 1
        self.memory[identity] = [Scalar(self.c.const(0,8)) for _ in range(size)]
        self.object_sizes[identity] = size
        self.alive[identity] = alive
        return Pointer(self.c.const(identity,32), self.c.const(0,64))

    def sret_contract(self, pointer, typ, attributes, active):
        c = self.c
        valid = self.valid_span(pointer,c.const(self.store_size(typ),64))
        alignment = re.search(r'\balign (\d+)\b',attributes)
        align = int(alignment[1]) if alignment else self.layout.get_abi_alignment(typ)
        valid = c.AND(valid,c.NOT(c.nonzero(Value(pointer.offset.bits[:align.bit_length()-1]))))
        for identity in self.readonly:
            valid = c.AND(valid,c.NOT(c.eq(pointer.object,c.const(identity,32))))
        self.flag('trap.undefined_behavior',c.OR(pointer.poison,c.NOT(valid)),active)

    def entry_arguments(self, entry):
        """Expose integer leaves; materialize ABI-only pointers in glyph RAM."""
        types,names,args,adapter = [],[],[],{}
        result_buffer = None
        input_bits = 0
        def scalar(typ, name):
            nonlocal input_bits
            width = integer_width(typ)
            input_bits += width
            if input_bits>MAX_ENTRY_INPUT_BITS:
                raise ResourceLimit('entry arguments exceed OpenType glyph-count capacity')
            value = Scalar(self.c.argument(len(types),width))
            types.append(f'i{width}'); names.append(name)
            return value
        def fields(recurse, typ, name):
            if typ.is_struct or typ.is_array:
                elements = aggregate_elements(typ)
                return tuple(recurse(recurse,t,f'{name}.{i}') for i,t in enumerate(elements))
            return scalar(typ,name)
        for i,parameter in enumerate(entry.arguments):
            name = parameter.name or str(i)
            attribute = abi_attribute(' '.join(x.decode() for x in parameter.attributes))
            if attribute is None:
                args.append(scalar(parameter.type,name))
                continue
            typ = self.abi_type(attribute)
            # The external register ABI cannot supply or decode pointers.
            def integers_only(t):
                if t.is_struct or t.is_array:
                    for element in t.elements: integers_only(element)
                else: integer_width(t)
            integers_only(typ)
            pointer = self.allocate_bytes(self.layout.get_abi_size(typ))
            self.frames[0].append(self.c.known(pointer.object))
            args.append(pointer)
            description = {'parameter':i,'name':name,'type':attribute[1],'bytes':self.layout.get_abi_size(typ)}
            if attribute[0]=='sret':
                result_buffer = pointer,typ
                adapter['sret'] = description
            else:
                start = len(types)
                value = fields(fields,typ,name)
                self.memory_access(pointer,typ,1,value)
                description['fields'] = names[start:]
                adapter.setdefault('byval',[]).append(description)
        return args,types,names,result_buffer,adapter

    def valid_span(self, pointer, length):
        c = self.c
        end = c.add(self.resize(pointer.offset,65),self.resize(length,65))
        valid = 0
        for identity,cells in self.memory.items():
            hit = c.AND(c.eq(pointer.object,c.const(identity,32)),
                        c.NOT(c.lt(c.const(len(cells),65),end)))
            valid = c.OR(valid,c.AND(hit,self.alive.get(identity,1)))
        return valid

    def call_argument(self, data, parameter, active):
        c = self.c
        parameter = syntax_text(parameter)
        range_attr = re.search(r'\brange\(i(1|8|16|32|64) (-?\d+), (-?\d+)\)',parameter)
        if range_attr:
            if not isinstance(data,Scalar) or data.value.width!=int(range_attr[1]): raise LLVMError('unsupported range attribute')
            width = data.value.width
            lo,hi = (int(x)&((1<<width)-1) for x in range_attr.groups()[1:])
            ge = c.NOT(c.lt(data.value,c.const(lo,width)))
            lt = c.lt(data.value,c.const(hi,width))
            valid = c.AND(ge,lt) if lo<hi else c.OR(ge,lt) if lo>hi else 0
            data = self.add_poison(data,c.NOT(valid))
        if isinstance(data,Pointer):
            bad = 0
            null = c.AND(c.eq(data.object,c.const(0,32)),c.eq(data.offset,c.const(0,64)))
            if re.search(r'\bnonnull\b',parameter): bad = c.OR(bad,null)
            align = re.search(r'\balign (\d+)\b',parameter)
            if align:
                bits = int(align[1]).bit_length()-1
                bad = c.OR(bad,c.nonzero(Value(data.offset.bits[:bits])))
            data = self.add_poison(data,bad)
            deref = re.search(r'\b(dereferenceable(?:_or_null)?)\((\d+)\)',parameter)
            if deref:
                valid = self.valid_span(data,c.const(int(deref[2]),64))
                if deref[1].endswith('_or_null'): valid = c.OR(valid,null)
                self.flag('trap.undefined_behavior',c.OR(data.poison,c.NOT(valid)),active)
        if re.search(r'\bnoundef\b',parameter): self.flag('trap.undefined_behavior',self.any_poison(data),active)
        return data

    def lifetime(self, name, args, active):
        c = self.c
        pointer = args[1]
        identity = c.known(pointer.object)
        if identity not in self.alive or c.known(pointer.offset)!=0:
            raise LLVMError('lifetime markers require a proven local allocation base')
        if pointer.poison!=0: raise LLVMError('poison lifetime pointers are unsupported')
        alive = self.alive[identity]
        if '.start.' in name:
            # LLVM 20: restarting a dead object gives undef bytes; starting an
            # already-live object poisons its contents. Refine undef to zero.
            self.memory[identity] = [self.mux(active,Scalar(c.const(0,8),alive),cell)
                                     for cell in self.memory[identity]]
            self.alive[identity] = c.MUX(active,1,alive)
        else: self.alive[identity] = c.MUX(active,0,alive)
        return ()

    def memory_intrinsic(self, name, args, active):
        c = self.c
        dest,source,length,_ = args
        known = c.known(length.value)
        capacity = max((len(cells) for cells in self.memory.values()),default=0)
        count = min(known,capacity) if known is not None else capacity
        self.lowered += count
        if self.lowered > self.limits.max_lowered_instructions: raise ResourceLimit('max_lowered_instructions exceeded')
        # A count outside every allocated object is an invalid access, even if
        # only its bounded prefix can be expanded into the circuit.
        self.flag('trap.undefined_behavior',length.poison,active)
        self.flag('trap.invalid_memory',c.lt(c.const(capacity,length.value.width),length.value),active)
        nonempty = c.nonzero(length.value)
        access = c.AND(active,nonempty)
        is_set = name.startswith('llvm.memset.')
        self.flag('trap.invalid_memory',c.OR(dest.poison,c.NOT(self.valid_span(dest,length.value))),access)
        if not is_set:
            self.flag('trap.invalid_memory',c.OR(source.poison,c.NOT(self.valid_span(source,length.value))),access)
        if name.startswith('llvm.memcpy.'):
            same = c.eq(dest.object,source.object)
            start_d,start_s = self.resize(dest.offset,65),self.resize(source.offset,65)
            size = self.resize(length.value,65)
            overlap = c.AND(c.lt(start_d,c.add(start_s,size)),c.lt(start_s,c.add(start_d,size)))
            if '.inline.' not in name: overlap = c.AND(overlap,c.NOT(c.eq(dest.offset,source.offset)))
            self.flag('trap.memcpy_overlap',c.AND(same,overlap),access)
        byte_type = self.typed_source('i8')
        copied = []
        for i in range(count):
            enabled = c.AND(active,c.lt(c.const(i,length.value.width),length.value))
            if is_set: value = source
            else:
                ptr = Pointer(source.object,c.add(source.offset,c.const(i,64)),source.poison)
                value = self.memory_access(ptr,byte_type,enabled,raw=True)
            copied.append((enabled,value))
        # Snapshot the complete source before any write; memmove may overlap.
        for i,(enabled,value) in enumerate(copied):
            ptr = Pointer(dest.object,c.add(dest.offset,c.const(i,64)),dest.poison)
            self.memory_access(ptr,byte_type,enabled,value,raw=True)
        return ()

    def store_size(self, typ):
        """LLVM store span, distinct from allocation/GEP stride including padding.

        llvmlite exposes allocation size but not LLVMStoreSizeOfType. For the
        fixed integer/pointer/aggregate subset, reconstruct StructLayout's size
        from LLVM's field offsets, allocation sizes and field alignments.
        """
        if typ not in self.store_sizes:
            if typ.is_pointer:
                if str(typ)!='ptr': raise LLVMError('non-default pointer address space')
                size = 8
            elif typ.is_array:
                size = array_length(typ)*self.layout.get_abi_size(next(iter(typ.elements)))
            elif typ.is_struct:
                elements = aggregate_elements(typ)
                if elements:
                    end = self.layout.get_element_offset(typ,len(elements)-1)+self.layout.get_abi_size(elements[-1])
                    align = 1 if typ.is_packed_struct else max(self.layout.get_abi_alignment(t) for t in elements)
                    size = (end+align-1)//align*align
                else: size = 0
            else: size = (integer_width(typ)+7)//8
            self.store_sizes[typ] = size
        return self.store_sizes[typ]

    def memory_access(self, pointer, typ, active, data=None, alignment=1, *, raw=False):
        """Finite byte-addressed RAM: predicates select each candidate byte."""
        c = self.c
        size = self.store_size(typ)
        if size > self.limits.max_memory_bytes: raise ResourceLimit('memory access exceeds byte budget')
        valid = 0
        loaded = [Scalar(c.const(0,8)) for _ in range(size)]
        stored = ([data] if raw else self.pack(data,typ)) if data is not None else None
        for identity, cells in self.memory.items():
            same = c.eq(pointer.object,c.const(identity,32))
            if same == 0: continue
            for start in range(0,len(cells)-size+1):
                if start % alignment: continue
                hit = c.AND(same,c.eq(pointer.offset,c.const(start,64)))
                hit = c.AND(hit,self.alive.get(identity,1))
                valid = c.OR(valid,hit)
                if hit == 0: continue
                for i in range(size):
                    if stored is None: loaded[i] = self.mux(hit,cells[start+i],loaded[i])
                    elif stored[i] is not None:
                        if identity in self.readonly:
                            self.flag('trap.readonly_memory',hit,active)
                        else: cells[start+i] = self.mux(c.AND(active,hit),stored[i],cells[start+i])
        self.flag('trap.invalid_memory',c.OR(pointer.poison,c.NOT(valid)),active)
        if stored is not None: return ()
        return loaded[0] if raw else self.unpack(loaded,typ,active)

    def pack(self, data, typ):
        c = self.c
        size = self.store_size(typ)
        if typ.is_pointer:
            self.pointer_memory_used = True
            # Pointer bytes are opaque payloads: provenance carries the actual
            # allocation and offset. Scalar reinterpretation is diagnosed.
            nonnull = c.OR(c.nonzero(data.object),c.nonzero(data.offset))
            bits = (nonnull,)+(0,)*63
            return [Scalar(Value(bits[i*8:(i+1)*8]),data.poison,
                           PointerByte(data,c.const(i,3))) for i in range(8)]
        if typ.is_struct or typ.is_array:
            out = [None]*size
            elements = aggregate_elements(typ)
            for i,(element,t) in enumerate(zip(data,elements)):
                offset = self.layout.get_element_offset(typ,i) if typ.is_struct else self.layout.get_abi_size(t)*i
                packed = self.pack(element,t)
                out[offset:offset+len(packed)] = packed
            return out
        width = integer_width(typ)
        bits = data.value.bits+(0,)*(size*8-width)
        return [Scalar(Value(bits[i*8:(i+1)*8]),data.poison) for i in range(size)]

    def unpack(self, cells, typ, active=1):
        c = self.c
        if typ.is_struct or typ.is_array:
            elements = aggregate_elements(typ)
            out = []
            for i,t in enumerate(elements):
                offset = self.layout.get_element_offset(typ,i) if typ.is_struct else self.layout.get_abi_size(t)*i
                out.append(self.unpack(cells[offset:offset+self.store_size(t)],t,active))
            return tuple(out)
        bits = Value(tuple(bit for cell in cells for bit in cell.value.bits))
        poison = self.any_poison(tuple(cells))
        any_tag = 0
        for cell in cells:
            if cell.provenance is not None: any_tag = c.OR(any_tag,cell.provenance.valid)
        if typ.is_pointer:
            self.pointer_memory_used = True
            empty = PointerByte(Pointer(c.const(0,32),c.const(0,64)),c.const(0,3),0)
            tags = [cell.provenance or empty for cell in cells]
            pointer = tags[0].pointer
            complete = 1
            for i,tag in enumerate(tags):
                complete = c.AND(complete,tag.valid)
                complete = c.AND(complete,c.eq(tag.lane,c.const(i,3)))
                complete = c.AND(complete,c.eq(tag.pointer.object,pointer.object))
                complete = c.AND(complete,c.eq(tag.pointer.offset,pointer.offset))
            # Fully untagged zero bytes represent null. Mixed/partial pointer
            # writes must not accidentally become null merely due to payload bits.
            zero = c.AND(c.NOT(any_tag),c.NOT(c.nonzero(bits)))
            invalid = c.AND(c.NOT(c.OR(complete,zero)),c.NOT(poison))
            self.flag('trap.pointer_representation',invalid,active)
            return Pointer(c.mux(complete,pointer.object,c.const(0,32)),
                           c.mux(complete,pointer.offset,c.const(0,64)),poison)
        if any_tag!=0: self.flag('trap.pointer_as_integer',c.AND(any_tag,c.NOT(poison)),active)
        return Scalar(Value(bits.bits[:integer_width(typ)]),poison)

    def gep(self, inst, args):
        return self.gep_text(rhs_text(inst),args)

    def gep_text(self, text, args):
        c = self.c
        text = text[len('getelementptr '):]
        inbounds = text.startswith('inbounds ')
        if inbounds: text = text[len('inbounds '):]
        nuw = text.startswith('nuw ')
        if nuw:
            if not inbounds: raise LLVMError('GEP nuw requires inbounds in this subset')
            text = text[len('nuw '):]
        if text.startswith('nusw '): raise LLVMError('standalone GEP nusw is unsupported')
        typ = self.typed_source(split_top(text)[0])
        pointer = args[0]
        offset = pointer.offset
        poison = pointer.poison
        def valid_offset(offset):
            valid = 0
            for identity,size in self.object_sizes.items():
                valid = c.OR(valid,c.AND(c.eq(pointer.object,c.const(identity,32)),
                                        c.NOT(c.lt(c.const(size,64),offset))))
            return c.OR(valid,c.AND(c.eq(pointer.object,c.const(0,32)),c.eq(offset,c.const(0,64))))
        inbounds_bad = c.NOT(valid_offset(offset)) if inbounds else 0
        all_zero = 1
        for i,index in enumerate(args[1:]):
            poison = c.OR(poison,index.poison)
            all_zero = c.AND(all_zero,c.NOT(c.nonzero(index.value)))
            if i and typ.is_struct:
                known = c.known(index.value)
                if known is None or known >= len(list(typ.elements)): raise LLVMError('nonconstant structure index')
                step = c.const(self.layout.get_element_offset(typ,known),64)
                typ = list(typ.elements)[known]
            else:
                if i:
                    if not typ.is_array: raise LLVMError('GEP index into non-aggregate type')
                    typ = list(typ.elements)[0]
                scale = self.layout.get_abi_size(typ)
                wide = c.mul(self.resize(index.value,128,True),c.const(scale,128))
                step = Value(wide.bits[:64])
                if inbounds: inbounds_bad = c.OR(inbounds_bad,c.NOT(c.eq(wide,self.resize(step,128,True))))
            summed = c.add(self.resize(offset,65,True),self.resize(step,65,True))
            # Within a finite inbounds object, the additional unsigned no-wrap
            # contract disallows a negative byte step. The signed-product and
            # per-step object bounds checks already exclude all other wraps.
            if nuw: poison = c.OR(poison,step.bits[-1])
            offset = Value(summed.bits[:64])
            if inbounds:
                inbounds_bad = c.OR(inbounds_bad,c.XOR(summed.bits[64],summed.bits[63]))
                inbounds_bad = c.OR(inbounds_bad,c.NOT(valid_offset(offset)))
        # An all-zero GEP is inbounds even for a non-allocated base address.
        if inbounds: poison = c.OR(poison,c.AND(c.NOT(all_zero),inbounds_bad))
        return Pointer(pointer.object,offset,poison)

    def instruction(self, inst, env, active, depth, allocations):
        c, op = self.c, inst.opcode
        operands = list(inst.operands)
        if op == 'alloca': return allocations[inst]
        if op == 'call':
            args = [self.operand(x,env) for x in operands[:-1]]
            name = self.symbol_key(operands[-1]) if operands[-1].value_kind.name=='function' else ''
            prefix,parameters = call_parts(inst)
            args = [self.call_argument(arg,parameter,active) for arg,parameter in zip(args,parameters)]
            if operands[-1].value_kind.name=='function':
                result = (self.intrinsic(name,args,active) if name.startswith('llvm.') else
                          self.invoke(self.functions[name],args,active,depth+1))
            else:
                callee = self.operand(operands[-1],env)
                result = self.zero(inst.type)
                valid = 0
                for candidate in self.call_targets.get(inst,[]):
                    hit = c.AND(c.eq(callee.object,c.const(self.function_ids[self.symbol_key(candidate)],32)),
                                c.NOT(c.nonzero(callee.offset)))
                    hit = c.AND(hit,c.NOT(callee.poison))
                    value = self.invoke(candidate,args,c.AND(active,hit),depth+1)
                    result = self.mux(hit,value,result)
                    valid = c.OR(valid,hit)
                self.flag('trap.invalid_indirect_call',c.OR(callee.poison,c.NOT(valid)),active)
            return self.call_argument(result,prefix,active)
        args = [self.operand(x,env) for x in operands]
        if op in {'add','sub','mul','udiv','sdiv','urem','srem','and','or','xor','shl','lshr','ashr'}:
            return self.binary(inst,*args,active)
        if op == 'icmp':
            a,b = args
            predicate = re.search(r'\bicmp\s+(\w+)',syntax_text(str(inst)))[1]
            if isinstance(a,Pointer):
                if predicate not in ('eq','ne'): raise LLVMError('ordered pointer comparison is unsupported')
                value = c.AND(c.eq(a.object,b.object),c.eq(a.offset,b.offset))
                if predicate=='ne': value = c.NOT(value)
            elif predicate in ('eq','ne'):
                value = c.eq(a.value,b.value)
                if predicate=='ne': value = c.NOT(value)
            else:
                x,y = a.value,b.value
                if predicate[1:] in ('gt','le'): x,y = y,x
                value = c.lt(x,y,predicate.startswith('s'))
                if predicate[1:] in ('le','ge'): value = c.NOT(value)
            return Scalar(Value((value,)),c.OR(a.poison,b.poison))
        if op in ('trunc','sext','zext'):
            a = args[0]
            width = integer_width(inst.type)
            result = self.resize(a.value,width,op=='sext')
            poison = a.poison
            if op=='zext' and re.search(r'\bzext nneg\b',syntax_text(str(inst))):
                poison = c.OR(poison,a.value.bits[-1])
            if op=='trunc':
                flags = syntax_text(str(inst)).split('=',1)[1].split()[1:]
                for flag in sorted(set(flags) & {'nsw','nuw'}):
                    poison = c.OR(poison,c.NOT(c.eq(a.value,self.resize(result,a.value.width,flag=='nsw'))))
            return Scalar(result,poison)
        if op == 'select':
            condition,a,b = args
            result = self.mux(condition.value.bits[0],a,b)
            return self.add_poison(result,condition.poison)
        if op == 'freeze': return self.freeze(args[0])
        if op == 'getelementptr': return self.gep(inst,args)
        if op in ('load','store'):
            pointer = args[-1]
            alignment = re.search(r'\balign (\d+)',syntax_text(str(inst)))
            typ = inst.type if op=='load' else operands[0].type
            align = int(alignment[1]) if alignment else self.layout.get_abi_alignment(typ)
            result = self.memory_access(pointer,typ,active,None if op=='load' else args[0],align)
            if op=='load' and '!nonnull' in metadata_tags(inst): result = self.call_argument(result,'nonnull',active)
            if op=='load' and '!noundef' in metadata_tags(inst): self.flag('trap.undefined_behavior',self.any_poison(result),active)
            return result
        if op in ('extractvalue','insertvalue'):
            indices = [int(x) for x in split_top(str(inst))[2 if op=='insertvalue' else 1:]
                       if not x.startswith('!')]
            if op=='extractvalue':
                result = args[0]
                for index in indices: result = result[index]
                return result
            def replace(value, path):
                out = list(value)
                out[path[0]] = replace(out[path[0]],path[1:]) if len(path)>1 else args[1]
                return tuple(out)
            return replace(args[0],indices)
        raise LLVMError(f'unsupported instruction: {inst}')

    def add_poison(self, data, poison):
        if isinstance(data,tuple): return tuple(self.add_poison(x,poison) for x in data)
        if isinstance(data,Pointer): return Pointer(data.object,data.offset,self.c.OR(data.poison,poison))
        return Scalar(data.value,self.c.OR(data.poison,poison))

    def freeze(self, data):
        if isinstance(data,tuple): return tuple(self.freeze(x) for x in data)
        if isinstance(data,Pointer):
            return Pointer(self.c.mux(data.poison,self.c.const(0,32),data.object),
                           self.c.mux(data.poison,self.c.const(0,64),data.offset))
        return Scalar(self.c.mux(data.poison,self.c.const(0,data.value.width),data.value))

    def invoke(self, function, args, active=1, depth=1, *, copy_byval=True):
        c = self.c
        result_type = function.global_value_type.get_function_return()
        result = self.zero(result_type)
        if active == 0: return result
        if depth > self.limits.max_call_depth:
            self.flag('limit.call_depth',active)
            return result
        blocks = list(function.blocks)
        instructions = {b:list(b.instructions) for b in blocks}
        header = self.function_header(function)
        return_attributes = header[:callee_span(header)[0]]
        env = dict(zip(function.arguments,args))
        for parameter,arg in zip(function.arguments,args):
            attributes = ' '.join(x.decode() for x in parameter.attributes)
            attribute = abi_attribute(attributes)
            if attribute:
                typ = self.abi_type(attribute)
                if attribute[0]=='byval' and copy_byval:
                    copied = self.allocate_bytes(self.layout.get_abi_size(typ))
                    # LLVM's hidden byval object belongs to the caller. Keep it
                    # alive after this callee returns, until that caller exits.
                    self.frames[-1].append(c.known(copied.object))
                    self.memory_intrinsic('llvm.memcpy.p0.p0.i64',[
                        copied,arg,Scalar(c.const(self.layout.get_abi_size(typ),64)),Scalar(c.const(0,1))],active)
                    arg = copied
                elif attribute[0]=='sret': self.sret_contract(arg,typ,attributes,active)
            env[parameter] = self.call_argument(arg,attributes,active)
        for block in blocks:
            for inst in instructions[block]:
                if str(inst.type)!='void': env[inst] = self.zero(inst.type,1)
        owned = []
        self.frames.append(owned)
        allocations = {}
        for inst in instructions[blocks[0]]:
            if inst.opcode == 'alloca':
                allocations[inst] = self.allocate(inst)
                owned.append(c.known(allocations[inst].object))
        edges = {(None,blocks[0]):active}
        for tick in range(self.limits.max_steps):
            if not any(v != 0 for v in edges.values()): break
            previous = env
            env = dict(previous)
            next_edges = {}
            for block in blocks:
                incoming = [(src,v) for (src,dst),v in edges.items() if dst==block]
                enabled = 0
                for _,v in incoming: enabled = c.OR(enabled,v)
                if enabled == 0: continue
                local = dict(previous)
                phis = {}
                for inst in instructions[block]:
                    if inst.opcode != 'phi': continue
                    value = self.zero(inst.type,1)
                    for operand,src in zip(inst.operands,inst.incoming_blocks):
                        edge = edges.get((src,block),0)
                        if edge != 0: value = self.mux(edge,self.operand(operand,previous),value)
                    phis[inst] = value
                local.update(phis)
                for inst in instructions[block]:
                    self.lowered += 1
                    if self.lowered > self.limits.max_lowered_instructions:
                        raise ResourceLimit('max_lowered_instructions exceeded')
                    op = inst.opcode
                    operands = list(inst.operands)
                    def edge(dst, predicate):
                        key = (block,dst)
                        next_edges[key] = c.OR(next_edges.get(key,0),c.AND(enabled,predicate))
                    if op == 'phi': pass
                    elif op == 'br':
                        if len(operands)==1: edge(operands[0],1)
                        else:
                            condition = self.operand(operands[0],local)
                            self.flag('trap.undefined_behavior',condition.poison,enabled)
                            edge(operands[2],condition.value.bits[0])
                            edge(operands[1],c.NOT(condition.value.bits[0]))
                    elif op == 'switch':
                        condition = self.operand(operands[0],local)
                        self.flag('trap.undefined_behavior',condition.poison,enabled)
                        taken = 0
                        for constant,dst in zip(operands[2::2],operands[3::2]):
                            hit = c.eq(condition.value,self.operand(constant,local).value)
                            edge(dst,hit); taken = c.OR(taken,hit)
                        edge(operands[1],c.NOT(taken))
                    elif op == 'ret':
                        value = self.operand(operands[0],local) if operands else ()
                        value = self.call_argument(value,return_attributes,enabled)
                        result = self.mux(enabled,value,result)
                    elif op == 'unreachable': self.flag('trap.undefined_behavior',1,enabled)
                    else: local[inst] = self.instruction(inst,local,enabled,depth,allocations)
                    if str(inst.type)!='void': env[inst] = self.mux(enabled,local[inst],previous[inst])
            edges = next_edges
        remaining = 0
        for v in edges.values(): remaining = c.OR(remaining,v)
        self.flag('limit.block_steps',remaining)
        for identity in owned:
            del self.memory[identity]
            self.alive.pop(identity,None)
        self.frames.pop()
        return result


@dataclass
class Program:
    circuit: Circuit
    results: list[Value]
    flags: dict[str,int]
    parameter_types: list[str]
    result_types: list[str]
    metadata: dict


def compile_ir(source, *, function=None, limits=None, optimize=False):
    limits = limits or Limits()
    module = parse(source)
    lowerings = []
    try:
        return compile_module(module,function,limits,optimize,lowerings)
    finally:
        # LLVM contexts must outlive their modules, including on exceptions
        # retained by Python tracebacks/GC. Dispose modules explicitly in order.
        for lowering in lowerings:
            for helper in lowering.type_modules: helper.close()
            lowering.layout.close()
        module.close()


def compile_module(module, function, limits, optimize, lowerings):
    lowering = Lowering(module,limits)
    lowerings.append(lowering)
    definitions = [f for f in module.functions if not f.is_declaration]
    if function is None:
        if len(definitions)!=1: raise LLVMError('select an entry function with --function')
        function = lowering.symbol_key(definitions[0])
    elif function not in lowering.functions and function not in lowering.aliases:
        if function.startswith('@'): function = lowering.global_name(function)
        else:
            named = named_symbol_key(function)
            if named in lowering.functions or named in lowering.aliases: function = named
            else: function = '@'+function if function.isdecimal() else named
    if function not in lowering.functions and function not in lowering.aliases:
        raise LLVMError(f'entry function not found: {symbol_spelling(function)}')
    entry = lowering.function_symbol(function)
    if function in lowering.aliases and lowering.aliases[function][1][0]!=str(entry.global_value_type):
        raise LLVMError('entry alias type must match its resolved function type')
    lowering.prepare(entry)  # Validate initializers and the closed indirect call graph before optimization.
    if optimize:
        llvm.initialize_native_target(); llvm.initialize_native_asmprinter()
        with llvm.Target.from_default_triple().create_target_machine() as machine:
            with llvm.create_pipeline_tuning_options(speed_level=1) as options:
                with llvm.create_pass_builder(machine,options) as builder:
                    with llvm.create_new_module_pass_manager() as passes:
                        passes.add_sroa_pass()
                        passes.add_instruction_combine_pass()
                        passes.add_simplify_cfg_pass()
                        passes.run(module,builder)
        module.verify()
        lowering = Lowering(module,limits)
        lowerings.append(lowering)
        entry = lowering.function_symbol(function)
        lowering.prepare(entry)
    args,parameter_types,parameter_names,result_buffer,adapter = lowering.entry_arguments(entry)
    for item in lowering.initializers:
        lowering.invoke(lowering.functions[item['function']],[])
    result = lowering.invoke(entry,args,copy_byval=False)
    if result_buffer:
        pointer,typ = result_buffer
        result = lowering.memory_access(pointer,typ,1)
    lowering.flag('trap.poison_result',lowering.any_poison(result))
    results = []
    def flatten(value):
        if isinstance(value,tuple):
            for x in value: flatten(x)
        elif isinstance(value,Pointer): raise LLVMError('pointer results are unsupported')
        else: results.append(value.value)
    flatten(result)
    return Program(lowering.c,results,lowering.flags,parameter_types,
                   [f'i{x.width}' for x in results],
                   {'language':'llvm','llvm_subset':'bounded-integer-v1','function':function,
                    'parameters':parameter_names,
                    'llvm_version':list(llvm.llvm_version_info), 'optimized':bool(optimize),
                    'limits':dict(vars(limits)), 'lowered_instructions':lowering.lowered,
                    **({'entry_abi':adapter} if adapter else {}),
                    **({'global_state':'fresh-per-shape','mutable_globals':sorted(lowering.mutable_globals)}
                       if lowering.mutable_globals else {}),
                    **({'pointer_memory':'opaque-provenance-v1'} if lowering.pointer_memory_used else {}),
                    **({'function_addresses':{name:lowering.function_ids[name] for name in sorted(lowering.address_taken)}}
                       if lowering.address_taken else {}),
                    **({'aliases':sorted(lowering.used_aliases)} if lowering.used_aliases else {}),
                    **({'indirect_calls':[{'function':lowering.symbol_key(inst.function),'instruction':inst.name,'targets':[lowering.symbol_key(f) for f in targets],
                         **({'declared_targets':sorted(lowering.callee_constraints[inst])} if inst in lowering.callee_constraints else {})}
                         for inst,targets in lowering.call_targets.items()]} if lowering.indirect_calls else {}),
                    **({'constructors':lowering.initializers} if lowering.initializers else {})})


def build(source, output, **options):
    started = time.perf_counter()
    program = compile_ir(source,**options)
    manifest = emit_font(program.circuit,program.results,program.flags,
                         program.parameter_types,program.result_types,output,
                         font_family='LLVM GSUB Registers',extra=program.metadata)
    # Timing belongs in benchmark reports, keeping paired manifests reproducible.
    build.last_seconds = time.perf_counter()-started
    return manifest
