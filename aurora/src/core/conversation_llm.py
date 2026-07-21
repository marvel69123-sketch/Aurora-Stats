"""
Aurora Conversation LLM — OpenAI Conversational Layer.

Architecture
------------
Aurora handles ALL calculations, stats, bankroll, odds, live scoring,
and business rules. OpenAI is called ONLY as a conversational polish
layer to produce natural, contextual, personalised responses.

OpenAI is called for:
  - follow-up questions on a previous analysis
  - open-ended conversational / emotional messages
  - educational / beginner explanations
  - user profile personalisation
  - any message that is subjective or context-dependent

OpenAI is NEVER called for:
  - fixture lookup / statistics / odds
  - live scraping / rankings
  - bankroll calculations / Kelly criterion
  - structured analysis payloads

Public API
----------
  needs_llm(intent: str, message: str, ctx: dict) -> bool
      LLM Router — returns True only when OpenAI should be invoked.

  enhance(
      payload: dict,
      message: str,
      ctx: dict,
      intent: str,
  ) -> dict
      Rewrites payload["executive_summary"] and payload["final_recommendation"]
      using GPT. All numerical fields are left untouched. Returns modified payload.

  chat(
      message: str,
      ctx: dict,
      intent: str,
      brain_meta: dict,
  ) -> dict
      Pure-conversational fallback — returns a CopilotResponse-compatible
      payload when there is no structured Aurora data to enhance.

Cache
-----
  Simple in-process LRU cache keyed on (norm_message, norm_context_hash).
  Avoids duplicate LLM calls within the same server process lifetime.
  Max 256 entries; entries expire after CACHE_TTL_SECONDS.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from functools import lru_cache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")
OPENAI_API_KEY  = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "")
MODEL           = "gpt-5.4-mini"      # cost-effective; fast enough for conversational layer
MAX_TOKENS      = 800                 # keep responses concise for the chat UI
CACHE_TTL_SECS  = 300                 # 5-minute in-process cache

# Intents that should ALWAYS be enhanced by the LLM
# NOTE: "emotional" removed — Emotional Presence owns those turns (v4.7.2).
# LLM fallback "Posso ajudar com leituras..." must never overwrite pride/thanks.
_LLM_INTENTS: frozenset[str] = frozenset({
    "fear",
    "had_losses",
    "beginner",
    "wants_to_learn",
    "confused",
    "wants_safer",
    "follow_up",
    "unknown",
    "user_profile_query",
})

# Intents that must NEVER invoke the LLM (pure calculation)
_NO_LLM_INTENTS: frozenset[str] = frozenset({
    "analyze_match",
    "live_opportunities",
    "bankroll_review",
    "learning_recap",
    "knowledge_search",
})

# ---------------------------------------------------------------------------
# Simple TTL cache (avoids repeated LLM calls for identical inputs)
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[str, float]] = {}   # key → (response_text, timestamp)
_CACHE_MAX = 256


def _cache_key(message: str, ctx_hash: str) -> str:
    raw = f"{message.strip().lower()}|{ctx_hash}"
    return hashlib.md5(raw.encode()).hexdigest()


def _ctx_hash(ctx: dict) -> str:
    last_match  = ctx.get("last_match", "")
    last_intent = ctx.get("last_intent", "")
    profile     = ctx.get("user_profile", {})
    raw = f"{last_match}|{last_intent}|{profile.get('experience_level','')}|{profile.get('risk_preference','')}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_get(key: str) -> str | None:
    entry = _cache.get(key)
    if not entry:
        return None
    text, ts = entry
    if time.time() - ts > CACHE_TTL_SECS:
        _cache.pop(key, None)
        return None
    return text


def _cache_set(key: str, value: str) -> None:
    if len(_cache) >= _CACHE_MAX:
        # Evict oldest entry
        oldest = min(_cache, key=lambda k: _cache[k][1])
        _cache.pop(oldest, None)
    _cache[key] = (value, time.time())


# ---------------------------------------------------------------------------
# LLM Router (Phase 6 — cost control)
# ---------------------------------------------------------------------------

def needs_llm(intent: str, message: str, ctx: dict) -> bool:
    """
    Return True only when calling the LLM is warranted.

    Rules (in priority order):
      1. Pure-calculation intents → always False.
      2. Presence / emotional / natural conversation → False (dedicated layers).
      3. Selected conversational intents → True.
      4. Greeting / identity / capabilities / help → False (templated responses are fine).
      5. Fallback: True when message has >10 words and context has a last_match
         (likely a nuanced follow-up the rule engine missed).
    """
    if intent in _NO_LLM_INTENTS:
        return False
    # v4.7.2 — never let LLM clobber emotional / presence short-circuits
    if intent in ("emotional", "small_talk", "capabilities", "greeting", "identity", "help"):
        return False
    if intent in _LLM_INTENTS:
        return True
    # Nuanced message with prior context
    word_count = len(message.split())
    if word_count > 10 and ctx.get("last_match"):
        return True
    return False


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def _build_system_prompt(ctx: dict) -> str:
    user_profile = ctx.get("user_profile", {})
    exp     = user_profile.get("experience_level")
    risk    = user_profile.get("risk_preference")
    bankroll= user_profile.get("bankroll")
    markets = user_profile.get("preferred_markets", [])
    last_match  = ctx.get("last_match", "")

    exp_map  = {"beginner": "iniciante", "intermediate": "intermediário", "experienced": "experiente"}
    risk_map = {"conservative": "conservador", "moderate": "moderado", "aggressive": "agressivo"}

    profile_lines: list[str] = []
    if exp:
        profile_lines.append(f"- Nível de experiência: {exp_map.get(exp, exp)}")
    if risk:
        profile_lines.append(f"- Perfil de risco: {risk_map.get(risk, risk)}")
    if bankroll:
        profile_lines.append(f"- Banca declarada: R${bankroll:.0f}")
    if markets:
        profile_lines.append(f"- Mercados preferidos: {', '.join(markets)}")
    if last_match:
        profile_lines.append(f"- Última partida analisada: {last_match}")

    profile_block = (
        "\n\nPerfil do usuário nesta sessão:\n" + "\n".join(profile_lines)
        if profile_lines else ""
    )

    # Tone adapts to experience
    if exp == "beginner":
        tone_note = (
            "O usuário é iniciante. Use linguagem simples, evite jargões. "
            "Quando usar termos técnicos (como VE, Kelly, xG), explique brevemente."
        )
    elif exp == "experienced":
        tone_note = (
            "O usuário é experiente. Pode usar terminologia técnica sem explicação. "
            "Seja direto e denso nas informações."
        )
    else:
        tone_note = "Equilíbrio entre clareza e profundidade técnica."

    return f"""Você é Aurora — especialista em futebol, apostas esportivas, análise de risco e gestão de banca.

