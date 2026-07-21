"""
Aurora Follow-Up Engine — Phase 4 + Phase 5B.

Resolves context-dependent follow-up questions without re-running the full
analysis pipeline. Reads ConversationContext and returns a focused PT-BR answer.

Phase 5B additions
------------------
  • Patterns: small_bankroll, still_valid, live_update
  • Conversational preamble ("Estou utilizando o contexto anterior…")
  • response_metadata explainability (used_previous_analysis, confidence_penalty)
  • No rigid "Peça uma nova análise" redirects when last_analysis is partial

Public API
----------
  is_followup(message: str) -> bool
  resolve(message: str, ctx: dict, brain_meta: dict) -> dict | None
"""
from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Follow-up patterns
# ---------------------------------------------------------------------------

_FOLLOWUP_PATTERNS: list[tuple[str, str]] = [
    # Who is better / favourite
    (r"quem\s+est[a]?\s+melhor",                    "who_is_better"),
    (r"qual\s+(?:time|equipe)\s+(?:est[a]?\s+)?melhor", "who_is_better"),
    (r"qual\s+o\s+favorito",                         "who_is_better"),
    (r"quem\s+tem\s+mais\s+chance",                  "who_is_better"),
    # Corners
    (r"e\s+(?:os\s+)?escanteios?",                   "corners_market"),
    (r"e\s+(?:os\s+)?cantos?",                       "corners_market"),
    (r"escanteios?\s*$",                             "corners_market"),
    (r"corners?\s*$",                                "corners_market"),
    # Goals
    (r"e\s+(?:os\s+)?gols?",                         "goals_market"),
    (r"e\s+(?:os\s+)?golos?",                        "goals_market"),
    (r"e\s+o\s+over|e\s+o\s+under",                  "goals_market"),
    (r"e\s+o\s+btts|e\s+ambos\s+marcam",             "goals_market"),
    # Cards
    (r"e\s+(?:os\s+)?cart[o]es?",                    "cards_market"),
    (r"e\s+(?:os\s+)?amarelos?",                     "cards_market"),
    (r"cards?\s*$",                                  "cards_market"),
    # Result
    (r"e\s+(?:o\s+)?resultado",                      "result_market"),
    (r"quem\s+(?:vai\s+)?ganhar",                    "result_market"),
    (r"qual\s+o\s+resultado\s+mais\s+prov[a]vel",    "result_market"),
    # Stake / how much
    (r"quanto\s+(?:apostar|devo\s+apostar|arriscar|colocar)", "how_much_stake"),
    (r"qual\s+(?:o\s+)?stake",                       "how_much_stake"),
    (r"quanto\s+devo\s+colocar",                     "how_much_stake"),
    (r"how\s+much\s+(?:to\s+)?(?:bet|stake)",        "how_much_stake"),
    # Small bankroll (Phase 5B)
    (r"e\s+para\s+banca\s+pequena",                  "small_bankroll"),
    (r"banca\s+pequena",                             "small_bankroll"),
    (r"stake\s+(?:baixo|conservador|pequeno)",       "small_bankroll"),
    (r"para\s+banca\s+(?:baixa|pequena|curta)",      "small_bankroll"),
    # Still valid? (Phase 5B)
    (r"continua\s+valendo",                          "still_valid"),
    (r"ainda\s+vale",                                "still_valid"),
    (r"ainda\s+valendo",                             "still_valid"),
    (r"segue\s+valendo",                             "still_valid"),
    (r"mantem\s+(?:a\s+)?recomendacao",              "still_valid"),
    # Live update from context (Phase 5B) — no full re-analyze
    (r"como\s+est[a]?\s+agora\s*$",                  "live_update"),
    (r"(?:^|(?<=\s))e\s+agora\s*$",                  "live_update"),
    (r"(?:^|(?<=\s))e\s+agora\s*\?",                 "live_update"),
    (r"atualiza(?:r)?\s+(?:o\s+)?(?:status|jogo)",   "live_update"),
    (r"atualiza(?:r)?\s+(?:a\s+)?partida",           "live_update"),
    (r"status\s+atual\s*$",                          "live_update"),
    # Risk
    (r"qual\s+(?:o\s+)?(?:nivel\s+de\s+)?risco",    "what_risk"),
    (r"e\s+(?:o\s+)?risco",                          "what_risk"),
    (r"e\s+arriscado|muito\s+risco",                 "what_risk"),
    # Explain more
    (r"explique\s+(?:melhor|mais|isso|a\s+recomendacao)", "explain_more"),
    (r"mais\s+detalhes?\s*(?:por\s+favor|pf)?\s*$", "explain_more"),
    (r"por\s+que\s+(?:essa|esta)\s+(?:recomendacao|aposta)", "explain_more"),
    (r"pode\s+explicar\s+(?:melhor|mais)",           "explain_more"),
    (r"nao\s+entendi\s+(?:bem|a\s+recomendacao|a\s+analise)", "explain_more"),
    # Safest bet
    (r"(?:aposta|mercado|opcao)\s+mais\s+segur[ao]", "safest_bet"),
    (r"menos\s+arriscad[ao]|menor\s+risco",          "safest_bet"),
    (r"me\s+d[ae]\s+(?:uma\s+)?opcao\s+(?:mais\s+)?segur[ao]", "safest_bet"),
    # Is live
    (r"est[a]?\s+ao\s+vivo|e\s+ao\s+vivo",          "is_live"),
    (r"est[a]?\s+(?:jogando|em\s+andamento)",        "is_live"),
    # Positive / negative factors
    (r"fatores?\s+positivos?|pontos?\s+(?:positivos?|fortes?)", "positive_factors"),
    (r"o\s+que\s+(?:fala\s+)?a\s+favor",            "positive_factors"),
    (r"fatores?\s+negativos?|pontos?\s+(?:negativos?|fracos?)", "negative_factors"),
    (r"o\s+que\s+(?:fala\s+)?contra",               "negative_factors"),
    # Repeat / show again
    (r"repita|pode\s+repetir|mostre\s+novamente",    "repeat"),
    (r"resumo\s+(?:da\s+)?analise\s*$",              "repeat"),
    # All markets
    (r"(?:e\s+)?todos\s+(?:os\s+)?mercados?",        "all_markets"),
    (r"melhores?\s+mercados?\s*$",                   "all_markets"),
    # Phase 8.4-A.8 — bare short follow-ups (continuity / prior analysis)
    (r"^(?:e\s+)?(?:os\s+)?mercados?\s*$",           "all_markets"),
    (r"^(?:e\s+)?(?:o\s+)?placar\s*$",               "result_market"),
    (r"^(?:e\s+)?(?:o\s+)?resultado\s*$",            "result_market"),
    (r"^(?:e\s+)?(?:o\s+)?favoritos?\s*$",           "who_is_better"),
    (r"^(?:e\s+)?(?:as\s+)?estatisticas?\s*$",       "explain_more"),
    (r"^(?:e\s+)?(?:as\s+)?escalacoes?\s*$",         "explain_more"),
]

