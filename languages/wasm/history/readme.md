# ChatGPT handoff provenance

Imported from the user-provided `wasm-division-identities-continued.zip` on
2026-10-16. The archive SHA-256 is
`f3c975a48c5515f6713597570afaa44ea1b2eebfb04e9aaf71d626431aa0f927`.
Python bytecode and pytest caches were excluded.

These files retain the original handoff's development notes and evidence:

- `REPO_INTEGRATION.md` describes the proposed repository integration before
  this project was imported.
- `SOURCE_MANIFEST.json` is the original snapshot, dated before the final
  division optimizations. It is not a checksum manifest of this checkout.
- `LEGACY_HISTORY.md` describes the earlier primitive compiler and reference VM.
- `../benchmarks/` retains the handoff's measurements and validation reports.
  Their counts and timings describe that earlier Linux environment, not a
  rerun of the current source.

Integration renamed `README.md` to `readme.md`, moved these historical notes,
added system HarfBuzz discovery for macOS, and made the optional C-rebuild
test check for a Wasm-capable toolchain. Current build instructions and limits
are in [the project readme](../readme.md).
