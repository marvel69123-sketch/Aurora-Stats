"""
Aurora Conversation Engine — Phase 5 & 6.

Handles emotional, educational, and casual inputs that fall outside the
standard intent-dispatch pipeline.  Generates empathetic, helpful responses
in Brazilian Portuguese and infers / updates the user profile stored in the
ConversationContext.

Public API
----------
  detect(message: str) -> tuple[str, float] | None
    Returns (intent_name, confidence) or None.
    Intent names: "fear" | "had_losses" | "beginner" | "wants_to_learn"
                  | "confused" | "wants_safer" | "user_profile_query"

  respond(emotional_intent: str, ctx: dict, brain_meta: dict) -> dict
    Returns a CopilotResponse-compatible payload dict.

  extract_user_profile_info(message: str, profile: dict) -> dict
    Parses the message for explicit profile information (bankroll, risk
    preference, experience level) and returns an updated profile dict.
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
# Detection patterns  (pattern, intent, confidence)
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, str, float]] = [
    # User profile query — check first (most specific)
    (r"o\s+que\s+(?:voce\s+)?sabe\s+(?:sobre|de)\s+mim",     "user_profile_query", 0.95),
    (r"qual\s+(?:e\s+)?(?:meu|minha)\s+perfil",               "user_profile_query", 0.92),
    (r"me\s+mostra\s+(?:meu\s+)?perfil",                      "user_profile_query", 0.90),
    # Fear / anxiety
    (r"tenho\s+medo(?:\s+de\s+perder)?",                      "fear",            0.93),
    (r"medo\s+de\s+(?:perder|apostar)",                       "fear",            0.93),
    (r"com\s+medo\s+de\s+perder",                             "fear",            0.93),
    (r"nervoso(?:\s+com\s+(?:a\s+)?aposta)?",                 "fear",            0.85),
    (r"ansioso(?:\s+com\s+(?:a\s+)?aposta)?",                 "fear",            0.83),
    (r"nao\s+sei\s+se\s+devo\s+apostar",                      "fear",            0.88),
    (r"inseguro\s+(?:sobre|com)\s+(?:a\s+)?aposta",           "fear",            0.85),
    # Had losses
    (r"perdi\s+(?:dinheiro|muito|tudo|hoje|essa\s+semana)",   "had_losses",      0.92),
    (r"tomei\s+prejuizo",                                     "had_losses",      0.93),
    (r"fui\s+mal(?:\s+(?:hoje|essa\s+semana|esse\s+mes))?",   "had_losses",      0.83),
    (r"perdi\s+(?:a\s+)?aposta",                              "had_losses",      0.88),
    (r"tudo\s+(?:que\s+)?apostei\s+perdeu",                   "had_losses",      0.90),
    # Beginner
    (r"sou\s+(?:um\s+)?iniciante",                            "beginner",        0.95),
    (r"sou\s+(?:um\s+)?novato",                               "beginner",        0.93),
    (r"nunca\s+apostei",                                      "beginner",        0.93),
    (r"primeira\s+vez\s+(?:apostando|que\s+aposto|aqui)",     "beginner",        0.91),
    (r"nao\s+(?:sei|entendo)\s+(?:de\s+)?apostas?",           "beginner",        0.90),
    (r"comecando\s+(?:agora\s+)?(?:em\s+)?apostas?",          "beginner",        0.88),
    # Wants to learn
    (r"me\s+ensina(?:\s+(?:a\s+)?apostar)?",                  "wants_to_learn",  0.88),
    (r"como\s+(?:aprender|comecar)\s+(?:a\s+)?apostar",       "wants_to_learn",  0.87),
    (r"pode\s+(?:me\s+)?ensinar",                             "wants_to_learn",  0.86),
    (r"quero\s+aprender\s+(?:a\s+)?apostar",                  "wants_to_learn",  0.88),
    # Confused
    (r"nao\s+entendi(?:\s+(?:bem|nada|isso|a\s+analise))?\s*$", "confused",      0.89),
    (r"estou\s+confuso|fiquei\s+confuso",                     "confused",        0.88),
    (r"pode\s+(?:simplificar|explicar\s+de\s+outro\s+jeito)", "confused",        0.87),
    (r"o\s+que\s+(?:significa|quer\s+dizer)(?:\s+isso)?\s*$", "confused",       0.82),
    (r"nao\s+entendo(?:\s+(?:isso|a\s+analise|bem))?\s*$",    "confused",        0.84),
    # Wants safer option
    (r"(?:quero|prefiro|me\s+d[ae])\s+(?:uma\s+)?opcao\s+mais\s+(?:segura|conservadora)",
                                                               "wants_safer",     0.92),
    (r"mais\s+conservador(?:a)?|menos\s+(?:arriscar|arriscado)", "wants_safer",  0.88),
    (r"nao\s+quero\s+(?:arriscar|perder\s+muito)",             "wants_safer",    0.89),
    (r"prefiro\s+(?:algo|uma\s+(?:aposta|opcao))\s+(?:mais\s+)?segur[ao]",
                                                               "wants_safer",     0.91),
    (r"sem\s+muito\s+risco|baixo\s+risco\s+por\s+favor",       "wants_safer",    0.86),
]


def detect(message: str) -> tuple[str, float] | None:
    """
    Detect emotional/conversational intent.
    Returns (intent, confidence) tuple or None if nothing matches.
    """
    norm = _norm(message)
    best_intent: str | None = None
    best_conf = 0.0
    for pattern, intent, conf in _PATTERNS:
        if re.search(pattern, norm):
            if conf > best_conf:
                best_conf = conf
                best_intent = intent
    return (best_intent, best_conf) if best_intent else None


# ---------------------------------------------------------------------------
# User profile extraction
# ---------------------------------------------------------------------------

def extract_user_profile_info(message: str, profile: dict) -> dict:
    """
    Parse *message* for explicit profile info and return an updated profile dict.

    Detected fields
    ---------------
    bankroll          : float — "minha banca é R$500"
    experience_level  : str   — "sou iniciante" → "beginner"
    risk_preference   : str   — "prefiro baixo risco" → "conservative"
    preferred_markets : list  — "gosto de escanteios" → ["corners"]
    """
    norm = _norm(message)
    updated = dict(profile)

    # Bankroll
    m_brl = re.search(r"banca\s+(?:[eé]|de|tem|[eé]\s+de)?\s*r?\$?\s*([\d.,]+)", norm)
    if m_brl:
        raw = m_brl.group(1).replace(",", ".")
        try:
            updated["bankroll"] = float(raw)
            logger.info("ConvEngine: bankroll extracted = %.2f", updated["bankroll"])
        except ValueError:
            pass

    # Experience level
    if re.search(r"sou\s+(?:um\s+)?iniciante|nunca\s+apostei|primeira\s+vez\s+(?:apostando|aqui)", norm):
        updated["experience_level"] = "beginner"
    elif re.search(r"tenho\s+experiencia|sou\s+(?:um\s+)?apostador\s+(?:experiente|profissional)", norm):
        updated["experience_level"] = "experienced"
    elif re.search(r"intermediario|alguma\s+experiencia", norm):
        updated["experience_level"] = "intermediate"

    # Risk preference
    if re.search(r"prefiro\s+(?:baixo\s+risco|apostas?\s+seguras?)|mais\s+conservador", norm):
        updated["risk_preference"] = "conservative"
    elif re.search(r"aceito\s+(?:alto|mais)\s+risco|gosto\s+de\s+risco", norm):
        updated["risk_preference"] = "aggressive"
    elif re.search(r"risco\s+moderado|equilibrado", norm):
        updated["risk_preference"] = "moderate"

    # Preferred markets (simple keyword detection)
    mkts = updated.get("preferred_markets", [])
    if re.search(r"escanteios?|corners?", norm) and "corners" not in mkts:
        mkts.append("corners")
    if re.search(r"gols?|over|under|btts", norm) and "goals" not in mkts:
        mkts.append("goals")
    if re.search(r"cart[oõ]es?|cards?", norm) and "cards" not in mkts:
        mkts.append("cards")
    if mkts:
        updated["preferred_markets"] = mkts

    return updated


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

def _empty_payload(intent_name: str, brain: dict) -> dict:
    return {
        "intent":    intent_name,
        "entities":  {},
        "match":     None, "status": None, "is_live": False, "minute": None,
        "best_markets": [],
        "confidence": {"score": 0.0, "label": "insufficient",
                       "explanation": "Resposta conversacional.", "data_sources": []},
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {"recommended_stake_pct": 0.0, "method": "quarter-Kelly",
                                    "examples": {}, "no_bet": True, "reasoning": ""},
        "positive_factors": [], "negative_factors": [],
        "historical_references": [], "knowledge_notes": [],
        "executive_summary":    "",
        "final_recommendation": "",
        "aurora_version": "Copilot v1.0",
        "brain": brain,
    }


def respond(emotional_intent: str, ctx: dict, brain_meta: dict) -> dict:
    """
    Generate a conversational response for emotional/educational intents.
    Returns a CopilotResponse-compatible payload dict.
    """
    p           = _empty_payload("emotional", brain_meta)
    last_match  = ctx.get("last_match", "")
    last_anal   = ctx.get("last_analysis") or {}
    user_profile = ctx.get("user_profile", {})
    bankroll    = user_profile.get("bankroll")
    experience  = user_profile.get("experience_level")

    # Helper to personalise stake advice
    banca_str = f"R${bankroll:.0f}" if bankroll else "sua banca"

    if emotional_intent == "fear":
        summary = (
            "Entendo perfeitamente — medo de perder é uma reação completamente normal "
            "e sinal de que você está levando isso a sério. 👍\n\n"
            "**Reflexões importantes:**\n\n"
            f"• **Aposte apenas o que pode perder.** Nunca comprometa {banca_str} com apostas impulsivas.\n"
            "• **O Critério de Kelly protege você.** Eu sempre recomendo stakes de 1–3% da banca — "
            "assim mesmo nas perdas o capital é preservado.\n"
            "• **Perdas fazem parte.** Apostadores profissionais perdem 40–45% das apostas. "
            "O que importa é o valor esperado acumulado.\n"
            "• **Sem análise, sem aposta.** Nunca aposte por impulso.\n\n"
            + (f"Quer que eu analise **{last_match}** em detalhe para ver o risco real?" if last_match else
               "Me diga o jogo que você quer analisar e verei o risco antes de qualquer decisão.")
        )
        p["knowledge_notes"] = [
            "Apostas responsáveis: nunca arrisque mais do que pode perder",
            "Kelly Criterion: stake proporcional ao valor esperado da aposta",
            "Variância: perder 40–45% das apostas é normal em sistemas rentáveis",
        ]
        p["final_recommendation"] = (
            "Tome sua decisão com calma. "
            + (f"Peça \"Analisar {last_match}\" para ver o risco real." if last_match else
               "Analise um jogo primeiro antes de apostar qualquer valor.")
        )

    elif emotional_intent == "had_losses":
        summary = (
            "Lamento pelas perdas. Isso acontece — variância é inevitável. 💙\n\n"
            "**O que fazer agora:**\n\n"
            "• **Pause.** Nunca tente recuperar perdas apostando mais (\"tilt\" — causa nº1 de ruína).\n"
            f"• **Revise {banca_str}.** Se as perdas foram significativas, reduza as stakes para 0,5–1%.\n"
            "• **Analise o que deu errado.** Foram apostas de valor ou de impulso?\n"
            "• **Diga \"Revisar banca\"** para ver seu desempenho histórico completo na Aurora.\n\n"
            "Lembre-se: um sistema lucrativo ainda perde muitas apostas individuais. "
            "O que importa é a disciplina ao longo do tempo."
        )
        p["knowledge_notes"] = [
            "Gestão de banca: após perdas, reduza stakes para 0,5–1% da banca",
            "Tilt: tentar recuperar perdas apostando mais é a maior armadilha",
            "Revisão: diga 'Revisar banca' para análise do desempenho histórico",
        ]
        p["final_recommendation"] = "Pause, respire, analise. Diga \"Revisar banca\" para ver seu histórico."

    elif emotional_intent == "beginner":
        summary = (
            "Ótimo começo — apostas esportivas com metodologia são fascinantes! 🎯\n\n"
            "**Conceitos que você precisa entender:**\n\n"
            "📊 **Probabilidade vs. Odds**\n"
            "Odds de 2.00 implica 50% de probabilidade segundo a casa. "
            "Se você acredita que é 60%, existe *valor* — e aí a Aurora entra.\n\n"
            "📈 **Valor Esperado (VE / EV)**\n"
            "A Aurora sempre exibe o VE: se positivo, a aposta vale a pena a longo prazo.\n\n"
            "💰 **Gestão de Banca**\n"
            "Nunca aposte mais de 2–3% da banca em qualquer aposta. "
            "Uso o Critério de Kelly para calcular o tamanho ideal automaticamente.\n\n"
            "🎯 **Por onde começar?**\n"
            "Diga **\"Analisar [Time A] x [Time B]\"** — recebe análise completa com "
            "recomendação, probabilidades, risco e quanto apostar.\n\n"
            "Tem algum jogo em mente? Me diga e analisamos juntos!"
        )
        p["knowledge_notes"] = [
            "Probabilidade implícita das odds = 1 ÷ odd × 100%",
            "VE positivo = aposta lucrativa a longo prazo",
            "Gestão de banca: máximo de 2–3% por aposta (Kelly Criterion)",
            "BTTS: ambas as equipes marcam pelo menos 1 gol",
            "Over/Under: apostas no total de gols da partida",
        ]
        p["final_recommendation"] = "Comece com: \"Analisar [Time da Casa] x [Time Visitante]\" para sua primeira análise."

    elif emotional_intent == "wants_to_learn":
        summary = (
            "Com prazer! Aqui está um guia rápido dos mercados e como a Aurora os analisa:\n\n"
            "**Mercados principais:**\n\n"
            "• **Resultado (1X2)** — casa vence / empate / visitante vence\n"
            "• **Over/Under** — total de gols acima ou abaixo de um número (ex: Over 2,5)\n"
            "• **BTTS (Ambos Marcam)** — ambas as equipes marcam ≥1 gol\n"
            "• **Escanteios** — total de escanteios (Over/Under ou handicap)\n"
            "• **Handicap Asiático** — equilibra partidas desequilibradas\n"
            "• **Cartões** — total de cartões amarelos/vermelhos\n\n"
            "**Como a Aurora analisa cada partida:**\n\n"
            "1️⃣ Estatísticas da temporada (GPG, forma, confrontos diretos)\n"
            "2️⃣ Gols esperados (xG) — qualidade das finalizações\n"
            "3️⃣ 40 regras metodológicas de apostas\n"
            "4️⃣ Critério de Kelly para dimensionamento de stake\n"
            "5️⃣ Motor de aprendizado — ajuste automático baseado em resultados anteriores\n\n"
            "Quer aprender sobre um mercado específico? Tente: **\"O que é BTTS?\"** ou **\"Explique handicap\"**."
        )
        p["knowledge_notes"] = [
            "Mercados: 1X2, Over/Under, BTTS, Escanteios, Handicap Asiático, Cartões",
            "xG (Expected Goals): mede qualidade das finalizações além do placar",
            "Kelly Criterion: fórmula para stake ótima baseada em valor esperado",
        ]
        p["final_recommendation"] = "Pergunte sobre qualquer mercado. Exemplo: \"O que é handicap asiático?\""

    elif emotional_intent == "confused":
        la_rec   = last_anal.get("final_recommendation", "")
        la_exec  = last_anal.get("executive_summary", "")
        summary  = "Sem problema — vou simplificar! 😊\n\n"
        if last_match and la_rec:
            summary += (
                f"**Para {last_match}, em uma linha:**\n\n"
                f"_{la_rec}_\n\n"
                "Quer que eu explique algum termo? Por exemplo:\n"
                "• *\"O que é VE (valor esperado)?\"*\n"
                "• *\"O que é o Critério de Kelly?\"*\n"
                "• *\"O que significa risco Médio?\"*\n\n"
                "Basta perguntar com suas próprias palavras!"
            )
        elif last_match and la_exec:
            summary += (
                f"**Resumo simples de {last_match}:**\n\n"
                f"{la_exec[:400]}{'...' if len(la_exec) > 400 else ''}\n\n"
                "Algum ponto específico ficou confuso? Pergunte!"
            )
        else:
            summary += (
                "A Aurora analisa jogos de futebol e indica qual aposta tem maior chance "
                "de lucro a longo prazo.\n\n"
                "**Três passos simples:**\n\n"
                "1. Diga: **\"Analisar [Time A] x [Time B]\"**\n"
                "2. A Aurora mostra a melhor aposta com explicação clara\n"
                "3. Diga **\"Explique melhor\"** se ainda tiver dúvidas\n\n"
                "O que ficou confuso? Pode perguntar do seu jeito — sem jargões necessários."
            )
        p["final_recommendation"] = "Pergunte sobre qualquer coisa que não ficou clara — estou aqui para ajudar."

    elif emotional_intent == "wants_safer":
        markets = last_anal.get("best_markets", [])
        low_risk = [m for m in markets if m.get("risk") == "Low"]
        if last_match and low_risk:
            safest = sorted(low_risk, key=lambda m: m.get("probability", 0), reverse=True)[0]
            summary = (
                f"Entendido — foco em baixo risco para **{last_match}**! 🛡️\n\n"
                f"**Opção mais conservadora:**\n\n"
                f"• **{safest['market']}**\n"
                f"  Probabilidade: {safest.get('probability',0):.0f}% · Risco: **Baixo** ✅\n"
                f"  VE: {safest.get('expected_value',0):+.1f}%\n\n"
                f"  _{safest.get('rationale','')}_"
            )
            p["best_markets"] = [safest]
            p["final_recommendation"] = f"Opção mais segura: **{safest['market']}** ({safest.get('probability',0):.0f}% prob)."
        elif last_match and markets:
            # Fall back to lowest risk among available
            ordered = sorted(markets, key=lambda m: {"Low": 0, "Medium": 1, "High": 2}.get(m.get("risk","High"), 3))
            safest = ordered[0]
            summary = (
                f"Nenhuma aposta de risco muito baixo identificada para **{last_match}**.\n\n"
                f"A opção de menor risco disponível é:\n\n"
                f"• **{safest['market']}** (Risco: {safest.get('risk','?')}, {safest.get('probability',0):.0f}%)\n\n"
                "Se ainda não parecer seguro o suficiente, **não apostar é sempre uma decisão válida**."
            )
            p["best_markets"] = [safest]
            p["final_recommendation"] = f"Menor risco disponível: **{safest['market']}**. Não apostar também é opção válida."
        else:
            summary = (
                "Ótima postura — priorizar segurança é inteligente! 🛡️\n\n"
                "**Dicas para apostas mais conservadoras:**\n\n"
                "• Foque em mercados com probabilidade acima de 65%\n"
                "• Prefira times com forma consistente em casa ou fora\n"
                "• Evite partidas com muitas variáveis (derby, árbitro desconhecido)\n"
                f"• Stake máxima de 1% de {banca_str} nas apostas 'seguras'\n\n"
                "Peça uma análise e diga **\"Opção mais segura\"** para filtrar o mercado de menor risco."
            )
            p["final_recommendation"] = "Analise uma partida e peça 'opção mais segura' para o mercado de menor risco."

    elif emotional_intent == "user_profile_query":
        exp    = user_profile.get("experience_level")
        risk   = user_profile.get("risk_preference")
        brl    = user_profile.get("bankroll")
        prefs  = user_profile.get("preferred_markets", [])

        if not any([exp, risk, brl, prefs]):
            summary = (
                "Ainda não sei muito sobre você nesta sessão! 🤔\n\n"
                "**O que posso aprender:**\n\n"
                "• **Nível de experiência** — diga *\"sou iniciante\"* ou *\"tenho experiência\"*\n"
                "• **Perfil de risco** — *\"prefiro apostas seguras\"* ou *\"aceito alto risco\"*\n"
                "• **Sua banca** — *\"minha banca é R$500\"*\n"
                "• **Mercados favoritos** — *\"gosto de escanteios\"*\n\n"
                "Quanto mais você compartilha, mais personalizadas ficam minhas análises e recomendações de stake."
            )
        else:
            _exp_map  = {"beginner": "Iniciante 🌱", "intermediate": "Intermediário 📊",
                         "experienced": "Experiente 🏆"}
            _risk_map = {"conservative": "Conservador 🛡️", "moderate": "Moderado ⚖️",
                         "aggressive": "Agressivo 🔥"}
            details = []
            if exp:
                details.append(f"**Nível:** {_exp_map.get(exp, exp)}")
            if risk:
                details.append(f"**Perfil de risco:** {_risk_map.get(risk, risk)}")
            if brl:
                details.append(f"**Banca declarada:** R${brl:.0f}")
            if prefs:
                details.append(f"**Mercados preferidos:** {', '.join(prefs)}")
            summary = (
                "**O que sei sobre você nesta sessão:**\n\n"
                + "\n".join(f"• {d}" for d in details)
                + "\n\nUsarei essas informações para personalizar análises e recomendações de stake."
            )
        p["intent"] = "user_profile_query"
        p["final_recommendation"] = "Compartilhe mais para análises cada vez mais personalizadas."

    p["executive_summary"] = summary
    return p
