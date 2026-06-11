# Qwen transcript boundary audit latest results

- Workflow: Qwen Transcript Boundary Audit
- Run id: 27323606700
- Run attempt: 1
- Commit: 0d244dfcaed0563c08c041f4870ec41197868716
- Generated at: 2026-06-11T04:23:07Z

This workflow generated a self-contained Lean proof artifact and ran a real Qwen/MLX transcript-boundary audit.

Main expected result:
- Lean build succeeds.
- Lean audit has no forbidden proof tokens.
- Real Qwen route-metadata success exceeds transcript-only success.
- Transcript-only audit can falsely pass when route metadata is omitted.
