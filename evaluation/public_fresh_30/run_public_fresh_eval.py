"""
Run zero-leakage evaluation on fresh_public_corpus_30.json ONCE without tuning.
Outputs structured report with full 5x5 confusion matrix, precision/recall/F1,
Wilson 95% CIs, p50/p95 latencies, EN/TR/FA breakdown, and honest miss list into evidence/EVAL_PUBLIC_SOURCES/.
"""
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CORPUS_PATH = HERE / 'fresh_public_corpus_30.json'
RUNNER_PATH = HERE / 'public_fresh_runner.mjs'
OUT_DIR = ROOT / 'evidence' / 'EVAL_PUBLIC_SOURCES'
CLASSES = ['YES', 'NO', 'ASK', 'CONFLICT', 'OUT_OF_SCOPE']
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


def percentile(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    idx = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return round(s[idx], 3)


def analyze(cases: list[dict], preds: list[dict]) -> dict:
    n = len(cases)
    matrix = {gt: {pr: 0 for pr in CLASSES} for gt in CLASSES}
    exact = 0
    false_yes = 0
    lats = []
    misses = []
    for c, p in zip(cases, preds):
        v = c['visible_input']
        g = c['ground_truth']
        gt = g['gt_decision']
        dec = p['decision']
        lats.append(float(p.get('latency_ms', 0.0)))
        matrix[gt][dec] = matrix[gt].get(dec, 0) + 1
        if dec == gt:
            exact += 1
        else:
            misses.append({
                'sample_id': v['sample_id'],
                'lang': v['lang'],
                'domain': v['domain'],
                'gt': gt,
                'pred': dec,
                'novel_labels': p.get('novel_labels', []),
                'rationale': g['rationale'],
            })
        if dec == 'YES' and gt != 'YES':
            false_yes += 1

    per_class = {}
    for cls in CLASSES:
        tp = matrix[cls][cls]
        fp = sum(matrix[other][cls] for other in CLASSES if other != cls)
        fn = sum(matrix[cls][other] for other in CLASSES if other != cls)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        per_class[cls] = {
            'support': tp + fn,
            'tp': tp,
            'fp': fp,
            'fn': fn,
            'precision': round(prec, 4),
            'recall': round(rec, 4),
            'f1': round(f1, 4),
        }

    by_lang = {}
    for lang in ('en', 'tr', 'fa'):
        sub_c = [(c, p) for c, p in zip(cases, preds) if c['visible_input']['lang'] == lang]
        sn = len(sub_c)
        sx = sum(1 for c, p in sub_c if c['ground_truth']['gt_decision'] == p['decision'])
        sfy = sum(1 for c, p in sub_c if p['decision'] == 'YES' and c['ground_truth']['gt_decision'] != 'YES')
        by_lang[lang] = {
            'n': sn,
            'exact_acc': round(sx / sn, 4) if sn else 0.0,
            'exact_num': f'{sx}/{sn}',
            'wilson95': wilson_ci(sx, sn),
            'false_yes': sfy,
        }

    return {
        'cases_evaluated': n,
        'errors_in_denominator': 0,
        'exact_accuracy': round(exact / n, 4),
        'exact_numerator': f'{exact}/{n}',
        'exact_accuracy_wilson95': wilson_ci(exact, n),
        'false_yes_count': false_yes,
        'false_yes_rate': round(false_yes / n, 4),
        'false_yes_wilson95': wilson_ci(false_yes, n),
        'p50_latency_ms': percentile(lats, 0.50),
        'p95_latency_ms': percentile(lats, 0.95),
        'confusion_matrix': matrix,
        'per_class_metrics': per_class,
        'by_language': by_lang,
        'misses': misses,
    }


def main():
    raw_bytes = CORPUS_PATH.read_bytes()
    corpus_sha = hashlib.sha256(raw_bytes).hexdigest()
    corpus = json.loads(raw_bytes.decode('utf-8'))
    cases = corpus['cases']
    visible = [c['visible_input'] for c in cases]
    proc = subprocess.run(
        [NODE_EXE, str(RUNNER_PATH)],
        input=json.dumps(visible, ensure_ascii=False),
        text=True,
        encoding='utf-8',
        capture_output=True,
        check=True,
        cwd=str(ROOT),
    )
    out = json.loads(proc.stdout)
    results = {
        'dataset': corpus['metadata']['dataset_name'],
        'corpus_sha256': corpus_sha,
        'adjudication_disclosure': 'Single-author rubric frozen prior to evaluation run; zero tuning applied on this corpus.',
        'methods': {k: analyze(cases, v) for k, v in out.items()},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / 'FRESH_PUBLIC_30_SUMMARY.json').write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8'
    )

    with open(OUT_DIR / 'FRESH_PUBLIC_30_RESULTS.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                'sample_id', 'lang', 'domain', 'source_key', 'source_url', 'source_file_sha256',
                'gt_decision', 'naive_pred', 'permissive_pred', 'gapwise_pred',
                'gapwise_correct', 'novel_count', 'conflict_signals', 'provenance_valid', 'latency_ms',
            ],
        )
        w.writeheader()
        for c, nv, pm, gw in zip(cases, out['naive_checklist'], out['permissive_doc_baseline'], out['gapwise_strict_one_turn']):
            v = c['visible_input']
            gt = c['ground_truth']['gt_decision']
            w.writerow({
                'sample_id': v['sample_id'],
                'lang': v['lang'],
                'domain': v['domain'],
                'source_key': v['source_key'],
                'source_url': v['source_url'],
                'source_file_sha256': v['source_file_sha256'],
                'gt_decision': gt,
                'naive_pred': nv['decision'],
                'permissive_pred': pm['decision'],
                'gapwise_pred': gw['decision'],
                'gapwise_correct': gw['decision'] == gt,
                'novel_count': gw.get('novel_count', 0),
                'conflict_signals': gw.get('conflict_signals', 0),
                'provenance_valid': gw.get('provenance_valid', False),
                'latency_ms': gw.get('latency_ms', 0.0),
            })

    print(json.dumps({
        'corpus_sha256': corpus_sha,
        'summary': {
            m: {
                'exact': d['exact_numerator'],
                'acc': d['exact_accuracy'],
                'ci95': d['exact_accuracy_wilson95'],
                'false_yes': d['false_yes_count'],
                'p50_ms': d['p50_latency_ms'],
                'p95_ms': d['p95_latency_ms'],
                'misses': [(x['sample_id'], x['gt'], x['pred']) for x in d['misses']],
            }
            for m, d in results['methods'].items()
        }
    }, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
