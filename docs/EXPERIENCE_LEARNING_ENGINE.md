# My Local AI — Experience Learning Engine 최종설계 V1.2
**결정일:** 2026-11-17 KST · **상태:** 설계 확정 / 코드 구현·실사용 검증 NOT_RUN

> 본 확장은 My Local AI의 독립 Controller·Qwen/OpenCode 기본 실행·선택형 EAI Advisor·선택형 Hydrogen ProviderPort를 보존한다. **실제 개발 경험으로 선택 전략을 개선**하는 소프트웨어 기능이며, LLM 가중치 학습이나 Codex/Sol Max 내부 추론 복제 프로젝트가 아니다. 모델의 답변 자체는 사실/테스트 PASS/허가된 학습 데이터라는 증거가 아니다.

## 1. 사용자 의도 및 불변 목표
- 수백·수천 개의 상황 변수/if문을 사전에 하드코딩하지 않는다. 승인된 작업을 실제 수행한 결과에서 **증상→가설→선택한 조치→코드 변화→독립 수용 테스트→실패/재시도**를 관찰한다.
- 검증된 자기 소유 개발 기록과 독립 테스트를 바탕으로 반복 패턴을 찾아, 같은 유형 작업에서 **작업 분할·관련 SKILL.md/템플릿 선택·테스트/복구 우선순위**를 개선한다.
- **수동 질문 대량 수집은 하지 않는다.** Sol Max/다른 제공자에게 질문하는 작업은 사용자가 적법하게 승인한 특정 소프트웨어 개발/기술 검수의 범위에 국한하고, 답변을 모아서 Codex를 대체할 모델의 학습자료·신호·선호 라벨·평가셋으로 만들지 않는다. 숨은 추론/비공개 내부 reasoning 추출·계정 한도 우회·자동 채팅 수집 금지. 서비스별 현재 약관·권리/데이터 동의 확인 필수.
- 결정론적 **안전 불변 정책**(owner GO, allowed_paths, 돈0, 외부송신 차단, 모델/도구 권한, F18 신뢰 경계, DB/원본/비밀 보호, CI·브랜치 보호)은 어떠한 경험·점수·추천으로도 해제할 수 없다.
- 기능 추가는 기존 **P1 REQ-01~30 / 구현 28작업, P2 검증 8작업/LOCKED**를 소급 변경하지 않는다. P1의 브라우저 전수 검증은 P2에 후행. 확장 기능 구현은 별도 승인/정확 HEAD 충돌 확인 후 새 큐에서 수행한다.

## 2. 설계 대안
| 대안 | 장점 | 비용/성능/보안 단점 | 결론 |
|---|---|---|---|
| A. 많은 고정 규칙/AXNODE만 먼저 만들기 | 일관적·단순 | 조합 폭발, 포맷 런타임 선행 비용, 새 상황 대응 취약 | 핵심 안전 규칙에만 사용 |
| B. Sol Max 답변 수천 건 저장·모델 모방 | 답변량 확보 | 검증 없는 오류 누적·토큰 소비·정책/권리 위험·실행능력 보장 없음 | 채택하지 않음 |
| **C. 자기 개발 결과 기반 경험·스킬 최적화** | 독립 증거로 품질 측정, 로컬 SQLite/FTS5와 Python으로 즉시 시작 가능 | 경험 오염·과적합 위험을 gate/실험으로 통제 | **채택** |