# Soft confidence haircut when reusing prior analysis (no new pipeline)
_CONTEXT_CONFIDENCE_PENALTY = 0.05


def _context_preamble(match: str) -> str:
    return (
        f"Estou utilizando o contexto anterior:\n"
        f"**{match}**.\n\n"
        f"Com base naquela análise:\n\n"
    )


def _attach_response_metadata(payload: dict, *, followup_type: str) -> dict:
    meta = {
        "used_previous_analysis": True,
        "confidence_penalty": _CONTEXT_CONFIDENCE_PENALTY,
        "source": "conversation_context",
        "followup_type": followup_type,
    }
    payload["response_metadata"] = meta
    brain = dict(payload.get("brain") or {})
    brain["conversation"] = meta
    payload["brain"] = brain
    # Soft confidence penalty on reused analysis
    conf = dict(payload.get("confidence") or {})
    try:
        score = float(conf.get("score") or 0.0)
        conf["score"] = max(0.0, round(score - (_CONTEXT_CONFIDENCE_PENALTY * 10), 2))
    except (TypeError, ValueError):
        pass
    expl = conf.get("explanation") or ""
    if "contexto anterior" not in expl.lower():
        conf["explanation"] = (
            (expl + " · " if expl else "")
            + "Reutilizado do contexto conversacional (leve redução de confiança)."
        ).strip(" ·")
    payload["confidence"] = conf
    notes = list(payload.get("knowledge_notes") or [])
    notes.append(
        "Follow-up resolveu via conversation_context — sem nova busca de fixture/análise completa."
    )
    payload["knowledge_notes"] = notes
    return payload


