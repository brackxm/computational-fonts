# HarfBuzz browser runtime

Unmodified runtime files from the official `harfbuzzjs` npm package, pinned to
**1.6.3**. Its WebAssembly engine reports HarfBuzz **14.6.0**.
Only the runtime entry point, JavaScript loader and shaping binary are bundled;
the optional subsetting binary is not needed by this playground.

- Package: https://www.npmjs.com/package/harfbuzzjs/v/1.6.3
- Source and API documentation: https://github.com/harfbuzz/harfbuzzjs
- Archive: https://registry.npmjs.org/harfbuzzjs/-/harfbuzzjs-1.6.3.tgz
- HarfBuzz source: https://github.com/harfbuzz/harfbuzz/tree/14.6.0

`LICENSE` retains the package's MIT notice. `HARFBUZZ-COPYING` retains the
HarfBuzz engine's Old MIT notice from the corresponding 14.6.0 tag.
`package.json` is a local module-type marker for Node.js regression tests.

The browser loads these files from the same static server as the playground;
there are no CDN requests. To update, download the official pinned package,
copy these three files together, retain both licenses, update these checksums,
and run `node --test languages/wasm/test_playground.mjs` plus browser checks.

| File | SHA-256 |
| --- | --- |
| `index.mjs` | `04ece1914c8720ad96257728119c1bf24088ee4ef3ab2a2ca688c9a4895d4e7e` |
| `harfbuzz.js` | `ba43463df44851fd58211ef8c19aa7956965390857727ae867b70dc7b3682de1` |
| `harfbuzz.wasm` | `5f67e3bd1c4f40ffd07c12d7faa30ebc40cc65998ce058fde5b3c6504607bfb4` |
