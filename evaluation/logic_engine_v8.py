"""Exact Horn-CNF consistency and ask-one decision solver for Logic-Q.

No labels are read by the solver. Reference gt_qs is only parsed by evaluation module.
This implementation is closed-world ONLY over the supplied rule vocabulary, never
certifies that a natural-language problem has no omitted concepts.
"""
from __future__ import annotations
import ast
import json
import re
from functools import lru_cache
from dataclasses import dataclass


def parse_literal_collection(value):
    if isinstance(value, (list, tuple, set, dict)):
        return value
    if value is None or str(value).strip().lower() in ('','none','nan','null'):
        return []
    for fn in (json.loads,ast.literal_eval):
        try: return fn(str(value))
        except (ValueError,SyntaxError,TypeError): pass
    return [str(value)]


def names(value):
    x=parse_literal_collection(value)
    if isinstance(x,dict): return sorted(str(k) for k in x)
    if isinstance(x,(list,tuple,set)): return [str(z).strip() for z in x]
    return [str(x).strip()] if x else []


def norm(s):
    return re.sub(r'\s+',' ',str(s).strip().lower()).strip(' .?"\'')


def gt_sets(value):
    """MT returns [['a','b'], ['c','d']]; Quest returns ['a','b'].
    Scalar strings containing serialized arrays are recursively parsed; none is
    exposed to the predictor. For Quest, each entry is one sufficient question.
    """
    x=parse_literal_collection(value)
    if isinstance(x,str): x=parse_literal_collection(x)
    if not isinstance(x,(list,tuple,set)): return []
    if not x: return []
    if all(isinstance(y,str) for y in x):
        # Optional nested serialized inner list strings, e.g. ["['a','b']"].
        parsed=[parse_literal_collection(y) for y in x]
        if all(isinstance(y,(list,tuple,set)) for y in parsed):
            return [frozenset(norm(z) for z in y) for y in parsed]
        return [frozenset([norm(y)]) for y in x]
    out=[]
    for seq in x:
        if isinstance(seq,(list,tuple,set)):
            out.append(frozenset(norm(z) for z in seq))
        elif isinstance(seq,str):
            q=parse_literal_collection(seq)
            out.append(frozenset(norm(z) for z in q) if isinstance(q,(list,tuple,set)) else frozenset([norm(seq)]))
    return out


