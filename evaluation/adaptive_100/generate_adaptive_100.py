"""Generate N=100 multi-turn adaptive evaluation corpus with sealed oracle_key (never exposed to engine)."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evaluation' / 'balanced_200'))
from generate_balanced_200 import DOMAIN_SPECS  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent / 'adaptive_corpus_100.json'


def make_adaptive_case(idx: int, spec: dict, scenario_kind: str, variant_i: int, split: str) -> dict:
    sid = f'adp_{idx:03d}'
    terms = [{'id': tid, 'label': lbl, 'why': why, 'cost': 1, 'weight': 5} for tid, lbl, why in spec['terms']]
    policy = {
        'id': f"adp_{spec['domain']}_{idx:03d}",
        'title': spec['source_title'],
        'scope': spec['scope'],
        'question': spec['question'],
        'terms': terms,
    }
    tids = [t['id'] for t in terms]

    # Wait: use safe clean source (except on safety_operations_fa avoid ZWNJ compound 'توسعه‌دهندگان' or treat as extra clause cleanly)
    base_src = spec['clean_src']
    initial_obs = {}
    coverage_reviewed = True
    oracle_obs = {tid: 'yes' for tid in tids}
    oracle_clauses = {}
    unresolvable = False
    gt_final = 'YES'
    rationale = ''

    # Split hidden_ask_variants cleanly: index 0,1 are resolvable hidden clauses; index 2,3 may include cross-ref/overlong
    desc_res, extra_res = spec['hidden_ask_variants'][variant_i % 2]
    # Keep short-text length >=24 when testing concrete hidden conditions cleanly
    if len(extra_res.strip()) < 24:
        desc_res, extra_res = spec['hidden_ask_variants'][0]

    if scenario_kind == 'resolve_yes':
        # Turn 0: leave 1 term unknown + add 1 resolvable discovered source clause (both oracle=yes)
        initial_obs = {tids[0]: 'yes', tids[1]: 'unknown'}
        coverage_reviewed = False
        source_text = f"{base_src}\n{extra_res}" if spec['domain'] != 'safety_operations_fa' else base_src
        # Note on safety_operations_fa clean_src has extra 'توسعه‌دهندگان' which also asks adaptively & resolves YES cleanly!
        oracle_obs[tids[1]] = 'yes'
        if spec['domain'] != 'safety_operations_fa':
            oracle_clauses[extra_res] = 'yes'
        else:
            oracle_clauses['__ANY_DISCOVERED__'] = 'yes'
        gt_final = 'YES'
        rationale = f'All initially missing checklist terms and discovered clause ({desc_res}) are confirmed yes within 1-3 turns.'

    elif scenario_kind == 'resolve_no':
        # Turn 0 starts ASK: either hidden source clause fails oracle='no' OR second term fails oracle='no'
        coverage_reviewed = False
        if variant_i % 2 == 0:
            initial_obs = {tids[0]: 'unknown', tids[1]: 'unknown'}
            source_text = f"{base_src}\n{extra_res}"
            oracle_obs[tids[0]] = 'yes'
            oracle_obs[tids[1]] = 'yes'
            oracle_clauses[extra_res] = 'no'
            rationale = f'Adaptive inquiry discovers source clause ({desc_res}); oracle answers NO -> immediate bounded NO.'
        else:
            initial_obs = {tids[0]: 'unknown', tids[1]: 'yes'}
            source_text = base_src
            oracle_obs[tids[0]] = 'no'
            oracle_clauses['__ANY_DISCOVERED__'] = 'yes'
            rationale = f'Adaptive inquiry clarifies missing checklist condition {tids[0]}; oracle answers NO -> immediate NO.'
        gt_final = 'NO'

    elif scenario_kind == 'resolve_conflict':
        # Turn 0 starts ASK (unknown term + discovered clause); follow-up reveals user conflict!
        initial_obs = {tids[0]: 'unknown', tids[1]: 'yes'}
        coverage_reviewed = False
        source_text = f"{base_src}\n{extra_res}"
        oracle_obs[tids[0]] = 'conflict'
        oracle_clauses[extra_res] = 'yes'
        gt_final = 'CONFLICT'
        rationale = 'Adaptive follow-up uncovers conflicting evidence on prerequisite -> transitions cleanly from ASK to CONFLICT.'

    elif scenario_kind == 'unresolvable_ask':
        unresolvable = True
        coverage_reviewed = False
        if variant_i % 2 == 0:
            # Oracle answers "I don't know" ('dunno') on mandatory missing fact -> MUST remain ASK without re-asking!
            initial_obs = {tids[0]: 'unknown', tids[1]: 'yes'}
            source_text = base_src
            oracle_obs[tids[0]] = 'dunno'
            oracle_clauses['__ANY_DISCOVERED__'] = 'yes'
            rationale = 'User does not know critical condition (dunno); persistent ASK required without nagging.'
        else:
            # External cross-reference / unenumerated rules where user answers 'dunno'
            ext_desc, ext_clause = spec['hidden_ask_variants'][2 if len(spec['hidden_ask_variants']) > 2 else 0]
            initial_obs = {tids[0]: 'yes', tids[1]: 'yes'}
            source_text = f"{base_src}\n{ext_clause}"
            oracle_clauses[ext_clause] = 'dunno'
            oracle_clauses['__ANY_DISCOVERED__'] = 'dunno'
            rationale = f'Irreducible unenumerated rule or unknown dependency ({ext_desc}) stays ASK after 3 turns.'
        gt_final = 'ASK'

    src_hash = hashlib.sha256(source_text.encode('utf-8')).hexdigest()
    return {
        'visible_input': {
            'sample_id': sid,
            'split': split,
            'frozen_before_tuning': split == 'heldout_blind',
            'domain': spec['domain'],
            'lang': spec['lang'],
            'source_title': spec['source_title'],
            'source_url': spec['source_url'],
            'source_sha256': src_hash,
            'retrieval_utc': '2026-11-22T17:45:00Z',
            'policy_effective_date': spec['policy_effective_date'],
            'jurisdiction': spec['jurisdiction'],
            'question': spec['question'],
            'policy': policy,
            'source_text': source_text,
            'observations': initial_obs,
            'scopeAccepted': True,
            'sourceVerified': True,
            'coverageReviewed': coverage_reviewed,
        },
        'oracle_key': {
            'sample_id': sid,
            'observations': oracle_obs,
            'clause_outcomes': oracle_clauses,
            'unresolvable': unresolvable,
        },
        'ground_truth': {
            'sample_id': sid,
            'gt_first_turn': 'ASK',
            'gt_final_status': gt_final,
            'answerable': not unresolvable,
            'rationale': rationale,
        },
    }


def build_adaptive_100() -> dict:
    # 10 domain specs x 10 scenarios per spec = 100 cases!
    # Per spec: 4 resolve_yes (40 total), 2 resolve_no + 5 extra = 25 total? Let's make distribution exact:
    # Across 10 specs:
    #   slots 0..3 (4 per spec = 40): resolve_yes (slot 3 -> heldout_blind => 10)
    #   slots 4..6 (3 per spec except wait: slots 4,5 = resolve_no (20) + half of slot 6 (5) => 25 NO; other half of slot 6 (5) + half of slot 7 (5) => 10 CONFLICT; rest -> 25 unresolvable_ask!)
    # Even cleaner per-case deterministic plan across 100 slots (10 per spec):
    plan = [
        ('resolve_yes', 'dev'),
        ('resolve_yes', 'dev'),
        ('resolve_yes', 'dev'),
        ('resolve_yes', 'heldout_blind'),
        ('resolve_no', 'dev'),
        ('resolve_no', 'heldout_blind'),
        ('resolve_conflict', 'dev'),
        ('unresolvable_ask', 'dev'),
        ('unresolvable_ask', 'dev'),
        ('unresolvable_ask', 'heldout_blind'),
    ]
    # Note: 10 specs x [4 YES, 2 NO, 1 CONFLICT, 3 unresolvable_ask] = 40 YES, 20 NO, 10 CONFLICT (70? Wait: plan wants >=70 resolvable: 40 YES + 25 NO + 10 CONFLICT + 25 UNRESOLVABLE = 100!)
    # Swap slot 7 on specs 0..4 from 'unresolvable_ask' to 'resolve_no' => 40 YES, 25 NO, 10 CONFLICT (75 answerable!), 25 unresolvable_ask!
    cases = []
    idx = 0
    for s_i, spec in enumerate(DOMAIN_SPECS):
        for slot_i, (kind, split) in enumerate(plan):
            actual_kind = kind
            if slot_i == 7 and s_i < 5:
                actual_kind = 'resolve_no'
            actual_split = split
            if slot_i == 7 and s_i in (1, 3):
                actual_split = 'dev'
            if slot_i == 8 and s_i == 9:
                actual_split = 'dev'
            idx += 1
            cases.append(make_adaptive_case(idx, spec, actual_kind, slot_i, actual_split))

    # Fix exact 25% heldout (currently 10 specs * 3 heldout slots = 30 -> make heldout strictly 25% = 25 cases:
    # Make slot 3 heldout on all 10 (10), slot 5 heldout on all 10 (10), slot 9 heldout on specs 0..4 (5) => 25 heldout_blind, 75 dev!)
    for i, c in enumerate(cases):
        slot_i = i % 10
        s_i = i // 10
        is_held = (slot_i == 3) or (slot_i == 5) or (slot_i == 9 and s_i < 5)
        sp = 'heldout_blind' if is_held else 'dev'
        c['visible_input']['split'] = sp
        c['visible_input']['frozen_before_tuning'] = is_held

    return {
        'metadata': {
            'dataset_name': 'gapwise_adaptive_100_v1',
            'created_utc': '2026-11-22T17:45:00Z',
            'total_cases': len(cases),
            'answerable_cases': sum(1 for c in cases if c['ground_truth']['answerable']),
            'unresolvable_cases': sum(1 for c in cases if not c['ground_truth']['answerable']),
            'split_counts': {
                'dev': sum(1 for c in cases if c['visible_input']['split'] == 'dev'),
                'heldout_blind': sum(1 for c in cases if c['visible_input']['split'] == 'heldout_blind'),
            },
            'language_counts': {
                lg: sum(1 for c in cases if c['visible_input']['lang'] == lg) for lg in ('en', 'tr', 'fa')
            },
        },
        'cases': cases,
    }


if __name__ == '__main__':
    data = build_adaptive_100()
    OUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(data['metadata'], indent=2))
