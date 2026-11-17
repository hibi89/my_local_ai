# MLA-020 — P1 Local model benchmark evidence boundary

Status: HARNESS_IMPLEMENTED_UNVERIFIED; NO actual Windows/Qwen/OpenCode benchmark performed. P2 remains LOCKED.

The benchmark_real_local.py harness enforces Qwen model identifier allowlists, exact source Git SHA / plan SHA256, a synthetic fixture identifier and bounded repetition. The P1 test-only path requires injected fake model, labels every result MOCK_ONLY, excludes actual OllamaProvider, and never records prompts, model output, credentials or environment variables.

The real model path is P2-only, gated on exact candidate SHA, explicit High approval, P2_VERIFICATION, owner Windows device and separately verifiable current LOCAL_PLAN owner consent. No CLI entrypoint or automatic model download/network/paid service is enabled here. This Python policy is NOT independently proved OS isolation.

The evidence schema stores duration, redacted output SHA256 and status UNVERIFIED_CANDIDATE. Generated token count, actual RAM/VRAM, power/thermal and accepted REQ/hour remain null until trustworthy independent instrumentation and accepted-REQ evidence exist. Mock numbers are not real performance measurements.

P2 later: validate exact model/version + workload SHA; run bounded trials on owner device; capture trusted memory, thermal, power, token, retry and acceptance metrics; independently verify F18 boundary before promotion. No real tests are claimed from this P1 harness.
