"""
P3-D.4 Response Diversification MVP — break finite response-bank loops.

Implements:
  1. Fingerprint cooldown
  2. Speech-act cooldown
  3. Recovery diversification
  4. Sport boilerplate suppression
  5. Context anchors before uncommitted fallback

Fail-open. Additive. Does not invent sports facts/odds.
"""

from __future__ import annotations

import hashlib
import re
import time
import unicodedata
from typing import Any

CTX_KEY = "response_diversification"

FP_COOLDOWN_N = 8
SPEECH_ACT_COOLDOWN_N = 3
FP_JACCARD_BAN = 0.52

_UNCOMMITTED_BANK = (
    "Sem hipótese ativa agora. Quando disser o foco em uma frase, eu sigo.",
    "Contexto de compromisso zerado. É só falar o assunto quando quiser.",
    "Modo aberto — sem checklist e sem travar no fio antigo.",
    "Não retenho a leitura anterior. Pode seguir direto no que importar.",
    "Hipótese antiga fora. Quando vier o foco, avanço sem menu.",
    "Aqui sem compromisso preso. Manda o próximo pedido quando estiver pronto.",
    "Zerei o enquadro. Uma frase do que você quer agora basta.",
    "Fico disponível sem insistir no mesmo caminho. O próximo assunto é seu.",
    "Sem reabrir o chute antigo. Diga o recorte atual e eu entro.",
    "Estado limpo do meu lado. Pode puxar o tema que importa agora.",
    "Não vou empurrar pergunta de novo. Quando quiser, manda o foco.",
    "Sem template preso. Estou pronta pro próximo fio quando você trouxer.",
    "Compromisso anterior solto. Continuo aqui; é só escolher o assunto.",
    "Não fico rodando o mesmo pedido. Me diga o que vale agora.",
    "Espaço aberto pra recomeçar do ponto que você escolher.",
)

_SPORT_SHORT = (
    "Leitura curta: cautela com filtro — sem repetir o bloco de análise. "
    "Quer só o risco principal ou a alternativa mais segura?",
    "Resumo direto: vejo margem, mas sem euforia. "
    "Prefere o ponto de atenção ou o caminho mais contido?",
    "Sem checklist longo desta vez. Minha leitura fica contida; "
    "me diga se quer risco, alternativa ou só opinião em uma linha.",
    "Troco o template por algo curto: ainda não fecho posição forte. "
    "O que você quer priorizar — risco ou alternativa?",
    "Versão enxuta: filtro ligado, sem reabrir todos os cenários. "
    "Posso ir só no receio ou só no caminho defensivo.",
)

_ANCHOR_TEMPLATES = (
    "Ancorando no que você trouxe (“{snip}”): posso seguir nisso direto — "
    "sem menu e sem repetir o bloco anterior. Quer aprofundar ou mudar o recorte?",
    "Pegando o fio de “{snip}”: avanço em cima disso. "
    "Se não for exatamente, corrige em uma frase.",
    "Sobre “{snip}”, fico no assunto sem checklist. "
    "Diz se quer continuidade ou um ângulo novo.",
    "Mantendo “{snip}” como âncora. Resposta curta: estou contigo nesse ponto — "
    "o que priorizar agora?",
)

_TEAM_ANCHORS = (
    "Voltando ao {team}: papo leve, sem inventar placar nem odd. "
    "Quer forma, rivalidade ou só sensação?",
    "No {team} eu sigo em conversa (sem número inventado). "
    "O que puxar — momento, clássico ou vibe?",
    "Falando do {team} sem template longo: te respondo direto. "
    "Forma recente, rival ou feeling?",
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9à-ú]{3,}", _fold(text))}


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def fingerprint(text: str) -> str:
    f = _fold(text)
    f = re.sub(r"[“”\"'].*?[“”\"']", "<Q>", f)
    f = re.sub(r"\b\d+(?:[.,]\d+)?%?\b", "<N>", f)
    f = re.sub(
        r"\b(flamengo|palmeiras|bahia|corinthians|santos|sao paulo|botafogo|"
        r"vasco|gremio|internacional|mandante|visitante)\b",
        "<TEAM>",
        f,
    )
    f = re.sub(r"\s+", " ", f).strip()[:120]
    return hashlib.sha1(f.encode("utf-8", errors="ignore")).hexdigest()[:16]


