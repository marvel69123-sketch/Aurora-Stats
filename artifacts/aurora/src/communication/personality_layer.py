"""
Aurora Personality & Communication Layer (Phase 6).

Presentation-only. Does NOT change analytical engines, EntityResolver,
Follow-Up detection logic, Conversation Memory, frontend, or deploy.

Applied to user-facing fields after engines / follow-up / i18n:
  executive_summary, final_recommendation, knowledge_notes (filter leaks).

Official voice:
  70% professional · 20% warm · 10% subtle anime-adjacent (Hmm… / Interessante…)
  Never caricature, never mascot, never technical internals.
"""

from __future__ import annotations

import logging
import random
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

AURORA_TAGLINE = "Aurora — Observando os detalhes que podem mudar o jogo."

# ---------------------------------------------------------------------------
# Cleanup — strip implementation / process language from user text
# ---------------------------------------------------------------------------

_STRIP_BLOCK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?im)^\s*estou utilizando o contexto anterior[:：]?\s*\n?", re.I),
    re.compile(r"(?im)^\s*\*\*[^*]+\*\*\s*\n+(?=com base naquela)", re.I),
    re.compile(r"(?im)^\s*com base naquela análise[:：]?\s*\n?", re.I),
    re.compile(r"(?im)^\s*status a partir do contexto\s*\([^)]*\)[:：]?\s*\n?", re.I),
]

_STRIP_INLINE: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\bestou utilizando o contexto anterior\.?\s*", re.I), ""),
    (re.compile(r"(?i)\bcom base naquela análise[:：]?\s*", re.I), ""),
    (re.compile(r"(?i)\bmantendo a leitura(?:\s+de\s+[^.]+)?(?:\s+a partir do contexto anterior)?\.?\s*", re.I), ""),
    (re.compile(r"(?i)\bmantive o contexto da partida sem abrir um novo pipeline\.?\s*", re.I), ""),
    (re.compile(r"(?i)\breutilizado do contexto(?:\s+conversacional)?\.?\s*", re.I), ""),
    (re.compile(r"(?i)\bcontexto(?:\s+de\s+[^.]+)?\s+reutilizado[^.]*\.?\s*", re.I), ""),
    (re.compile(r"(?i)\bsem nova busca(?:\s+ao vivo)?\.?\s*", re.I), ""),
    (re.compile(r"(?i)\bsem reabrir análise completa\.?\s*", re.I), ""),
    (re.compile(r"(?i)\bsem abrir um novo pipeline\.?\s*", re.I), ""),
    (re.compile(r"(?i)\bsnapshot(?:\s+em)?[:：]?\s*[^\n.]*\.?\s*", re.I), ""),
    (re.compile(r"(?i)\bslice(?:\s+dedicado)?[^.]*\.?\s*", re.I), ""),
    (re.compile(r"(?i)\bpipeline[^.]*\.?\s*", re.I), ""),
    (re.compile(r"(?i)\bQuickFollowUpGate\b", re.I), ""),
    (re.compile(r"(?i)\bconversation_context\b", re.I), ""),
    (re.compile(r"(?i)\bEntityResolver\b", re.I), ""),
    (re.compile(r"(?i)\bInference(?:\s+Layer)?\s*V2\b", re.I), ""),
    (re.compile(r"(?i)\bleve redução de confiança[^.]*\.?\s*", re.I), ""),
    (re.compile(r"(?i)\breutilizado do contexto conversacional[^.]*\.?\s*", re.I), ""),
    (re.compile(
        r"(?i)para economizar processamento[^.]*\.\s*",
        re.I,
    ), ""),
    (re.compile(
        r"(?i)não reexecutei a busca ao vivo[^.]*\.\s*",
        re.I,
    ), ""),
    (re.compile(
        r"(?i)follow-up resolveu via[^.]*\.\s*",
        re.I,
    ), ""),
]

# ---------------------------------------------------------------------------
# Human language map
# ---------------------------------------------------------------------------

