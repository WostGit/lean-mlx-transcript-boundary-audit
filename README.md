# Qwen Transcript Boundary Audit

This artifact combines Lean proofs with real Qwen inference on Apple Silicon through MLX.

The Lean proof checks the valid audit boundary:

```text
train : Transcript -> Student
```

The Qwen experiment checks the failure mode:

```text
train : Transcript -> RouteMetadata -> Student
```

If route metadata is omitted from the audited transcript, a transcript-only audit can falsely pass.
