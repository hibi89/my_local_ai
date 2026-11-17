# My Local AI — local model benchmark contract (P1)

This file defines a **synthetic-only** baseline; no Windows/Ollama/Qwen/OpenCode benchmark has been executed.

- Compare candidate local 3B and 4B models only after owner-device P2 gate.
- Capture model identifier and digest, device RAM/VRAM, context length, warmup, tokens generated, wall time, peak resident memory, failure/timeout, output validity, and repeat count.
- Record environment and source provenance separately; never use placeholder zeros as real performance evidence.
- `scripts/benchmark_synthetic.py` emits explicit `SYNTHETIC_NOT_MEASURED` records without model/network access.
- Real results require P2 approval, exact executable/model SHA, bounded workload, local-only endpoint, and owner device evidence. No automatic downloads or paid services.

## MLA-005 P1 aggregate and failure accounting (code only)

The synthetic generator is offline. \`SyntheticTrial\` requires a fixed synthetic source, one of five simulated outcomes, and a 0/1 retry count. \`aggregate_synthetic_trials\` refuses empty, oversized (>100), mixed-model, and non-synthetic records. Its success/failure/retry counts describe **fabricated fixtures only** and deliberately omit tokens/second and accepted requirements/hour. Failure classification uses exception type only, never a potentially sensitive exception message. Successful fixture counters are not real accepted REQs.

P2 acceptance will require independent measured start/end timestamps, token accounting, hardware telemetry with trustworthy sources, error/timeout/retry denominators, accepted REQ ledger plus observation window, and exact source/model/workload SHAs before any throughput claim. Until then: \`SYNTHETIC_NOT_MEASURED\`, \`NO_REAL_PERFORMANCE_CLAIM\`.