_HUMANIZE: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(?i)\*\*nenhuma stake recomendada\.\*\*", re.I),
        "Eu ficaria de fora neste momento.",
    ),
    (
        re.compile(r"(?i)nenhuma stake recomendada\.?", re.I),
        "Eu ficaria de fora neste momento. O risco parece maior do que a oportunidade.",
    ),
    (
        re.compile(r"(?i)a aurora \*\*não recomenda aposta\*\* nesta partida\.?", re.I),
        "Eu teria cautela — ainda não vejo vantagem clara para uma entrada.",
    ),
    (
        re.compile(r"(?i)não recomenda aposta nesta partida\.?", re.I),
        "Eu teria cautela — ainda não vejo vantagem clara para uma entrada.",
    ),
    (
        re.compile(r"(?i)mercado principal(?:\s+identificado)?[:：]?", re.I),
        "Esse mercado começou a chamar minha atenção:",
    ),
    (
        re.compile(r"(?i)recomendação principal(?:\s+da análise)?[:：]?", re.I),
        "O que mais me chamou atenção:",
    ),
    (
        re.compile(
            r"(?i)a análise anterior não destacou um mercado específico de escanteios[^.]*\.",
            re.I,
        ),
        "Na leitura anterior não encontrei sinais suficientemente fortes para escanteios.",
    ),
    (
        re.compile(
            r"(?i)sem slice dedicado de escanteios[^.]*\.",
            re.I,
        ),
        "Ainda não vejo um valor claro nesse mercado de escanteios.",
    ),
    (
        re.compile(
            r"(?i)nenhum mercado de gols[^.]*ranking da análise anterior\.?",
            re.I,
        ),
        "Ainda não vejo um valor claro nos mercados de gols.",
    ),
    (
        re.compile(
            r"(?i)contexto de [^.]+ reutilizado — sem ranking forte em gols\.?",
            re.I,
        ),
        "Ainda não vejo um valor claro nesse mercado.",
    ),
    (
        re.compile(
            r"(?i)sem ranking forte em (?:gols|cartões|escanteios)\.?",
            re.I,
        ),
        "Ainda não vejo um valor claro nesse mercado.",
    ),
    (
        re.compile(r"(?i)dados insuficientes para recomendar[^.]*\.?", re.I),
        "Ainda não tenho sinais claros o bastante para uma recomendação firme.",
    ),
    (
        re.compile(r"(?i)análise não indica valor claro[^.]*\.?", re.I),
        "Ainda não vejo uma vantagem suficientemente clara.",
    ),
    (
        re.compile(r"(?i)peça(?:\s+uma)?\s+nova análise[^.]*\.?", re.I),
        "Se o jogo mudou, podemos revisar a leitura juntos.",
    ),
    (
        re.compile(r"(?i)peça:\s*[\"'].*?[\"']\.?", re.I),
        "Se quiser, seguimos aprofundando essa partida.",
    ),
]

_HOOKS = [
    "Também posso olhar os escanteios, se fizer sentido.",
    "Se algo mudou na partida, podemos revisar a leitura.",
    "Também podemos explorar outros mercados.",
    "Esse cenário ainda pode evoluir.",
    "Podemos acompanhar os próximos minutos.",
    "Esse cenário merece um segundo olhar.",
]

_SOFT_OPENERS = [
    "Hmm… ",
    "Interessante. ",
    "Curioso. ",
    "Entendo. ",
    "Vamos observar. ",
]

_NOTE_LEAK_RE = re.compile(
    r"(?i)conversation_context|pipeline|QuickFollow|EntityResolver|"
    r"Inference\s*V2|follow-up resolveu|sem nova busca|best-effort|"
    r"confidence_penalty|used_previous_analysis"
)


