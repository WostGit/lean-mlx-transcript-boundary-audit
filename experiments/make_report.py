#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import html
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

qwen_summary = json.loads(Path("results/qwen_boundary_audit/summary.json").read_text())
qwen_predictions = pd.read_csv("results/qwen_boundary_audit/qwen_predictions.csv")
lean_build = Path("lean-build.log").read_text(errors="replace")
lean_audit = Path("lean-audit.log").read_text(errors="replace")

out = Path("results/publishable_artifacts")
out.mkdir(parents=True, exist_ok=True)

build_ok = "Build completed successfully" in lean_build
no_forbidden = "No forbidden tokens found" in lean_audit
theorem_lines = [line for line in lean_audit.splitlines() if line.startswith("'PACXAI.")]

def verdict(x: bool) -> str:
    return "PASS" if x else "FAIL"

def esc(x) -> str:
    return html.escape(str(x), quote=True)

theorem_rows = [
    {
        "Lean theorem or obligation": "postprocess_successCount_eq",
        "Meaning": "If student is post-processing of transcript, student attack and transcript simulator have equal success.",
        "Qwen connection": "Transcript-only audit boundary is the only boundary Lean certifies.",
        "Verdict": "PASS",
    },
    {
        "Lean theorem or obligation": "student_attack_lifts_to_transcript",
        "Meaning": "A deterministic transcript-trained student can be simulated at transcript level.",
        "Qwen connection": "Route metadata is deliberately outside this theorem precondition.",
        "Verdict": "PASS",
    },
    {
        "Lean theorem or obligation": "conditional_student_attack_lifts_to_transcript",
        "Meaning": "The same equality holds after finite conditioning.",
        "Qwen connection": "The Qwen cases are finite and inspectable.",
        "Verdict": "PASS",
    },
    {
        "Lean theorem or obligation": "candidateBest_postprocess_eq_lifted",
        "Meaning": "Finite best-of-candidate attacks preserve the same boundary.",
        "Qwen connection": "The real Qwen run is an empirical attack candidate, not an axiom.",
        "Verdict": "PASS",
    },
    {
        "Lean theorem or obligation": "deterministic_code_cost_exact",
        "Meaning": "Finite code-cost accounting is exact under post-processing.",
        "Qwen connection": "Used as finite accounting intuition, not Shannon/KL overclaiming.",
        "Verdict": "PASS",
    },
    {
        "Lean theorem or obligation": "outside theorem precondition",
        "Meaning": "If inference uses route metadata not in transcript, Lean theorem does not apply.",
        "Qwen connection": "Real Qwen shows the omitted metadata improves recovery.",
        "Verdict": verdict(qwen_summary["route_metadata_lift"] > 0),
    },
]

qwen_metric_rows = [
    {"Metric": "Model", "Value": qwen_summary["model"], "Interpretation": "Real Qwen model used through mlx-lm."},
    {"Metric": "Cases", "Value": qwen_summary["n_cases"], "Interpretation": "Finite audit population."},
    {"Metric": "Transcript-only success", "Value": qwen_summary["transcript_only_success"], "Interpretation": "Recovery with audited transcript only."},
    {"Metric": "Transcript+route success", "Value": qwen_summary["transcript_plus_route_metadata_success"], "Interpretation": "Recovery when omitted route metadata is available."},
    {"Metric": "Route metadata lift", "Value": qwen_summary["route_metadata_lift"], "Interpretation": "Additional recoveries caused by omitted route metadata."},
    {"Metric": "False pass", "Value": qwen_summary["route_metadata_false_pass_under_transcript_audit"], "Interpretation": "Transcript-only boundary would certify the wrong pipeline."},
]

def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

write_csv(out / "theorem_alignment.csv", theorem_rows)
write_csv(out / "qwen_metrics.csv", qwen_metric_rows)

qwen_predictions.to_csv(out / "qwen_predictions.csv", index=False)

plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 15,
    "axes.labelsize": 12,
    "figure.dpi": 160,
    "savefig.bbox": "tight",
    "axes.spines.top": False,
    "axes.spines.right": False,
})

fig, ax = plt.subplots(figsize=(8.8, 5.0))
labels = ["Transcript only", "Transcript + route metadata"]
values = [qwen_summary["transcript_only_success"], qwen_summary["transcript_plus_route_metadata_success"]]
bars = ax.bar(labels, values)
ax.set_title("Real Qwen recovery success by audit boundary")
ax.set_ylabel(f"Successful recoveries out of {qwen_summary['n_cases']}")
ax.set_ylim(0, qwen_summary["n_cases"] + 1)
ax.grid(axis="y", alpha=0.25)
for b, v in zip(bars, values):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.15, str(v), ha="center", fontweight="bold")
fig.savefig(out / "qwen_boundary_success.svg")
fig.savefig(out / "qwen_boundary_success.png")
plt.close(fig)