def _detect_followup_type(message: str) -> str | None:
    norm = _norm(message)
    for pattern, followup_type in _FOLLOWUP_PATTERNS:
        if re.search(pattern, norm):
            logger.warning(
                "[AUDIT] _detect_followup_type: message=%r → type=%r (pattern=%r)",
                message, followup_type, pattern,
            )
            return followup_type
    logger.warning("[AUDIT] _detect_followup_type: message=%r → no pattern matched → None", message)
    return None


def is_followup(message: str) -> bool:
    return _detect_followup_type(message) is not None


# ---------------------------------------------------------------------------
# Helper renderers
# ---------------------------------------------------------------------------

def _market_rows(markets: list[dict]) -> str:
    if not markets:
        return "Nenhum mercado específico encontrado."
    lines = []
    for m in markets:
        prob = m.get("probability", 0)
        ev   = m.get("expected_value", 0)
        risk = m.get("risk", "?")
        lines.append(
            f"• **{m['market']}** — {prob:.0f}% prob · VE {ev:+.1f}% · Risco {risk}\n"
            f"  _{m.get('rationale','')}_"
        )
    return "\n".join(lines)


def _filter_markets(markets: list[dict], keywords: list[str]) -> list[dict]:
    result = []
    for m in markets:
        combined = (m.get("market", "") + " " + m.get("rationale", "")).lower()
        if any(kw.lower() in combined for kw in keywords):
            result.append(m)
    return result


def _attach_followup_match_card(payload: dict, la: dict | None, home: str, away: str) -> dict:
    """Reuse prior match_card (presentation only) when follow-up has fixture context."""
    card = la.get("match_card") if isinstance(la, dict) else None
    if isinstance(card, dict) and card.get("home") and card.get("away"):
        try:
            from src.communication.match_card import attach_match_card
            return attach_match_card(payload, card)
        except Exception:
            payload["match_card"] = card
            return payload
    if home and away:
        try:
            from src.communication.match_card import (
                AURORA_MATCH_VERSION,
                build_predictability,
            )
            is_live = bool(payload.get("is_live"))
            payload["match_card"] = {
                "home": {"name": home, "logo": None},
                "away": {"name": away, "logo": None},
                "score": None,
                "competition": None,
                "venue": None,
                "status_label": payload.get("status"),
                "minute": payload.get("minute"),
                "is_live": is_live,
                "momentum": None,
                "predictability": build_predictability(
                    payload.get("confidence")
                    if isinstance(payload.get("confidence"), dict)
                    else None,
                    is_live=is_live,
                ),
            }
            payload["aurora_version"] = AURORA_MATCH_VERSION
        except Exception:
            pass
    return payload


def _base_payload(intent_name: str, la: dict | None, home: str, away: str, match: str, brain: dict) -> dict:
    defaults = {
        "confidence": {"score": 0.0, "label": "insufficient",
                       "explanation": "Follow-up da análise anterior.", "data_sources": []},
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {"recommended_stake_pct": 0.0, "method": "quarter-Kelly",
                                    "examples": {}, "no_bet": True,
                                    "reasoning": "Use a análise completa para recomendação de stake."},
    }
    if la:
        payload = {
            "intent":    intent_name,
            "entities":  {"home": home, "away": away, "followup": True},
            "match":     la.get("match", match),
            "status":    la.get("status", "Follow-up"),
            "is_live":   la.get("is_live", False),
            "minute":    la.get("minute"),
            "best_markets":            la.get("best_markets", []),
            "confidence":              la.get("confidence", defaults["confidence"]),
            "risk":                    la.get("risk", defaults["risk"]),
            "bankroll_recommendation": la.get("bankroll_recommendation", defaults["bankroll_recommendation"]),
            "positive_factors":        la.get("positive_factors", []),
            "negative_factors":        la.get("negative_factors", []),
            "historical_references":   la.get("historical_references", []),
            "knowledge_notes":         la.get("knowledge_notes", []),
            "executive_summary":       "",
            "final_recommendation":    "",
            "aurora_version": "Copilot v1.0",
            "brain": brain,
        }
        return _attach_followup_match_card(payload, la, home, away)
    payload = {
        "intent":    intent_name,
        "entities":  {"home": home, "away": away, "followup": True},
        "match":     match,
        "status":    None, "is_live": False, "minute": None,
        "best_markets": [],
        **defaults,
        "positive_factors": [], "negative_factors": [],
        "historical_references": [], "knowledge_notes": [],
        "executive_summary":    "",
        "final_recommendation": "",
        "aurora_version": "Copilot v1.0",
        "brain": brain,
    }
    return _attach_followup_match_card(payload, None, home, away)


