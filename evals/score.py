"""Score recorded Dify runs against the labelled tickets and write a Markdown report.

    python evals/score.py            # every file in evals/runs/ -> evals/report.md

A case passes only when category, order ID and sentiment all match. Cases that did
not run (quota, timeouts) are reported separately instead of being counted as wrong.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
FIELDS = ("category", "order_id", "sentiment")


def _norm(field: str, value):
    if value in (None, "", "null"):
        return None
    return str(value).strip().upper() if field == "order_id" else str(value).strip().lower()


def score(run: list[dict], expected: dict[str, dict]) -> dict:
    graded, not_run, failures = 0, [], []
    passed = 0
    field_ok = dict.fromkeys(FIELDS, 0)
    flagged_correctly = flagged_wrongly = 0
    for rec in run:
        if rec.get("status") != "succeeded":
            not_run.append(rec["id"])
            continue
        graded += 1
        exp, out = expected[rec["id"]]["expected"], rec.get("outputs") or {}
        ok = {f: _norm(f, out.get(f)) == _norm(f, exp.get(f)) for f in FIELDS}
        for f in FIELDS:
            field_ok[f] += ok[f]
        if all(ok.values()):
            passed += 1
        else:
            failures.append((rec["id"], expected[rec["id"]]["input"], exp, out))
        if out.get("needs_review"):
            if all(ok.values()):
                flagged_wrongly += 1
            else:
                flagged_correctly += 1
    latencies = [r["latency_ms"] for r in run if r.get("latency_ms")]
    return {
        "graded": graded,
        "passed": passed,
        "accuracy": passed / graded if graded else 0.0,
        "field_accuracy": {f: field_ok[f] / graded if graded else 0.0 for f in FIELDS},
        "not_run": not_run,
        "failures": failures,
        "p50_latency_ms": median(latencies) if latencies else None,
        "flagged_correctly": flagged_correctly,
        "flagged_wrongly": flagged_wrongly,
    }


def main() -> None:
    expected = {}
    for line in (HERE / "support_tickets.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            case = json.loads(line)
            expected[case["id"]] = case

    runs = sorted((HERE / "runs").glob("*.json"))
    lines = ["# inquiry-triage on Dify: measured results", "",
             "Real runs of the `inquiry-triage` workflow on Dify Cloud against the 40 labelled tickets.",
             "Same prompt and validation code for every model; only the model was changed.", "",
             "| Run | Graded | Accuracy | category | order_id | sentiment | p50 latency | Not run |",
             "|---|---|---|---|---|---|---|---|"]
    details = []
    for path in runs:
        result = score(json.loads(path.read_text(encoding="utf-8")), expected)
        fa = result["field_accuracy"]
        lines.append(
            f"| `{path.stem}` | {result['graded']} | **{result['accuracy']:.1%}** | {fa['category']:.1%} | "
            f"{fa['order_id']:.1%} | {fa['sentiment']:.1%} | "
            f"{result['p50_latency_ms']:,.0f} ms | {', '.join(result['not_run']) or '-'} |"
        )
        details += ["", f"## `{path.stem}`: failed cases", "",
                    "| Case | Input | Expected | Output |", "|---|---|---|---|"]
        for cid, text, exp, out in result["failures"]:
            e = ", ".join(f"{f}={exp.get(f)}" for f in FIELDS)
            o = ", ".join(f"{f}={out.get(f) or None}" for f in FIELDS)
            details.append(f"| {cid} | {text} | {e} | {o} |")
    (HERE / "report.md").write_text("\n".join(lines + details) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
