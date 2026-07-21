# Deploy health evidence — 2026-07-20
Corpus: 36 log-like files under artifacts/aurora (observations/** smoke/uvicorn, roadmap *.log/*out*, root smoke/uvicorn).
Live: TestClient /aurora/healthz + /aurora/chat + /aurora/copilot SPORT path.
Note: validate_p25_sport_understanding.py is design-only (no product TestClient); used TestClient instead.

## Healthz
- GET /aurora/healthz -> 200 {"status":"ok","service":"Aurora","version":"1.1.0","backend_commit":"b984c48"}

## ERROR lines (deduped, with source)

### Live smoke (fatal for analyze_match path)
1. source: sport_smoke_capture*.txt / src.core.copilot_engine
   ERROR [src.core.copilot_engine] Copilot dispatch error [analyze_match]: 'Query' object has no attribute 'strip'
   class: FATAL (for /aurora/chat analyze_match) — AttributeError in cost_protection.begin_request when user_id is FastAPI Query object; HTTP still 200 with user-facing error string.

### Historical artifacts (non-namespace logger ERROR mostly absent)
2. source: artifacts/aurora/_smoke_out.txt
   NameError: name 'test3_calendar_followup' is not defined
   class: HARMLESS (local smoke script bug, not runtime product path)

3. source: artifacts/aurora/uvicorn-err2.log
   ERROR: Traceback ... OSError: [WinError 10022] Foi fornecido um argumento inválido
   class: HARMLESS/local — Windows uvicorn socket bind/serve issue during old local start

4. source: artifacts/aurora/uvicorn-err2.log
   asyncio.exceptions.CancelledError
   class: HARMLESS — shutdown/cancel during uvicorn teardown

5. source: roadmap/p3a4_diagnosis_run.log, roadmap/_p3a6_after_cert_run.log (pattern, ~979 hits)
   API-Football rateLimit / status=429 / teams_search|fetch|live_sweep|stale_cache failures
   class: DEGRADATION — external quota; sport data freshness/search degraded; often fail-open or stale cache

6. No `ERROR [src.conversation|src.routers|aurora.pipeline_trace]` logger lines found in scanned corpus (0 hits).

## TRACEBACK blocks summary
1. _smoke_out.txt:99 — NameError test3_calendar_followup (smoke script)
2. uvicorn-err2.log:9 — OSError WinError 10022 (uvicorn serve)
3. uvicorn-err2.log:36 — CancelledError (uvicorn shutdown)
4. uvicorn-err2.log:47 — truncated/nested uvicorn serve frame
5. LIVE sport_smoke_capture*.txt — AttributeError in cost_protection.begin_request via analyze.py analyze_fixture <- copilot_engine._handle_analyze (analyze_match path)

## WARNING lines from three namespaces (representative / top loops)

Audit/trace WARNINGs are intentionally verbose (pipeline_trace + AUDIT). Top repeats (>5 = loop pattern YES):

| count | message pattern | class | reason |
|------:|-----------------|-------|--------|
| 54 | turn_ownership [OWNER_AFTER] owner=SPORT locked=True | harmless | intentional audit spam |
| 36 | pipeline_trace [OWNER_AFTER] owner=SPORT locked=True intent=follow_up | harmless | intentional audit |
| 24 | turn_ownership [FINAL_SOURCE] owner=SPORT locked=True | harmless | intentional audit |
| 21 | copilot_unified_router ContextReinforcement fx=0.00 mkt=0.00 | harmless/degradation | low reinforcement signal; observability |
| 18+ | OWNER_BEFORE/AFTER GA|SPORT locked | harmless | ownership lock churn audit |
| 15 | ThinkingDelay SKIPPED / ResponseReview skipped | harmless | ownership guards |
| 14 | IntelFallback/Reasoner/CIL/SmallTalk skipped — owned | harmless | ownership protection working |
| 12 | INTENT/ROUTE SPORT_QUERY sport_signal | harmless | intent audit |
| live×4 | natural_conversation fixtures fetch fail-open: 500 API_FOOTBALL_KEY not configured | degradation | local env missing API key; fail-open continues |
| hist | pipeline_trace [FALLBACK] source=intelligence_fallback + FINAL_RESPONSE fallback=True | degradation | some turns fell back to intelligence_fallback (phase84a* smokes) |
| live | WebSynthesis mode=light status=fallback_no_web | degradation | web intel unavailable; local reasoning |

## Warning loop pattern
YES — same OWNER_*/AUDIT messages repeat >>5 times per multi-turn smoke (54× OWNER_AFTER SPORT). Expected from WARNING-level audit logging, not a retry storm.
Also LIVE: natural_conversation fixtures fetch fail-open repeated 4× in one request (same message cluster; near-loop).

## Live SPORT path outcome
- /aurora/chat "Flamengo x ..." -> intent=analyze_match, HTTP 200, body contains processing error (Query.strip) → FATAL functional for analyze path
- /aurora/copilot same opinion prompt -> intent=conversation_assist, owner=SPORT, HTTP 200, team_summary without live fixtures (API key missing) → DEGRADATION not crash

## Raw extracts directory
artifacts/aurora/observations/deploy_health_20260720/
- scanned_files.txt, errors_*.txt, warnings_*.txt, traceback_summaries.txt
- sport_smoke_capture.txt, sport_smoke_capture2.txt, live_smoke_ewt_extract.txt
- FINDINGS.md (this file)
