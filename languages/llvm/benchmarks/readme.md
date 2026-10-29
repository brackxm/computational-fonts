# LLVM compiler measurements

Measured locally on 2026-10-29: macOS arm64, Python 3.12.15, LLVM 20.1.8,
HarfBuzz 15.0.0. Each font uses a 32-block execution budget, three call frames
and 64 global/frame allocation bytes, with at most 16 candidates per indirect
call and 32 module initializer entries. Shaping times are medians of 20 warmed invocations;
build times include parsing, lowering, serialization and manifest generation.
Timings are indicative and depend on the machine and concurrent work.

| Font | Bytes | Glyphs | Gates | Lookups | Build seconds | Shape ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| max | 18,024 | 426 | 98 | 99 | 0.021 | 0.103 |
| loop | 268,500 | 5,300 | 1,744 | 1,568 | 0.270 | 4.242 |
| memory | 62,948 | 1,284 | 384 | 384 | 0.111 | 0.558 |
| clang_max | 39,036 | 834 | 234 | 234 | 0.038 | 0.276 |
| clang_mix | 26,164 | 699 | 189 | 128 | 0.036 | 0.230 |
| clang_indexed | 82,808 | 1,674 | 514 | 483 | 0.589 | 0.735 |
| clang_loop | 107,396 | 2,234 | 722 | 640 | 0.169 | 1.323 |
| rust_max | 18,292 | 432 | 100 | 101 | 0.017 | 0.061 |
| rust_mix | 36,916 | 1,034 | 258 | 196 | 0.038 | 0.305 |
| clang_lookup | 7,992 | 233 | 55 | 40 | 0.060 | 0.026 |
| clang_copied | 61,920 | 1,317 | 395 | 362 | 0.275 | 0.470 |
| clang_checked_add | 17,608 | 531 | 133 | 86 | 0.021 | 0.148 |
| clang_checked_mul | 523,012 | 12,531 | 4,133 | 2,165 | 0.770 | 38.276 |
| rust_lookup | 7,992 | 233 | 55 | 40 | 0.038 | 0.027 |
| rust_checked_add | 17,608 | 531 | 133 | 86 | 0.028 | 0.139 |
| rust_checked_mul | 523,012 | 12,531 | 4,133 | 2,165 | 0.768 | 38.436 |
| clang_sat_add | 19,976 | 531 | 133 | 102 | 0.021 | 0.127 |
| clang_sat_sub | 21,296 | 540 | 136 | 105 | 0.029 | 0.096 |
| clang_global_calls | 26,376 | 711 | 193 | 132 | 0.030 | 0.148 |
| clang_pointer_table | 15,068 | 450 | 106 | 77 | 0.131 | 0.055 |
| clang_pointer_copy | 29,080 | 717 | 195 | 165 | 0.255 | 0.134 |
| rust_sat_add | 19,976 | 531 | 133 | 102 | 0.020 | 0.127 |
| rust_sat_sub | 21,296 | 540 | 136 | 105 | 0.022 | 0.103 |
| rust_global_calls | 26,376 | 711 | 193 | 132 | 0.031 | 0.145 |
| rust_pointer_table | 26,352 | 660 | 176 | 144 | 0.103 | 0.123 |
| rust_pointer_copy | 31,096 | 759 | 209 | 177 | 0.298 | 0.147 |
| clang_dispatch | 105,932 | 2,491 | 765 | 584 | 0.184 | 1.400 |
| clang_dispatch_twice | 201,544 | 4,480 | 1,428 | 1,093 | 0.280 | 4.614 |
| clang_copied_dispatch | 102,704 | 2,422 | 742 | 562 | 0.335 | 1.435 |
| clang_ctor_callback | 12,408 | 348 | 72 | 72 | 0.016 | 0.046 |
| clang_constructors | 12,844 | 356 | 96 | 67 | 0.019 | 0.047 |
| rust_dispatch | 106,168 | 2,494 | 766 | 586 | 0.160 | 1.401 |
| rust_dispatch_twice | 201,348 | 4,483 | 1,429 | 1,095 | 0.259 | 4.516 |
| rust_copied_dispatch | 78,840 | 1,867 | 557 | 436 | 0.292 | 0.848 |
| rust_ctor_callback | 12,460 | 351 | 73 | 72 | 0.024 | 0.047 |
| alias_table | 44,676 | 1,030 | 320 | 260 | 0.102 | 0.329 |
| rust_aliases | 35,612 | 831 | 233 | 204 | 0.038 | 0.215 |
| rust_merged_aliases | 13,912 | 426 | 98 | 68 | 0.016 | 0.050 |
| rust_alias_entry | 12,988 | 359 | 97 | 68 | 0.013 | 0.046 |
| clang_triple | 66,496 | 1,796 | 512 | 386 | 0.127 | 1.036 |
| clang_triple_callback | 151,248 | 3,489 | 1,055 | 865 | 0.328 | 3.636 |
| clang_triple_calls | 83,808 | 2,168 | 636 | 449 | 0.192 | 1.251 |
| clang_byval | 46,808 | 1,354 | 322 | 260 | 0.101 | 0.490 |
| clang_byval_calls | 83,916 | 2,171 | 637 | 450 | 0.417 | 1.211 |
| rust_triple | 66,496 | 1,796 | 512 | 386 | 0.121 | 1.038 |
| rust_triple_calls | 83,808 | 2,168 | 636 | 449 | 0.194 | 1.203 |
| rust_triple_callback | 152,296 | 3,510 | 1,062 | 871 | 0.303 | 3.860 |