def speech_act(text: str) -> str:
    f = _fold(text)
    if any(
        x in f
        for x in (
            "ha contexto suficiente",
            "há contexto suficiente",
            "minha inclinacao",
            "minha inclinação",
            "vejo valor, mas",
            "pontos a favor",
            "o que me favorece",
            "o que mais me chama atencao",
            "o que mais me chama atenção",
            "eu teria uma visao",
            "eu teria uma visão",
            "caminho interessante, sem euforia",
        )
    ):
        return "sport_analysis"
    if any(
        x in f
        for x in (
            "sem hipotese ativa",
            "sem hipótese ativa",
            "compromisso zerado",
            "modo aberto",
            "sem compromisso",
            "hipotese antiga fora",
            "hipótese antiga fora",
            "zerei o enquadro",
            "estado limpo",
            "espaco aberto",
            "espaço aberto",
            "nao vou empurrar pergunta",
            "não vou empurrar pergunta",
            "sem template preso",
        )
    ):
        return "uncommitted_status"
    if any(
        x in f
        for x in (
            "soltei aquela",
            "abandonei o fio",
            "reset limpo",
            "manda o pedido atual",
            "assunto novo",
            "recomece do zero",
        )
    ):
        return "escape_ask"
    if any(
        x in f
        for x in (
            "voce esta falando de",
            "você está falando de",
            "selecao",
            "seleção",
            "jogo especifico",
            "jogo específico",
        )
    ) and ("?" in (text or "")):
        return "clarify_triage"
    if any(
        x in f
        for x in (
            "vou assumir o fio",
            "seguindo do ponto",
            "retomo o ponto",
            "avancando no assunto",
            "avançando no assunto",
            "entendi que o pedido era",
        )
    ):
        return "soft_assume"
    if any(x in f for x in ("ancor", "pegando o fio", "voltando ao", "falando do")):
        return "context_anchor"
    return "contentful"


