#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path
from typing import Dict, List

from mlx_lm import generate, load

LABELS = ["reasoning", "coding", "tool_use", "computer_use", "policy_edge", "domain_expert"]

ROUTES = {
    "reasoning_route": "reasoning",
    "code_route": "coding",
    "tool_route": "tool_use",
    "computer_route": "computer_use",
    "safety_route": "policy_edge",
    "expert_route": "domain_expert",
}

CASES = [
    {
        "id": "case_001",
        "label": "coding",
        "query_family": "agentic task",
        "transcript": "The user asks for a precise solution involving files, syntax, and implementation details. The answer is procedural and includes structured steps.",
        "route_id": "code_route",
    },
    {
        "id": "case_002",
        "label": "policy_edge",
        "query_family": "safety/policy task",
        "transcript": "The user asks for a borderline request. The answer is cautious, constrained, and explains boundaries.",
        "route_id": "safety_route",
    },
    {
        "id": "case_003",
        "label": "tool_use",
        "query_family": "tool orchestration task",
        "transcript": "The user asks for a task requiring external actions. The answer discusses sequencing, checking outputs, and using available tools.",
        "route_id": "tool_route",
    },
    {
        "id": "case_004",
        "label": "domain_expert",
        "query_family": "expert explanation task",
        "transcript": "The user asks for a specialized technical judgment. The answer uses domain language and compares subtle alternatives.",
        "route_id": "expert_route",
    },
    {
        "id": "case_005",
        "label": "reasoning",
        "query_family": "general reasoning task",
        "transcript": "The user asks for a multi-step conclusion. The answer weighs evidence and reaches a compact final judgment.",
        "route_id": "reasoning_route",
    },
    {
        "id": "case_006",
        "label": "computer_use",
        "query_family": "computer interaction task",
        "transcript": "The user asks for GUI or system interaction. The answer describes clicking, inspecting screen state, and operating a computer.",
        "route_id": "computer_route",
    },
    {
        "id": "case_007",
        "label": "coding",
        "query_family": "software repair task",
        "transcript": "The user gives a failing automated run and asks for a fix. The answer identifies the bug and changes implementation details.",
        "route_id": "code_route",
    },
    {
        "id": "case_008",
        "label": "policy_edge",
        "query_family": "sensitive transformation task",
        "transcript": "The user asks for a transformed artifact with possible misuse. The answer carefully narrows the allowed help.",
        "route_id": "safety_route",
    },
    {
        "id": "case_009",
        "label": "tool_use",
        "query_family": "workflow automation task",
        "transcript": "The user asks the assistant to coordinate several steps, inspect outputs, and update a result file.",
        "route_id": "tool_route",
    },
    {
        "id": "case_010",
        "label": "domain_expert",
        "query_family": "specialist review task",
        "transcript": "The user requests a publication-style technical evaluation. The answer discusses scope, novelty, and limitations.",
        "route_id": "expert_route",
    },
    {
        "id": "case_011",
        "label": "reasoning",
        "query_family": "logical comparison task",
        "transcript": "The user asks which of several alternatives is best. The answer compares tradeoffs and chooses one.",
        "route_id": "reasoning_route",
    },
    {
        "id": "case_012",
        "label": "computer_use",
        "query_family": "browser/computer task",
        "transcript": "The user asks for interaction with an app or website. The answer references navigation, screen checks, and UI state.",
        "route_id": "computer_route",
    },
]

def parse_label(text: str) -> str:
    t = text.strip().lower()
    t = re.sub(r"[^a-z_ ]", " ", t)
    for label in LABELS:
        if re.search(rf"\b{re.escape(label)}\b", t):
            return label
    aliases = {
        "coding": ["code", "programming", "software"],
        "tool_use": ["tool", "tools"],
        "computer_use": ["computer", "browser", "gui"],
        "policy_edge": ["safety", "policy"],
        "domain_expert": ["expert", "specialist", "domain"],
        "reasoning": ["reason", "logic"],
    }
    for label, words in aliases.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", t):
                return label
    return "invalid"

def prompt_for(case: Dict[str, str], with_route: bool) -> str:
    labels = ", ".join(LABELS)
    base = f"""You are auditing an assistant transcript.

Task: infer the hidden capability label.

Valid labels: {labels}

Audited transcript:
{case['transcript']}

Query family:
{case['query_family']}
"""
    if with_route:
        base += f"""
Additional route metadata available to the training/inference pipeline:
route_id = {case['route_id']}

Route metadata dictionary:
reasoning_route -> reasoning
code_route -> coding
tool_route -> tool_use
computer_route -> computer_use
safety_route -> policy_edge
expert_route -> domain_expert
"""
    base += """
Answer with exactly one valid label and nothing else.
"""
    return base

def qwen_generate(model, tokenizer, prompt: str, max_tokens: int = 12) -> str:
    try:
        return generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens, verbose=False)
    except TypeError:
        return generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    out = Path("results/qwen_boundary_audit")
    out.mkdir(parents=True, exist_ok=True)

    start = time.time()
    model, tokenizer = load(args.model)

    rows = []
    for case in CASES:
        for mode, with_route in [("transcript_only", False), ("transcript_plus_route_metadata", True)]:
            prompt = prompt_for(case, with_route)
            raw = qwen_generate(model, tokenizer, prompt)
            pred = parse_label(raw)
            success = int(pred == case["label"])
            rows.append({
                "case_id": case["id"],
                "mode": mode,
                "gold_label": case["label"],
                "route_id": case["route_id"],
                "prediction": pred,
                "success": success,
                "raw_output": raw.strip().replace("\n", " ")[:300],
            })

    transcript_success = sum(r["success"] for r in rows if r["mode"] == "transcript_only")
    route_success = sum(r["success"] for r in rows if r["mode"] == "transcript_plus_route_metadata")
    n = len(CASES)
    budget = transcript_success
    false_pass = transcript_success <= budget and route_success > budget

    summary = {
        "model": args.model,
        "n_cases": n,
        "transcript_only_success": transcript_success,
        "transcript_plus_route_metadata_success": route_success,
        "route_metadata_lift": route_success - transcript_success,
        "transcript_only_accuracy": round(transcript_success / n, 6),
        "transcript_plus_route_metadata_accuracy": round(route_success / n, 6),
        "route_metadata_false_pass_under_transcript_audit": false_pass,
        "seconds": round(time.time() - start, 3),
    }

    with (out / "qwen_predictions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print("")
    print("Predictions:")
    for r in rows:
        print(f"{r['case_id']} | {r['mode']} | gold={r['gold_label']} | pred={r['prediction']} | success={r['success']} | raw={r['raw_output']}")

if __name__ == "__main__":
    main()
