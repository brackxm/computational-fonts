# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Generate the bounded opening book with an external UCI engine.

The engine is a build-time tool only. No engine code is copied into the font.
"""
import argparse
from collections import deque
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import queue
import tempfile
import threading
import time
import model


def fen(board):
    rows=[]
    for y in reversed(range(5)):
        row=''; empty=0
        for c in board[y*5:y*5+5]:
            if c=='.':empty+=1
            else:
                if empty:row+=str(empty);empty=0
                row+=c
        if empty:row+=str(empty)
        rows.append(row)
    return '/'.join(rows)+' w - - 0 1'


class Engine:
    def __init__(self,path):
        env={k:v for k,v in os.environ.items() if not k.startswith('GARDNER_')}
        self.process=subprocess.Popen([str(Path(path).resolve())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1,env=env)
        self.lines=queue.Queue()
        def read():
            for line in self.process.stdout:self.lines.put(line)
            self.lines.put(None)
        self.reader=threading.Thread(target=read,daemon=True)
        self.reader.start()
        try:
            self.send('uci');self.until('uciok')
            self.send('setoption name UCI_Variant value gardner')
            self.send('setoption name Threads value 1')
            self.send('setoption name Hash value 64')
            self.send('isready');self.until('readyok')
        except BaseException:
            self.close()
            raise

    def send(self,line):
        self.process.stdin.write(line+'\n');self.process.stdin.flush()

    def until(self,prefix):
        deadline=time.monotonic()+30
        while True:
            try:line=self.lines.get(timeout=max(0,deadline-time.monotonic()))
            except queue.Empty:raise TimeoutError('UCI engine did not respond within 30 seconds') from None
            if line is None:raise RuntimeError('UCI engine exited unexpectedly')
            if line.startswith(prefix):return line.strip()

    def choose(self,board,nodes):
        self.send('position fen '+fen(board));self.send('go nodes '+str(nodes))
        move=self.until('bestmove ').split()[1]
        if move not in model.legal(board,True):raise ValueError(('Engine returned illegal move',board,move))
        return move

    def close(self):
        try:self.send('quit')
        except (BrokenPipeError,OSError):pass
        try:self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill();self.process.wait()
        self.reader.join(timeout=2)
        self.process.stdin.close();self.process.stdout.close()


def generate(engine_path,output,positions,nodes):
    engine=Engine(engine_path);pending=deque([model.INITIAL]);seen=set();records={};started=time.monotonic()
    try:
        while pending and len(records)<positions:
            board=pending.popleft()
            if board in seen:continue
            seen.add(board)
            if model.dead(board) or not model.legal(board,True):continue
            move=engine.choose(board,nodes*10 if board==model.INITIAL else nodes)
            records[board]=move
            after=model.legal(board,True)[move]
            if not model.dead(after):pending.extend(model.legal(after,False).values())
            if len(records)%100==0:print(len(records),'positions',round(time.monotonic()-started,1),'seconds',flush=True)
    finally:engine.close()
    data={'format':1,'engine':'Fairy-Stockfish','engine_sha256':hashlib.sha256(Path(engine_path).read_bytes()).hexdigest(),
          'nodes_per_position':nodes,'root_nodes':nodes*10,'records':dict(sorted(records.items()))}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='.book-') as temp:
        pending=Path(temp)/'book.gz'
        with pending.open('wb') as target:
            with gzip.GzipFile(filename='',fileobj=target,mode='wb',mtime=0) as out:
                out.write((json.dumps(data,separators=(',',':'))+'\n').encode())
        pending.replace(output)
    print('Saved',len(records),'positions to',output,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine',type=Path,required=True)
    parser.add_argument('--positions',type=int,default=8192)
    parser.add_argument('--nodes',type=int,default=50000)
    parser.add_argument('--output',type=Path,default=Path(__file__).with_name('book.json.gz'))
    args=parser.parse_args()
    if args.positions<1 or args.nodes<1:parser.error('budgets must be positive')
    generate(args.engine,args.output,args.positions,args.nodes)
