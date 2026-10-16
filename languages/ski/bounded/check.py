"""Deterministic real-HarfBuzz differential and acceptance suite."""
import argparse,json,random,time,hashlib
from collections import Counter
from pathlib import Path
from .runtime import Machine,InputOverflow,MachineError
from .syntax import App,Leaf,parse,prefix,height,count
from .reference import evaluate,step
from .config import DEFAULT_FONT, ROOT


def check(font=DEFAULT_FONT, report_dir=ROOT / 'build'):
    report_dir=Path(report_dir)
    report_dir.mkdir(parents=True,exist_ok=True)
    m=Machine(font);counts=Counter();started=time.perf_counter();total=0;max_steps=0;failures=[]
    def compare(source,fuel=None):
        nonlocal total,max_steps
        fuel=m.rounds if fuel is None else fuel
        expected=evaluate(source,m.depth,fuel)
        try:got=m.run(source,fuel)
        except InputOverflow:
            assert expected.status=='input_overflow';counts['input_overflow']+=1;total+=1;return None
        actual=(got.status,got.expression,got.steps)
        wanted=(expected.status,expected.expression,expected.steps)
        if actual!=wanted:
            failures.append({'input':source,'fuel':fuel,'expected':wanted,'actual':actual,'glyphs':got.glyphs})
            (report_dir/'failures.json').write_text(json.dumps(failures,indent=2))
            raise AssertionError(failures[-1])
        total+=1;counts[got.status]+=1;max_steps=max(max_steps,got.steps)
        if total%1000==0:print('checked',total,dict(counts),flush=True)
        return got
    basics={'I a':'a','K a b':'a','S K K a':'a','S K K (I a)':'a','S K K (K a b)':'a','S K K (S K K a)':'a','K a (S I I b)':'a','K a (S I I (S I I))':'a', 'S (I a) b (I c)':'a c (b c)'}
    for source,want in basics.items():
        got=compare(source)
        assert got.status=='normal' and got.expression==prefix(parse(want))
        for fuel in (0,1,2):compare(source,fuel)
    for x in ('I','K','S','K a','S K','S K K'):
        got=compare(x);assert got.steps==0 and got.expression==prefix(parse(x))
    r=compare('S a b (K c d)',1)
    assert r.expression==prefix(parse('a (K c d) (b (K c d))'))
    for x in ('S (I a) (K b c) (S K K d)','S (K a) (S I I) (a (b c))','a (S (I b) (K c) d)','S a b c d','I (S (I a) (K b) c)'):
        for fuel in (0,1,2,8):compare(x,min(fuel,m.rounds))
    # S pushes z one level deeper. Entire failed contraction is transactional.
    deep='a'
    for _ in range(m.depth-1):deep='@a'+deep
    over='@@@Sab'+deep
    r=compare(over,1);assert r.status=='overflow' and r.steps==0 and r.expression==over
    r=compare(over,0);assert r.status=='budget'
    full='I'
    for _ in range(m.depth):full='@'+full+full
    assert count(parse(full))==m.meta['capacity']
    r=compare(full);assert r.steps==min(2**m.depth-1,m.rounds)
    compare('S I I (S I I)',2);compare('S I I (S I I)')
    compare('@a'+full) # encoder rejection, not a font computation
    long_case='@@@@@SI@KII@@@IK@II@@II@SS@@@@II@SI@@II@II@@@SI@IS@@II@II'
    for fuel in (0,1,2,31,32):
        if fuel<=m.rounds:compare(long_case,fuel)
    # Every tree with <=3 applications over six values, including saturated S.
    small={0:list('SKIabc')}
    for k in range(1,4):
        small[k]=['@'+l+r for i in range(k) for l in small[i] for r in small[k-i-1]]
    for group in small.values():
        for text in group:compare(text)
    rng=random.Random(360036)
    def tree(d):
        if not d or rng.random()<.36:return Leaf(rng.choice('SKIabcdefghijklmnopqrstuvwxyz'))
        return App(tree(d-1),tree(d-1))
    for _ in range(2000):compare(prefix(tree(m.depth)),rng.randrange(m.rounds+1))
    # Force S redexes; both arbitrary compound x/y and deeper duplicands.
    for _ in range(1000):
        x,y,z=tree(m.depth-3),tree(m.depth-2),tree(m.depth-1)
        expr=prefix(App(App(App(Leaf('S'),x),y),z))
        compare(expr,1);compare(expr,min(8,m.rounds))
    # All values through fixed slot copying, including retained partial combinators.
    for a in 'SKIabcdefghijklmnopqrstuvwxyz':
        for b in 'SKIabcdefghijklmnopqrstuvwxyz':
            compare(f'S ({a} b) ({b} c) (d e)',1)
    report={'tests':total,'statuses':dict(counts),'max_steps':max_steps,'seconds':time.perf_counter()-started,'harfbuzz':m.hb.version,'font_sha256':hashlib.sha256(Path(font).read_bytes()).hexdigest()}
    (report_dir/'test-results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    m.close();return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font',type=Path,default=DEFAULT_FONT)
    parser.add_argument('--report-dir',type=Path,default=ROOT/'build')
    args=parser.parse_args()
    check(args.font,args.report_dir)
