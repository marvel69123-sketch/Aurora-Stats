"""
Optional LLM soft-judge.

Enabled only when AURORA_JUDGE_LLM=1 and an API key exists.
Never invents match stats; only scores conversational quality.
On any failure, returns None (caller keeps rubric scores).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


def llm_judge_enabled() -> bool:
    flag = (os.environ.get("AURORA_JUDGE_LLM") or "").strip().lower()
    if flag not in {"1", "true", "yes", "on"}:
        return False
    return bool(
        (os.environ.get("OPENAI_API_KEY") or os.environ.get("AURORA_OPENAI_KEY") or "").strip()
    )


def soft_judge_conversation(
    turns: list[dict[str, Any]],
    *,
    rubric: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Ask LLM for soft scores. Hard floor: cannot raise credibility above rubric
    when rubric credibility <= 4 (INVALID / invention risk).
    """
    if not llm_judge_enabled():
        return None
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        logger.warning("[AUDIT] LLM Judge: openai package unavailable")
        return None

    transcript = []
    for t in turns[-8:]:
        transcript.append(f"USER: {t.get('message')}")
        transcript.append(f"AURORA: {t.get('summary_prefix') or ''}")
    prompt = (
        "You are a conversational quality judge for a football analytics assistant.\n"
        "Score 0-10 for: understanding, utility, continuity, credibility, "
        "naturalness, clarity, overall.\n"
        "Do NOT invent match statistics. Return ONLY compact JSON keys: "
        "understanding,utility,continuity,credibility,naturalness,clarity,overall.\n\n"
        f"TRANSCRIPT:\n" + "\n".join(transcript)
    )
    try:
        client = OpenAI()
        resp = client.chat.completions.create(
            model=os.environ.get("AURORA_JUDGE_MODEL") or "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200,
        )
        text = (resp.choices[0].message.content or "").strip()
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        data = json.loads(m.group(0))
    except Exception as exc:
        logger.warning("[AUDIT] LLM Judge call failed: %s", exc)
        return None

    def _num(key: str, fallback: float) -> float:
        try:
            return max(0.0, min(10.0, float(data.get(key, fallback))))
        except (TypeError, ValueError):
            return fallback

    out = {
        "understanding_score": round(_num("understanding", rubric.get("understanding_score", 7)), 1),
        "utility_score": round(_num("utility", rubric.get("utility_score", 7)), 1),
        "continuity_score": round(_num("continuity", rubric.get("continuity_score", 7)), 1),
        "credibility_score": round(_num("credibility", rubric.get("credibility_score", 7)), 1),
        "naturalness_score": round(_num("naturalness", rubric.get("naturalness_score", 7)), 1),
        "clarity_score": round(_num("clarity", rubric.get("clarity_score", 7)), 1),
        "overall_score": round(_num("overall", rubric.get("overall_score", 7)), 1),
        "judge_mode": "llm+rubric",
    }
    # Hard floor on credibility when rubric already flagged risk
    rub_cred = float(rubric.get("credibility_score") or 10)
    if rub_cred <= 4.0:
        out["credibility_score"] = min(out["credibility_score"], rub_cred)
        out["overall_score"] = min(out["overall_score"], max(rub_cred + 1.0, 0))
    return out