@dataclass(frozen=True)
class HornEngine:
    rules: tuple
    true_init: frozenset
    false_init: frozenset
    goal: str
    candidates: tuple
    max_solve_queries: int = 50

    @classmethod
    def from_row(cls,r,max_solve_queries=50):
        rules=[]
        for clause in parse_literal_collection(r['rules']):
            lits=names(clause)
            pos=[norm(t) for t in lits if not t.startswith('not ')]
            neg=[norm(t[4:]) for t in lits if t.startswith('not ')]
            if len(pos)>1: raise ValueError('Non-Horn input: '+str(clause))
            rules.append((tuple(neg),pos[0] if pos else None))
        known_true=frozenset(map(norm,names(r.get('known_facts','[]'))))
        known_false=frozenset(map(norm,names(r.get('known_untrue_facts','[]'))))
        banned=set(map(norm,names(r.get('cannot_ask_facts','[]'))))
        goal=norm(r['goal'])
        raw=names(r.get('all_valid_qs','[]'))
        if not raw: raw=names(r.get('all_qs','[]'))
        cand=tuple(sorted(set(map(norm,raw))-known_true-known_false-banned-{goal}))
        return cls(tuple(rules),known_true,known_false,goal,cand,max_solve_queries)

    @lru_cache(maxsize=100_000)
    def satisfiable(self, extra_true=frozenset(),extra_false=frozenset()):
        """Complete satisfiability for propositional Horn CNF.
        Forward-chain to least model. Negative-only clauses and explicitly false
        facts must not be triggered by least model. This algorithm is sound and
        complete for Horn CNF, not arbitrary propositional CNF.
        """
        T=set(self.true_init)|set(extra_true)
        F=set(self.false_init)|set(extra_false)
        if T&F: return False
        while True:
            added=False
            for body,head in self.rules:
                if all(ant in T for ant in body):
                    if head is None or head in F:return False
                    if head not in T:
                        T.add(head);added=True
            if not added:break
        return not bool(T&F)

    @lru_cache(maxsize=100_000)
    def goal_status(self,extra_true=frozenset(),extra_false=frozenset()):
        if not self.satisfiable(extra_true,extra_false):return 'INCONSISTENT'
        t=self.satisfiable(extra_true|frozenset([self.goal]),extra_false)
        f=self.satisfiable(extra_true,extra_false|frozenset([self.goal]))
        if not f:return 'TRUE'
        if not t:return 'FALSE'
        return 'UNKNOWN'

    def rank_one(self):
        status=self.goal_status()
        if status!='UNKNOWN':return {'action':'END' if status!='INCONSISTENT' else 'CONFLICT','status':status, 'ranked':[]}
        items=[]
        for attr in self.candidates[:self.max_solve_queries]:
            t=frozenset([attr]); f=frozenset([attr]);
            poss=self.satisfiable(t,frozenset());negs=self.satisfiable(frozenset(),f)
            if not poss and not negs:continue
            st=self.goal_status(t,frozenset()) if poss else 'IMPOSSIBLE'
            sf=self.goal_status(frozenset(),f) if negs else 'IMPOSSIBLE'
            unknown=sum(x=='UNKNOWN' for x in (st,sf))
            # valid question when both feasible branches are decisive.
            sufficient=(unknown==0)
            # score highest when it makes at least one branch decisive.
            decisive=sum(x in ('TRUE','FALSE') for x in (st,sf))
            relevance=sum(1 for ant,head in self.rules if attr in ant and head==self.goal)
            items.append((sufficient,decisive,relevance,-unknown,attr,st,sf,poss,negs))
        items.sort(reverse=True)
        if not items:return {'action':'ABSTAIN','status':status,'ranked':[]}
        return {'action':items[0][4],'status':status,'ranked':[
            {'question':q,'sufficient':bool(s),'decisive_branches':d,'if_yes':yes,'if_no':no,
             'yes_possible':yp,'no_possible':np}
            for s,d,_,_,q,yes,no,yp,np in items]}

    def verify_first_question(self,name):
        x=norm(name)
        if x not in self.candidates:return {'legal':False,'sufficient':False}
        if self.goal_status()!='UNKNOWN':return {'legal':True,'sufficient':False}
        p=self.satisfiable(frozenset([x]),frozenset())
        n=self.satisfiable(frozenset(),frozenset([x]))
        s1=self.goal_status(frozenset([x]),frozenset()) if p else 'IMPOSSIBLE'
        s0=self.goal_status(frozenset(),frozenset([x])) if n else 'IMPOSSIBLE'
        return {'legal':True,'sufficient': all(s!='UNKNOWN' for s in (s1,s0)), 'if_yes':s1,'if_no':s0}


def is_member_any_gt(name,gt):
    return bool(name and any(norm(name) in gt_set for gt_set in gt))


def minimal_gt_size(gt):
    return min((len(x) for x in gt),default=0)


def parse_candidate_from_model(raw,candidates):
    """Accept an exact candidate, index, or simple question; never accept a multi-property query."""
    q=str(raw).strip()
    for token in (q,q.splitlines()[0].strip()):
        m=re.search(r'(?:^|\b)(?:choice|option|index|answer)\s*[:=]\s*(\d+)\b',token,re.I)
        if m:
            ix=int(m.group(1));return candidates[ix-1] if 1<=ix<=len(candidates) else None
        m=re.fullmatch(r'\s*(\d+)\s*',token)
        if m:
            ix=int(m.group(1));return candidates[ix-1] if 1<=ix<=len(candidates) else None
        m=re.search(r'(?:is\s+alice\s+)([^?\n]+)',token,re.I)
        if m:token=m.group(1)
        lookup={norm(x):x for x in candidates}
        if norm(token) in lookup:return lookup[norm(token)]
    return None
