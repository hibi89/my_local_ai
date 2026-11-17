# My Local AI — 탈부착형 멀티 모델 병렬 구현 워커 최종설계 V1.1
2026-11-17 KST | 설계 확장 정본 | 구현·실연동·무료 티어 계정 자격 검증 전

> **정본 우선순위:** `AGENTS.md` 안전정책 → 승인된 기존 REQ-01~32/P1·P2 phase gate → 이 확장 설계. 이 문서로 기존 30개 필수 구현 REQ, 28개 P1 작업, 8개 P2 검증 작업의 분모·완료상태·승인·Git 이력을 자동 변경하지 않는다. 사용자 요청은 **설계 반영 승인**이며 외부 모델 호출/데이터 전송/결제/자격증명·GitHub 권한 변경/실운영 승인이 아니다.

## 목적과 제품 경계
My Local AI 자체 Controller가 승인된 High PlanSpec 및 DAG를 관리한다. AX Dev Factory에서 선별·권리 검토한 작업 실행 기법(OpenCode/Ollama, 격리 worktree, lease, SQLite 복구)을 재사용하며 EAI 분석기술은 선택형 AdvisorPort에만 둔다. 원본 EAI·AX 저장소는 변경하지 않는다.

최소 작동은 **Qwen 로컬 단일 워커·오프라인만으로 가능**해야 한다. `Gemini 4 Hydrogen`은 무료 자격/데이터 승인/독립 작업이 모두 있을 때만 ON이 되는 **두 번째 구현 워커**이며 단순 코드 리뷰어가 아니다. 가격 변경·쿼터 초과·사용자 OFF·자격 불명·키 없음·네트워크 끊김에도 Qwen/기존 Instant 워크플로는 정상 진행한다. 외부 워커가 없어도 기존 REQ-01~30 구현 100% 후보 도달을 막지 않는다.

**웹 GPT-6 Instant는 외부 API가 호출하는 워커가 아님.** 현재는 사람이 웹 작업을 진행하고 GitHub 큐/커밋을 읽어오는 독립 lane이며 자동화 서버가 웹 Instant에 직접 명령/세션 시작을 보장하지 않는다. Codex는 이 구성요소를 구현하거나 후행 독립 감사할 수 있으나 Codex 자체가 Hydrogen API를 자동 제공한다는 뜻은 아니다.

## 비교한 세 가지 설계
| 방식 | 성능·효율 | 비용 | 유지보수·위험 | 선택 |
|---|---|---|---|---|
| 외부 Hydrogen 필수 런타임 | 빠른 복잡 작업 가능 | 무료 상실 시 핵심 중단 | 데이터·단일 공급자 종속 | 기각 |
| 각 툴에 Hydrogen 직접 삽입 | 초기 간편 | 중복 호출/쿼터 추적 어려움 | 비밀·승인·복구 정책 분산 | 기각 |
| **공통 ProviderPort + 독립 실행 lane + 정책 가드** | 조건 충족 시 실 병렬 코딩 | 기본 0원, 쿼터 차단 | 어댑터만 교체 가능 | **채택** |

## 설계 데이터 흐름
```text
High-approved immutable plan SHA + owner-approved scope
    │
    ▼
My Local AI Controller (DAG, OWNER GO, REQ/allowed_paths, priorities)
    ├── optional EAI AdvisorPort: non-authoritative reasoning hints only
    ▼
Capability + Privacy + Budget + Concurrency Scheduler (no AI approval authority)
    ├── lane A: local Qwen/Ollama + OpenCode executor, one local resident model
    ├── lane B: remote Hydrogen ProviderAdapter [DEFAULT OFF, separate GO]
    └── lane C: web GPT-6 Instant [MANUAL/EXTERNAL, not programmatically invoked]
    ▼  each task in a disposable isolated Git worktree; exact source+plan+lease
untrusted CandidateDiff + redacted usage/evidence
    ▼
independent Trusted Review Boundary (AX F18 cannot self-attest)
    ▼
approved isolated local ref OR HOLD; never implicit remote push/main merge
    ▼
SQLite reconciled checkpoint/metrics/next independent READY
```

