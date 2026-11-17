# My Local AI — local model benchmark contract (P1)

This file defines a **synthetic-only** baseline; no Windows/Ollama/Qwen/OpenCode benchmark has been executed.

- Compare candidate local 3B and 4B models only after owner-device P2 gate.
- Capture model identifier and digest, device RAM/VRAM, context length, warmup, tokens generated, wall time, peak resident memory, failure/timeout, output validity, and repeat count.
- Record environment and source provenance separately; never use placeholder zeros as real performance evidence.
- `scripts/benchmark_synthetic.py` emits explicit `SYNTHETIC_NOT_MEASURED` records without model/network access.
- Real results require P2 approval, exact executable/model SHA, bounded workload, local-only endpoint, and owner device evidence. No automatic downloads or paid services.
