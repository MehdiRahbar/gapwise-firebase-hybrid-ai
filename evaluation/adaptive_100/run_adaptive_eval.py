"""Execute N=100 multi-turn adaptive evaluation against sealed oracle_key and emit CSV + JSON reports."""
import argparse
import csv
import json
import math
import os
import shutil
import statistics
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = Path(__file__).resolve().parent / 'adaptive_corpus_100.json'
RUNNER_PATH = Path(__file__).resolve().parent / 'adaptive_runner.mjs'
OUT_DIR = ROOT / 'evidence'
_win_node = Path(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'NodeJS-24.20.0', 'node-v24.20.0-win-x64', 'node.exe')
NODE_EXE = str(_win_node) if _win_node.is_file() else (shutil.which('node.exe' if os.name == 'nt' else 'node') or 'node')


def wilson_ci(k: int, n: int, z: float = 1.96) -> list[float]:
    if n <= 0:
        return [0.0, 0.0]
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = (z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)) / denom
    return [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)]


def oracle_answer_for_question(q: dict, oracle: dict) -> tuple[str, bool]:
    """Return (oracle_action, is_question_relevant_to_oracle_missing)."""
    kind = q.get('kind', '')
    req_id = q.get('requirementId', '')
    if kind == 'term':
        ans = oracle['observations'].get(req_id, 'yes')
        # Relevant if term was actually missing/unanswered or unconfirmed
        return ans, (req_id in oracle['observations'])
    if kind in ('discovered-clause', 'ai-proposal'):
        lbl = q.get('label', '').strip()
        clause_map = oracle.get('clause_outcomes', {})
        for k, v in clause_map.items():
            if k != '__ANY_DISCOVERED__' and (k.strip() in lbl or lbl in k.strip()):
                return v, True
        if '__ANY_DISCOVERED__' in clause_map:
            return clause_map['__ANY_DISCOVERED__'], True
        return ('dunno' if oracle.get('unresolvable') else 'yes'), True
    if kind == 'conflict':
        return 'conflict', True
    return 'dunno', False