def get_div_state(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return {
            "recent_fps": [],
            "recent_acts": [],
            "counters": {},
            "last_emit_at": None,
        }
    st = ctx.get(CTX_KEY)
    if not isinstance(st, dict):
        st = {
            "recent_fps": [],
            "recent_acts": [],
            "counters": {},
            "last_emit_at": None,
        }
        ctx[CTX_KEY] = st
    st.setdefault("recent_fps", [])
    st.setdefault("recent_acts", [])
    st.setdefault("counters", {})
    return st


def _bump(st: dict[str, Any], key: str) -> None:
    c = st.setdefault("counters", {})
    c[key] = int(c.get(key) or 0) + 1


def fingerprint_on_cooldown(ctx: dict[str, Any] | None, text: str) -> bool:
    st = get_div_state(ctx)
    fp = fingerprint(text)
    recent = list(st.get("recent_fps") or [])[-FP_COOLDOWN_N:]
    if fp in recent:
        return True
    raw = list(st.get("recent_raw") or [])[-FP_COOLDOWN_N:]
    return any(jaccard(text, r) >= FP_JACCARD_BAN for r in raw)


def speech_act_on_cooldown(ctx: dict[str, Any] | None, act: str) -> bool:
    st = get_div_state(ctx)
    recent = list(st.get("recent_acts") or [])
    if act in {"contentful"}:
        return len(recent) >= 2 and recent[-1] == act and recent[-2] == act
    if act == "context_anchor":
        # allow one anchor, cool the second+
        return "context_anchor" in recent[-2:]
    if act == "sport_analysis":
        return "sport_analysis" in recent[-5:]
    if act == "uncommitted_status":
        return recent[-SPEECH_ACT_COOLDOWN_N:].count("uncommitted_status") >= 1
    window = recent[-SPEECH_ACT_COOLDOWN_N:]
    return act in window


def record_emission(ctx: dict[str, Any] | None, text: str) -> None:
    if not isinstance(ctx, dict):
        return
    st = get_div_state(ctx)
    fp = fingerprint(text)
    act = speech_act(text)
    fps = list(st.get("recent_fps") or [])
    fps.append(fp)
    st["recent_fps"] = fps[-FP_COOLDOWN_N:]
    raw = list(st.get("recent_raw") or [])
    raw.append((text or "")[:220])
    st["recent_raw"] = raw[-FP_COOLDOWN_N:]
    acts = list(st.get("recent_acts") or [])
    acts.append(act)
    st["recent_acts"] = acts[-12:]
    st["last_emit_at"] = time.time()
    st["last_fp"] = fp
    st["last_act"] = act
    ctx[CTX_KEY] = st


def _perception(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return {}
    pcs = ctx.get("perception_conversation_state")
    return pcs if isinstance(pcs, dict) else {}


def _snip_user(ctx: dict[str, Any] | None) -> str | None:
    pcs = _perception(ctx)
    msg = str(pcs.get("last_user_message") or "").strip()
    if not msg:
        return None
    toks = re.findall(r"[a-z0-9à-ú]{3,}", _fold(msg))
    if len(toks) < 2:
        return None
    if _fold(msg) in {"nao", "não", "errado", "para", "aff", "ok", "sim"}:
        return None
    return msg[:90]


def _team(ctx: dict[str, Any] | None) -> str | None:
    pcs = _perception(ctx)
    ents = pcs.get("entities") if isinstance(pcs.get("entities"), dict) else {}
    team = ents.get("team") if isinstance(ents, dict) else None
    if team:
        return str(team)[:40]
    try:
        view = ctx.get("conversation_view") if isinstance(ctx, dict) else None
        if isinstance(view, dict):
            home = view.get("home")
            if home:
                return str(home)[:40]
    except Exception:
        pass
    return None


def context_anchor_reply(ctx: dict[str, Any] | None) -> str | None:
    """Prefer a contentful anchor over hollow uncommitted when context exists."""
    st = get_div_state(ctx)
    team = _team(ctx)
    snip = _snip_user(ctx)
    n = int(st.get("counters", {}).get("anchors") or 0)

    candidates: list[str] = []
    if team:
        candidates.extend(t.format(team=team) for t in _TEAM_ANCHORS)
    if snip:
        candidates.extend(t.format(snip=snip) for t in _ANCHOR_TEMPLATES)

    if not candidates:
        return None

    best = None
    best_score = 1.0
    for i in range(len(candidates)):
        c = candidates[(n + i) % len(candidates)]
        if fingerprint_on_cooldown(ctx, c):
            score = 0.9
        else:
            score = max(
                (jaccard(c, r) for r in (st.get("recent_raw") or [])),
                default=0.0,
            )
        if score < best_score:
            best_score = score
            best = c
            if score < 0.15:
                break
    if best is None:
        best = candidates[n % len(candidates)]
    _bump(st, "anchors")
    if isinstance(ctx, dict):
        ctx[CTX_KEY] = st
    return best


def diversify_recovery_line(ctx: dict[str, Any] | None = None) -> str:
    """Recovery diversification + context anchors before uncommitted fallback."""
    try:
        if not speech_act_on_cooldown(ctx, "context_anchor"):
            anchored = context_anchor_reply(ctx)
            if anchored and not fingerprint_on_cooldown(ctx, anchored):
                record_emission(ctx, anchored)
                st = get_div_state(ctx)
                _bump(st, "recovery_anchor")
                return anchored
    except Exception:
        pass

    st = get_div_state(ctx)
    c = st.setdefault("counters", {})
    n = int(c.get("uncommitted_picks") or 0)
    c["uncommitted_picks"] = n + 1

    best = _UNCOMMITTED_BANK[n % len(_UNCOMMITTED_BANK)]
    best_score = 1.0
    for offset in range(len(_UNCOMMITTED_BANK)):
        cand = _UNCOMMITTED_BANK[(n + offset) % len(_UNCOMMITTED_BANK)]
        if fingerprint_on_cooldown(ctx, cand):
            continue
        score = max(
            (jaccard(cand, r) for r in (st.get("recent_raw") or [])),
            default=0.0,
        )
        if score < best_score:
            best_score = score
            best = cand
            if score == 0.0:
                break
    if speech_act_on_cooldown(ctx, "uncommitted_status"):
        pivot = (
            "Mudando o formato: sem status de compromisso de novo. "
            "Me diga só o assunto em uma linha e eu entro."
        )
        if not fingerprint_on_cooldown(ctx, pivot):
            best = pivot
            _bump(st, "speech_act_pivot")
    record_emission(ctx, best)
    _bump(st, "recovery_bank")
    if isinstance(ctx, dict):
        ctx[CTX_KEY] = st
    return best


def looks_sport_boilerplate(text: str) -> bool:
    return speech_act(text) == "sport_analysis"


def suppress_sport_boilerplate(
    ctx: dict[str, Any] | None,
    text: str,
) -> str:
    """Replace sticky deep-analysis templates with short conversational variants."""
    if not looks_sport_boilerplate(text):
        return text
    st = get_div_state(ctx)
    cool = fingerprint_on_cooldown(ctx, text) or speech_act_on_cooldown(
        ctx, "sport_analysis"
    )
    if not cool:
        return text

    team = _team(ctx)
    n = int(st.get("counters", {}).get("sport_suppress") or 0)
    out = _SPORT_SHORT[n % len(_SPORT_SHORT)]
    for offset in range(len(_SPORT_SHORT)):
        cand = _SPORT_SHORT[(n + offset) % len(_SPORT_SHORT)]
        if team:
            cand = f"Sobre o {team}: {cand}"
        if not fingerprint_on_cooldown(ctx, cand):
            out = cand
            break
    else:
        if team:
            out = f"Sobre o {team}: {out}"
    _bump(st, "sport_suppress")
    if isinstance(ctx, dict):
        ctx[CTX_KEY] = st
    return out


def diversify_reply(ctx: dict[str, Any] | None, text: str) -> str:
    """Final diversification pass: sport suppress → cooldown rewrite → record."""
    if not text:
        return text
    try:
        st = get_div_state(ctx)
        # Already emitted this exact line this turn (e.g. recovery then anti_sticky)
        raw = list(st.get("recent_raw") or [])
        if raw and raw[-1] == (text or "")[:220]:
            return text

        out = suppress_sport_boilerplate(ctx, text)
        act = speech_act(out)
        if fingerprint_on_cooldown(ctx, out) or speech_act_on_cooldown(ctx, act):
            if act == "sport_analysis":
                out = suppress_sport_boilerplate(ctx, out)
                if looks_sport_boilerplate(out):
                    n = int(st.get("counters", {}).get("sport_force") or 0)
                    st.setdefault("counters", {})["sport_force"] = n + 1
                    out = _SPORT_SHORT[n % len(_SPORT_SHORT)]
            elif act == "uncommitted_status":
                out = diversify_recovery_line(ctx)
                return out
            elif act in {"soft_assume", "clarify_triage", "escape_ask"}:
                anchored = context_anchor_reply(ctx)
                if anchored and not fingerprint_on_cooldown(ctx, anchored):
                    out = anchored
                else:
                    out = diversify_recovery_line(ctx)
                    return out
            else:
                prefixes = (
                    "Mudando o ângulo pra não repetir.\n\n",
                    "Outro formato, mesmo assunto:\n\n",
                    "Sem o mesmo bloco:\n\n",
                )
                n = int(st.get("counters", {}).get("prefix_div") or 0)
                st.setdefault("counters", {})["prefix_div"] = n + 1
                pref = prefixes[n % len(prefixes)]
                if not out.startswith(pref.strip()[:12]):
                    out = pref + out
        record_emission(ctx, out)
        return out
    except Exception:
        return text
