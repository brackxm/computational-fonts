# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Original Gardner rules, used to compile and verify the font.

Boards are 25 cells, bottom rank first. Coordinates are a1..e5. White pawns
advance one rank, Black pawns retreat one rank; every far-rank pawn promotes.
No double steps, castling, or en passant.
"""
import re

INITIAL='RNBQKPPPPP.....ppppprnbqk'
KING=((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1))
KNIGHT=((1,2),(2,1),(-1,2),(-2,1),(1,-2),(2,-1),(-1,-2),(-2,-1))
ROOK=KING[:4]
BISHOP=KING[4:]


def white(piece):return piece.isupper()
def square(i):return chr(97+i%5)+str(1+i//5)


def uci(move):
    origin,target,promotion=move
    return square(origin)+square(target)+promotion.lower()


def parse_uci(text):
    def index(s):return (int(s[1])-1)*5+ord(s[0])-97
    return index(text[:2]),index(text[2:4]),text[4:].upper()


def apply(board,move):
    origin,target,promotion=move;piece=board[origin]
    changed=list(board);changed[origin]='.'
    changed[target]=(promotion if white(piece) else promotion.lower()) if promotion else piece
    return ''.join(changed)


def attacked(board,target,by_white):
    tx,ty=target%5,target//5
    for dx,dy in KNIGHT:
        x,y=tx+dx,ty+dy
        if 0<=x<5 and 0<=y<5 and board[y*5+x]==('N' if by_white else 'n'):return True
    for dx in (-1,1):
        x,y=tx+dx,ty+(-1 if by_white else 1)
        if 0<=x<5 and 0<=y<5 and board[y*5+x]==('P' if by_white else 'p'):return True
    for dx,dy in KING:
        x,y=tx+dx,ty+dy;distance=1
        while 0<=x<5 and 0<=y<5:
            piece=board[y*5+x]
            if piece!='.':
                if white(piece)==by_white:
                    kind=piece.upper()
                    if kind=='K' and distance==1:return True
                    if kind=='Q' or kind==('R' if dx==0 or dy==0 else 'B'):return True
                break
            x+=dx;y+=dy;distance+=1
    return False


def checked(board,side):return attacked(board,board.index('K' if side else 'k'),not side)


def dead(board):
    pieces=[(i,p) for i,p in enumerate(board) if p not in '.Kk']
    if not pieces or (len(pieces)==1 and pieces[0][1].upper() in 'BN'):return True
    return all(p.upper()=='B' for i,p in pieces) and len({(i%5+i//5)%2 for i,p in pieces})==1


def pseudo(board,side):
    for origin,piece in enumerate(board):
        if piece=='.' or white(piece)!=side:continue
        kind=piece.upper();x,y=origin%5,origin//5
        if kind=='P':
            ny=y+(1 if side else -1)
            if not 0<=ny<5:continue
            for dx in (0,-1,1):
                nx=x+dx
                if not 0<=nx<5:continue
                target=ny*5+nx;victim=board[target]
                if (dx==0 and victim!='.') or (dx!=0 and (victim=='.' or white(victim)==side or victim.upper()=='K')):continue
                for promote in ('QRBN' if ny in (0,4) else ('',)):yield origin,target,promote
            continue
        directions=KNIGHT if kind=='N' else KING if kind in 'KQ' else ROOK if kind=='R' else BISHOP
        for dx,dy in directions:
            nx,ny=x+dx,y+dy
            while 0<=nx<5 and 0<=ny<5:
                target=ny*5+nx;victim=board[target]
                if victim!='.' and (white(victim)==side or victim.upper()=='K'):break
                yield origin,target,''
                if victim!='.' or kind in 'NK':break
                nx+=dx;ny+=dy


def legal(board,side):
    result={}
    for move in pseudo(board,side):
        child=apply(board,move)
        if not checked(child,side):result[uci(move)]=child
    return result


def tick(board,move,count):
    origin,target,promotion=parse_uci(move)
    return 0 if board[origin].upper()=='P' or board[target]!='.' else min(count+1,150)


VALUE = dict(zip('PKNBRQ', (100, 20000, 300, 325, 500, 900)))

def templates(side):
    """Geometric moves, with intervening squares and pawn capture flag."""
    for origin in range(25):
        x, y = origin % 5, origin // 5
        for kind in 'PNBRQK':
            piece = kind if side else kind.lower()
            if kind == 'P':
                ny = y + (1 if side else -1)
                if not 0 <= ny < 5:
                    continue
                for dx in (0, -1, 1):
                    nx = x + dx
                    if 0 <= nx < 5:
                        for promo in ('QRBN' if ny in (0, 4) else ('',)):
                            yield piece, origin, ny*5+nx, promo, (), dx != 0
                continue
            directions = KNIGHT if kind == 'N' else KING if kind in 'KQ' else ROOK if kind == 'R' else BISHOP
            for dx, dy in directions:
                nx, ny = x+dx, y+dy
                path = []
                while 0 <= nx < 5 and 0 <= ny < 5:
                    target = ny*5+nx
                    yield piece, origin, target, '', tuple(path), False
                    if kind in 'NK':
                        break
                    path.append(target)
                    nx += dx
                    ny += dy


def load_book(path=None):
    import gzip,json
    from pathlib import Path
    with gzip.open(path or Path(__file__).with_name('book.json.gz'),'rt',encoding='utf8') as source:
        data=json.load(source)
    if data['format']!=1:raise ValueError('Unsupported opening book format')
    records=data['records']
    if not records or INITIAL not in records:raise ValueError('Opening book must include the initial position')
    for board,move in records.items():
        if len(board)!=25 or board.count('K')!=1 or board.count('k')!=1 or not set(board)<=set('.KQRBNPkqrbnp'):
            raise ValueError('Invalid opening-book board')
        if move not in legal(board,True):raise ValueError('Illegal opening-book move: '+move)
    return records

def move_priority(temp):
    piece,o,t,promo,path,capture=temp
    return (0 if promo else 1,0 if piece in 'PNB' else 1,
            abs(t%5-2)+abs(t//5-2),0 if t//5>o//5 else 1,VALUE[piece],uci((o,t,promo)))


def choose(board,book=None):
    """Reference for the font's bounded book and two-pass capture heuristic."""
    options=legal(board,True)
    if not options:return None
    if book is not None and board in book:
        move=book[board]
        if move not in options:raise ValueError('Illegal opening-book move')
        return move
    candidates=sorted((t for t in templates(True) if not t[3] or t[3]=='Q'),key=move_priority)
    for safe in (True,False):
        for victim in 'qrbnp.':
            for piece,o,t,promo,path,capture in candidates:
                if board[o]!=piece or board[t]!=victim:continue
                if piece=='P' and capture != (victim!='.'):continue
                move=uci((o,t,promo))
                if move not in options:continue
                if safe and attacked(options[move],t,False):continue
                return move
    raise AssertionError('No fallback move despite legal options')


def reply(board,count=0,book=None):
    options=legal(board,True)
    if not options:return board,None,'human_win' if checked(board,True) else 'draw',count
    if dead(board) or count>=150:return board,None,'draw',count
    move=choose(board,book);after=options[move];count=tick(board,move,count)
    black=legal(after,False)
    if not black:return after,move,'font_win' if checked(after,False) else 'draw',count
    if dead(after) or count>=150:return after,move,'draw',count
    return after,move,'ready',count


def replay(source,book=None):
    source=''.join(c for c in source if c not in ' \t\r\n')
    board=INITIAL;count=0;last=None
    if not source or source[0]!='b':return board,last,'malformed',count
    board,last,status,count=reply(board,count,book)
    position=1
    while position<len(source) and status=='ready':
        end=source.find(';',position)
        if end<0:return board,None,'malformed',count
        key=source[position:end];position=end+1
        if not re.fullmatch('[A-E][1-5][A-E][1-5][QRBN]?',key):return board,None,'malformed',count
        move=key.lower();options=legal(board,False)
        if move not in options:return board,None,'invalid',count
        count=tick(board,move,count);board=options[move]
        board,last,status,count=reply(board,count,book)
    return board,last,status,count
