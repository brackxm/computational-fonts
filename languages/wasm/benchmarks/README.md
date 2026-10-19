# Native GSUB benchmarks

The current [dispatch-capacity report](dispatch_capacity.json) records a 256-slot
table sharing one dynamic i64 divider: 5,680 → 4,322 gates and 2,078,972 →
1,532,548 font bytes after replacing per-slot comparisons with a shared reference
lookup. This measures compilation size, with no timing claim. Reproduce the
optimized result with `tests/test_indirect_calls.py::test_duplicate_table_targets_share_one_expensive_callee`.
The timing and validation reports below remain historical.

Historical reports supplied with the ChatGPT ZIP. These describe the handoff's
Linux environment and source snapshot, not the current checkout. To measure
this checkout, run the reproduction commands below.

Measured locally on the environment recorded in `latest.json`; these are not browser or cross-platform guarantees. Every reported output was checked against a fresh V8 WebAssembly instance.

Each timing uses a cached font face, three warmups and 20 repetitions of the same input. HarfBuzz time measures only `hb_shape_full`. End-to-end time includes argument serialization, buffer input/output, scratch/status validation and result unpacking. Compilation and the V8 oracle are outside the shaping timings.

| Program | Font bytes | Glyphs | Lookups | Compile ms | HarfBuzz median ms | End-to-end median ms |

| --- | ---: | ---: | ---: | ---: | ---: | ---: |

| compose32 | 43,564 | 714 | 131 | 42.893 | 0.353 | 0.689 |

| compose64 | 86,924 | 1,418 | 259 | 57.050 | 1.014 | 1.624 |

| multiply64 | 1,370,648 | 18,620 | 4,166 | 640.963 | 143.129 | 151.825 |

| divide32 | 1,037,040 | 12,441 | 3,141 | 365.797 | 77.278 | 82.739 |

| branch | 55,172 | 816 | 165 | 40.813 | 0.370 | 0.740 |

| loop | 271,244 | 4,106 | 949 | 196.871 | 5.265 | 7.149 |

| recursion | 254,828 | 4,124 | 955 | 132.833 | 4.719 | 6.558 |

| memory | 276,936 | 4,404 | 1,423 | 153.438 | 8.728 | 10.577 |

| count | 134,164 | 2,733 | 469 | 88.620 | 1.562 | 2.721 |

| c-mix32 | 80,900 | 1,275 | 259 | 56.449 | 1.052 | 1.582 |

| c-mix64 | 219,696 | 2,951 | 676 | 97.704 | 5.034 | 6.342 |


## Interpretation

The register tape permits independent computed values to compose, but the current implementation scans a substantial tape for each gate lookup. Dynamic multiplication, division and bounded memory are consequently much more expensive than simple arithmetic. The 64-bit multiplier takes roughly 143 ms of HarfBuzz work on this machine; it should not be presented as a low-latency interactive primitive.

Program expansion is bounded by the circuit budget, glyph limit and compact GSUB lookup-offset capacity. These measurements do not imply unbounded loop execution or general WebAssembly compatibility. Memory and call state are fresh for each invocation.

The 11 demonstration font builds also completed successfully; `demo-builds.json` records their layout sizes. The source package includes their rebuild script rather than prebuilt font binaries.


## Reproduce

```sh
python benchmark.py --repeats 20 --output benchmarks/latest.json
python build_examples.py --recompile-c
```


## Validation

`validation.txt` and `validation-summary.json` record **316 passed tests and 20 passed subtests**, completed in three non-overlapping pytest batches. `junit.xml` combines the three original JUnit reports; its 336 test cases include the 20 subtests. There are no failures, errors or skips. Full single-process invocations were interrupted in this tool environment, so this is not represented as one uninterrupted test run.

The new backend contributes 122 tests; all 194 legacy tests and their 20 subtests remain passing. Circuit tests exhaust all 256 pairs at four bits for 13 operations; three of those operations also exhaust the input pairs through HarfBuzz. The C demonstration was both tested as a supplied binary and rebuilt with the installed Clang compiler.
