# Reproduce

```bash
lake build
bash scripts/audit.sh
source .venv/bin/activate
python experiments/qwen_boundary_audit.py --model mlx-community/Qwen2.5-0.5B-Instruct-4bit
python experiments/make_report.py
```

Expected:
- Lean build succeeds.
- No forbidden proof tokens.
- Transcript-only Qwen audit has lower success than route-metadata Qwen audit.
- HTML report appears at `results/publishable_artifacts/index.html`.