## 3. 계층과 데이터 흐름
```text
High-approved PlanSpec + immutable source/plan SHA + owner scope
        |
        v
My Local AI Controller [DAG/READY/allowed_paths/consent/budget — 최종 권한]
        |                        + optional EAI AdvisorPort (non-authoritative)
        v
ExperienceSelector (읽기 전용; 안전정책보다 낮은 우선순위)
  1. 작업/환경/언어/도구버전/위험도 분류 — deterministic
  2. SQLite FTS5 + 메타데이터/정확 SHA 검색 (옵션; FTS5 없으면 기본 검색)
  3. trusted-evidence / compatibility / conflicts / expiry filter
  4. top-k <= 3 관련 skill/template/experience suggestion + 근거
        |
        v
Local Qwen/OpenCode coder (기본) | optional approved remote Hydrogen
        |
        v
isolated CandidateDiff (UNTRUSTED) + exact source/run/task SHA
        |
        v
Trusted F18 independent verifier / outcome evidence [PASS/FAIL/NOT_RUN]
        |
        v
ExperienceCollector (redacted, append-only raw record; NEVER self-VERIFIED)
        |
        v
Curator / PromotionGate: candidate → test on separate synthetic cases
        |                                  └ fail => QUARANTINED / REJECTED
        v
Versioned skills/decision hints (shadow mode -> owner GO -> scoped active)
        |
        v
Next independently approved READY; keep previous version and rollback
```
AXNODE는 **미래의 독립 실행 패키지·typed graph export**용 선택 어댑터다. 학습/경험 원장의 기본 저장 포맷을 미구현 독자 `.axnode` 바이너리 형식에 종속시키지 않는다. AX Dev Factory 기술·기존 성공 코드/테스트는 출처/라이선스/동일 SHA 검증 후에만 재사용한다.

## 4. 경험 수집·비신뢰·권리 경계
**허용된 원천:** 사용자가 소유하고 권리를 가진 소스에서 발생한 실제 작업 이벤트, 승인된 공개·합성 fixture, 도구의 종료코드, 독립 F18 verifier의 실제 테스트 실행 결과, 로컬 수동 작성 스킬/템플릿, 적법하게 사용 가능한 기술 문서. 사용자 자신의 REQ/계약/변경 근거를 별도 보관한다.
**금지 또는 HOLD:** 민감 고객 코드/프롬프트/개인정보, 계정 비밀/토큰, 비공개 데이터의 공개 repo 게시, 대량 API/웹채팅 스크래핑, 공급자 출력의 경쟁 모델 훈련용 선별/라벨링/보상, 지시 우회·보호된 추론 추출, 약관 미확인 third-party 문서의 무단 복제. 외부 모델 답변은 요청한 프로젝트의 **비권한 개발 참고자료**일 뿐 자동 학습의 유일한 근거가 아니며, 허가된 경우에도 정본으로 저장하는 것은 주로 **자기 소유 코드 diff·실제 실행 결과**다.
**데이터 최소화:** 기록 전 데이터 등급 검사 + redaction → 키워드·오류코드·버전·프로젝트별 공개 가능한 해시/요약만 local SQLite에 저장. 원본 stack trace/시스템 경로/프롬프트·private diff는 기본 저장하지 않음. 공개 GitHub에는 정책 코드·스키마·합성 fixture만; 사용자 PC의 실제 기록·SQLite/로그는 외부 분리. 저장 거부/삭제 정책·TTL·사용자 export/delete controls를 설계; 실제 파기 기능과 보존 기간은 구현/사용 승인 때 확정.

## 5. BE / API / DB / FE 목표 (실제 구현 전 경로·스키마 충돌 확인)
- **BE**: `src/my_local_ai/experience/{schema,collector,retrieval,curator,policy,skills}.py` + `tests/{unit,security,integration}/test_experience_*.py` 후보. core Controller는 provider/skill의 승인 권한을 신뢰하지 않고 추천만 읽는다.
- **SQLite (one writer)**: `experience_events` (event_id/run_id/task_id/req_ids/source_sha/plan_sha/outcome/test_receipt_ref/error_fingerprint/environment_digest/observed_at/redaction_version/rights_tag), `experience_candidates` (candidate_id/event_refs/suggested_skill/path/rationale/uncertainty/state), `skill_versions` (skill_id/version/content_sha/approved_scope/parent/rollback_ref/expiry), `retrieval_decisions` (task_id/selected_refs/exclusion_reasons/evaluation_sha), `experience_approvals` (scope,actor,revoked_at), optional SQLite `FTS5` indexed **redacted** summaries only. Migration APP_ID/checkpoint/backup & no unknown DB write.
- **수집 계약**: `ExperienceEventV1`은 event/plan/source SHA, test run id, runner identity, trusted verifier receipt ref, rights/sensitivity, environment/tool versions, observed timestamp, proposed root cause, success/failure tags를 구분. 원격 모델·게스트가 `trusted=true`, test PASS, owner GO를 직접 지정하면 무조건 reject.
- **추천 계약**: `ExperienceSuggestionV1`: record IDs, similarity features, evidence tier, applicability constraints, known conflicts, expiry, confidence **estimate**(증거 기반과 구별), rationale, fallback; `approved=false`가 초기값. 추천은 명령/권한/승격/안전 체크를 변경할 수 없다. 안전 filter → token/context budget 검사를 통과한 상위 3개만 전달, 없거나 충돌 시 **no-memory baseline**.
- **상태기계**: `OBSERVED_UNTRUSTED → CURATION_PENDING → SYNTHETIC_TESTED → TRUSTED_EVIDENCE_CHECKED → OWNER_APPROVED_ACTIVE`; 불일치/비밀/오염 시 `QUARANTINED/REVOKED/EXPIRED`. test 없이 모델 본인의 PASS로 상태 승격 불가. `SYNTHETIC_TESTED`만으로 실사용 검증 완료 아님.
- **FE/CLI**: 기본 read-only `mla experience status/search/inspect/export-redacted` 및 근거·거부 이유·원본 SHA/skill version 표시. `learn/approve/revoke/delete`는 승인 범위/저장 정책 확정 및 보안 심사 후. 사용자의 외출 중 브라우저/OTP 팝업으로 P1 READY를 멈추지 않는다.
- **복구**: append-only 관측 로그와 versioned skill을 유지하되 권리 범위/보존 정책에 따른 안전 삭제 지원, experience를 끄거나 SQLite FTS가 없어도 Qwen 기본 실행·F18 보호 경계 정상. 자동 rollback은 정확 부모 hash 및 독립 복구 승인이 있을 때만.

