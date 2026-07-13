"""
Aurora Follow-Up Engine — Phase 4.

Resolves context-dependent follow-up questions without re-running the full
analysis pipeline.  Reads the ConversationContext stored in the session and
generates a focused, conversational Portuguese answer.

Public API
----------
  is_followup(message: str) -> bool
  resolve(message: str, ctx: dict, brain_meta: dict) -> dict | None
    Returns None when there is no usable context or the message is not a
    recognised follow-up phrase.  On success returns a CopilotResponse-
    compatible payload dict.
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
]


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
        return {
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
    return {
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


# ---------------------------------------------------------------------------
# Per-type resolvers
# ---------------------------------------------------------------------------

def _resolve_with_analysis(
    followup_type: str,
    la: dict,
    home: str, away: str, match: str,
    brain: dict,
) -> dict:
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
            summary = f"**Escanteios — {match}:**\n\n" + _market_rows(corner_mkts)
            final   = f"Os mercados de escanteios acima têm o maior valor para {match}."
            p["best_markets"] = corner_mkts
        else:
            summary = (
                f"A análise de **{match}** não destacou um mercado específico de escanteios.\n\n"
                "Escanteios têm valor tipicamente em jogos com:\n"
                "• Equipes ofensivas que cruzam muito\n"
                "• Placar equilibrado na segunda etapa\n"
                "• Times que precisam virar o resultado\n\n"
                f"Peça uma nova análise de {match} para incluir escanteios explicitamente."
            )
            final = f"Peça: \"Analisar {match} — escanteios\" para mercado detalhado."
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── goals market ─────────────────────────────────────────────────────────
    elif followup_type == "goals_market":
        goal_mkts = _filter_markets(markets, ["gol", "goal", "over", "under", "btts", "ambos", "marca"])
        if goal_mkts:
            summary = f"**Mercados de gols — {match}:**\n\n" + _market_rows(goal_mkts)
            final   = f"Os mercados de gols acima são os destaques para {match}."
            p["best_markets"] = goal_mkts
        else:
            summary = (
                f"Nenhum mercado de gols foi destacado para **{match}**.\n\n"
                "Isso geralmente indica que a partida não apresenta valor claro "
                "nos mercados Over/Under ou BTTS com base nos dados disponíveis."
            )
            final = "Análise não indica valor claro em mercados de gols para esta partida."
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── cards market ─────────────────────────────────────────────────────────
    elif followup_type == "cards_market":
        card_mkts = _filter_markets(markets, ["cart", "card", "amarelo", "vermelho", "falta", "foul"])
        if card_mkts:
            summary = f"**Mercados de cartões — {match}:**\n\n" + _market_rows(card_mkts)
            final   = "Mercados de cartões com maior valor para esta partida."
            p["best_markets"] = card_mkts
        else:
            summary = (
                f"Nenhum mercado de cartões foi destacado para **{match}**.\n\n"
                "Cartões têm valor em jogos com árbitro rigoroso, rivalidade intensa "
                "ou partidas com muito a perder (rebaixamento, título)."
            )
            final = "Sem dados suficientes para recomendar mercado de cartões nesta análise."
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
        if is_live:
            summary = (
                f"✅ **{match} estava ao vivo** quando foi analisado!\n\n"
                f"Minuto da análise: **{minute or '?'}**.\n\n"
                f"Peça uma nova análise para dados atualizados: \"Analisar {match}\""
            )
            final = f"{match} ao vivo — peça nova análise para dados do minuto atual."
        else:
            summary = (
                f"❌ **{match} não estava ao vivo** quando foi analisado.\n\n"
                "Foram utilizados dados de pré-jogo: estatísticas da temporada, "
                "confrontos diretos e probabilidades baseadas em modelos.\n\n"
                "Veja jogos ao vivo: **\"Melhores oportunidades ao vivo\"**"
            )
            final = "Análise pré-jogo. Para ao vivo: \"Melhores oportunidades ao vivo\"."
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── positive factors ─────────────────────────────────────────────────────
    elif followup_type == "positive_factors":
        if pos:
            summary = (
                f"**Fatores positivos para {match}:**\n\n"
                + "\n".join(f"✅ {x}" for x in pos)
            )
            final = f"{len(pos)} fator(es) positivo(s) identificado(s) para {match}."
        else:
            summary = f"Nenhum fator positivo significativo identificado para **{match}**."
            final   = "Fatores positivos não detectados nesta análise."
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── negative factors ─────────────────────────────────────────────────────
    elif followup_type == "negative_factors":
        if neg:
            summary = (
                f"**Fatores negativos/riscos para {match}:**\n\n"
                + "\n".join(f"⚠️ {x}" for x in neg)
            )
            final = f"{len(neg)} risco(s) identificado(s) — considere-os antes de apostar."
        else:
            summary = f"Nenhum fator negativo significativo para **{match}** — sinal favorável."
            final   = "Análise favorável — sem fatores negativos detectados."
        p.update({"executive_summary": summary, "final_recommendation": final})

    # ── repeat / all markets ─────────────────────────────────────────────────
    elif followup_type in ("repeat", "all_markets"):
        exec_s  = la.get("executive_summary", "")
        final_r = la.get("final_recommendation", "")
        top_mkt = markets[0] if markets else None
        summary = f"**Resumo da análise — {match}:**\n\n{exec_s}"
        if top_mkt and followup_type == "repeat":
            summary += (
                f"\n\n**Recomendação principal:** {top_mkt.get('market','?')} "
                f"({top_mkt.get('probability',0):.0f}%)"
            )
        elif followup_type == "all_markets" and markets:
            summary = f"**Todos os mercados rankeados — {match}:**\n\n" + _market_rows(markets)
        p["best_markets"] = markets
        p.update({
            "executive_summary":  summary,
            "final_recommendation": final_r or f"Análise completa de {match} acima.",
        })

    return p


def _no_analysis_response(match: str, followup_type: str, brain: dict) -> dict:
    """Helpful redirect when context exists but no stored analysis."""
    _topic = {
        "corners_market": "escanteios",
        "goals_market":   "gols",
        "cards_market":   "cartões",
        "how_much_stake": "stake",
        "what_risk":      "risco",
    }
    topic = _topic.get(followup_type, "detalhes")
    summary = (
        f"Lembro que você perguntou sobre **{match}**, mas a análise detalhada "
        f"não está disponível nesta sessão.\n\n"
        f"Para obter informações sobre **{topic}**, peça uma análise:\n\n"
        f"> **\"Analisar {match}\"**"
    )
    return {
        "intent": "follow_up",
        "entities": {"followup_type": followup_type},
        "match": match,
        "status": None, "is_live": False, "minute": None,
        "executive_summary": summary,
        "best_markets": [],
        "confidence": {"score": 0.0, "label": "insufficient",
                       "explanation": "Análise anterior não disponível.", "data_sources": []},
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {"recommended_stake_pct": 0.0, "method": "quarter-Kelly",
                                    "examples": {}, "no_bet": True,
                                    "reasoning": "Analise a partida primeiro."},
        "positive_factors": [], "negative_factors": [],
        "historical_references": [], "knowledge_notes": [],
        "final_recommendation": f"Peça: \"Analisar {match}\" para análise completa.",
        "aurora_version": "Copilot v1.0",
        "brain": brain,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve(message: str, ctx: dict, brain_meta: dict) -> dict | None:
    """
    Resolve a follow-up question using conversation context.

    Parameters
    ----------
    message : str
        Raw user message.
    ctx : dict
        ConversationContext dict from chat_db.get_conversation_context().
        Expected keys: last_home, last_away, last_match, last_analysis.
    brain_meta : dict
        Output of src.brain.get_brain_meta().

    Returns
    -------
    dict
        CopilotResponse-compatible payload dict, or None when the message is
        not a follow-up or there is no context to reference.
    """
    home  = ctx.get("last_home", "")
    away  = ctx.get("last_away", "")
    match = ctx.get("last_match") or (f"{home} x {away}" if home else "")

    if not match:
        return None

    followup_type = _detect_followup_type(message)
    if not followup_type:
        logger.warning("[AUDIT] resolve: no followup_type → returning None")
        return None

    la = ctx.get("last_analysis")
    has_analysis = la is not None
    logger.warning(
        "[AUDIT] resolve: followup_type=%r | match=%r | home=%r | away=%r"
        " | has_last_analysis=%s → selected_engine=%s",
        followup_type, match, home, away, has_analysis,
        "_resolve_with_analysis" if has_analysis else "_no_analysis_response",
    )
    logger.info("FollowUpEngine.resolve: type=%s  match=%r", followup_type, match)

    if la:
        return _resolve_with_analysis(followup_type, la, home, away, match, brain_meta)
    return _no_analysis_response(match, followup_type, brain_meta)