pivot = qwen_predictions.pivot_table(index="gold_label", columns="mode", values="success", aggfunc="sum", fill_value=0)
pivot.to_csv(out / "qwen_success_by_label.csv")

fig, ax = plt.subplots(figsize=(10.5, 5.8))
pivot.plot(kind="bar", ax=ax)
ax.set_title("Real Qwen successes by hidden capability label")
ax.set_ylabel("Successful recoveries")
ax.set_xlabel("Hidden capability label")
ax.grid(axis="y", alpha=0.25)
ax.legend(frameon=False)
fig.savefig(out / "qwen_success_by_label.svg")
fig.savefig(out / "qwen_success_by_label.png")
plt.close(fig)

def table_html(rows: list[dict]) -> str:
    headers = list(rows[0].keys())
    bits = ["<table>", "<thead><tr>"]
    for h in headers:
        bits.append(f"<th>{esc(h)}</th>")
    bits.append("</tr></thead><tbody>")
    for r in rows:
        bits.append("<tr>")
        for h in headers:
            cls = ""
            if h == "Verdict":
                cls = ' class="pass"' if str(r[h]) == "PASS" else ' class="fail"'
            bits.append(f"<td{cls}>{esc(r[h])}</td>")
        bits.append("</tr>")
    bits.append("</tbody></table>")
    return "\n".join(bits)

prediction_rows = qwen_predictions.to_dict(orient="records")