## 6. 선택·실험·학습 알고리즘
1. **Harvest AFTER execution**: 실행 전 정답 라벨 생성이 아니라 실행 후 관찰 가능한 결과부터 기록한다. test run이나 F18 receipt가 없으면 `UNVERIFIED_OBSERVATION`으로만 보관, 재사용 우선순위 낮음/자동 promotion 금지.
2. **Normalize**: 소스/계약 SHA, 언어·컴파일러·의존성, 오류 코드·위험 유형, 변경 경로 카테고리·버전·테스트 환경을 구조화한다. 추론된 원인은 `HYPOTHESIS`, 확인된 원인은 `VERIFIED_CAUSE`로 분리한다.
3. **Retrieve**: 안전/권리/민감도 필터 우선; 같은 언어/버전/수정 경계/에러 타입/수용조건과 가장 유사한 사례 top-k. 충돌하는 스킬은 함께 주입하지 않는다. 비신뢰 저장된 텍스트의 도구/쉘/정책 지시를 실행하지 않는다.
4. **Promote**: 자체·공개/합성 적법 사례의 동일 시작 SHA에서 baseline vs skill-assisted A/B 시험. independent verifier 결과, accepted REQ/hour, 재작업률·원본 무결성·권한 위반·자원/메모리·토큰/시간을 비교한다. 효과 없거나 regress하면 SHADOW/HOLD/revoke. 통계적 확실성 없는 소량 결과를 '성능 향상 입증'이라 하지 않음.
5. **Adapt**: 처음에는 사람이 승인한 skill 후보만 active. 충분히 반복되면 whitelist된 특정 위험 낮은 작업에만 자동 추천할 수 있지만 **자동 승인/자기 코드 merge/검증 통과/새 외부 API 사용은 불허**. 실패·예외·상충을 같이 기억하고, 향후 환경이 달라지면 자동 낮은 우선순위/재검증.
6. **Retire**: 오래되거나 깨진 스킬/환각/유출 징후는 quarantine·rollback; 이전 승인과 SHA 증거는 보존 정책 범위 내에서 감사 가능하게 유지.

