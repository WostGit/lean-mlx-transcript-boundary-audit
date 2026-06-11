# Qwen Transcript Boundary Audit

## Executive verdict

- Lean build: PASS
- Forbidden-token audit: PASS
- Real Qwen model: `mlx-community/Qwen2.5-0.5B-Instruct-4bit`
- Transcript-only success: 2/12
- Transcript+route success: 4/12
- Route-metadata lift: +2
- False pass: True

## Interpretation

Lean certifies the transcript-only post-processing boundary. Real Qwen inference shows that omitted route metadata changes recovery success, so the theorem does not apply to that hidden pipeline.