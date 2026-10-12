"""Unit tests for the Python code nodes, loaded straight from the Dify DSL files.

The checks in these nodes are what make the LLM output safe to use, so they are
tested like any other code: the tests read the YAML that is imported into Dify,
so the code under test is exactly the code that runs there.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_code_node(dsl: str, node_id: str):
    app = yaml.safe_load((ROOT / "dify" / dsl).read_text(encoding="utf-8"))
    node = next(n for n in app["workflow"]["graph"]["nodes"] if n["id"] == node_id)
    namespace: dict = {}
    exec(node["data"]["code"], namespace)  # noqa: S102 - our own reviewed code
    return namespace["main"], node["data"]["outputs"]


triage, triage_outputs = load_code_node("inquiry-triage.yml", "validate")
order_check, order_outputs = load_code_node("order-sheet-extractor.yml", "check")


# ---------------------------------------------------------------- inquiry triage


def test_triage_normalises_a_valid_answer():
    out = triage('{"category": "Cancel_Order", "order_id": "#11345", "sentiment": "NEUTRAL"}',
                 "Please cancel order 11345")
    assert out == {"category": "cancel_order", "order_id": "ORD-11345", "sentiment": "neutral",
                   "needs_review": False, "issues": ""}


def test_triage_accepts_markdown_fences_and_prose():
    out = triage('Sure!\n```json\n{"category": "order_status", "order_id": null, "sentiment": "neutral"}\n```',
                 "Where is my parcel?")
    assert out["category"] == "order_status" and out["order_id"] == "" and not out["needs_review"]


def test_triage_flags_an_invented_order_id():
    out = triage('{"category": "order_status", "order_id": "ORD-99999", "sentiment": "neutral"}',
                 "Where is my parcel?")
    assert out["needs_review"]
    assert "not in the message" in out["issues"]


@pytest.mark.parametrize("bad", ['{"category": "shipping", "order_id": null, "sentiment": "neutral"}',
                                 '{"category": "complaint", "order_id": null, "sentiment": "angry"}'])
def test_triage_flags_labels_outside_the_schema(bad):
    assert triage(bad, "text")["needs_review"]


def test_triage_flags_non_json():
    out = triage("The customer wants to cancel.", "cancel please")
    assert out["needs_review"] and out["issues"] == "LLM output was not a JSON object"


def test_triage_returns_every_declared_output():
    out = triage('{"category": "complaint", "order_id": null, "sentiment": "negative"}', "rude staff")
    assert set(out) == set(triage_outputs)


# ---------------------------------------------------------- order sheet extractor

SOURCE = "MUG-BLU-01 ストーンマグ 24 980 23,520\nMUG-RED-01 ストーンマグ 12 980 11,760\n合計 35,280円"


def _llm(lines, total):
    return json.dumps({"buyer": "株式会社サンプル", "po_number": "PO-1", "lines": lines, "stated_total": total},
                      ensure_ascii=False)


GOOD_LINES = [{"sku": "MUG-BLU-01", "name": "ストーンマグ", "quantity": 24, "unit_price": 980, "amount": 23520},
              {"sku": "MUG-RED-01", "name": "ストーンマグ", "quantity": 12, "unit_price": 980, "amount": 11760}]


def test_order_lines_that_add_up_produce_csv_without_review():
    out = order_check(_llm(GOOD_LINES, 35280), SOURCE)
    assert not out["needs_review"]
    assert out["lines_total"] == out["stated_total"] == 35280
    rows = out["csv"].strip().splitlines()
    assert rows[0] == "po_number,line_no,sku,name,quantity,unit_price,amount"
    assert rows[1] == "PO-1,1,MUG-BLU-01,ストーンマグ,24,980,23520"


def test_order_total_mismatch_is_flagged():
    out = order_check(_llm(GOOD_LINES, 36000), SOURCE)
    assert out["needs_review"]
    assert "35,280" in out["issues"] and "36,000" in out["issues"]


def test_order_full_width_numbers_are_normalised():
    lines = [{"sku": "ＭＵＧ－ＢＬＵ－０１", "name": "x", "quantity": "２４",
              "unit_price": "９８０", "amount": "２３，５２０"}]
    out = order_check(_llm(lines, "２３，５２０円"), SOURCE)
    assert out["lines_total"] == 23520 and out["stated_total"] == 23520
    assert "MUG-BLU-01" in out["csv"]


def test_order_line_not_on_the_sheet_is_flagged():
    lines = GOOD_LINES + [{"sku": "GHOST-01", "name": "x", "quantity": 1, "unit_price": 100, "amount": 100}]
    out = order_check(_llm(lines, 35380), SOURCE)
    assert out["needs_review"] and "GHOST-01 not found" in out["issues"]


def test_order_line_amount_that_does_not_match_qty_times_price_is_flagged():
    lines = [dict(GOOD_LINES[0], amount=99999), GOOD_LINES[1]]
    out = order_check(_llm(lines, 35280), SOURCE)
    assert out["needs_review"] and "line 1: amount" in out["issues"]


def test_order_returns_every_declared_output():
    assert set(order_check(_llm(GOOD_LINES, 35280), SOURCE)) >= set(order_outputs)


# ------------------------------------------------------------------- DSL sanity


@pytest.mark.parametrize("dsl", sorted(p.name for p in (ROOT / "dify").glob("*.yml")))
def test_dsl_graph_is_connected(dsl):
    app = yaml.safe_load((ROOT / "dify" / dsl).read_text(encoding="utf-8"))
    assert app["kind"] == "app" and app["version"] == "0.7.0"
    graph = app["workflow"]["graph"]
    ids = {n["id"] for n in graph["nodes"]}
    for edge in graph["edges"]:
        assert edge["source"] in ids and edge["target"] in ids
    reachable, frontier = {"start"}, ["start"]
    while frontier:
        node = frontier.pop()
        for edge in graph["edges"]:
            if edge["source"] == node and edge["target"] not in reachable:
                reachable.add(edge["target"])
                frontier.append(edge["target"])
    assert reachable == ids


# ------------------------------------------------------------------ n8n workflow


def test_n8n_workflow_is_connected_and_has_no_secrets():
    wf = json.loads((ROOT / "n8n" / "inquiry-triage-router.json").read_text(encoding="utf-8"))
    names = {n["name"] for n in wf["nodes"]}
    targets = {c["node"] for outs in wf["connections"].values() for branch in outs["main"] for c in branch}
    assert set(wf["connections"]) <= names and targets <= names
    assert names - targets == {"Inquiry received"}  # the webhook is the only entry point
    responders = [n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.respondToWebhook"]
    assert len(responders) == 2  # one per branch of "Needs review?"
    assert "app-" not in json.dumps(wf)  # the Dify key lives in an n8n credential, never in the export
