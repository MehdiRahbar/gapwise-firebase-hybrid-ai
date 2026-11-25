"""Evaluate GAPWISE on real-world public documents with strict dev / heldout_blind separation."""
import argparse
import csv
import json
import math
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = Path(__file__).resolve().parent / 'real_world_corpus.json'
RUNNER_PATH = Path(__file__).resolve().parent / 'real_world_runner.mjs'
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


def matches_hidden(pred_labels: list[str], gt: dict) -> bool:
    reqs = [r.lower() for r in gt.get('hidden_requirements', [])]
    if not reqs:
        return False
    combined = ' '.join(pred_labels).lower()
    hits = sum(1 for r in reqs if r in combined)
    return hits >= 1


def score(cases: list[dict], preds: list[dict]) -> tuple[dict, list[dict]]:
    n = len(cases)
    exact = 0
    false_yes = 0
    pred_yes = 0
    ask_count = 0
    cond_gt = 0
    cond_tp = 0
    misses = []
    rows = []
    for c, pr in zip(cases, preds):
        v = c['visible_input']
        g = c['ground_truth']
        dec = pr['decision']
        gt_dec = g['gt_decision']
        if dec == gt_dec:
            exact += 1
        else:
            misses.append({
                'sample_id': v['sample_id'],
                'lang': v['lang'],
                'domain': v['domain'],
                'gt': gt_dec,
                'pred': dec,
                'novel_labels': pr.get('novel_labels', []),
                'truncated_count': pr.get('truncated_count', 0),
                'rationale': g['rationale'],
            })
        if dec == 'YES':
            pred_yes += 1
            if gt_dec != 'YES':
                false_yes += 1
        if dec == 'ASK':
            ask_count += 1
        if g.get('hidden_requirements'):
            cond_gt += 1
            if matches_hidden(pr.get('novel_labels', []), g) and pr.get('provenance_valid'):
                cond_tp += 1
        rows.append({
            'sample_id': v['sample_id'],
            'split': v['split'],
            'domain': v['domain'],
            'lang': v['lang'],
            'source_url': v['source_url'],
            'captured_utc': v['captured_utc'],
            'gt_decision': gt_dec,
            'pred_decision': dec,
            'correct': dec == gt_dec,
            'novel_count': pr.get('novel_count', 0),
            'truncated_count': pr.get('truncated_count', 0),
            'provenance_valid': pr.get('provenance_valid', False),
            'latency_ms': pr.get('latency_ms', 0.0),
        })
    metrics = {
        'cases_evaluated': n,
        'exact_accuracy': round(exact / n, 4) if n else 0.0,
        'exact_accuracy_wilson95': wilson_ci(exact, n),
        'false_yes_count': false_yes,
        'false_yes_rate': round(false_yes / n, 4) if n else 0.0,
        'false_yes_among_yes': round(false_yes / pred_yes, 4) if pred_yes else 0.0,
        'hidden_condition_recall': round(cond_tp / cond_gt, 4) if cond_gt else 0.0,
        'abstention_rate': round(ask_count / n, 4) if n else 0.0,
        'misses': misses,
    }
    return metrics, rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--split', default='dev', choices=['dev', 'heldout_blind', 'all'])
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
    naive_m, _ = score(cases, out['naive_checklist'])
    gap_m, rows = score(cases, out['gapwise_strict'])
    summary = {
        'dataset': corpus['metadata']['dataset_name'],
        'split': args.split,
        'naive_checklist': naive_m,
        'gapwise_strict': gap_m,
    }
    OUT_DIR.mkdir(exist_ok=True)
    if args.split == 'all':
        (OUT_DIR / 'real_world_eval.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
        with open(OUT_DIR / 'REAL_WORLD_RESULTS.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