## 역할·병렬 스케줄 규약
1. 주 워커는 로컬 Qwen, 부 워커는 승인된 Hydrogen. 각자의 `task_id`·REQ·`allowed_paths`·baseline commit을 고정한다. Hydrogen은 **실제 코드·테스트 작성** lane이며 미완료 코드를 재검토만 하는 역할로 제한하지 않는다.
2. 승인된 High PlanSpec(정확 SHA)에서 READY DAG만 선택. 선행의 `VERIFIED`는 **독립 신뢰 검증기**의 증거가 있어야 유효하고, 모델 자기 주장은 무효.
3. 서로 다른 task라도 경로 겹침, 생성 파일·lockfile·스키마·API 계약 충돌, import 종속성, 코드 생성 부작용이 있으면 병렬화하지 않는다. 상호 독립 READ/WRITE 집합이 증명된 경우에만 lease 2개를 병렬 발급한다.
4. `Git worktree`는 워커별 분리하며 후보 패치를 다른 워커 checkout에 자동 적용하지 않는다. 충돌이 발생하면 중단·최종 설계자/통합자에게 재계획 요청.
5. GTX 1050 Ti/RAM16GB에서 동시에 상주하는 **로컬** 모델은 1개. Hydrogen 원격 추론은 로컬 GPU 사용량을 늘리지 않지만, 네트워크 통신·격리 로컬 패치 적용·메모리·디스크·파일 I/O는 공통 자원 예산으로 제한한다. 기본 remote 동시성 0, 승인 후 최대 1에서 시작; 이후 실측 기반 조절.
6. 외부 워커 구현 결과를 실제 baseline에 안전하게 통합하고 소스 SHA/REQ 수용 근거를 확보해야만 기존 `구현완료율`의 분자에 기여한다. **모델 응답·개별 PR·검수 제안만으로 증가하지 않는다**. Hydrogen 확장 기능 구현 자체는 별도 확장 큐의 상태로 추적하며 기존 30 REQ 분모에 자동 편입 금지.

## BE·API 계약 및 실행 경계
- `src/my_local_ai/providers/{base,registry,local_qwen,hydrogen,policy}.py` 목표. 기존 `controller`/ `ax_runtime`/ `runner`와 분리; 구현 전에 실제 dev tree 경로를 재검토한다. 원본 소스와 실제 구현 차이가 있으면 기존 경로 보존, 새 API는 명시적 adapter로만.
- `ProviderCapabilitiesV1`: `provider_id`, `model_id`, `supports_code`, `tool_capabilities`, `token_limits`, `transport`, `cost_mode`, `availability`. 모델별 실제 API tool-calling/streaming/structured-output 능력은 계정별 smoke 전 미확인으로 처리.
- `WorkerRequestV1`: `version`, `run_id`, `task_id`, `req_ids`, `plan_sha256`, `source_git_sha`, `approval_digest`, `allowed_paths`, `data_class`, `input_manifest_sha256`, `worker_epoch`, `max_calls`, `deadline`, `max_output_bytes`, `max_spend_usd=0`. Controller만 생성한다.
- `WorkerResponseV1`: `candidate_id`, `provider_id`, `model_id`, `model_version`, `request_digest`, `candidate_diff_sha256`, `declared_files`, `usage`, `finish_reason`, `untrusted=true`, `error_code`. 모델은 approval/VERIFIED/remote write/receipt signer 필드를 설정할 수 없다.
- 외부 모델은 직접 filesystem/shell/GitHub 권한을 갖지 않는다. 응답은 구조화 후보 패치/도구 요청뿐, 로컬의 **별도** 허용 경로·명령 필터 및 sandbox executor가 검증·실행한다. JSON schema/크기/반환 개수/인코딩/경로·diff 검사 및 prompt injection 차단, 오류 시 fail closed.
- 실제 Hydrogen 호출은 Google 공식 SDK/API 어댑터를 우선 시험. Codex CLI의 provider 교체 기능이나 OpenAI 호환 엔드포인트가 동일 기능·tool invocation을 보장한다는 전제 금지. Google 콘솔의 **실제 계정 모델 ID, 응답 계약, 가용 티어, ToS**를 별도 확인.
- SQLite one-writer에 `provider_registry`(상태·기능·정책), `provider_quota`(project/model/tier, observed limits, reset evidence), `worker_assignments`(run/task/attempt/provider/baseline/epoch), `provider_calls`(redacted request digest, usage, result), `provider_approvals`(owner scope+expiry+revocation) 확장 계획. migration 전에 APP_ID·버전·백업/복구·선행 스키마 검사; 기존 테이블 변경·파괴적 DB 수정 승인 전 금지.
- FE/CLI: `providers list/status/enable/disable`, provider별 `FREE_CONFIRMED/UNKNOWN/QUOTA_HOLD/POLICY_HOLD/OFFLINE` 상태·쿼터 소진·다음 재검토 조건·current task·cost 0 제한. 처음에는 read-only 상태만 P1 구현 후보, 실제 enable/API key 주입/송신은 owner GO 이후. 화면에는 고객 원본/프롬프트/키 표시 금지.

