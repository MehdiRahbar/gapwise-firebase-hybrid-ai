"""Execute the 120-case blind benchmark and emit PER_CASE_RESULTS.csv + METRICS_SUMMARY.json."""
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'evidence'
OUT_DIR.mkdir(exist_ok=True)
_win_node = Path(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'NodeJS-24.20.0', 'node-v24.20.0-win-x64', 'node.exe')
NODE_EXE = str(_win_node) if _win_node.is_file() else (shutil.which('node.exe' if os.name == 'nt' else 'node') or 'node')
_backup_env = os.environ.get('GAPWISE_BACKUP_DIR', '')
BACKUP_DIR = Path(_backup_env) if _backup_env else None

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pregithub_blind_100 import build_blind_suite  # noqa: E402


def wilson_ci(k: int, n: int, z: float = 1.96) -> list[float]:
    if n <= 0:
        return [0.0, 0.0]
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = (z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)) / denom
    return [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)]


def matches_hidden_condition(pred_labels: list[str], gt: dict) -> bool:
    toks = [t.lower() for t in gt.get('hidden_tokens', [])]
    if not toks:
        return False
    combined = ' '.join(pred_labels).lower()
    hits = sum(1 for t in toks if t in combined)
    if gt.get('category') == 'internal_contradiction':
        return hits >= 1 or 'opposing' in combined or 'conflict' in combined
    return hits >= max(1, math.ceil(len(toks) * 0.6))