`max` is the hand-written SSA/select example. `clang_max` retains Clang's
unoptimized stack memory; `rust_max` uses an optimized integer intrinsic.
These are different circuits implementing the same signed comparison.
The optimized Clang/Rust checked-arithmetic examples compile to identical
font bytes. Checked multiplication needs a wider product to detect overflow,
which explains its larger circuit and higher shaping cost. The copied-array
example includes lifetime markers, a copy from a constant global and dynamic
runtime indexing and mutation.
The dispatch fonts select among four callbacks at shaping time, including one
that mutates a global. The repeated-dispatch examples verify that the second
call sees the first call's effects. Copied-dispatch examples preserve function
identities through memcpy. The Rust callback examples use a native initializer
section; the separate unoptimized Clang constructor example retains two
priority-ordered startup functions. Clang folds the optimized callback example's
constructors into static data before this frontend sees them.
`alias_table` shares code/data identities through aliases, runs an aliased
constructor and restricts the table's callback set with `!callees`.
`rust_aliases` retains two equivalent callbacks at `-O1`; at `-O2`, Rust merges
one into an alias, so `rust_merged_aliases` needs only one dispatch target and
a smaller circuit. `rust_alias_entry` selects that exported alias as the entry.
The aggregate ABI examples add hidden result buffers and caller-owned byval
copies. The Clang and Rust triple constructors produce identical 512-gate fonts;
their manifests expose three `i64` fields and twenty-four `i8` bytes respectively,
following each frontend's LLVM storage type. Callback variants select the
constructor at shaping time. `clang_byval` takes three integer fields as input,
while `clang_byval_calls` makes an implicit private copy during its internal call.
The loop circuit supports different runtime iteration counts up to its block
budget. Its size includes all bounded stages, even for short invocations.

The [JSON report](latest.json) contains inputs, checked results, detailed
packing metrics and complete-invocation timing (encoding + shaping + decoding).
The [glyph trace](max-trace.json) contains the complete uninitialized input tape,
the actual HarfBuzz-substituted tape, decoded result and font digest.

Rebuild from the repository root, using the environment described in the
[compiler README](../readme.md):

```sh
python languages/llvm/build_examples.py --iterations 20
```

The XML report records the LLVM Python test suite. Font/manifest reproduction
is tested byte-for-byte, separately from these variable timing measurements.

The [validation report](validation.json) records 315 passing LLVM Python tests,
47 LLVM browser tests and 328 current shared/Verilog regression tests
(216 skipped). These include native Clang/Rust callback programs through both
text and bitcode, copied/mutable function tables, guarded side effects, indirect
recursion, constructor priorities checked against a native linked library,
startup sections and explicit invalid-target/resource diagnostics. All prior
arithmetic, saturation, memory and pointer checks remain in the full run.
Alias checks add native shared identity, interior offsets, cyclic relocations,
constructor aliases and Rust `-O1`/`-O2` `.ll`/`.bc` differential tests.
Aggregate ABI checks cover native Clang/Rust struct and callback returns,
flattened byval inputs, hidden-copy lifetime/provenance/poison, guarded invalid
buffers, signature compatibility and bounded memory. Repeated builds/failures
exercise deterministic named types and ordered LLVM context cleanup. The full
run includes byte-for-byte reproduction of all forty-seven fonts.
Validation also covers array lengths beyond 32 bits, aggregate limits before
expansion, keyword-like byte strings and quoted LLVM identifiers, iterative
lifetime-root discovery, failed verification cleanup, and identical builds
under different Python hash seeds.
Numbered-symbol regressions cover globals, direct/indirect calls, aliases,
constructors, quoted numeric names and interleaved definitions. Store-span
regressions cover over-aligned integers/pointers, aggregate ABI alignment and
field stride, poisoned padding, and full-size global copies. Custom layouts are
normalized by LLVM before host-native execution, after checking that no
layout-dependent memory instructions or calls remain. Existing demo font bytes
and metrics are unchanged by these correctness fixes.
Startup regressions compare quoted-name initializer sections against a native
linked loader. Boundary checks cover UTF-8 source sizes, bounded file reads and
scalar/flattened-byval input capacity; unsupported Mach-O startup type flags
produce explicit diagnostics.
The earlier full shared/Verilog/WebAssembly, browser and
fontbuild results are retained separately. The shared executable backend is
unchanged.
