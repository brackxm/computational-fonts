"""Independent binary validation and the supported module-section policy."""
import shutil
import subprocess

from .ir import uleb


def validate(data: bytes) -> None:
    node=shutil.which('node')
    if not node:raise RuntimeError('Node.js is required for independent WebAssembly validation')
    result=subprocess.run([node,'-e',"const b=require('fs').readFileSync(0); try { new WebAssembly.Module(b); } catch(e) { console.error(e.message); process.exit(1); }"],input=data,capture_output=True,timeout=15)
    if result.returncode:raise ValueError('V8 rejected WebAssembly: '+result.stderr.decode().strip())


def validate_supported(data: bytes) -> None:
    validate(data)
    pos=8
    while pos<len(data):
        sid=data[pos];size,start=uleb(data,pos+1);pos=start+size
        if sid in (2,13):
            raise NotImplementedError(f'unsupported module section {sid} (imports/tags)')