def summarize_method(name: str, visible_list: list[dict], gt_list: list[dict], preds: list[dict]) -> tuple[dict, list[dict]]:
    assert len(visible_list) == len(gt_list) == len(preds)
    n = len(preds)
    exact_ok = 0
    false_yes_all = 0
    pred_yes_count = 0
    gt_yes_count = 0
    true_yes_count = 0
    abstentions = 0
    errors_in_denom = 0

    cond_tp = 0
    cond_gt_total = 0
    cond_fp = 0
    need_q_total = 0
    valid_q_hits = 0
    latencies = []
    rows = []

    ranked_for_rc = []
    for vis, gt, pr in zip(visible_list, gt_list, preds):
        dec = pr['decision']
        gt_dec = gt['gt_decision']
        is_err = dec == 'ERROR' or pr.get('error_class', 'none') != 'none'
        if is_err:
            errors_in_denom += 1
        if dec == gt_dec:
            exact_ok += 1
        if dec == 'YES':
            pred_yes_count += 1
            if gt_dec != 'YES':
                false_yes_all += 1
            else:
                true_yes_count += 1
        if gt_dec == 'YES':
            gt_yes_count += 1
        if dec == 'ASK':
            abstentions += 1

        has_hidden = bool(gt.get('hidden_tokens'))
        matched_cond = False
        if has_hidden:
            cond_gt_total += 1
            if matches_hidden_condition(pr.get('novel_labels', []) + ([pr.get('predicted_condition', '')] if pr.get('predicted_condition') else []), gt) and (pr.get('provenance_valid') or gt['category'] == 'internal_contradiction'):
                cond_tp += 1
                matched_cond = True
        else:
            if gt_dec == 'YES' and pr.get('novel_labels'):
                cond_fp += 1

        if gt_dec == 'ASK':
            need_q_total += 1
            if str(pr.get('generated_question', '')).strip():
                valid_q_hits += 1

        latencies.append(float(pr.get('latency_ms', 0.0)))
        priority = {'OUT_OF_SCOPE': 4, 'NO': 3, 'CONFLICT': 3, 'YES': 2, 'ASK': 1}.get(dec, 0)
        ranked_for_rc.append((priority, 1 if dec != gt_dec else 0))

        rows.append({
            'sample_id': vis['sample_id'],
            'document_hash': vis['document_hash'],
            'domain': vis['domain'],
            'source_type': vis['source_type'],
            'question': vis['policy']['question'],
            'hidden_condition': gt['hidden_condition'],
            'gt_decision': gt_dec,
            'predicted_condition': pr.get('predicted_condition', ''),
            'generated_question': pr.get('generated_question', ''),
            'reference_quote': pr.get('reference_quote', ''),
            'provenance_valid': str(bool(pr.get('provenance_valid', False))).lower(),
            'decision': dec,
            'latency_ms': pr.get('latency_ms', 0.0),
            'inferenceSource': pr.get('inferenceSource', ''),
            'consent': pr.get('consent', ''),
            'error_class': pr.get('error_class', 'none'),
        })

    lat_sorted = sorted(latencies)
    median_lat = lat_sorted[len(lat_sorted) // 2] if lat_sorted else 0.0
    p95_idx = min(len(lat_sorted) - 1, math.floor(0.95 * len(lat_sorted)))
    p95_lat = lat_sorted[p95_idx] if lat_sorted else 0.0

    # Risk-coverage curve across non-ASK answered vs all points
    ranked_for_rc.sort(key=lambda x: -x[0])
    rc_curve = []
    for frac in (0.25, 0.50, 0.75, 1.0):
        k = max(1, math.ceil(frac * n))
        errs = sum(err for _, err in ranked_for_rc[:k])
        rc_curve.append({
            'target_fraction': frac,
            'cases_evaluated': k,
            'risk_error_rate': round(errs / k, 4),
        })

    non_abstention = n - abstentions
    cond_recall = round(cond_tp / cond_gt_total, 4) if cond_gt_total else 0.0
    cond_prec = round(cond_tp / (cond_tp + cond_fp), 4) if (cond_tp + cond_fp) else 0.0

    summary = {
        'method': name,
        'total_cases_in_denominator': n,
        'errors_in_denominator': errors_in_denom,
        'exact_decision_accuracy': round(exact_ok / n, 4),
        'exact_decision_accuracy_wilson95': wilson_ci(exact_ok, n),
        'false_yes_count': false_yes_all,
        'false_yes_rate_overall': round(false_yes_all / n, 4),
        'false_yes_rate_overall_wilson95': wilson_ci(false_yes_all, n),
        'accepted_yes_total': pred_yes_count,
        'false_yes_rate_among_accepted_yes': round(false_yes_all / pred_yes_count, 4) if pred_yes_count else 0.0,
        'clean_yes_recall_on_gt_yes': round(true_yes_count / gt_yes_count, 4) if gt_yes_count else 0.0,
        'clean_yes_recall_wilson95': wilson_ci(true_yes_count, gt_yes_count),
        'non_abstention_coverage': round(non_abstention / n, 4),
        'abstention_ask_rate': round(abstentions / n, 4),
        'condition_recall': cond_recall,
        'condition_recall_wilson95': wilson_ci(cond_tp, cond_gt_total),
        'condition_precision': cond_prec,
        'valid_question_rate': round(valid_q_hits / need_q_total, 4) if need_q_total else 0.0,
        'median_latency_ms': round(median_lat, 3),
        'p95_latency_ms': round(p95_lat, 3),
        'risk_coverage_curve': rc_curve,
    }
    return summary, rows


def main():
    suite = build_blind_suite()
    visible = [c['visible_input'] for c in suite]
    gt = [c['ground_truth'] for c in suite]

    args = [NODE_EXE, str(ROOT / 'evaluation' / 'pregithub_runner.mjs')]
    if BACKUP_DIR and (BACKUP_DIR / 'web' / 'source-audit.mjs').is_file():
        args.append(f'--backup={BACKUP_DIR.as_posix()}')

    proc = subprocess.run(
        args,
        input=json.dumps({'items': visible}, ensure_ascii=False).encode('utf-8'),
        capture_output=True,
        check=True,
        cwd=str(ROOT),
    )
    runner_out = json.loads(proc.stdout.decode('utf-8'))

    summaries = {}
    gapwise_rows = []
    for method_name, pred_list in runner_out.items():
        summary, rows = summarize_method(method_name, visible, gt, pred_list)
        summaries[method_name] = summary
        if method_name == 'gapwise_strict':
            gapwise_rows = rows

    # Breakdown by language and domain for gapwise_strict
    lang_breakdown = {}
    for lang in ('en', 'fa', 'tr'):
        sub_idx = [i for i, v in enumerate(visible) if v['language'] == lang]
        sub_vis = [visible[i] for i in sub_idx]
        sub_gt = [gt[i] for i in sub_idx]
        sub_pr = [runner_out['gapwise_strict'][i] for i in sub_idx]
        s, _ = summarize_method(f'gapwise_strict_{lang}', sub_vis, sub_gt, sub_pr)
        lang_breakdown[lang] = s

    fieldnames = [
        'sample_id', 'document_hash', 'domain', 'source_type', 'question', 'hidden_condition',
        'gt_decision', 'predicted_condition', 'generated_question', 'reference_quote',
        'provenance_valid', 'decision', 'latency_ms', 'inferenceSource', 'consent', 'error_class',
    ]
    csv_path = OUT_DIR / 'PER_CASE_RESULTS.csv'
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(gapwise_rows)

    live_path = OUT_DIR / 'live_hybrid_blind_summary.json'
    full_summary = {
        'benchmark': 'gapwise_pregithub_blind_120_v1',
        'total_cases': len(suite),
        'domains': sorted({v['domain'] for v in visible}),
        'languages': {l: sum(1 for v in visible if v['language'] == l) for l in ('en', 'fa', 'tr')},
        'methods': summaries,
        'gapwise_by_language': lang_breakdown,
    }
    if live_path.is_file():
        full_summary['live_hybrid_subset'] = json.loads(live_path.read_text(encoding='utf-8'))
    json_path = OUT_DIR / 'METRICS_SUMMARY.json'
    json_path.write_text(json.dumps(full_summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(full_summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