# ---------------------------------------------------------------------------
# Per-type resolvers
# ---------------------------------------------------------------------------

def _resolve_with_analysis(
    followup_type: str,
    la: dict,
    home: str, away: str, match: str,
    brain: dict,
    ctx: dict | None = None,
) -> dict:
    ctx = ctx or {}
    p = _base_payload("follow_up", la, home, away, match, brain)
    markets  = la.get("best_markets", [])
    conf_score = (la.get("confidence") or {}).get("score", 0.0)
    pos = la.get("positive_factors", [])
    neg = la.get("negative_factors", [])
    risk_info = la.get("risk", {})

    # ── who is better ────────────────────────────────────────────────────────
    if followup_type == "who_is_better":
        if conf_score >= 5.5:
            verdict = f"Os dados favorecem ligeiramente o **{home}**."
        elif conf_score <= 4.5:
            verdict = f"Os dados favorecem ligeiramente o **{away}**."
        else:
            verdict = "A partida está bastante **equilibrada** segundo a análise."
        summary = (
            f"**Quem está melhor em {match}?**\n\n"
            f"{verdict} Confiança geral: **{conf_score:.1f}/10**.\n\n"
        )
        if pos:
            summary += "**Pontos favoráveis detectados:**\n" + "\n".join(f"✅ {x}" for x in pos[:4])
        if neg:
            summary += "\n\n**Riscos / pontos fracos:**\n" + "\n".join(f"⚠️ {x}" for x in neg[:3])
        p.update({
            "executive_summary": summary,
            "final_recommendation": (
                f"Confiança {conf_score:.1f}/10 — {verdict} "
                "Consulte os mercados e stake na análise completa."
            ),
        })

    # ── corners market ───────────────────────────────────────────────────────
    elif followup_type == "corners_market":
        corner_mkts = _filter_markets(markets, ["corner", "escanteio", "canto"])
        if corner_mkts:
            summary = _context_preamble(match) + "**Escanteios:**\n\n" + _market_rows(corner_mkts)
            final   = f"Os mercados de escanteios acima têm o maior valor para {match}."
            p["best_markets"] = corner_mkts
        else:
            top_line = (
                f"**Recomendação principal da análise:** {markets[0].get('market')}\n"
                if markets else ""
            )
            summary = (
                _context_preamble(match)
                + "A análise anterior não destacou um mercado específico de escanteios "
                "entre os melhores rankeados.\n\n"
                "Em geral, escanteios ganham valor quando há equipes ofensivas que cruzam "
                "muito, placar equilibrado na 2ª etapa ou times precisando virar.\n\n"
                + top_line
            )
            final = f"Sem slice dedicado de escanteios — mantendo o contexto de {match}."
            if markets:
                p["best_markets"] = markets[:2]
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── goals market ─────────────────────────────────────────────────────────
    elif followup_type == "goals_market":
        goal_mkts = _filter_markets(markets, ["gol", "goal", "over", "under", "btts", "ambos", "marca"])
        if goal_mkts:
            summary = _context_preamble(match) + "**Mercados de gols:**\n\n" + _market_rows(goal_mkts)
            final   = f"Os mercados de gols acima são os destaques para {match}."
            p["best_markets"] = goal_mkts
        else:
            summary = (
                _context_preamble(match)
                + "Nenhum mercado de gols (Over/Under/BTTS) apareceu no topo do ranking "
                "da análise anterior.\n\n"
                + (
                    f"O destaque daquela análise foi **{markets[0].get('market')}** "
                    f"({markets[0].get('probability', 0):.0f}%)."
                    if markets else
                    "Isso costuma indicar ausência de valor claro em gols com os dados disponíveis."
                )
            )
            final = f"Contexto de {match} reutilizado — sem ranking forte em gols."
            if markets:
                p["best_markets"] = markets[:2]
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── cards market ─────────────────────────────────────────────────────────
    elif followup_type == "cards_market":
        card_mkts = _filter_markets(markets, ["cart", "card", "amarelo", "vermelho", "falta", "foul"])
        if card_mkts:
            summary = _context_preamble(match) + "**Mercados de cartões:**\n\n" + _market_rows(card_mkts)
            final   = "Mercados de cartões com maior valor para esta partida."
            p["best_markets"] = card_mkts
        else:
            summary = (
                _context_preamble(match)
                + "Nenhum mercado de cartões foi destacado no ranking anterior.\n\n"
                "Cartões tendem a ter valor com árbitro rigoroso, rivalidade intensa "
                "ou jogos com muito a perder."
                + (
                    f"\n\nDestaque da análise: **{markets[0].get('market')}**."
                    if markets else ""
                )
            )
            final = f"Contexto de {match} mantido — sem ranking forte em cartões."
            if markets:
                p["best_markets"] = markets[:2]
        p.update({"executive_summary": summary, "final_recommendation": final})
    # ── result market ────────────────────────────────────────────────────────
    elif followup_type == "result_market":
        res_mkts = _filter_markets(markets, ["vitoria", "vitória", "empate", "result", "1x2", "win", "ganha"])
        if res_mkts:
            summary = f"**Resultado — {match}:**\n\n" + _market_rows(res_mkts)
            final   = "Mercados de resultado com maior valor identificado pela análise."
            p["best_markets"] = res_mkts
        elif markets:
            top = markets[0]
            summary = (
                f"O mercado principal recomendado para **{match}** é:\n\n"
                f"• **{top['market']}** ({top.get('probability',0):.0f}% probabilidade)\n"
                f"  _{top.get('rationale','')}_\n\n"
                "Para apostas no resultado (1X2) use as probabilidades da análise como referência."
            )
            final = f"Mercado mais recomendado: **{top['market']}**."
            p["best_markets"] = [top]
        else:
            summary = f"Nenhum mercado de resultado foi rankeado para **{match}**."
            final   = "Dados insuficientes para recomendar resultado específico."
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── how much to stake ────────────────────────────────────────────────────
    elif followup_type == "how_much_stake":
        br       = la.get("bankroll_recommendation", {})
        no_bet   = br.get("no_bet", True)
        pct      = br.get("recommended_stake_pct", 0.0)
        reason   = br.get("reasoning", "")
        examples = br.get("examples", {})
        if no_bet or pct == 0.0:
            summary = (
                f"**Quanto apostar em {match}?**\n\n"
                "⚠️ A Aurora **não recomenda aposta** nesta partida.\n\n"
                f"Motivo: {reason}"
            )
            final = "Não aposte nesta partida — o risco não justifica o retorno potencial."
        else:
            ex_str = ""
            if examples:
                ex_str = "\n\nExemplos por banca:\n" + "\n".join(
                    f"• Banca R${k}: apostar **R${v:.2f}**" for k, v in examples.items()
                )
            summary = (
                f"**Quanto apostar em {match}?**\n\n"
                f"🎯 Recomendação: **{pct:.1f}% da banca** (Critério de Kelly — quarter)\n\n"
                f"{reason}{ex_str}"
            )
            final = f"Stake recomendada: **{pct:.1f}%** da banca pelo Critério de Kelly."
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── what risk ────────────────────────────────────────────────────────────
    elif followup_type == "what_risk":
        rl       = risk_info.get("level", "Unknown")
        flags    = risk_info.get("flags", [])
        inv_cond = risk_info.get("invalidation_conditions", [])
        _risk_pt = {"Low": "🟢 Baixo", "Medium": "🟡 Médio", "High": "🔴 Alto", "Unknown": "⚪ Desconhecido"}
        summary  = f"**Risco para {match}: {_risk_pt.get(rl, rl)}**\n\n"
        if flags:
            summary += "**Fatores de risco:**\n" + "\n".join(f"• {f}" for f in flags)
        else:
            summary += "Nenhum fator de risco crítico identificado."
        if inv_cond:
            summary += "\n\n**Não aposte se:**\n" + "\n".join(f"• {c}" for c in inv_cond[:3])
        advice = {
            "Low":     "Adequado para apostar com a stake recomendada.",
            "Medium":  "Reduza a stake ou aguarde dados ao vivo.",
            "High":    "Alto risco — considere não apostar.",
        }
        final = f"Risco **{rl}** para {match}. {advice.get(rl, '')}"
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── explain more ─────────────────────────────────────────────────────────
    elif followup_type == "explain_more":
        exec_s   = la.get("executive_summary", "")
        pos_list = "\n".join(f"✅ {x}" for x in pos[:5]) or "Nenhum fator positivo listado."
        neg_list = "\n".join(f"⚠️ {x}" for x in neg[:5]) or "Nenhum fator negativo listado."
        kn       = la.get("knowledge_notes", [])
        kn_str   = ("\n\n**Regras metodológicas aplicadas:**\n" + "\n".join(f"📚 {k}" for k in kn[:3])) if kn else ""
        summary  = (
            f"**Explicação detalhada — {match}**\n\n"
            f"{exec_s}\n\n"
            f"**Fatores positivos:**\n{pos_list}\n\n"
            f"**Fatores negativos/riscos:**\n{neg_list}"
            f"{kn_str}"
        )
        final = la.get("final_recommendation") or f"Análise detalhada de {match} acima."
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── safest bet ───────────────────────────────────────────────────────────
    elif followup_type == "safest_bet":
        low_risk = [m for m in markets if m.get("risk") == "Low"]
        medium   = [m for m in markets if m.get("risk") == "Medium"]
        target   = sorted(low_risk or medium or markets,
                          key=lambda m: m.get("probability", 0), reverse=True)
        if target:
            s = target[0]
            summary = (
                f"**Aposta mais segura — {match}:**\n\n"
                f"• **{s['market']}**\n"
                f"  Probabilidade: {s.get('probability',0):.0f}% · Risco: {s.get('risk','?')}"
                f" · VE {s.get('expected_value',0):+.1f}%\n\n"
                f"  _{s.get('rationale','')}_"
            )
            final = f"Menor risco: **{s['market']}** ({s.get('probability',0):.0f}% prob, risco {s.get('risk','?')})."
            p["best_markets"] = [s]
        else:
            summary = f"Nenhum mercado de baixo risco identificado para **{match}**. Considere não apostar."
            final   = "Sem mercados de baixo risco disponíveis — considere não apostar."
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── is live ──────────────────────────────────────────────────────────────
    elif followup_type == "is_live":
        is_live = la.get("is_live", False)
        minute  = la.get("minute")
        live_at = ctx.get("last_live_at") or la.get("updated_at") or ctx.get("updated_at")
        if is_live:
            summary = (
                _context_preamble(match)
                + f"**{match}** estava **ao vivo** no momento da análise.\n\n"
                f"Minuto registrado: **{minute if minute is not None else '?'}**.\n"
                + (f"Snapshot em: {live_at}\n" if live_at else "")
                + "\nNão reexecutei a busca ao vivo — este é o estado da análise anterior."
            )
            final = f"{match} — estado ao vivo reutilizado do contexto."
        else:
            summary = (
                _context_preamble(match)
                + f"**{match}** não estava ao vivo na análise anterior "
                "(dados de pré-jogo / pós-jogo).\n\n"
                "Mantive o contexto da partida sem abrir um novo pipeline."
            )
            final = "Análise pré-jogo no contexto — sem nova busca ao vivo."
        p.update({
            "executive_summary": summary,
            "final_recommendation": final,
            "is_live": bool(is_live),
            "minute": minute,
        })

    # ── small bankroll (Phase 5B) ────────────────────────────────────────────
    elif followup_type == "small_bankroll":
        br = la.get("bankroll_recommendation", {}) or {}
        pct = float(br.get("recommended_stake_pct") or 0.0)
        no_bet = bool(br.get("no_bet", True))
        reason = br.get("reasoning") or ""
        examples = br.get("examples") or {}
        # Conservative haircut for small bank: ~half of recommended, cap low
        small_pct = 0.0 if no_bet else min(pct * 0.5, 1.0)
        top = markets[0] if markets else None
        summary = _context_preamble(match) + "**Orientação para banca pequena:**\n\n"
        if no_bet or pct <= 0:
            summary += (
                "A análise anterior **não recomendava aposta** (ou stake zero).\n"
                f"Motivo: {reason or 'risco/retorno desfavorável'}\n\n"
                "Para banca pequena, o padrão é ainda mais conservador: "
                "**não forçar entrada** só para 'estar no jogo'."
            )
            final = "Banca pequena — priorize preservar capital; sem entrada forçada."
        else:
            summary += (
                f"Stake sugerido na análise: **{pct:.2f}%** da banca.\n"
                f"Para banca pequena, use cerca de **{small_pct:.2f}%** "
                "(metade, com teto baixo).\n\n"
            )
            if top:
                summary += (
                    f"Mercado de referência: **{top.get('market')}** "
                    f"({top.get('probability', 0):.0f}%).\n"
                )
            if examples:
                summary += "\nExemplos da análise anterior:\n"
                for k, v in list(examples.items())[:3]:
                    summary += f"• {k}: {v}\n"
            final = (
                f"Banca pequena em {match}: stake reduzido (~{small_pct:.2f}%), "
                "sem reabrir análise completa."
            )
            p["best_markets"] = markets[:2] if markets else []
        p["bankroll_recommendation"] = {
            **br,
            "recommended_stake_pct": small_pct,
            "reasoning": (
                f"Ajuste conversacional para banca pequena sobre {match}. "
                + (reason or "")
            ).strip(),
        }
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── still valid? (Phase 5B) ──────────────────────────────────────────────
    elif followup_type == "still_valid":
        final_r = la.get("final_recommendation") or ""
        conf = (la.get("confidence") or {}).get("score")
        top = markets[0] if markets else None
        is_live = bool(la.get("is_live"))
        updated = ctx.get("updated_at") or ""
        summary = (
            _context_preamble(match)
            + "**A recomendação anterior continua como referência**, "
            "com leve redução de confiança por reuso (sem nova coleta de dados).\n\n"
        )
        if top:
            summary += (
                f"Mercado principal: **{top.get('market')}** "
                f"({top.get('probability', 0):.0f}%).\n"
            )
        if conf is not None:
            summary += f"Confiança na análise: **{conf}**/10.\n"
        if is_live:
            summary += (
                f"A partida estava ao vivo (minuto {la.get('minute', '?')}) — "
                "o cenário pode ter mudado desde então.\n"
            )
        if updated:
            summary += f"\nContexto atualizado em: {updated}."
        if final_r:
            summary += f"\n\n_{final_r}_"
        final = f"Mantendo a leitura de {match} a partir do contexto anterior."
        p["best_markets"] = markets[:3] if markets else []
        p.update({"executive_summary": summary, "final_recommendation": final or final_r})

    # ── live update from context only (Phase 5B) ─────────────────────────────
    elif followup_type == "live_update":
        is_live = bool(la.get("is_live") or ctx.get("last_is_live"))
        minute = la.get("minute") if la.get("minute") is not None else ctx.get("last_minute")
        live_at = ctx.get("last_live_at") or ctx.get("updated_at")
        status = la.get("status") or ""
        summary = (
            _context_preamble(match)
            + "**Status a partir do contexto (sem nova busca ao vivo):**\n\n"
            f"• Ao vivo na análise: **{'sim' if is_live else 'não'}**\n"
            f"• Minuto registrado: **{minute if minute is not None else 'n/d'}**\n"
            f"• Status: **{status or 'n/d'}**\n"
            + (f"• Snapshot: {live_at}\n" if live_at else "")
            + "\nPara economizar processamento, não reabri a Live Fixture Search. "
            "Se precisar de minuto fresco, diga o placar ou peça a análise completa "
            f"de {match} novamente."
        )
        final = f"Status de {match} reutilizado do contexto conversacional."
        p.update({
            "executive_summary": summary,
            "final_recommendation": final,
            "is_live": is_live,
            "minute": minute,
            "status": status or None,
            "best_markets": markets[:2] if markets else [],
        })

    # ── positive factors ─────────────────────────────────────────────────────
    elif followup_type == "positive_factors":
        if pos:
            summary = (
                _context_preamble(match)
                + "**Fatores positivos:**\n\n"
                + "\n".join(f"✅ {x}" for x in pos)
            )
            final = f"{len(pos)} fator(es) positivo(s) identificado(s) para {match}."
        else:
            summary = _context_preamble(match) + "Nenhum fator positivo significativo na análise anterior."
            final   = "Fatores positivos não detectados nesta análise."
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── negative factors ─────────────────────────────────────────────────────
    elif followup_type == "negative_factors":
        if neg:
            summary = (
                _context_preamble(match)
                + "**Fatores negativos/riscos:**\n\n"
                + "\n".join(f"⚠️ {x}" for x in neg)
            )
            final = f"{len(neg)} risco(s) identificado(s) — considere-os antes de apostar."
        else:
            summary = _context_preamble(match) + "Nenhum fator negativo significativo na análise anterior."
            final   = "Análise favorável — sem fatores negativos detectados."
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── repeat / all markets ─────────────────────────────────────────────────
    elif followup_type in ("repeat", "all_markets"):
        exec_s  = la.get("executive_summary", "")
        final_r = la.get("final_recommendation", "")
        top_mkt = markets[0] if markets else None
        summary = _context_preamble(match) + f"**Resumo:**\n\n{exec_s}"
        if top_mkt and followup_type == "repeat":
            summary += (
                f"\n\n**Recomendação principal:** {top_mkt.get('market','?')} "
                f"({top_mkt.get('probability',0):.0f}%)"
            )
        elif followup_type == "all_markets" and markets:
            summary = _context_preamble(match) + "**Todos os mercados rankeados:**\n\n" + _market_rows(markets)
        p["best_markets"] = markets
        p.update({
            "executive_summary":  summary,
            "final_recommendation": final_r or f"Análise completa de {match} acima.",
        })

    return _attach_response_metadata(p, followup_type=followup_type)

