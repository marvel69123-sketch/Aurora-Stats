"""
Perceived Intelligence Engine — transmit reasoning without inventing facts.

Structure: Fact → Interpretation → Conclusion (when evidence exists).
When evidence is thin: prioritize + admit uncertainty.

Additive. Fail-open.
Does NOT modify FactPolicy / LivePipeline / MasterIntent / HCE / NRE.
Does NOT invent stats, odds, or match events.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


@dataclass
class Evidence:
    entity: str | None = None
    is_live: bool = False
    minute: str | None = None
    score: str | None = None
    status: str | None = None
    facts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    markets: list[dict[str, Any]] = field(default_factory=list)
    confidence_label: str | None = None
    confidence_score: float | None = None
    source: str = "none"

    @property
    def richness(self) -> str:
        n = len(self.facts) + (1 if self.score or self.minute else 0) + len(self.markets)
        if n >= 3:
            return "rich"
        if n >= 1:
            return "moderate"
        return "thin"


def _clean_fact(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    t = t.rstrip(".")
    return t[:160] if t else ""


def collect_evidence(
    payload: dict[str, Any] | None,
    ctx: dict[str, Any] | None,
) -> Evidence:
    ev = Evidence()
    ctx = ctx if isinstance(ctx, dict) else {}
    payload = payload if isinstance(payload, dict) else {}

    hce = ctx.get("human_conversation_state") or {}
    if isinstance(hce, dict):
        ev.entity = hce.get("last_entity") or ev.entity
        ev.is_live = bool(hce.get("is_live"))

    match = payload.get("match") or {}
    if isinstance(match, dict):
        home = match.get("home") or match.get("home_team")
        away = match.get("away") or match.get("away_team")
        if home and away:
            ev.entity = f"{home} x {away}"
        elif home:
            ev.entity = str(home)
        if match.get("score") or match.get("goals"):
            ev.score = str(match.get("score") or match.get("goals"))
        if match.get("status"):
            ev.status = str(match["status"])

    if payload.get("is_live"):
        ev.is_live = True
    if payload.get("minute") is not None:
        ev.minute = str(payload.get("minute"))

    for key in ("positive_factors", "negative_factors"):
        items = payload.get(key) or []
        if not isinstance(items, list):
            continue
        bucket = ev.facts if key == "positive_factors" else ev.risks
        for item in items:
            if isinstance(item, str) and item.strip():
                bucket.append(_clean_fact(item))
            elif isinstance(item, dict):
                label = item.get("text") or item.get("factor") or item.get("label")
                if label:
                    bucket.append(_clean_fact(str(label)))

    markets = payload.get("best_markets") or []
    if isinstance(markets, list):
        ev.markets = [m for m in markets if isinstance(m, dict)][:5]

    conf = payload.get("confidence") or {}
    if isinstance(conf, dict):
        ev.confidence_label = conf.get("label")
        try:
            ev.confidence_score = float(conf.get("score"))
        except Exception:
            pass

    # Fallback: last_analysis in session (never invent — only reuse)
    last = ctx.get("last_analysis") or {}
    if isinstance(last, dict) and ev.richness == "thin":
        for key, bucket_name in (
            ("positive_factors", "facts"),
            ("negative_factors", "risks"),
        ):
            items = last.get(key) or []
            if not isinstance(items, list):
                continue
            bucket = ev.facts if bucket_name == "facts" else ev.risks
            for item in items[:3]:
                if isinstance(item, str) and item.strip():
                    bucket.append(_clean_fact(item))
        if not ev.markets and isinstance(last.get("best_markets"), list):
            ev.markets = [m for m in last["best_markets"] if isinstance(m, dict)][:5]
        if not ev.entity:
            lm = last.get("match") or ctx.get("last_match") or {}
            if isinstance(lm, dict):
                h, a = lm.get("home"), lm.get("away")
                if h and a:
                    ev.entity = f"{h} x {a}"
                elif h:
                    ev.entity = str(h)
        if last.get("is_live"):
            ev.is_live = True
        conf = last.get("confidence") or {}
        if isinstance(conf, dict):
            if ev.confidence_label is None or ev.confidence_label in {
                "insufficient",
                "low",
                "baixa",
            }:
                if conf.get("label"):
                    ev.confidence_label = conf.get("label")
                try:
                    ev.confidence_score = float(conf.get("score"))
                except Exception:
                    pass

    ev.facts = ev.facts[:3]
    ev.risks = ev.risks[:2]
    ev.source = "payload+ctx"
    return ev


def _is_social_skip(payload: dict[str, Any], message: str) -> bool:
    ents = dict(payload.get("entities") or {})
    nre = ents.get("natural_response_v2")
    if nre in {
        "ack",
        "thanks",
        "farewell",
        "goodnight",
        "goodmorning",
        "goodafternoon",
        "laugh",
    }:
        return True
    if ents.get("assistant_kind") in {"math", "system", "small_talk", "natural_social"}:
        # Allow meta / sport soft through
        if ents.get("hce_kind") in {
            "meta_question",
            "soft_followup",
            "short_sport_continue",
            "market_before_fixture",
        }:
            return False
        if ents.get("assistant_kind") == "math":
            return True
        if ents.get("assistant_kind") in {"system", "natural_social"}:
            return True
        # small_talk: skip unless sport follow-up intent in message
        folded = _fold(message)
        if re.search(r"\b(mercado|ao\s+vivo|analis|porque|por\s+que)\b", folded):
            return False
        return True
    if ents.get("hce_kind") in {
        "short_loose",
        "short_await_fixture",
        "await_fixture",
        "memory_bankroll_pending",
        "memory_bankroll_saved",
        "memory_stake_guidance",
    }:
        return True
    return False


def _wants_conservative_market(message: str) -> bool:
    return bool(
        re.search(
            r"\b(mais\s+conservador|menor\s+risco|mais\s+seguro|opcao\s+conservadora|"
            r"opção\s+conservadora|qual\s+mercado\s+mais\s+conservador)\b",
            _fold(message),
        )
    )


def _wants_why(message: str) -> bool:
    return bool(
        re.search(
            r"\b(por\s+que\s+voce\s+acha|porque\s+voce\s+acha|por\s+que\s+isso|"
            r"justifica|baseado\s+em\s+que|como\s+voce\s+chegou)\b",
            _fold(message),
        )
    )


def _wants_live_or_sport_read(message: str, payload: dict[str, Any]) -> bool:
    folded = _fold(message)
    ents = dict(payload.get("entities") or {})
    if ents.get("hce_kind") in {"soft_followup", "short_sport_continue"}:
        return True
    if payload.get("best_markets") or payload.get("is_live"):
        return True
    if (payload.get("entities") or {}).get("has_analysis"):
        return True
    if re.search(
        r"\b(ao\s+vivo|live|mercado|pressao|placar|analis|leitura|e\s+agora)\b",
        folded,
    ):
        return True
    return False


def _pick_conservative_market(markets: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not markets:
        return None

    def risk_key(m: dict[str, Any]) -> float:
        for k in ("risk_score", "risk", "volatility"):
            try:
                return float(m.get(k))
            except Exception:
                pass
        label = str(m.get("risk_level") or m.get("label") or "").lower()
        if "conserv" in label or "low" in label or "baixo" in label:
            return 0.0
        if "high" in label or "alto" in label or "agress" in label:
            return 9.0
        # Prefer lower odds as proxy for safer (not inventing — using given number)
        try:
            return float(m.get("odds") or m.get("price") or 99)
        except Exception:
            return 50.0

    return sorted(markets, key=risk_key)[0]


def _market_label(m: dict[str, Any]) -> str:
    return str(
        m.get("market")
        or m.get("name")
        or m.get("selection")
        or m.get("title")
        or "mercado indicado"
    )


def render_thin(ev: Evidence, *, ask: str) -> str:
    subj = ev.entity or "esse jogo"
    live_bit = " ao vivo" if ev.is_live else ""
    if ask == "conservative":
        return (
            f"Para **{subj}**{live_bit}, ainda não tenho uma análise aberta com mercados "
            "ranqueados nesta conversa. Sem isso, eu não cravo um 'mais conservador' — "
            "faltam sinais. Me manda o confronto (ou abre a análise) que eu priorizo o "
            "menor risco com o motivo."
        )
    if ask == "why":
        return (
            f"Sobre **{subj}**, eu só justifico com base em sinais da análise "
            "(fatores, confiança, estado do jogo). Ainda faltam esses elementos aqui — "
            "por isso evito uma conclusão forte sem lastro."
        )
    # live / general sport
    parts = [
        f"No fio de **{subj}**{live_bit}, o que mais importa agora é o estado atual "
        f"da partida"
    ]
    if ev.minute or ev.score:
        detail = []
        if ev.score:
            detail.append(f"placar {ev.score}")
        if ev.minute:
            detail.append(f"minuto {ev.minute}")
        parts[0] += f" ({', '.join(detail)})"
    else:
        parts[0] += " (placar/minuto e se o ritmo está mudando)"
    parts.append(
        "Ainda faltam sinais estatísticos suficientes nesta mensagem para uma conclusão "
        "de mercado mais firme — por isso eu priorizo cautela em vez de uma leitura genérica"
    )
    return ". ".join(p.rstrip(".") for p in parts if p) + "."


def render_reasoned(ev: Evidence, *, ask: str) -> str:
    subj = ev.entity or "o jogo"
    fact = ev.facts[0] if ev.facts else None
    risk = ev.risks[0] if ev.risks else None

    if ask == "conservative":
        m = _pick_conservative_market(ev.markets)
        if not m:
            return render_thin(ev, ask="conservative")
        label = _market_label(m)
        why = _clean_fact(str(m.get("reasoning") or m.get("why") or m.get("explanation") or ""))
        bits = [f"Entre as opções disponíveis para **{subj}**, eu priorizaria **{label}**"]
        if why:
            w = why[0].lower() + why[1:] if why[:1].isupper() else why
            bits[0] += f", porque {w}"
        elif fact:
            bits[0] += f", porque o sinal mais estável que temos é: {fact}"
        else:
            bits[0] += (
                ", porque no conjunto atual é a leitura de menor exposição entre as listadas"
            )
        if risk:
            bits.append(f"Ainda assim, fico atenta a: {risk}")
        if ev.confidence_label in {"low", "insufficient", "baixa"}:
            bits.append("A confiança ainda é limitada — tamanho de stake menor faz sentido")
        return ". ".join(bits) + "."

    if ask == "why":
        if fact:
            body = (
                f"Chego nessa leitura sobre **{subj}** porque {fact[0].lower() + fact[1:]}"
                if fact[:1].isupper()
                else f"Chego nessa leitura sobre **{subj}** porque {fact}"
            )
            if risk:
                body += f". O contraponto que eu não ignoro: {risk}"
            if ev.confidence_label:
                body += f". Confiança atual: {ev.confidence_label}"
            body += ". Se esses sinais mudarem, a conclusão muda com eles."
            return body
        return render_thin(ev, ask="why")

    # Standard F → I → C
    lines: list[str] = []
    if fact:
        lines.append(f"Fato: {fact}.")
        lines.append(
            "Interpretação: isso altera o ritmo da partida e muda o que vale acompanhar agora."
        )
    elif ev.score or ev.minute:
        detail = []
        if ev.score:
            detail.append(f"placar {ev.score}")
        if ev.minute:
            detail.append(f"aos {ev.minute}'")
        lines.append(f"Fato: **{subj}** {' '.join(detail)}.".replace("  ", " "))
        lines.append(
            "Interpretação: o momento do jogo manda mais do que a prévia — "
            "o foco é se a pressão está sustentada."
        )
    else:
        return render_thin(ev, ask="live")

    # Conclusion from markets or caution
    if ev.markets:
        top = ev.markets[0]
        label = _market_label(top)
        lines.append(
            f"Conclusão: se o cenário permanecer, **{label}** é o recorte que eu priorizaria "
            "— não como certeza, mas como leitura mais coerente com os sinais."
        )
    else:
        lines.append(
            "Conclusão: ainda sem mercado cravado; o útil agora é confirmar se a pressão "
            "se sustenta antes de aumentar exposição."
        )
    if risk:
        lines.append(f"Risco a monitorar: {risk}.")
    if ev.confidence_label in {"low", "insufficient", "baixa"} or (
        ev.confidence_score is not None and ev.confidence_score < 0.45
    ):
        lines.append("Ainda faltam sinais para uma leitura mais forte.")
    return " ".join(lines)


def apply_perceived_intelligence(
    message: str,
    payload: dict[str, Any] | None,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Expression of reasoning over sport/analysis turns.
    Never invents evidence. Fail-open returns original payload.
    Phase 7.4: respects turn ownership — no rewrite of HCE/NRE/META.
    """
    try:
        if not isinstance(payload, dict):
            return payload
        ask = "live"
        if _wants_why(message):
            ask = "why"
        elif (payload.get("entities") or {}).get("hce_kind") == "meta_question":
            # Data provenance stays META-owned; do not reclaim
            if not _wants_why(message):
                return payload
            ask = "why"
        if _wants_conservative_market(message):
            ask = "conservative"

        ev = collect_evidence(payload, ctx)

        try:
            from src.conversation.turn_ownership import pie_allowed

            # Ownership lock — except evidence-backed sport clarification (not thin caution)
            if not pie_allowed(payload):
                if not (
                    ask in {"conservative", "why"}
                    and ev.richness != "thin"
                    and (ev.markets or ev.facts)
                ):
                    logger.warning("[AUDIT] PIE: skipped — ownership lock")
                    return payload
                logger.warning(
                    "[AUDIT] PIE: ownership exception — rich evidence ask=%s", ask
                )
        except Exception:
            pass
        if _is_social_skip(payload, message) and ask == "live":
            return payload

        if ask == "live" and not _wants_live_or_sport_read(message, payload):
            # Only upgrade analysis-shaped payloads
            if not (
                payload.get("best_markets")
                or (payload.get("entities") or {}).get("has_analysis")
                or payload.get("positive_factors")
            ):
                return payload
        if ask == "live" and ev.richness == "thin" and not ev.entity and not ev.is_live:
            return payload
        if ask not in {"why", "conservative"} and not (
            ev.entity or ev.is_live or ev.richness != "thin"
        ):
            return payload

        if ask == "conservative":
            text = render_reasoned(ev, ask="conservative")
        elif ask == "why":
            text = render_reasoned(ev, ask="why")
        elif ev.richness == "thin":
            # Priority 1 — no PIE thin-caution loop without new evidence
            if isinstance(ctx, dict):
                sig = f"thin|{ask}|{ev.entity}|{ev.is_live}"
                if ctx.get("pie_last_signature") == sig:
                    logger.warning("[AUDIT] PIE: skipped thin loop signature=%s", sig)
                    return payload
                ctx["pie_last_signature"] = sig
            text = render_thin(ev, ask="live")
        else:
            text = render_reasoned(ev, ask="live")
            if isinstance(ctx, dict):
                ctx["pie_last_signature"] = f"rich|{ask}|{ev.entity}|{len(ev.facts)}"

        # Keep short — perceived intelligence ≠ length
        if len(text) > 520:
            text = text[:517].rsplit(" ", 1)[0] + "…"

        # Don't replace with identical meaning spam
        prev = str(payload.get("executive_summary") or "").strip()
        if prev and text.strip() == prev:
            return payload
        if prev and "faltam sinais" in prev.lower() and "faltam sinais" in text.lower():
            if ev.richness == "thin":
                logger.warning("[AUDIT] PIE: skipped — would repeat caution")
                return payload

        out = dict(payload)
        out["executive_summary"] = text
        out["final_recommendation"] = text
        ents = dict(out.get("entities") or {})
        ents["perceived_intelligence"] = True
        ents["pie_richness"] = ev.richness
        ents["pie_ask"] = ask
        out["entities"] = ents
        logger.warning(
            "[AUDIT] PIE: ask=%s richness=%s entity=%s",
            ask,
            ev.richness,
            ev.entity,
        )
        return out
    except Exception as exc:
        logger.warning("apply_perceived_intelligence fail-open: %s", exc)
        return payload
