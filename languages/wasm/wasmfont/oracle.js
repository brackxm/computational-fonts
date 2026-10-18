'use strict';
// Independent differential oracle: executes the binary in Node's V8 Wasm engine.
const fs = require('fs');
const request = JSON.parse(fs.readFileSync(0, 'utf8'));
const module_ = new WebAssembly.Module(Buffer.from(request.wasm, 'base64'));
const responses = request.cases.map(values => {
  try {
    // A fresh instance matches the native font's per-shaping invocation state.
    const instance = new WebAssembly.Instance(module_);
    const args = values.map((v,i) => request.params[i] === 'i64' ? BigInt.asIntN(64, BigInt(v)) : Number(BigInt.asIntN(32, BigInt(v))));
    const returned = instance.exports[request.export](...args);
    const results = returned === undefined ? [] : Array.isArray(returned) ? returned : [returned];
    return {values: results.map(String)};
  } catch (error) {
    if (!(error instanceof WebAssembly.RuntimeError)) throw error;
    return {trap: error.message};
  }
});
process.stdout.write(JSON.stringify(responses));