## 데이터·비밀·무료 비용 정책: 기본 거부
- 기본 `remote_enabled=false`, `max_spend_usd=0`, `network_egress=deny`. **무료라고 자동 승인되지 않는다.** Google API 호출은 외부 데이터 전송이며 대상 repo/브랜치/파일·데이터 등급·목적·호출량에 대한 별도 사용자 GO 필요.
- 외부 허용 데이터는 사용자가 별도로 승인한 **PUBLIC_NON_SENSITIVE 또는 SYNTHETIC** 최소 입력만. 비공개 GitHub 코드, 고객 소스/PDF/DB, `.env`, 토큰, 인증·서명 정보, 챗 기록, 프롬프트 원본, 개인 경로, 신원 관련 정보를 분류·필터하고 전송 차단. 공개 repo라 해도 사용자가 승인하지 않은 전체 소스를 자동 대량 업로드하지 않는다.
- 무료 tier 여부는 가격표 일반 정보가 아니라 **해당 프로젝트/account의 실제 tier와 서비스 조건**으로 판정한다. tier·billing metadata의 신뢰 가능한 읽기 전용 확인 불가능 시 `COST_UNVERIFIED` → 호출 거부. 프리티어에서 $0 초과 위험을 검증할 수 없는 자동 워커도 호출 거부. 사용량 숫자 자체가 직접 청구 차단을 보장한다고 가정하지 않는다.
- 별도 credential은 OS 비밀 저장/프로세스 주입 후 로그·SQLite·공개 GitHub에 절대 쓰지 않는다. API 키 없는 상태도 정상 동작. 유료 전환이나 billing 연결·권한 확대는 별도 GO.
- 사용자나 운영자가 `off`하면 새로운 remote 호출 즉시 중단하고 inflight 작업은 안전 종료 또는 HOLD. 이미 전송된 데이터는 회수 불가이므로 전송 전 승인 우선.

## 장애·재배정·복구 상태기계
`DISABLED → ELIGIBLE_FREE → ASSIGNED → RUNNING → CANDIDATE_UNTRUSTED → REVIEW_PENDING → [TRUSTED_VERIFIED|HOLD]`. 장애 전이 `QUOTA_HOLD`, `POLICY_HOLD`, `AUTH_HOLD`, `NETWORK_HOLD`, `COST_UNVERIFIED`, `OWNER_OFF`.
- `429 RESOURCE_EXHAUSTED` / project RPM·TPM·RPD: remote 새 작업 차단·circuit breaker, 서버 Retry-After 또는 사용량 갱신 근거로만 재개. 지속 호출/우회 계정·키 로테이션 금지.
- `401/403` 또는 모델/티어 비가용: AUTO OFF + owner 확인. `5xx/timeout`: bounded retry 최대 1회(명시 개선·멱등 조건 충족 시), 이후 HOLD.
- 모델 중간 중단: lease를 invalidation/fencing, 후보 diff를 `UNTRUSTED`로 격리, 모든 원본 경로/hash 변경 재확인. 동일 task/plan/source/baseline 중복 실행 차단. snapshot/owner 승인 범위가 맞을 때 Qwen에 **재배정 후보**를 만들어 새 epoch에서 실행; 외부 작업 결과를 그대로 이어서 privileged 실행하지 않는다.
- Qwen도 불가하면 `WAITING_LOCAL_CAPACITY`/HOLD, 나머지 독립 READY 지속. 웹 Instant는 자동 fallback 아님; GitHub 큐에 재할당 **제안**만 기록.
- `provider-off`가 되어도 My Local AI의 SQLite 데이터베이스, 기존 작업 큐/증거·승인 범위와 EAI advisor는 살아있어야 한다. provider 제거 시 이전 worker receipt의 SHA/trace를 삭제·변조하지 않는다.

## F18 독립 검증 및 진척 게이트
모델·격리 coder/remote API가 만든 patch, 테스트 결과, 로그, PASS 문자열, `TrustedReceipt`는 전부 **비신뢰**. 별도 권한의 trusted verifier가 정확 SHA·검사 항목·실 OS 격리·테스트 환경을 판정하고 서명·증거 고정을 검증하기 전 `VERIFIED` 승격 금지. 기존 AX F18 취약 신뢰 경계가 해결되지 않으면 auto-integration 및 중요 repo 무인 적용 HOLD. 외부 Hydrogen을 별도 모델로 쓴다는 것만으로 독립 검증 경계가 달성되지 않는다.

P1 기존 28 task/REQ-01~30는 **그대로**. 이 문서의 확장은 `docs/OPTIONAL_PROVIDER_TASK_QUEUE.json`의 `EXT-HYD-01..08` 별도 선택형 큐이며, 기존 구현완료율·공식 검증률 100%에 포함하거나 소급 증감시키지 않는다. 이후 공식 필수 범위 변경은 High가 REQ/가중치/의존성·수용조건과 SHA를 새 기준선으로 작성하고 사용자 별도 범위 승인을 받아야 한다. P2는 계속 LOCKED.

