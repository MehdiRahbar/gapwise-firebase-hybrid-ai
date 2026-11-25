"""Independent blind evaluation across 40 multi-condition synthetic test cases.

Tests real JS web/engine.mjs + web/source-audit.mjs via Node without label leakage.
Not an official benchmark leaderboard score.
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOMAINS = [
    {
        "domain": "travel_rebooking",
        "question": "Can this airline ticket be rebooked without a change fee?",
        "scope": "Synthetic travel fare rules",
        "source": "Synthetic fare table",
        "terms": [
            {"id": "fare", "label": "Ticket is a flexible fare class", "why": "Basic fares exclude free changes", "cost": 1, "weight": 5},
            {"id": "window", "label": "Request is made at least 24 hours before departure", "why": "Late changes incur fee", "cost": 1, "weight": 4},
        ],
        "base_doc": "1. Ticket must be a flexible fare class.\n2. Request must be made at least 24 hours before departure.",
        "hidden_clause": "3. Passenger must hold confirmed seat assignment and must not have checked baggage.",
        "hidden_needle": "checked baggage",
    },
    {
        "domain": "warranty_claim",
        "question": "Is this hardware unit eligible for replacement under warranty?",
        "scope": "Synthetic device warranty terms",
        "source": "Synthetic warranty card",
        "terms": [
            {"id": "period", "label": "Purchase was within 12 months", "why": "Warranty expires at 12 months", "cost": 1, "weight": 5},
            {"id": "serial", "label": "Device serial number is legible", "why": "Serial verifies unit", "cost": 1, "weight": 4},
        ],
        "base_doc": "1. Purchase must be within 12 months.\n2. Device serial number must be legible.",
        "hidden_clause": "3. Internal liquid indicator must not show moisture exposure unless factory defect is verified.",
        "hidden_needle": "liquid indicator",
    },
    {
        "domain": "data_export",
        "question": "Can we export this dataset to an external partner?",
        "scope": "Synthetic data governance policy",
        "source": "Synthetic governance handbook",
        "terms": [
            {"id": "anonymized", "label": "Personal identifiers are removed", "why": "No raw PII allowed", "cost": 1, "weight": 5},
            {"id": "dpa", "label": "Partner signed a data processing agreement", "why": "Contract required", "cost": 2, "weight": 4},
        ],
        "base_doc": "1. Personal identifiers must be removed.\n2. Partner must have signed a data processing agreement.",
        "hidden_clause": "3. Security officer approval is required before cross-border transfer.",
        "hidden_needle": "Security officer approval",
    },
    {
        "domain": "lab_access",
        "question": "Can the visiting researcher enter the cleanroom?",
        "scope": "Synthetic facility access guidelines",
        "source": "Synthetic facility manual",
        "terms": [
            {"id": "training", "label": "Safety orientation is completed", "why": "Mandatory training", "cost": 1, "weight": 5},
            {"id": "badge", "label": "Temporary visitor badge is issued", "why": "Access control", "cost": 1, "weight": 4},
        ],
        "base_doc": "1. Safety orientation must be completed.\n2. Temporary visitor badge must be issued.",
        "hidden_clause": "3. Host supervisor escort is required during all cleanroom shifts.",
        "hidden_needle": "Host supervisor escort",
    },
]

def build_cases():
    cases = []
    idx = 0
    for d in DOMAINS:
        policy = {
            "id": f"blind_{d['domain']}",
            "title": d["domain"],
            "question": d["question"],
            "scope": d["scope"],
            "source": d["source"],
            "terms": d["terms"],
        }
        t0, t1 = d["terms"][0]["id"], d["terms"][1]["id"]
        # 10 scenario templates per domain -> 40 total blind cases
        templates = [
            ("TRUE_ALL_MET", d["base_doc"], {t0: "yes", t1: "yes"}, {}, True, "YES"),
            ("TRUE_WITH_HIDDEN_MET", d["base_doc"] + "\n" + d["hidden_clause"], {t0: "yes", t1: "yes"}, {d["hidden_needle"]: "yes"}, True, "YES"),
            ("FALSE_HIDDEN_CLAUSE_1", d["base_doc"] + "\n" + d["hidden_clause"], {t0: "yes", t1: "yes"}, {d["hidden_needle"]: "no"}, True, "NO"),
            ("FALSE_HIDDEN_CLAUSE_2", d["base_doc"] + "\n" + d["hidden_clause"], {t0: "yes", t1: "yes"}, {d["hidden_needle"]: "no"}, True, "NO"),
            ("ASK_HIDDEN_UNKNOWN", d["base_doc"] + "\n" + d["hidden_clause"], {t0: "yes", t1: "yes"}, {d["hidden_needle"]: "unknown"}, True, "ASK"),
            ("FALSE_KNOWN", d["base_doc"], {t0: "no", t1: "yes"}, {}, True, "NO"),
            ("ASK_KNOWN_MISSING", d["base_doc"], {t0: "yes", t1: "unknown"}, {}, True, "ASK"),
            ("CONFLICT_KNOWN", d["base_doc"], {t0: "conflict", t1: "yes"}, {}, True, "CONFLICT"),
            ("OUT_OF_SCOPE", d["base_doc"], {t0: "yes", t1: "yes"}, {}, False, "OUT_OF_SCOPE"),
            ("NO_SOURCE_TEXT", "", {t0: "yes", t1: "yes"}, {}, True, "ASK"),
        ]
        for cat, src, init_ans, hid_ans, scope_ok, gt in templates:
            idx += 1
            cases.append({
                "id": f"case_{idx:02d}_{d['domain']}_{cat.lower()}",
                "domain": d["domain"],
                "category": cat,
                "policy": policy,
                "sourceText": src,
                "initialAnswers": init_ans,
                "hiddenAnswers": hid_ans,
                "scopeAccepted": scope_ok,
                "groundTruth": gt,
            })
    return cases

def main():
    cases = build_cases()
    runner = ROOT / "evaluation" / "blind_eval_runner.mjs"
    proc = subprocess.run(
        ["node", str(runner)],
        input=json.dumps(cases),
        text=True,
        capture_output=True,
        check=True,
    )
    report = json.loads(proc.stdout)
    out_file = ROOT / "evidence" / "blind_eval_40.json"
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"n_cases": report["n_cases"], "metrics": report["metrics"]}, indent=2))

if __name__ == "__main__":
    main()
