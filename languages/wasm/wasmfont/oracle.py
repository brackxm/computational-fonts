"""Independent V8 differential oracle. Never imported by the native runtime."""
import base64
import json
import shutil
import subprocess
from pathlib import Path


def execute_binary(data,export,params,cases):
    node=shutil.which('node')
    if not node:raise RuntimeError('Node.js is required for the V8 differential oracle')
    request={'wasm':base64.b64encode(data).decode(),'export':export,'params':params,
             'cases':[[str(v) for v in case] for case in cases]}
    process=subprocess.run([node,str(Path(__file__).with_suffix('.js'))],
                           input=json.dumps(request),text=True,capture_output=True,timeout=20)
    if process.returncode:raise RuntimeError('V8 oracle failed: '+process.stderr)
    return json.loads(process.stdout)
