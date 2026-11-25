"""Execute balanced 200-case benchmark and emit evidence/EVAL_BALANCED_RESULTS.csv + EVAL_BALANCED_SUMMARY.json."""
import argparse
import csv
import json
import math
import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = Path(__file__).resolve().parent / 'balanced_corpus_200.json'
RUNNER_PATH = Path(__file__).resolve().parent / 'balanced_runner.mjs'
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


def compute_metrics(cases: list[dict], preds: list[dict]) -> dict:
    n = len(cases)
    exact = 0
    false_yes = 0
    pred_yes = 0
    gt_yes = 0
    true_yes = 0
    gt_no = 0
    true_no = 0
    justified_ask = 0
    unnecessary_ask = 0
    refusal_pred = 0
    err_denom = 0
    latencies = []
    misses = []
    class_matrix = Counter()

    for c, pr in zip(cases, preds):
        v = c['visible_input']
        g = c['ground_truth']
        gt = g['gt_decision']
        dec = pr['decision']
        latencies.append(float(pr.get('latency_ms', 0.0)))
        if pr.get('error_class', 'none') != 'none' or dec == 'ERROR':
            err_denom += 1
        class_matrix[f"{gt}->{dec}"] += 1
        if dec == gt:
            exact += 1
        else:
            misses.append({
                'sample_id': v['sample_id'],
                'split': v['split'],
                'lang': v['lang'],
                'domain': v['domain'],
                'gt': gt,
                'pred': dec,
                'rationale': g['rationale'],
            })
        if dec == 'YES':
            pred_yes += 1
            if gt != 'YES':
                false_yes += 1
            else:
                true_yes += 1
        if gt == 'YES':
            gt_yes += 1
        if gt == 'NO':
            gt_no += 1
            if dec == 'NO':
                true_no += 1
        if dec == 'ASK':
            if gt == 'ASK':
                justified_ask += 1
            else:
                unnecessary_ask += 1
        if dec in ('NO', 'CONFLICT', 'OUT_OF_SCOPE'):
            refusal_pred += 1

    ask_total = justified_ask + unnecessary_ask
    lat_sorted = sorted(latencies)
    med_lat = lat_sorted[len(lat_sorted) // 2] if lat_sorted else 0.0
    return {
        'cases_evaluated': n,
        'errors_in_denominator': err_denom,
        'exact_accuracy': round(exact / n, 4) if n else 0.0,
        'exact_accuracy_numerator': exact,
        'exact_accuracy_wilson95': wilson_ci(exact, n),
        'false_yes_count': false_yes,
        'false_yes_rate': round(false_yes / n, 4) if n else 0.0,
        'false_yes_wilson95': wilson_ci(false_yes, n),
        'positive_recall': round(true_yes / gt_yes, 4) if gt_yes else 0.0,
        'positive_recall_numerator': f"{true_yes}/{gt_yes}",
        'positive_recall_wilson95': wilson_ci(true_yes, gt_yes),
        'negative_no_recall': round(true_no / gt_no, 4) if gt_no else 0.0,
        'negative_no_recall_numerator': f"{true_no}/{gt_no}",
        'ask_total': ask_total,
        'justified_ask_count': justified_ask,
        'unnecessary_ask_count': unnecessary_ask,
        'ask_rate': round(ask_total / n, 4) if n else 0.0,
        'refusal_count': refusal_pred,
        'median_latency_ms': round(med_lat, 3),
        'confusion_counts': dict(sorted(class_matrix.items())),
        'misses_sample': misses[:15],
        'misses_total': len(misses),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--split', default='all', choices=['all', 'dev', 'heldout_blind'])
    args = parser.parse_args()

    corpus = json.loads(CORPUS_PATH.read_text(encoding='utf-8'))
    cases = corpus['cases'] if args.split == 'all' else [c for c in corpus['cases'] if c['visible_input']['split'] == args.split]
    visible_only = [c['visible_input'] for c in cases]

    proc = subprocess.run(
        [NODE_EXE, str(RUNNER_PATH)],
        input=json.dumps(visible_only, ensure_ascii=False),
        text=True,
        encoding='utf-8',
        capture_output=True,
        check=True,
        cwd=str(ROOT),
    )
    out = json.loads(proc.stdout)

    methods = {}
    for m_name, preds in out.items():
        m_all = compute_metrics(cases, preds)
        held_idx = [i for i, c in enumerate(cases) if c['visible_input']['split'] == 'heldout_blind']
        m_held = compute_metrics([cases[i] for i in held_idx], [preds[i] for i in held_idx]) if held_idx else None
        lang_stats = {}
        for lg in ('en', 'tr', 'fa'):
            li = [i for i, c in enumerate(cases) if c['visible_input']['lang'] == lg]
            if li:
                lang_stats[lg] = compute_metrics([cases[i] for i in li], [preds[i] for i in li])
        domain_stats = {}
        for dom in sorted({c['visible_input']['domain'] for c in cases}):
            di = [i for i, c in enumerate(cases) if c['visible_input']['domain'] == dom]
            domain_stats[dom] = compute_metrics([cases[i] for i in di], [preds[i] for i in di])
        methods[m_name] = {
            'overall': m_all,
            'heldout_blind': m_held,
            'by_language': lang_stats,
            'by_domain': domain_stats,
        }

    OUT_DIR.mkdir(exist_ok=True)
    if args.split == 'all':
        csv_path = OUT_DIR / 'EVAL_BALANCED_RESULTS.csv'
        fieldnames = [
            'sample_id', 'split', 'domain', 'lang', 'source_sha256', 'policy_effective_date',
            'jurisdiction', 'gt_decision', 'naive_checklist', 'permissive_doc_baseline',
            'gapwise_strict_one_turn', 'strict_correct', 'latency_ms', 'novel_count', 'conflict_signals',
        ]
        with csv_path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for idx, c in enumerate(cases):
                v = c['visible_input']
                gt = c['ground_truth']['gt_decision']
                st = out['gapwise_strict_one_turn'][idx]
                w.writerow({
                    'sample_id': v['sample_id'],
                    'split': v['split'],
                    'domain': v['domain'],
                    'lang': v['lang'],
                    'source_sha256': v['source_sha256'],
                    'policy_effective_date': v['policy_effective_date'],
                    'jurisdiction': v['jurisdiction'],
                    'gt_decision': gt,
                    'naive_checklist': out['naive_checklist'][idx]['decision'],
                    'permissive_doc_baseline': out['permissive_doc_baseline'][idx]['decision'],
                    'gapwise_strict_one_turn': st['decision'],
                    'strict_correct': str(st['decision'] == gt).lower(),
                    'latency_ms': st.get('latency_ms', 0.0),
                    'novel_count': st.get('novel_count', 0),
                    'conflict_signals': st.get('conflict_signals', 0),
                })

        summary = {
            'dataset': corpus['metadata']['dataset_name'],
            'split': args.split,
            'metadata': corpus['metadata'],
            'methods': methods,
        }
        (OUT_DIR / 'EVAL_BALANCED_SUMMARY.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')

    print(json.dumps({k: v['overall'] for k, v in methods.items()}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
