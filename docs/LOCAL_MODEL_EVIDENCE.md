# MLA-020 — P1 Local model benchmark evidence boundary

Status: HARNESS_IMPLEMENTED_UNVERIFIED; NO actual Windows/Qwen/OpenCode benchmark performed. P2 remains LOCKED.

The benchmark_real_local.py harness enforces Qwen model identifier allowlists, exact source Git SHA / plan SHA256, a synthetic fixture identifier and bounded repetition. The P1 test-only path requires injected fake model, labels every result MOCK_ONLY, excludes actual OllamaProvider, and never records prompts, model output, credentials or environment variables.

The real model path is P2-only, gated on exact candidate SHA, explicit High approval, P2_VERIFICATION, owner Windows device and separately verifiable current LOCAL_PLAN owner consent. No CLI entrypoint or automatic model download/network/paid service is enabled here. This Python policy is NOT independently proved OS isolation.

The evidence schema stores duration, redacted output SHA256 and status UNVERIFIED_CANDIDATE. Generated token count, actual RAM/VRAM, power/thermal and accepted REQ/hour remain null until trustworthy independent instrumentation and accepted-REQ evidence exist. Mock numbers are not real performance measurements.

P2 later: validate exact model/version + workload SHA; run bounded trials on owner device; capture trusted memory, thermal, power, token, retry and acceptance metrics; independently verify F18 boundary before promotion. No real tests are claimed from this P1 harness.

## MLA-020 P1 bounded summary hardening

\`summarize_observations\` only accepts 1–3 schema-valid observations with identical model, source SHA, plan SHA256, synthetic fixture ID and evidence level. A mixed mock/real or different-source batch is rejected; the redacted summary includes only count/min/max/total duration, not prompts, generated text, invented tokens/sec or accepted REQ/hour. Exceptions use redacted policy/resource/model-unavailable/observation reason codes.

**No live benchmark has run.** Injected model fakes are local test fixtures; mock durations have zero hardware evidentiary weight. The P2 entrypoint remains non-CLI, owner-consent and exact-SHA gated and Windows-only. OS-enforced F18, Windows real device and trusted metric collectors remain NOT_RUN.


## 2026-11-17 P1 model harness hardening (source-only)

The offline mocked benchmark now guards clock types, validates exact source/plan
SHA and output hash before recording a result, and checks the remaining resource
budget both before and after each mocked generation. Any elapsed-time or output
anomaly returns HOLD. Real Qwen/Ollama and 24-hour Windows performance have
**not** been measured; no benchmark result means owner-device acceptance.
