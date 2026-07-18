# AEP Phase 4 — Implementation Guide

```bash
cd artifacts/aurora
python scripts/run_llm_judge.py --conversations 40
python scripts/run_llm_judge.py --conversations 100 --persona short_followup --quiet
```

Optional LLM:

```bash
set AURORA_JUDGE_LLM=1
set OPENAI_API_KEY=...
python scripts/run_llm_judge.py --conversations 20
```

Audit mode: call copilot with `debug=true` → `debug.llm_judge`.

Do not use judge scores to rewrite production replies or bypass AEP hard fails.