REGRAS ABSOLUTAS:
1. Responda SEMPRE em português brasileiro — nunca em inglês.
2. Jamais invente estatísticas, odds, probabilidades ou dados de partidas. Se não souber, diga claramente.
3. Não substitua os cálculos da Aurora — eles já foram feitos pelos motores internos. Sua função é comunicar, contextualizar e conversar.
4. Admita incerteza quando necessário.
5. Seja conciso — o usuário vê respostas em um chat. Máximo de 250 palavras.
6. Use markdown: **negrito** para termos-chave, • para listas, ## para seções quando necessário.

PERSONALIDADE:
- Amigável, profissional e empática.
- Faz perguntas quando necessário: "Quer uma análise mais conservadora?", "Sua banca continua em R$100?".
- Lembra preferências: "Noto que você prefere apostas mais seguras."
- Natural — não robótica.

{tone_note}{profile_block}"""


# ---------------------------------------------------------------------------
# OpenAI client (lazy init to avoid import errors when key is absent)
# ---------------------------------------------------------------------------

def _get_client():
    """Return a configured OpenAI client or raise a clear error."""
    if not OPENAI_BASE_URL or not OPENAI_API_KEY:
        raise RuntimeError(
            "AI_INTEGRATIONS_OPENAI_BASE_URL or AI_INTEGRATIONS_OPENAI_API_KEY not set. "
            "Run setupReplitAIIntegrations to provision them."
        )
    from openai import OpenAI
    return OpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# Core LLM call
# ---------------------------------------------------------------------------

def _call_llm(system: str, messages: list[dict]) -> str:
    """
    Call gpt-5.4-mini with the given system + message history.
    Returns the assistant reply text, or raises on error.
    """
    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": system}] + messages,
    )
    return (response.choices[0].message.content or "").strip()


# ---------------------------------------------------------------------------
# Context message builder
# ---------------------------------------------------------------------------

def _build_messages(message: str, ctx: dict, aurora_summary: str = "") -> list[dict]:
    """
    Build the message list for the LLM, injecting prior context as an
    assistant turn so the LLM understands what Aurora already said.
    """
    msgs: list[dict] = []

    last_anal = ctx.get("last_analysis") or {}
    last_match = ctx.get("last_match", "")

    # If we have a previous analysis, inject it as an assistant turn so
    # the LLM has the structured data to reference in its reply.
    if last_match and last_anal:
        exec_sum = last_anal.get("executive_summary", "")
        final_rec = last_anal.get("final_recommendation", "")
        markets = last_anal.get("best_markets", [])
        best_mkt = markets[0].get("market", "") if markets else ""
        prev_context = (
            f"[Análise anterior: {last_match}]\n"
            + (f"Resumo: {exec_sum[:300]}\n" if exec_sum else "")
            + (f"Melhor mercado: {best_mkt}\n" if best_mkt else "")
            + (f"Recomendação final: {final_rec}" if final_rec else "")
        ).strip()
        if prev_context:
            msgs.append({"role": "assistant", "content": prev_context})

    # If Aurora already computed a structured summary, inject it so the
    # LLM can rewrite/enhance it rather than fabricating content.
    if aurora_summary:
        msgs.append({
            "role": "assistant",
            "content": f"[Dados Aurora calculados]\n{aurora_summary}",
        })

    msgs.append({"role": "user", "content": message})
    return msgs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enhance(payload: dict, message: str, ctx: dict, intent: str) -> dict:
    """
    Rewrite payload["executive_summary"] and payload["final_recommendation"]
    using GPT for a more natural, contextual, personalised response.

    All numerical fields (best_markets, confidence, risk, bankroll_recommendation,
    positive_factors, negative_factors) are preserved UNCHANGED.

    Returns the modified payload dict (in-place modification + return).
    """
    aurora_summary = payload.get("executive_summary", "")
    ck = _cache_key(message, _ctx_hash(ctx) + aurora_summary[:100])
    cached = _cache_get(ck)
    if cached:
        logger.debug("conversation_llm: cache hit for intent=%s", intent)
        payload["executive_summary"] = cached
        return payload

    system = _build_system_prompt(ctx)
    enhance_instruction = (
        f"O usuário disse: \"{message}\"\n\n"
        f"A Aurora calculou os dados abaixo. Reescreva o resumo de forma mais natural, "
        f"contextual e personalizada. Mantenha todos os dados numéricos precisamente como estão. "
        f"Não invente nenhum número novo. Seja conciso (máximo 200 palavras).\n\n"
        f"Resumo Aurora:\n{aurora_summary}"
    )
    msgs = _build_messages(enhance_instruction, ctx)

    try:
        rewritten = _call_llm(system, msgs)
        if rewritten:
            _cache_set(ck, rewritten)
            payload["executive_summary"] = rewritten
            logger.info("conversation_llm: enhanced summary for intent=%s (%d chars)", intent, len(rewritten))
    except Exception as exc:
        logger.warning("conversation_llm: enhance failed (%s) — using Aurora summary", exc)
        # Graceful degradation: keep the original summary

    return payload


def chat(message: str, ctx: dict, intent: str, brain_meta: dict) -> dict:
    """
    Pure-conversational response — no prior structured Aurora data.

    Used when intent is conversational/emotional/unknown and there is
    no structured analysis payload to enhance.

    Returns a CopilotResponse-compatible payload dict.
    """
    ck = _cache_key(message, _ctx_hash(ctx))
    cached = _cache_get(ck)

    system = _build_system_prompt(ctx)
    msgs   = _build_messages(message, ctx)

    if cached:
        reply = cached
        logger.debug("conversation_llm: chat cache hit for intent=%s", intent)
    else:
        try:
            reply = _call_llm(system, msgs)
            if reply:
                _cache_set(ck, reply)
                logger.info("conversation_llm: chat response for intent=%s (%d chars)", intent, len(reply))
        except Exception as exc:
            logger.warning("conversation_llm: chat failed (%s) — falling back to rule engine", exc)
            reply = ""

    # Extract a short final recommendation from the reply (last sentence)
    if reply:
        sentences = [s.strip() for s in reply.replace("\n", " ").split(".") if s.strip()]
        final_rec = sentences[-1] + "." if sentences else reply[:120]
    else:
        final_rec = "Se tiver um jogo em mente, posso analisar com você."

    return {
        "intent":   intent,
        "entities": {},
        "match":    ctx.get("last_match"),
        "status":   None,
        "is_live":  False,
        "minute":   None,
        "executive_summary": reply or (
            "Posso ajudar com leituras de partidas e mercados.\n"
            "Qual confronto você gostaria de observar?"
        ),
        "best_markets": [],
        "confidence": {
            "score":       0.0,
            "label":       "conversational",
            "explanation": "Resposta conversacional — sem dados estruturados.",
            "data_sources": ["Aurora Conversation LLM"],
        },
        "risk": {"level": "N/A", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method":                "quarter-Kelly",
            "examples":              {},
            "no_bet":                True,
            "reasoning":             "Sem partida analisada.",
        },
        "positive_factors":      [],
        "negative_factors":      [],
        "historical_references": [],
        "knowledge_notes":       [],
        "final_recommendation":  final_rec,
        "aurora_version":        "Copilot v1.0 + LLM",
        "brain":                 brain_meta,
    }
