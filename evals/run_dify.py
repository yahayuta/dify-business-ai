"""Run the labelled support tickets through the published `inquiry-triage` Dify app.

    export DIFY_API_KEY=app-...            # the app's API key (Dify -> API Access)
    export DIFY_BASE_URL=https://api.dify.ai/v1   # or your self-hosted URL
    python evals/run_dify.py --label gemini-3.5-flash

Writes evals/runs/<label>.json, which `evals/score.py` turns into a report.
Uses only the standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_one(base_url: str, api_key: str, message: str) -> dict:
    body = json.dumps({"inputs": {"message": message}, "response_mode": "blocking", "user": "evals"}).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/workflows/run",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.load(resp)["data"]
    return {
        "status": data.get("status"),
        "outputs": data.get("outputs") or {},
        "error": data.get("error"),
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "total_tokens": data.get("total_tokens"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="name of the run, e.g. the model")
    parser.add_argument("--dataset", default=str(HERE / "support_tickets.jsonl"))
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between calls (rate limits)")
    args = parser.parse_args()

    api_key = os.environ["DIFY_API_KEY"]
    base_url = os.environ.get("DIFY_BASE_URL", "https://api.dify.ai/v1")
    cases = [json.loads(line) for line in Path(args.dataset).read_text(encoding="utf-8").splitlines() if line.strip()]

    results = []
    for case in cases:
        try:
            result = run_one(base_url, api_key, case["input"])
        except Exception as exc:  # keep going; the failure is part of the result
            result = {"status": "failed", "outputs": {}, "error": str(exc), "latency_ms": None, "total_tokens": None}
        results.append({"id": case["id"], **result})
        print(case["id"], result["status"], result["outputs"])
        time.sleep(args.delay)

    out = HERE / "runs" / f"{args.label}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