def _norm_key(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip()


def is_short_query(message: str, intent: str) -> bool:
    msg = (message or "").strip()
    if intent in ("follow_up", "greeting", "identity"):
        return True
    if len(msg) <= 48 and not re.search(r"\b(?:vs|versus|\bx\b|contra)\b", msg, re.I):
        return True
    return False


def detect_user_tone(message: str) -> str:
    """casual | playful | technical | neutral"""
    n = _norm_key(message)
    if re.search(r"\b(kkk+|rs+|haha|kk+|lol|bagunca|zuera|mano|cara)\b", n):
        return "playful"
    if re.search(r"\b(xg|ev|kelly|odds|probabilidade|stake|btts|over|under)\b", n):
        return "technical"
    if re.search(r"\b(valeu|blz|beleza|show|massa|top)\b", n):
        return "casual"
    return "neutral"


def cleanup_text(text: str) -> str:
    if not text:
        return text
    out = text
    for pat in _STRIP_BLOCK_PATTERNS:
        out = pat.sub("", out)
    for pat, repl in _STRIP_INLINE:
        out = pat.sub(repl, out)
    # Drop orphan bold match lines left after stripping preamble
    out = re.sub(r"(?m)^\s*\*\*[^*]{1,40}\*\*\s*$\n?", "", out, count=1)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def humanize_text(text: str) -> str:
    if not text:
        return text
    out = text
    for pat, repl in _HUMANIZE:
        out = pat.sub(repl, out)
    return out.strip()


def _line_count(text: str) -> int:
    return len([ln for ln in (text or "").splitlines() if ln.strip()])


def control_size(text: str, *, short: bool, intent: str) -> str:
    if not text:
        return text
    max_lines = 6 if short else (10 if intent != "analyze_match" else 28)
    lines = [ln for ln in text.splitlines()]
    nonempty = [ln for ln in lines if ln.strip()]
    if len(nonempty) <= max_lines:
        return text.strip()

    kept: list[str] = []
    count = 0
    for ln in lines:
        if ln.strip():
            count += 1
        if count > max_lines:
            break
        kept.append(ln)
    body = "\n".join(kept).strip()
    # Avoid dangling list markers
    body = re.sub(r"(?m)^\s*[•\-\*]\s*$", "", body).strip()
    return body


def maybe_add_opener(text: str, *, intent: str, tone: str, rng: random.Random) -> str:
    if not text or intent not in ("follow_up", "emotional"):
        return text
    if tone == "technical":
        return text
    # Stable light touch ~25%
    if rng.random() > 0.28:
        return text
    if re.match(r"(?i)^(hmm|interessante|curioso|entendo|vamos observar|bem\b)", text):
        return text
    return rng.choice(_SOFT_OPENERS) + text[0].lower() + text[1:] if text else text


def maybe_add_hook(text: str, *, intent: str, short: bool, rng: random.Random) -> str:
    if not text or intent not in ("follow_up", "analyze_match"):
        return text
    if _line_count(text) >= (5 if short else 9):
        return text
    if rng.random() > 0.35:
        return text
    # Don't double-hook
    if any(h.lower()[:20] in text.lower() for h in _HOOKS):
        return text
    return text.rstrip() + "\n\n" + rng.choice(_HOOKS)


def adaptive_playful(text: str, message: str, tone: str) -> str:
    if tone != "playful" or not text:
        return text
    if re.search(r"(?i)bagunca|imprevisivel|kk", _norm_key(message)):
        if not text.lower().startswith(("bem", "hmm")):
            return (
                "Bem… esse jogo resolveu ficar bastante imprevisível.\n\n" + text
            )
    return text


def filter_knowledge_notes(notes: list | None) -> list[str]:
    out: list[str] = []
    for n in notes or []:
        if not isinstance(n, str):
            continue
        if _NOTE_LEAK_RE.search(n):
            continue
        if "penalidade" in n.lower() and "inference" in n.lower():
            continue
        out.append(n)
    return out[:6]


def polish_payload(
    payload: dict[str, Any],
    *,
    message: str,
    intent: str,
    ctx: dict | None = None,
) -> dict[str, Any]:
    """
    Main entry — mutate a shallow copy of user-facing narrative fields.
    Analytical numbers / markets / brain stay intact.
    """
    if not isinstance(payload, dict):
        return payload

    p = dict(payload)
    intent = intent or p.get("intent") or "unknown"
    short = is_short_query(message, intent)
    tone = detect_user_tone(message)
    # Deterministic RNG per message for stable hooks across retries
    seed = abs(hash((message or "")[:80] + intent)) % (2**31)
    rng = random.Random(seed)

    for field in ("executive_summary", "final_recommendation"):
        raw = p.get(field) or ""
        if not isinstance(raw, str) or not raw.strip():
            continue
        text = cleanup_text(raw)
        text = humanize_text(text)
        text = adaptive_playful(text, message, tone)
        if field == "executive_summary":
            text = maybe_add_opener(text, intent=intent, tone=tone, rng=rng)
            text = control_size(text, short=short, intent=intent)
            text = maybe_add_hook(text, intent=intent, short=short, rng=rng)
        else:
            text = control_size(text, short=True, intent=intent)
        p[field] = text.strip()

    p["knowledge_notes"] = filter_knowledge_notes(p.get("knowledge_notes"))

    # Soften confidence explanation if it leaks internals (still machine field)
    conf = p.get("confidence")
    if isinstance(conf, dict):
        conf = dict(conf)
        expl = conf.get("explanation")
        if isinstance(expl, str) and (
            "contexto conversacional" in expl.lower()
            or "reutilizado" in expl.lower()
            or "conversation" in expl.lower()
        ):
            conf["explanation"] = "Leitura baseada na análise mais recente da partida."
        p["confidence"] = conf

    # Bankroll reasoning humanize (shown in UI sometimes)
    br = p.get("bankroll_recommendation")
    if isinstance(br, dict):
        br = dict(br)
        reason = br.get("reasoning")
        if isinstance(reason, str) and reason:
            br["reasoning"] = humanize_text(cleanup_text(reason))
        p["bankroll_recommendation"] = br

    logger.info(
        "personality_layer applied intent=%s short=%s tone=%s lines=%s",
        intent, short, tone, _line_count(p.get("executive_summary") or ""),
    )
    return p


def official_greeting_summary() -> str:
    return (
        "Olá! Eu sou a **Aurora**.\n\n"
        "Especialista em análises esportivas e sempre atenta aos detalhes "
        "que podem fazer diferença em uma partida.\n\n"
        "Se tiver algum jogo em mente, vamos analisá-lo juntos.\n"
        "Qual confronto chamou sua atenção hoje?"
    )


def official_greeting_recommendation() -> str:
    return AURORA_TAGLINE