## 7. 안전·평가 수용 매트릭스 (모두 NOT_RUN)
| ID | 필수 조건 | 테스트 시점 |
|---|---|---|
| EXP-AC-01 | 경험 엔진 OFF여도 기존 30 REQ 범위 Qwen/Controller 정상·외부 egress 0 | P1 좁은 local / P2 회귀 |
| EXP-AC-02 | 잘못된 tenant/project/source SHA/권리 없는 기록은 검색·자동 적용 거부 | P1 즉시 안전 |
| EXP-AC-03 | 모델·게스트가 위조한 test PASS/F18 receipt/GO는 경험 승격 불가 | P1 즉시 안전 + P2 |
| EXP-AC-04 | private code/토큰/프롬프트·PII canary가 로그·공개 repo·external로 누출 0 | P1 즉시 안전 + P2 |
| EXP-AC-05 | 독립 사례 top-3 선택 및 안전 충돌/오래된 버전 제외, 빈 검색은 정상 baseline | P1 국소 / P2 |
| EXP-AC-06 | skill version 변경·revocation·rollback 시 중복 실행/원본 파일 변경 0 | P1 국소 / P2 통합 |
| EXP-AC-07 | 실제 benchmark에서 no-memory baseline vs scoped experience 의 accepted REQ/hour, fail/HOLD, 테스트/보안 결과·차이를 정확 SHA로 기록 | P2 |
| EXP-AC-08 | 과거의 위조/실패·잘못된 추론에 의한 경험 오염을 격리하고 하향 조정 | P1 즉시 안전 + P2 |
| EXP-AC-09 | AXNODE 미설치/미구현, 외부 API OFF, UI 브라우저 NOT_RUN에서도 MLA P1 구현 진행 | P1 |
| EXP-AC-10 | 사용자 GO 없이 새 수집 범위·외부 송신·브라우저 로그인·실 고객 자료·자가 학습/모델 파인튜닝 없음 | P1 정책 검사 + P2 |

## 8. 실행 순서·상태·승인
- 기존 P1 READY `MLA-012` 및 후속 BE/FE 구현을 **우선 진행**. 경험 엔진은 학습형 최종 비전의 **독립 확장 명세**로 설계 반영하되, 기존 P1 30 REQ/28작업 공식 분모를 변경하거나 즉시 새로운 READY로 만들지 않는다. 확장 큐는 `docs/OPTIONAL_EXPERIENCE_TASK_QUEUE.json`의 `EXT-EXP-01..07`이고 첫 6개는 local synthetic/mock only. 충분한 증거 없는 실제 사용자 프로젝트로의 자동 학습/승격은 HOLD.
- P2는 기본 P1 구현 후보 + High 정확 SHA 수용 게이트 후에만 시작한다. 전체 CI·실 브라우저/Windows/Qwen·보안·통합 검증을 P2에 보존. 작업을 수행하지 않은 모델·독립 감사는 `NOT_RUN`.
- 향후 이 학습 기능을 MLA 필수 REQ로 통합하기로 결정하면 High가 새 전체 REQ-ID·기능 범위/가중치·작업 분모/수용·이식경로·기존 기록 migration을 재기준화하고 사용자 별도 scope GO를 받는다.
- 설계만으로 Codex 대체율, 비용 절감, 지능 향상, 테스트 PASS, 성공률 증가를 주장하지 않는다.

## 9. 정책·기술 근거
- OpenAI 사용 약관: https://openai.com/policies/terms-of-use/
- OpenAI 사용 정책: https://openai.com/policies/usage-policies/
- 허용된 일상적 소프트웨어 개발·개발 결과 검토와, 대체 모델의 학습자료/신호 조성을 구분한다. 필요시 사용하는 서비스별 최신 약관·권한/데이터 전송 조건을 다시 검증한다.

## 10. V2.0 상위 통합 규칙 — MESA 명칭 및 재사용 (2026-11-18)

본 V1.2 문서는 **MESA(MLA Experience & Strategy Advisor)의 기존 기능·수용조건 정본**으로 승계한다. 새 시스템/새 7 SWU를 중복 신설하지 않는다. EXT-EXP-01..07의 ID·allowed_paths·수용조건·이력은 보존하고, V2.0 세부 계약/확장은 [V2 최종 통합설계](MLA_V2_FINAL_ARCHITECTURE_MESA_AXZERO_20261118.md)와 [별도 V2 접점 4 SWU](OPTIONAL_V2_INTEGRATION_TASK_QUEUE.json)를 따른다. EAI 독립 제품은 개명/이식하지 않고 기존 advisors/eai.py는 선택형 비권한 포트로 유지한다. ExperienceRecordV2는 기존 V1 필드를 확장·호환하는 마이그레이션 계획이지 실 DB 변경 승인 아님. Evidence Gate의 REUSABLE_ADVICE는 서명·재검증 또는 자동 실행 허가가 아니다. 모델 답변/실패 가설은 후보 데이터만 된다.