def _no_analysis_response(match: str, followup_type: str, brain: dict) -> dict:
    """Context exists but detailed analysis blob missing — stay conversational."""
    _topic = {
        "corners_market": "escanteios",
        "goals_market":   "gols",
        "cards_market":   "cartões",
        "how_much_stake": "stake",
        "what_risk":      "risco",
        "small_bankroll": "banca pequena",
        "still_valid":    "validade da recomendação",
        "live_update":    "status ao vivo",
    }
    topic = _topic.get(followup_type, "detalhes")
    summary = (
        f"Estou utilizando o contexto anterior:\n**{match}**.\n\n"
        f"Lembro da partida, mas o detalhamento de **{topic}** não ficou "
        f"armazenado nesta sessão (análise parcial ou sessão migrada).\n\n"
        f"Podemos seguir falando sobre {match}, ou você pode pedir uma "
        f"análise completa se quiser dados frescos."
    )
    home = ""
    away = ""
    if " x " in match:
        parts = match.split(" x ", 1)
        home, away = parts[0].strip(), parts[1].strip()
    payload = {
        "intent": "follow_up",
        "entities": {"followup_type": followup_type, "followup": True},
        "match": match,
        "status": None, "is_live": False, "minute": None,
        "executive_summary": summary,
        "best_markets": [],
        "confidence": {
            "score": 2.0, "label": "weak",
            "explanation": "Contexto de partida sem blob de análise completo.",
            "data_sources": ["conversation_context"],
        },
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True,
            "reasoning": "Análise detalhada ausente no contexto.",
        },
        "positive_factors": [], "negative_factors": [],
        "historical_references": [], "knowledge_notes": [],
        "final_recommendation": (
            f"Mantendo o contexto de {match} — análise detalhada incompleta nesta sessão."
        ),
        "aurora_version": "Copilot v1.0",
        "brain": brain,
    }
    payload = _attach_followup_match_card(payload, None, home, away)
    return _attach_response_metadata(payload, followup_type=followup_type)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve(message: str, ctx: dict, brain_meta: dict) -> dict | None:
    """
    Resolve a follow-up question using conversation context (no full re-analyze).
    """
    home  = ctx.get("last_home", "")
    away  = ctx.get("last_away", "")
    match = ctx.get("last_match") or ctx.get("last_fixture") or (
        f"{home} x {away}" if home else ""
    )

    if not match:
        return None

    followup_type = _detect_followup_type(message)
    if not followup_type:
        logger.warning("[AUDIT] resolve: no followup_type → returning None")
        return None

    la = ctx.get("last_analysis")
    has_analysis = isinstance(la, dict) and bool(la)
    logger.warning(
        "[AUDIT] resolve: followup_type=%r | match=%r | home=%r | away=%r"
        " | has_last_analysis=%s",
        followup_type, match, home, away, has_analysis,
    )
    logger.info("FollowUpEngine.resolve: type=%s  match=%r", followup_type, match)

    if has_analysis:
        return _resolve_with_analysis(
            followup_type, la, home, away, match, brain_meta, ctx=ctx,
        )
    return _no_analysis_response(match, followup_type, brain_meta)
