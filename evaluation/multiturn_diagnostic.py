"""Adversarial / fixed-world *independent* Logic-Q-MT simulator.

NOT the MT-InfoSeek author's canonical evaluation. No LLM and no GT labels
are passed to the policy/oracle, regardless of selected mode. Fixed world
uses the least Horn model (a coherent but unrepresentative possible world).
Adversarial answers may differ by policy. Use author runner for public scores.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,random,statistics,time
from pathlib import Path
from dataclasses import replace
from logic_engine_v8 import HornEngine


def least_model(engine):
    T=set(engine.true_init)
    if not engine.satisfiable():raise ValueError('Inconsistent puzzle')
    changed=True
    while changed:
        changed=False
        for body,head in engine.rules:
            if head and all(x in T for x in body) and head not in T:
                T.add(head);changed=True
    return frozenset(T)


def choose_candidate(engine, strategy, rng, used):
    remaining=[x for x in engine.candidates if x not in used]
    if not remaining:return None
    if strategy=='alphabetical':return sorted(remaining)[0]
    if strategy=='random':return rng.choice(remaining)
    if strategy=='horn':
        rank=engine.rank_one()
        for it in rank.get('ranked',[]):
            if it['question'] in remaining:return it['question']
        return remaining[0]
    raise ValueError(strategy)


def possible_branch(engine,q,answer):
    if answer:return engine.satisfiable(frozenset([q]),frozenset())
    return engine.satisfiable(frozenset(),frozenset([q]))


def branch_status(engine,q,answer):
    if answer:return engine.goal_status(frozenset([q]),frozenset())
    return engine.goal_status(frozenset(),frozenset([q]))


def choose_oracle_reply(engine,q,world,mode,rng):
    if mode=='least_world':return q in world
    if mode=='adversarial':
        branches=[]
        for val in (False,True):
            if not possible_branch(engine,q,val):continue
            status=branch_status(engine,q,val)
            # Choose an unknown branch if possible. When both survive,
            # tie-break deterministically to a false answer; NOT author's oracle.
            branches.append((status=='UNKNOWN',not val,val))
        if not branches:raise RuntimeError('No feasible oracle branch')
        branches.sort(reverse=True)
        return branches[0][2]
    raise ValueError(mode)


def play(row,strategy,mode,budget,seed):
    base=HornEngine.from_row(row,max_solve_queries=500)
    world=least_model(base)
    rng=random.Random(seed)
    known_true=set(base.true_init);known_false=set(base.false_init)
    history=[]
    for turn in range(budget+1):
        current=replace(base,true_init=frozenset(known_true),false_init=frozenset(known_false))
        status=current.goal_status()
        if status!='UNKNOWN':return dict(status=status,resolved=status in ('TRUE','FALSE'),steps=len(history),history=history)
        if turn==budget:break
        q=choose_candidate(current,strategy,rng,set(known_true)|set(known_false))
        if not q:break
        a=choose_oracle_reply(current,q,world,mode,rng)
        (known_true if a else known_false).add(q)
        history.append({'question':q,'answer':a})
    return dict(status='UNKNOWN',resolved=False,steps=len(history),history=history)


def evaluate(rows,strategies=('horn','alphabetical','random'),modes=('least_world','adversarial'),budget=10,seed=20261120):
    results=[];meta=[]
    for i,row in enumerate(rows):
        # Never pass ground-truth labels, alternative GT sets or oracle outcomes
        # from the dataset into the predictor. Side effect: no official score.
        restricted={k:row[k] for k in ('rules','known_facts','known_untrue_facts','cannot_ask_facts','goal','all_valid_qs','all_qs') if k in row}
        try:
            for mode in modes:
                for method in strategies:
                    res=play(restricted,method,mode,budget,seed+i*101)
                    results.append({'row':i,'sample_id':row.get('sample_id',str(i)),'k':row.get('k'),
                        'oracle_mode':mode,'strategy':method,'resolved':res['resolved'],
                        'status':res['status'],'steps':res['steps'],'trace':json.dumps(res['history'],ensure_ascii=False)})
        except Exception as exc:
            meta.append({'row':i,'exception':repr(exc)})
    summary=[]
    for mode in modes:
        for method in strategies:
            matches=[r for r in results if r['oracle_mode']==mode and r['strategy']==method]
            success=[r for r in matches if r['resolved']]
            summary.append({'oracle_mode':mode,'method':method,'n':len(matches),'resolved_rate':round(len(success)/len(matches),4) if matches else None,'avg_questions':round(statistics.mean(r['steps'] for r in matches),3) if matches else None,'avg_questions_successful':round(statistics.mean(r['steps'] for r in success),3) if success else None})
    return summary,results,meta


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--csv',required=True);ap.add_argument('--out',required=True);ap.add_argument('--limit',type=int,default=120);ap.add_argument('--budget',type=int,default=10);args=ap.parse_args()
    path=Path(args.csv);raw=path.read_bytes();rows=list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
    if args.limit>0 and len(rows)>args.limit:
        # MT-InfoSeek CSV is sorted by k=1,2,3: use balanced strata.
        groups={}
        for row in rows:groups.setdefault(row.get('k','one'),[]).append(row)
        rng=random.Random(20261120)
        if len(groups)>1:
            base=args.limit//len(groups); extra=args.limit%len(groups)
            picked=[]
            for j,k in enumerate(sorted(groups)):
                n=min(len(groups[k]),base+(j<extra))
                picked.extend(rng.sample(groups[k],n))
            rows=picked
        else:rows=rng.sample(rows,args.limit)
    start=time.time();summary,details,failures=evaluate(rows,budget=args.budget)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    (out/'summary.json').write_text(json.dumps({'dataset_path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'evaluated_rows':len(rows),'budget':args.budget,'not_official_author_evaluation':True,'world_modes':['least_world','adversarial'],'statistics':summary,'failures':failures,'seconds':round(time.time()-start,2)},indent=2,ensure_ascii=False))
    with (out/'per_case.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(details[0]) if details else ['row']);w.writeheader();w.writerows(details)
    print((out/'summary.json').read_text());return int(bool(failures))
if __name__=='__main__':raise SystemExit(main())