def summarize_rows(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {}
    answerable = [r for r in rows if r['answerable']]
    unresolvable = [r for r in rows if not r['answerable']]
    ans_n = len(answerable)
    unres_n = len(unresolvable)

    exact = sum(1 for r in rows if r['final_status'] == r['gt_final_status'])
    false_yes = sum(1 for r in rows if r['final_status'] == 'YES' and r['gt_final_status'] != 'YES')
    false_no = sum(1 for r in rows if r['final_status'] == 'NO' and r['gt_final_status'] != 'NO')

    gt_yes = [r for r in rows if r['gt_final_status'] == 'YES']
    pos_tp = sum(1 for r in gt_yes if r['final_status'] == 'YES')
    gt_no = [r for r in rows if r['gt_final_status'] == 'NO']
    no_tp = sum(1 for r in gt_no if r['final_status'] == 'NO')

    ans_unnecessary_ask = sum(1 for r in answerable if r['final_status'] == 'ASK')
    ans_resolved = sum(1 for r in answerable if r['final_status'] == r['gt_final_status'])
    unres_persistent_ask = sum(1 for r in unresolvable if r['final_status'] == 'ASK')

    total_q = sum(r['questions_asked'] for r in rows)
    rel_q = sum(r['relevant_questions'] for r in rows)
    cit_total = sum(r['source_citation_questions'] for r in rows)
    cit_valid = sum(r['verified_source_citations'] for r in rows)
    dups = sum(r['duplicate_questions'] for r in rows)

    turn_ask = {
        'turn0_ask_rate': round(sum(1 for r in rows if r['turn0_status'] == 'ASK') / n, 4),
        'turn1_ask_rate': round(sum(1 for r in rows if r['turn1_status'] == 'ASK') / n, 4),
        'turn2_ask_rate': round(sum(1 for r in rows if r['turn2_status'] == 'ASK') / n, 4),
        'turn3_ask_rate': round(sum(1 for r in rows if r['turn3_status'] == 'ASK') / n, 4),
    }

    q_counts = [r['questions_asked'] for r in rows]
    lats = [r['total_latency_ms'] for r in rows]
    refusals = sum(1 for r in rows if r['final_status'] in ('NO', 'CONFLICT', 'OUT_OF_SCOPE'))
    justified_asks = sum(1 for r in rows if r['final_status'] == 'ASK' and not r['answerable'])

    return {
        'cases_evaluated': n,
        'errors_in_denominator': 0,
        'exact_final_accuracy': round(exact / n, 4),
        'exact_final_accuracy_numerator': f"{exact}/{n}",
        'exact_final_accuracy_wilson95': wilson_ci(exact, n),
        **turn_ask,
        'answerable_cases': ans_n,
        'answerable_resolved_rate': round(ans_resolved / ans_n, 4) if ans_n else 0.0,
        'answerable_resolved_numerator': f"{ans_resolved}/{ans_n}",
        'answerable_unnecessary_ask_rate': round(ans_unnecessary_ask / ans_n, 4) if ans_n else 0.0,
        'answerable_unnecessary_ask_numerator': f"{ans_unnecessary_ask}/{ans_n}",
        'answerable_unnecessary_ask_wilson95': wilson_ci(ans_unnecessary_ask, ans_n),
        'unresolvable_cases': unres_n,
        'unresolvable_persistent_ask_rate': round(unres_persistent_ask / unres_n, 4) if unres_n else 0.0,
        'unresolvable_persistent_ask_numerator': f"{unres_persistent_ask}/{unres_n}",
        'positive_recall': round(pos_tp / len(gt_yes), 4) if gt_yes else 0.0,
        'positive_recall_numerator': f"{pos_tp}/{len(gt_yes)}",
        'positive_recall_wilson95': wilson_ci(pos_tp, len(gt_yes)),
        'negative_no_recall': round(no_tp / len(gt_no), 4) if gt_no else 0.0,
        'negative_no_recall_numerator': f"{no_tp}/{len(gt_no)}",
        'negative_no_recall_wilson95': wilson_ci(no_tp, len(gt_no)),
        'false_yes_count': false_yes,
        'false_no_count': false_no,
        'refusal_count': refusals,
        'justified_ask_count': justified_asks,
        'unnecessary_ask_count': ans_unnecessary_ask,
        'question_relevance_rate': round(rel_q / total_q, 4) if total_q else 1.0,
        'question_relevance_numerator': f"{rel_q}/{total_q}",
        'source_backed_citation_rate': round(cit_valid / cit_total, 4) if cit_total else 1.0,
        'source_backed_citation_numerator': f"{cit_valid}/{cit_total}",
        'duplicate_questions_count': dups,
        'mean_questions_per_case': round(statistics.mean(q_counts), 3),
        'median_questions_per_case': round(statistics.median(q_counts), 3),
        'mean_latency_ms': round(statistics.mean(lats), 3),
        'median_latency_ms': round(statistics.median(lats), 3),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--split', default='all', choices=['all', 'dev', 'heldout_blind'])
    args = parser.parse_args()

    corpus = json.loads(CORPUS_PATH.read_text(encoding='utf-8'))
    cases = corpus['cases'] if args.split == 'all' else [c for c in corpus['cases'] if c['visible_input']['split'] == args.split]

    proc = subprocess.Popen(
        [NODE_EXE, str(RUNNER_PATH)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        cwd=str(ROOT),
    )

    def rpc(obj: dict) -> dict:
        proc.stdin.write(json.dumps(obj, ensure_ascii=False) + '\n')
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError('Adaptive Node runner terminated unexpectedly')
        return json.loads(line)

    rows = []
    naive_correct = 0
    naive_false_yes = 0
    single_turn_correct = 0

    try:
        for case in cases:
            vis = case['visible_input']
            oracle = case['oracle_key']
            gt = case['ground_truth']

            init_out = rpc({'op': 'init', 'visible_input': vis})
            cur_policy = init_out['policy']
            cur_snap = init_out['snapshot']
            cur_plan = init_out['plan']

            turn_statuses = [init_out['single_turn_status']]
            total_ms = init_out['latency_ms']
            asked_uids = set()
            dups = 0
            q_count = 0
            rel_q = 0
            src_q = 0
            src_q_valid = 0

            if init_out['naive_status'] == gt['gt_final_status']:
                naive_correct += 1
            if init_out['naive_status'] == 'YES' and gt['gt_final_status'] != 'YES':
                naive_false_yes += 1
            if init_out['single_turn_status'] == gt['gt_final_status']:
                single_turn_correct += 1

            for turn_idx in range(1, 4):
                batch = cur_plan.get('recommendedBatch') or []
                if cur_plan['status'] != 'ASK' or not batch:
                    turn_statuses.append(cur_plan['status'])
                    continue
                responses = []
                for q in batch:
                    q_count += 1
                    qid = q.get('uid') or q.get('requirementId')
                    if qid in asked_uids:
                        dups += 1
                    asked_uids.add(qid)
                    ans, is_rel = oracle_answer_for_question(q, oracle)
                    if is_rel:
                        rel_q += 1
                    if q.get('kind') in ('discovered-clause', 'ai-proposal'):
                        src_q += 1
                        cit = q.get('sourceCitation') or {}
                        if cit.get('quoteVerified') and isinstance(cit.get('startOffset'), int) and cit['startOffset'] >= 0:
                            if vis['source_text'][cit['startOffset']:cit['endOffset']] == cit.get('quote'):
                                src_q_valid += 1
                    responses.append({
                        'kind': q.get('kind'),
                        'requirementId': q.get('requirementId'),
                        'action': ans,
                    })

                step_out = rpc({'op': 'step', 'policy': cur_policy, 'snapshot': cur_snap, 'responses': responses})
                cur_policy = step_out['policy']
                cur_snap = step_out['snapshot']
                cur_plan = step_out['plan']
                total_ms += step_out['latency_ms']
                turn_statuses.append(cur_plan['status'])

            rows.append({
                'sample_id': vis['sample_id'],
                'split': vis['split'],
                'domain': vis['domain'],
                'lang': vis['lang'],
                'answerable': gt['answerable'],
                'gt_first_turn': gt['gt_first_turn'],
                'gt_final_status': gt['gt_final_status'],
                'naive_status': init_out['naive_status'],
                'turn0_status': turn_statuses[0],
                'turn1_status': turn_statuses[1],
                'turn2_status': turn_statuses[2],
                'turn3_status': turn_statuses[3],
                'final_status': turn_statuses[3],
                'questions_asked': q_count,
                'relevant_questions': rel_q,
                'source_citation_questions': src_q,
                'verified_source_citations': src_q_valid,
                'duplicate_questions': dups,
                'total_latency_ms': round(total_ms, 3),
                'correct': str(turn_statuses[3] == gt['gt_final_status']).lower(),
            })
    finally:
        proc.stdin.close()
        proc.wait(timeout=10)

    overall = summarize_rows(rows)
    held_rows = [r for r in rows if r['split'] == 'heldout_blind']
    held_summary = summarize_rows(held_rows) if held_rows else None
    by_lang = {lg: summarize_rows([r for r in rows if r['lang'] == lg]) for lg in ('en', 'tr', 'fa') if any(r['lang'] == lg for r in rows)}
    by_dom = {dom: summarize_rows([r for r in rows if r['domain'] == dom]) for dom in sorted({r['domain'] for r in rows})}

    OUT_DIR.mkdir(exist_ok=True)
    if args.split == 'all':
        csv_path = OUT_DIR / 'EVAL_ADAPTIVE_RESULTS.csv'
        with csv_path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

        summary = {
            'dataset': corpus['metadata']['dataset_name'],
            'metadata': corpus['metadata'],
            'baseline_comparison': {
                'naive_checklist_final_accuracy': round(naive_correct / len(rows), 4),
                'naive_checklist_false_yes_count': naive_false_yes,
                'gapwise_strict_one_turn_accuracy': round(single_turn_correct / len(rows), 4),
                'gapwise_adaptive_3turn_accuracy': overall['exact_final_accuracy'],
            },
            'gapwise_adaptive_3turn_overall': overall,
            'gapwise_adaptive_3turn_heldout_blind': held_summary,
            'by_language': by_lang,
            'by_domain': by_dom,
        }
        (OUT_DIR / 'EVAL_ADAPTIVE_SUMMARY.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')

    print(json.dumps({
        'overall': overall,
        'heldout_blind': held_summary,
        'baseline_comparison': {
            'naive_checklist_false_yes_count': naive_false_yes,
            'single_turn_accuracy': round(single_turn_correct / len(rows), 4),
            'adaptive_3turn_accuracy': overall['exact_final_accuracy'],
        },
    }, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
