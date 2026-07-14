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
    (re.compile(r"(?i)\[?\s*REGRA DE OURO\s*\]?[:：]?\s*", re.I), ""),
    (re.compile(r"(?i)\[?\s*ALERTA\s*\]?[:：]?\s*", re.I), ""),
    (re.compile(r"(?i)\[GOLDEN RULE\][:：]?\s*", re.I), ""),
    (re.compile(r"(?i)\[RED FLAG\][:：]?\s*", re.I), ""),
    (re.compile(r"(?i)\bPoisson\b.*?(?:[.!?](?:\s|$)|$)", re.I), ""),
    (re.compile(r"(?i)score metodol[oó]gico.*?(?:[.!?](?:\s|$)|$)", re.I), ""),
    (re.compile(r"(?i)\b39 regras\b.*?(?:[.!?](?:\s|$)|$)", re.I), ""),
    (re.compile(r"(?i)metodologia da aurora.*?(?:[.!?](?:\s|$)|$)", re.I), ""),
    (re.compile(r"(?i)estou aqui para ajudar.*?(?:[.!?](?:\s|$)|$)", re.I), ""),
    # Phase 6.4.1 — keep internals out of the main reply
    (re.compile(r"(?i)\bVE\s*[+\-]?\s*\d+(?:[.,]\d+)?%?", re.I), ""),
    (re.compile(r"(?i)\b(?:expected\s+value|valor\s+esperado)\s*[+\-]?\s*\d+(?:[.,]\d+)?%?", re.I), ""),
    (re.compile(r"(?i)\b\d+(?:[.,]\d+)?\s*%\s*prob\b", re.I), ""),
    (re.compile(r"(?i)\bprob(?:abilidade)?\s*[:=]?\s*\d+(?:[.,]\d+)?\s*%", re.I), ""),
    (re.compile(r"(?i)[λλ]\s*=\s*\d+(?:[.,]\d+)?", re.I), ""),
    (re.compile(r"(?i)\blambda\s*=\s*\d+(?:[.,]\d+)?", re.I), ""),
    (re.compile(r"(?i)\b\d+(?:[.,]\d+)?\s*/\s*10\b", re.I), ""),
    (re.compile(r"(?i)\bbest[-_\s]?mercado\b[^.!\n]*", re.I), ""),
    (re.compile(r"(?i)\bbest[-_\s]?market\b[^.!\n]*", re.I), ""),
    (re.compile(r"(?i)\bover_\d+\w*", re.I), ""),
    (re.compile(r"(?i)n[aã]o\s+foi\s+confirmada\s+na\s+API[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"(?i)partida\s+n[aã]o\s+foi\s+confirmada[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"(?i)tente\s+o\s+nome\s+oficial\s+dos\s+times[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"(?i)em\s+vez\s+de\s+abortar[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"(?i)continuou\s+a\s+an[aá]lise\s+com\s+confian[cç]a\s+reduzida[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"(?i)\*\*dados\s+parciais\*\*[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"(?i)dados\s+parciais\s+para[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"(?i)an[aá]lise\s+parcial\s+para[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"(?i)confian[cç]a\s+ajustada\s+para[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"(?i)confian[cç]a\s+insuficiente[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"(?i)sem\s+stake\s+recomendada[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"(?i),\s*risco\s+Alto\b", re.I), ""),
    (re.compile(r"(?i)\brisco\s+Alto\b", re.I), ""),
    (re.compile(r"(?i)\bInference\s+Layer\b[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"(?i)modo\s+degradado[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"(?i)precis[aã]o\s+\d+(?:[.,]\d+)?%\s*—?[^.!\n]*", re.I), ""),
    (re.compile(r"(?i)≥\s*60%\s*filtro", re.I), ""),
    (re.compile(r"(?i)Aprendizado\s+Hist[oó]rico\s*\([^)]*\)\s*:?\s*", re.I), ""),
    (re.compile(r"(?i)forte\s+desempenho\s+hist[oó]rico[^.!\n]*", re.I), ""),
    (re.compile(r"(?i)_?estimativa\s+pr[eé]-jogo[^.!\n]*_?", re.I), ""),
    (re.compile(r"(?i)refer[eê]ncia\s+de\s+\d+(?:[.,]\d+)?\s*escanteios\s*/\s*90[^.!\n]*", re.I), ""),
    (re.compile(r"(?i)^\s*a\s+aurora\.?\s*$", re.I | re.M), ""),
    (re.compile(r"(?i)a\s+aurora\s+continuou[^.!\n]*[.!]?", re.I), ""),
    (re.compile(r"[—\-–]\s*[·•.\s]{1,}", re.I), " "),
    (re.compile(r"(?:\s*·\s*){1,}", re.I), " "),
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
        re.compile(
            r"(?i)dados\s+parciais[^.]*?(?:abortar|reduzida)[^.]*\.?",
            re.I,
        ),
        "Ainda não tenho todos os sinais confirmados para este confronto, "
        "mas já dá para observar alguns mercados com atenção.",
    ),
    (
        re.compile(
            r"(?i)an[aá]lise\s+parcial[^.]*?(?:API|times)[^.]*\.?",
            re.I,
        ),
        "Neste momento eu aguardaria mais confirmação antes de uma entrada mais agressiva.",
    ),
    (
        re.compile(r"(?i)os mercados de escanteios acima t[eê]m o maior valor[^.]*\.?", re.I),
        "Os escanteios são o que mais me chamou atenção neste confronto.",
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
    "Quer aprofundar em gols ou escanteios?",
    "Esse mercado chamou sua atenção?",
    "Posso comparar as equipes mais profundamente se desejar.",
    "Também podemos observar outros mercados.",
    "Se algo mudou na partida, podemos revisar a leitura.",
    "Esse cenário merece um segundo olhar.",
    "Vamos observar mais alguns minutos.",
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
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s*[—\-–]\s*(?=\n|$)", "", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def humanize_text(text: str) -> str:
    if not text:
        return text
    out = text
    for pat, repl in _HUMANIZE:
        out = pat.sub(repl, out)
    return out.strip()


_INTERNAL_PROSE_RE = re.compile(
    r"(?i)\b(?:metodol|filtro\s+metod|xG|bloqueio|Inference|pipeline|"
    r"pontua[cç][aã]o\s+metod|VE\b|λ|Best[-_]?mercado|confirmada\s+na\s+API)\b"
)


def sanitize_public_prose(text: str) -> str:
    """Main-reply sanitizer: human first, then strip internals."""
    if not text:
        return text
    out = humanize_text(text)
    out = cleanup_text(out)
    # Drop leftover metric crumbs on their own lines
    cleaned_lines: list[str] = []
    for ln in out.splitlines():
        s = ln.strip().strip("*").strip()
        if not s:
            cleaned_lines.append("")
            continue
        if re.search(
            r"(?i)^\s*(?:ve\b|λ|lambda|best[-_]?mercado|over_\d+|/\s*10|api\b|a aurora\.?$)",
            s,
        ):
            continue
        if re.fullmatch(r"[—\-–·.•\s*]+", s):
            continue
        if re.search(r"(?i)estimativa\s+pr[eé]-jogo|escanteios\s*/\s*90|metodol|bloqueio", s):
            continue
        cleaned_lines.append(ln.rstrip())
    out = "\n".join(cleaned_lines)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+[—\-–]\s*$", "", out, flags=re.M)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    if _INTERNAL_PROSE_RE.search(out):
        # Still contaminated — caller should replace with human fallback
        return ""
    return out


def human_analyze_fallback(match: str = "") -> str:
    title = f"**{match}**\n\n" if match else ""
    return (
        f"{title}"
        "Leitura ainda cautelosa neste confronto.\n"
        "Alguns sinais precisam se confirmar, mas já há mercados que merecem atenção — "
        "especialmente gols e escanteios."
    )


def human_followup_fallback(match: str = "", market_hint: str = "") -> str:
    title = f"**{match}**\n\n" if match else ""
    if market_hint:
        return (
            f"{title}"
            f"Olhando de perto: **{market_hint}** é o que mais me chama atenção agora.\n"
            "Se quiser, posso aprofundar esse mercado ou comparar com gols."
        )
    return (
        f"{title}"
        "Mantive a leitura da partida e foquei no mercado que você perguntou.\n"
        "Posso detalhar mais se fizer sentido."
    )


_TECH_FACTOR_RE = re.compile(
    r"(?i)(?:\d+(?:[.,]\d+)?\s*/\s*10|best[-_\s]?mercado|best[-_\s]?market|"
    r"over_\d+|λ\s*=|ve\s*[+\-]|puxando a pontua|"
    r"modo degradado|fixture oficial|sem dados de xg|"
    r"inference|pipeline|precis[aã]o\s+\d)"
)


def public_strengths(factors: list | None, *, limit: int = 3) -> list[str]:
    """Human bullets for the main reply — technical factors stay in details only."""
    out: list[str] = []
    for f in factors or []:
        if not isinstance(f, str) or not f.strip():
            continue
        raw = f.strip().lstrip("• ").strip()
        if _TECH_FACTOR_RE.search(raw):
            low = raw.lower()
            if "escanteio" in low or "corner" in low:
                tip = "O histórico recente favorece atenção aos escanteios."
            elif "gol" in low:
                tip = "Há sinais que merecem atenção nos mercados de gols."
            else:
                continue
            if tip not in out:
                out.append(tip)
            if len(out) >= limit:
                break
            continue
        cleaned = sanitize_public_prose(raw)
        if cleaned and cleaned not in out:
            out.append(cleaned)
        if len(out) >= limit:
            break
    return out


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
        if re.search(r"(?i)regra de ouro|golden rule|red flag|alerta metod", n):
            continue
        cleaned = cleanup_text(n)
        if cleaned:
            out.append(cleaned)
    return out[:4]


def compress_analyze_summary(text: str, payload: dict[str, Any]) -> str:
    """
    Progressive disclosure for full match analyses: short human overview first.
    Heavy metrics stay in structured fields (UI details, collapsed).
    Markets are surfaced by the UX layer — keep prose lean here.
    """
    match = payload.get("match") or ""
    text = sanitize_public_prose(text)
    if not text:
        return human_analyze_fallback(match)

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    kept: list[str] = []
    for para in paragraphs:
        if _INTERNAL_PROSE_RE.search(para):
            continue
        if len(para) < 8:
            continue
        kept.append(para)
        if len(kept) >= 3:
            break
    body = "\n\n".join(kept) if kept else ""
    body = control_size(body, short=False, intent="analyze_match")
    body = sanitize_public_prose(body)

    body_wo_match = body
    if match:
        body_wo_match = re.sub(
            re.escape(match), "", body, count=1, flags=re.I
        ).strip(" \n*•-—.")
    if not body or not body_wo_match or len(body_wo_match) < 28:
        return human_analyze_fallback(match)
    if match and match.lower() not in body.lower()[:80]:
        body = f"**{match}**\n\n" + body
    elif match and not body.strip().startswith("**"):
        body = f"**{match}**\n\n" + body
    return body.strip()


def polish_payload(
    payload: dict[str, Any],
    *,
    message: str,
    intent: str,
    ctx: dict | None = None,
) -> dict[str, Any]:
    """
    Main entry — mutate a shallow copy of user-facing narrative fields.
    Analytical numbers / markets / brain stay intact for Detalhes da análise.
    """
    if not isinstance(payload, dict):
        return payload

    p = dict(payload)
    intent = intent or p.get("intent") or "unknown"
    short = is_short_query(message, intent) or intent in (
        "small_talk", "greeting", "identity", "help", "capabilities", "follow_up",
    )
    tone = detect_user_tone(message)
    seed = abs(hash((message or "")[:80] + intent)) % (2**31)
    rng = random.Random(seed)
    match = p.get("match") or ""
    top_market = ""
    markets = p.get("best_markets") or []
    if markets and isinstance(markets[0], dict):
        top_market = (markets[0].get("market") or "").strip()

    # Social / greeting: keep short, no analysis chrome
    if intent in ("small_talk", "greeting", "identity"):
        for field in ("executive_summary", "final_recommendation"):
            raw = p.get(field) or ""
            if isinstance(raw, str) and raw.strip():
                p[field] = control_size(sanitize_public_prose(raw), short=True, intent=intent)
        p["knowledge_notes"] = []
        return p

    for field in ("executive_summary", "final_recommendation"):
        raw = p.get(field) or ""
        if not isinstance(raw, str) or not raw.strip():
            continue
        if field == "executive_summary" and intent == "analyze_match":
            text = compress_analyze_summary(raw, p)
            text = maybe_add_hook(text, intent=intent, short=False, rng=rng)
        elif field == "executive_summary" and intent == "follow_up":
            text = sanitize_public_prose(raw)
            text = adaptive_playful(text, message, tone)
            text = maybe_add_opener(text, intent=intent, tone=tone, rng=rng)
            text = control_size(text, short=True, intent=intent)
            text = sanitize_public_prose(text)
            body_wo_match = re.sub(re.escape(match), "", text, count=1, flags=re.I).strip(" \n*•-—.") if match else text
            if not text or not body_wo_match or len(body_wo_match) < 20:
                text = human_followup_fallback(match, top_market)
            text = maybe_add_hook(text, intent=intent, short=True, rng=rng)
        else:
            text = sanitize_public_prose(raw)
            text = adaptive_playful(text, message, tone)
            if field == "executive_summary":
                text = maybe_add_opener(text, intent=intent, tone=tone, rng=rng)
                text = control_size(text, short=short, intent=intent)
                text = maybe_add_hook(text, intent=intent, short=short, rng=rng)
                text = sanitize_public_prose(text) or text
            else:
                text = control_size(text, short=True, intent=intent)
                text = sanitize_public_prose(text)
                if not text or _INTERNAL_PROSE_RE.search(text):
                    if intent in ("analyze_match", "follow_up"):
                        text = (
                            "Neste momento eu aguardaria um pouco mais de confirmação "
                            "antes de uma entrada mais agressiva."
                        )
                        if top_market:
                            text += f" **{top_market}** chama atenção, mas sem pressa."
        p[field] = text.strip()

    # Public strengths for main UI (raw factors remain for Detalhes)
    meta = dict(p.get("response_metadata") or {})
    strengths = public_strengths(p.get("positive_factors"))
    if strengths:
        meta["public_strengths"] = strengths
    meta["presentation"] = "phase_6_4_public"
    p["response_metadata"] = meta

    p["knowledge_notes"] = filter_knowledge_notes(p.get("knowledge_notes"))

    conf = p.get("confidence")
    if isinstance(conf, dict):
        conf = dict(conf)
        expl = conf.get("explanation")
        if isinstance(expl, str) and (
            "contexto conversacional" in expl.lower()
            or "reutilizado" in expl.lower()
            or "conversation" in expl.lower()
            or "regra de ouro" in expl.lower()
            or "api" in expl.lower()
            or "metodol" in expl.lower()
        ):
            conf["explanation"] = "Leitura baseada na análise mais recente da partida."
        p["confidence"] = conf

    br = p.get("bankroll_recommendation")
    if isinstance(br, dict):
        br = dict(br)
        reason = br.get("reasoning")
        if isinstance(reason, str) and reason:
            br["reasoning"] = sanitize_public_prose(reason) or ""
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