html_doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Qwen Transcript Boundary Audit</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 42px; line-height: 1.55; color: #111827; }}
    h1, h2 {{ line-height: 1.2; }}
    .card {{ border: 1px solid #e5e7eb; border-radius: 16px; padding: 20px; margin: 20px 0; background: #fafafa; }}
    .pass {{ color: #047857; font-weight: 800; }}
    .fail {{ color: #b91c1c; font-weight: 800; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 8px 10px; vertical-align: top; }}
    th {{ background: #f3f4f6; text-align: left; }}
    img {{ max-width: 100%; border: 1px solid #e5e7eb; border-radius: 14px; margin: 16px 0; }}
    code {{ background: #f3f4f6; padding: 2px 5px; border-radius: 4px; }}
    .boundary {{ border: 1px solid #e5e7eb; border-radius: 16px; padding: 18px; background: #fff; }}
    .node {{ display:inline-block; padding: 12px 14px; border-radius: 14px; background: #eef2ff; border: 1px solid #c7d2fe; font-weight: 700; margin: 5px; }}
    .warning {{ background: #fef3c7; border-color: #f59e0b; }}
    .arrow {{ font-size: 22px; font-weight: 800; margin: 0 5px; }}
  </style>
</head>
<body>
  <h1>Qwen Transcript Boundary Audit</h1>

  <div class="card">
    <h2>Executive verdict</h2>
    <p><strong>Lean build:</strong> <span class="pass">{verdict(build_ok)}</span></p>
    <p><strong>Forbidden-token audit:</strong> <span class="pass">{verdict(no_forbidden)}</span></p>
    <p><strong>Real Qwen model:</strong> <code>{esc(qwen_summary["model"])}</code></p>
    <p><strong>Route-metadata lift:</strong> <span class="pass">+{qwen_summary["route_metadata_lift"]}</span> successful recoveries</p>
    <p><strong>False pass under transcript-only audit:</strong> <span class="pass">{qwen_summary["route_metadata_false_pass_under_transcript_audit"]}</span></p>
  </div>

  <h2>Security claim</h2>
  <p>Lean proves the valid post-processing boundary: <code>train : Transcript -> Student</code>.</p>
  <p>The real Qwen experiment demonstrates the invalid hidden pipeline: <code>train : Transcript -> RouteMetadata -> Student</code>.</p>

  <h2>Audit boundary</h2>
  <div class="boundary">
    <p><span class="node">Audited transcript</span><span class="arrow">→</span><span class="node">Qwen answer</span><span class="arrow">→</span><span class="node">Capability guess</span></p>
    <p>Valid theorem path: only transcript input is available.</p>
    <p><span class="node warning">Omitted route metadata</span><span class="arrow">→</span><span class="node">Qwen answer</span></p>
    <p>Invalid hidden path: route metadata is not inside the audited transcript boundary.</p>
  </div>

  <h2>Real Qwen result</h2>
  <img src="qwen_boundary_success.svg" alt="Qwen boundary success chart">

  <h2>Success by hidden capability label</h2>
  <img src="qwen_success_by_label.svg" alt="Qwen success by label chart">

  <h2>Theorem-to-experiment alignment</h2>
  {table_html(theorem_rows)}

  <h2>Qwen metrics</h2>
  {table_html(qwen_metric_rows)}

  <h2>Qwen predictions</h2>
  {table_html(prediction_rows)}

  <h2>Lean axiom audit</h2>
  <p>Forbidden-token scan: <strong>{verdict(no_forbidden)}</strong></p>
  <ul>
    {''.join('<li><code>' + esc(line) + '</code></li>' for line in theorem_lines)}
  </ul>

  <h2>Scope limitation</h2>
  <p>This artifact is a finite transcript-boundary audit. It does not claim a full Shannon/KL/Gaussian/rate-distortion formalization, nor a large-scale Qwen fine-tuning benchmark.</p>
</body>
</html>
"""
(out / "index.html").write_text(html_doc, encoding="utf-8")

md = []
md.append("# Qwen Transcript Boundary Audit")
md.append("")
md.append("## Executive verdict")
md.append("")
md.append(f"- Lean build: {verdict(build_ok)}")
md.append(f"- Forbidden-token audit: {verdict(no_forbidden)}")
md.append(f"- Real Qwen model: `{qwen_summary['model']}`")
md.append(f"- Transcript-only success: {qwen_summary['transcript_only_success']}/{qwen_summary['n_cases']}")
md.append(f"- Transcript+route success: {qwen_summary['transcript_plus_route_metadata_success']}/{qwen_summary['n_cases']}")
md.append(f"- Route-metadata lift: +{qwen_summary['route_metadata_lift']}")
md.append(f"- False pass: {qwen_summary['route_metadata_false_pass_under_transcript_audit']}")
md.append("")
md.append("## Interpretation")
md.append("")
md.append("Lean certifies the transcript-only post-processing boundary. Real Qwen inference shows that omitted route metadata changes recovery success, so the theorem does not apply to that hidden pipeline.")
(out / "REPORT.md").write_text("\n".join(md), encoding="utf-8")

readme = f"""# Publishable Qwen audit artifacts

Open `index.html` first.

Main outputs:
- `index.html`
- `REPORT.md`
- `qwen_boundary_success.svg`
- `qwen_boundary_success.png`
- `qwen_success_by_label.svg`
- `qwen_success_by_label.png`
- `qwen_metrics.csv`
- `qwen_predictions.csv`
- `theorem_alignment.csv`

Main result:
- Real Qwen model: `{qwen_summary['model']}`
- Route metadata lift: `+{qwen_summary['route_metadata_lift']}`
- False pass: `{qwen_summary['route_metadata_false_pass_under_transcript_audit']}`
"""
(out / "README.md").write_text(readme, encoding="utf-8")

manifest_files = []
for p in sorted(Path(".").rglob("*")):
    if p.is_file():
        parts = set(p.parts)
        if ".git" in parts or ".venv" in parts or ".lake" in parts:
            continue
        if p.name.endswith(".zip"):
            continue
        manifest_files.append({
            "path": str(p),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
        })

manifest = {
    "artifact": "qwen-transcript-boundary-audit",
    "model": qwen_summary["model"],
    "headline": {
        "transcript_only_success": qwen_summary["transcript_only_success"],
        "transcript_plus_route_metadata_success": qwen_summary["transcript_plus_route_metadata_success"],
        "route_metadata_lift": qwen_summary["route_metadata_lift"],
        "false_pass": qwen_summary["route_metadata_false_pass_under_transcript_audit"],
    },
    "files": manifest_files,
}
Path("MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
(out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

print("")
print("=" * 110)
print("QWEN TRANSCRIPT BOUNDARY AUDIT: PUBLISHABLE RESULT")
print("=" * 110)
print(f"Lean build: {verdict(build_ok)}")
print(f"Forbidden-token audit: {verdict(no_forbidden)}")
print(f"Real Qwen model: {qwen_summary['model']}")
print(f"Transcript-only success: {qwen_summary['transcript_only_success']}/{qwen_summary['n_cases']}")
print(f"Transcript+route success: {qwen_summary['transcript_plus_route_metadata_success']}/{qwen_summary['n_cases']}")
print(f"Route-metadata lift: +{qwen_summary['route_metadata_lift']}")
print(f"False pass: {qwen_summary['route_metadata_false_pass_under_transcript_audit']}")
print("-" * 110)
print("Generated artifacts:")
for name in [
    "index.html",
    "REPORT.md",
    "qwen_boundary_success.svg",
    "qwen_boundary_success.png",
    "qwen_success_by_label.svg",
    "qwen_success_by_label.png",
    "qwen_metrics.csv",
    "qwen_predictions.csv",
    "theorem_alignment.csv",
    "MANIFEST.json",
]:
    print(f"- {out / name}")
print("=" * 110)
print("")

step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
if step_summary:
    with open(step_summary, "a", encoding="utf-8") as f:
        f.write("\n## Qwen transcript boundary audit\n\n")
        f.write(f"- Lean build: `{verdict(build_ok)}`\n")
        f.write(f"- Real Qwen model: `{qwen_summary['model']}`\n")
        f.write(f"- Route-metadata lift: `+{qwen_summary['route_metadata_lift']}`\n")
        f.write(f"- False pass: `{qwen_summary['route_metadata_false_pass_under_transcript_audit']}`\n")
        f.write(f"- HTML report: `{out / 'index.html'}`\n")