## 수용 테스트(설계, 아직 실행 전)
| ID | 인수조건 | 방법 | 실행 단계 |
|---|---|---|---|
| HYD-AC-01 | `remote_enabled=false`에서 네트워크 호출 0, Qwen 작업 정상 | socket denial synthetic | P1 국소 / P2 전체 |
| HYD-AC-02 | 2 독립 READY는 격리 worktree에서 patch 충돌 없이 저장 | fake provider/fake FS + actual disposable repo | P1 국소 / P2 |
| HYD-AC-03 | 경로/소유권·가로채기·겹침 작업 병렬 차단 | adversarial allowlist/lease tests | P1 즉시 보안 / P2 |
| HYD-AC-04 | quota 429·tier 유료·키 없음·owner OFF 시 remote 0회 | fake transport/count assertions | P1 국소 / P2 |
| HYD-AC-05 | 429/timeout 중복 실행·원본 훼손 없음, Qwen 안전 재배정 | injected failure/restart SQL/worktree recovery | P1 국소 / P2 |
| HYD-AC-06 | private path·secret·customer bytes outbound 전송 0 | canary/DLP fixture & audit | P1 즉시 보안 / P2 |
| HYD-AC-07 | remote coder 위조 `VERIFIED` / 영수증 거부 | F18 adversarial, independent reviewer real OS | P1 즉시 / P2 실제 |
| HYD-AC-08 | 모델별 성능 비교에서 실제 코드·SHA·REQ·테스트 근거만 집계 | fixed 12 synthetic tasks, comparable source SHA | P2 별도 |
| HYD-AC-09 | 유료 티어/비공개 자료/원격 PR은 별도 GO 없이는 fail closed | owner policy tests | P1 즉시 / P2 |
| HYD-AC-10 | remote OFF로 코어 30 REQ baseline 회귀 없음 | baseline test suite on exact SHA | P2 |

## 성능·비용 실험
공개·합성 12개 독립 작업(FFAX UI3, DATA2WEB/DBVORA3, MyLocalAI/AX3, 문서/분석3)을 동일 시작 SHA/allowed_paths/수용조건으로 로컬/외부 후보와 비교하되, 제품 원본·고객 자료는 실험에 쓰지 않는다. 측정: true accepted REQ/hour, code diff quality, build/test run, latency, total tokens, queue wait, retries/HOLD, provider off recovery, billing tier. 단순 자체 벤치마크·Google 마케팅 수치로 구현완료율/예상 가속 배수 주장 금지.

## 공급자 자료 및 확인 시점
- Google 모델 카드(2026-11-12): https://deepmind.google/models/model-cards/gemini-4-hydrogen/
- Gemini API 요금표(현재 무료·유료 티어 구분): https://ai.google.dev/gemini-api/docs/pricing
- Gemini API rate limits(계정·프로젝트별 값 변동): https://ai.google.dev/gemini-api/docs/rate-limits
- 모델 ID `gemini-4-hydrogen`은 문서 표시값이며 실제 계정 호출·쿼터·SDK 호환은 **NOT_RUN**; 유료 가격/무료 정책은 향후 변경 가능. 현재 사용자 계정/API 권한·비용 0 보장 **UNVERIFIED**.

## 변경·되돌리기
이 확장은 문서·큐만 추가. 런타임 코딩/SDK 설치/API 호출/GitHub 권한/원본 수정/Production 배포는 하지 않는다. 향후 실제 구현 시 `remote_enabled=false`가 안전 rollback. Git 복구는 해당 문서 변경 전 HEAD로 되돌릴 수 있으나 기존 커밋 이력을 강제 수정하지 않는다. 설계 브랜치→개발 브랜치 반영은 정확 SHA 및 dev HEAD 확인 후 별도 동기화; 진행 중 Instant 코드/큐 상태 덮어쓰기 금지.


## P1/P2 브라우저 검사 최적화 — 2026-11-17 추가
Hydrogen/Qwen/Instant/Codex 등 **모든 코딩 워커**는 P1에서 BE+FE 실제 코드와 테스트 하네스를 작성하고 문법·타입·최소 빌드·국소 smoke 및 위험 변경의 즉시 안전 검사만 수행한다. 브라우저/Playwright E2E·시각/반응형/a11y 반복 검증은 기본 `DEFERRED_TO_P2`다. 다만 구현 자체에 불가피하거나 인증/권한/비밀/원본 손실/F18 같은 고위험 검사에 필요한 **최소** 브라우저 시나리오를 예외적으로 실행할 수 있으며 정확 SHA/사유/결과를 남긴다. P1 후보는 `IMPLEMENTED_UNVERIFIED`이며 실제 브라우저 PASS를 의미하지 않는다. P2는 기존 High phase gate 이후 전체 E2E/실브라우저/회귀 검증을 수행한다. 기존 필수 CI·안전 정책·선택형 Hydrogen 외부 승인/무료 한도는 변하지 않는다.
