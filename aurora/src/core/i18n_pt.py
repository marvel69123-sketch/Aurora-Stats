"""
Aurora i18n — Brazilian Portuguese presentation layer.

This module is a PURE PRESENTATION LAYER. It translates the final,
already-computed copilot payload into natural Brazilian Portuguese.

It NEVER touches numbers, probabilities, odds, expected value, Kelly
sizing, methodology scores, or any calculation. It only rewrites the
natural-language labels and prose produced by the engines/formatters.

Flow:
    engines → formatter → translate_report(payload) → frontend

Public API
----------
    translate_label(label)      — market / generic label → PT
    translate_category(cat)     — knowledge / methodology category → PT
    translate_text(text)        — free-form prose → PT (patterns + phrases)
    translate_report(payload)   — walk a copilot payload dict, translate all
                                  user-facing string fields (numbers untouched)

Design
------
translate_text applies three ordered passes:
  1. REGEX PATTERNS  — templated sentences with interpolated numbers/names,
     rebuilt in PT with dynamic groups preserved.
  2. PHRASES         — literal multi-word English fragments (longest first),
     case-insensitive.
  3. WORDS           — standalone English-only nouns/verbs that never collide
     with Portuguese, word-boundary matched.

Everything is graceful: unknown input passes through unchanged. Running the
translator over text that is already Portuguese is safe — the English-only
patterns/phrases/words simply do not match.
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# 1. LABEL DICTIONARIES
# ---------------------------------------------------------------------------

RISK_TRANSLATIONS: dict[str, str] = {
    "High": "Alto",
    "Medium": "Médio",
    "Low": "Baixo",
    "Unknown": "Desconhecido",
    "Critical": "Crítico",
}

CONFIDENCE_TRANSLATIONS: dict[str, str] = {
    # _confidence_adjective (intelligence_engine)
    "Exceptional": "Excepcional",
    "Strong": "Forte",
    "Solid": "Sólida",
    "Moderate": "Moderada",
    "Limited": "Limitada",
    "Low": "Baixa",
    # _conf_label (copilot router)
    "strong": "alta",
    "moderate": "moderada",
    "adequate": "adequada",
    "weak": "fraca",
    "insufficient": "muito baixa",
    "unavailable": "indisponível",
    "exceptional": "excepcional",
    "solid": "sólida",
    "limited": "limitada",
    "low": "baixa",
}

# Knowledge-engine categories + methodology category labels.
CATEGORY_TRANSLATIONS: dict[str, str] = {
    # knowledge_db category keys
    "methodology": "Metodologia",
    "betting_rules": "Regras de Apostas",
    "bankroll_rules": "Regras de Banca",
    "market_rules": "Regras de Mercado",
    "live_rules": "Regras Ao Vivo",
    "pre_match_rules": "Regras Pré-Jogo",
    "referee_rules": "Regras de Arbitragem",
    "league_rules": "Regras da Liga",
    "team_rules": "Regras das Equipes",
    "psychology": "Psicologia",
    "risk_management": "Gestão de Risco",
    "red_flags": "Alertas",
    "golden_rules": "Regras de Ouro",
    # Same keys as they appear upper-cased with spaces in knowledge notes tags
    "METHODOLOGY": "METODOLOGIA",
    "BETTING RULES": "REGRAS DE APOSTAS",
    "BANKROLL RULES": "REGRAS DE BANCA",
    "MARKET RULES": "REGRAS DE MERCADO",
    "LIVE RULES": "REGRAS AO VIVO",
    "PRE MATCH RULES": "REGRAS PRÉ-JOGO",
    "REFEREE RULES": "REGRAS DE ARBITRAGEM",
    "LEAGUE RULES": "REGRAS DA LIGA",
    "TEAM RULES": "REGRAS DAS EQUIPES",
    "PSYCHOLOGY": "PSICOLOGIA",
    "RISK MANAGEMENT": "GESTÃO DE RISCO",
    "RED FLAGS": "ALERTAS",
    "GOLDEN RULES": "REGRAS DE OURO",
    # methodology category labels (intelligence_engine _CATEGORY_LABELS)
    "Match Context": "Contexto da Partida",
    "Team Strength": "Força das Equipes",
    "Current Form": "Forma Atual",
    "Motivation & Stakes": "Motivação & Importância",
    "Home Advantage": "Vantagem de Jogar em Casa",
    "Away Performance": "Desempenho Fora de Casa",
    "Expected Goals Analysis": "Análise de Gols Esperados (xG)",
    "Live Momentum": "Momentum Ao Vivo",
    "Referee Tendency": "Tendência da Arbitragem",
    "Tactical Patterns": "Padrões Táticos",
    "Player Availability": "Disponibilidade de Jogadores",
    "Head-to-Head Record": "Histórico de Confrontos",
    "Weather Impact": "Impacto do Clima",
    "Portfolio Risk": "Risco da Carteira",
    "Learning Calibration": "Calibração de Aprendizado",
    "Historical Learning": "Aprendizado Histórico",
    # methodology_v1 internal category display names (cs.name)
    "Value Bet Detection": "Detecção de Aposta de Valor",
    "Corners Pattern": "Padrão de Escanteios",
    "Cards Pattern": "Padrão de Cartões",
    "Referee Influence": "Influência da Arbitragem",
    "Tactical Style": "Estilo Tático",
    "Bankroll Risk": "Risco de Banca",
}

# Market names (intelligence_engine _MARKET_LABELS + decision_center market_name).
MARKET_TRANSLATIONS: dict[str, str] = {
    "Home Win": "Vitória do Mandante",
    "Away Win": "Vitória do Visitante",
    "Draw": "Empate",
    "Both Teams To Score — Yes": "Ambas Marcam — Sim",
    "Both Teams To Score — No": "Ambas Marcam — Não",
    "BTTS Yes": "Ambas Marcam — Sim",
    "BTTS No": "Ambas Marcam — Não",
    "Draw No Bet — Home": "Empate Anula Aposta — Mandante",
    "Draw No Bet — Away": "Empate Anula Aposta — Visitante",
    "Double Chance 1X": "Chance Dupla 1X",
    "Double Chance X2": "Chance Dupla X2",
    "Double Chance 12": "Chance Dupla 12",
    "Asian Handicap — Home −0.5": "Handicap Asiático — Mandante −0.5",
    "Asian Handicap — Away +0.5": "Handicap Asiático — Visitante +0.5",
    "Over 1.5 Goals": "Mais de 1.5 Gols",
    "Over 2.5 Goals": "Mais de 2.5 Gols",
    "Over 3.5 Goals": "Mais de 3.5 Gols",
    "Over 4.5 Goals": "Mais de 4.5 Gols",
    "Under 2.5 Goals": "Menos de 2.5 Gols",
    "Over 8.5 Corners": "Mais de 8.5 Escanteios",
    "Over 9.5 Corners": "Mais de 9.5 Escanteios",
    "Over 3.5 Cards": "Mais de 3.5 Cartões",
    "Over 4.5 Cards": "Mais de 4.5 Cartões",
    "Anytime Goalscorer": "Marca a Qualquer Momento",
    "Anytime Assist": "Assistência a Qualquer Momento",
}


# ---------------------------------------------------------------------------
# 2. REGEX PATTERNS — templated sentences (numbers/names preserved)
# ---------------------------------------------------------------------------
# NOTE: order matters. Sub-phrases (probability / EV / risk) are translated
# BEFORE the sentence frames that embed them, so the frames capture PT text.

_RAW_PATTERNS: list[tuple[str, str]] = [
    # ── probability phrases (_probability_phrase) ───────────────────────────
    (r"a high (\d+)% probability", r"uma alta probabilidade de \1%"),
    (r"a solid (\d+)% probability", r"uma probabilidade sólida de \1%"),
    (r"a marginal (\d+)% probability", r"uma probabilidade marginal de \1%"),
    (r"a (\d+)% probability", r"uma probabilidade de \1%"),
    # ── expected-value phrases (_ev_phrase) ─────────────────────────────────
    (r"a substantial \+([\d.]+)% edge over the bookmaker",
     r"uma vantagem substancial de +\1% sobre a casa de apostas"),
    (r"a healthy \+([\d.]+)% expected value",
     r"um valor esperado saudável de +\1%"),
    (r"a positive \+([\d.]+)% edge", r"uma vantagem positiva de +\1%"),
    (r"a marginal \+([\d.]+)% edge", r"uma vantagem marginal de +\1%"),
    (r"a negative EV of ([\-\d.]+)% \(below threshold\)",
     r"um VE negativo de \1% (abaixo do limite)"),

    # ── executive summary opening lines ─────────────────────────────────────
    (r"(.+?) is currently live in minute (\d+), with the score at (.+?)\.",
     r"\1 está ao vivo no minuto \2, com o placar em \3."),
    (r"(.+?) is currently live, with the score at (.+?)\.",
     r"\1 está ao vivo, com o placar em \2."),
    (r"(.+?) is the subject of Aurora's pre-match analysis\.",
     r"A partida \1 está sendo analisada pela Aurora (análise pré-jogo)."),

    # ── recommendation / no-recommendation sentences ────────────────────────
    (r"Aurora's (\w+)-confidence assessment \(([\d.]+)/10\) identifies \*\*(.+?)\*\* "
     r"as the primary opportunity, carrying (.+?) and (.+?)\.",
     r"A avaliação da Aurora, com confiança \1 (\2/10), identifica **\3** "
     r"como a principal oportunidade, apresentando \4 e \5."),
    (r"Aurora's methodology score of ([\d.]+)/10 does not clear the minimum "
     r"threshold for a confident recommendation at this time — exercise caution "
     r"before acting on any market in this fixture\.",
     r"A pontuação metodológica da Aurora, de \1/10, ainda não atingiu o nível "
     r"mínimo necessário para uma recomendação confiante neste momento — tenha "
     r"cautela antes de agir em qualquer mercado desta partida."),

    # ── data-quality sentences ──────────────────────────────────────────────
    (r"The assessment integrates (.+?), processed through Aurora's three-layer "
     r"Poisson model\.",
     r"A avaliação integra \1, processados pelo modelo de Poisson de três "
     r"camadas da Aurora."),
    (r"The assessment relies on season-average goal rates \(xG data is "
     r"unavailable, increasing uncertainty across all goal markets\)\.",
     r"A avaliação se baseia nas médias de gols da temporada (dados de xG "
     r"indisponíveis, aumentando a incerteza em todos os mercados de gols)."),

    # ── verdict sentences ───────────────────────────────────────────────────
    (r"A total of (\d+) markets pass Aurora's full methodology gate, offering "
     r"good breadth of opportunity with a (.+?)\.",
     r"Um total de \1 mercados passam pelo filtro metodológico completo da "
     r"Aurora, oferecendo boa variedade de oportunidades com um \2."),
    (r"(\d+) markets clear Aurora's gates\. The risk profile is (.+?) — size "
     r"stakes accordingly\.",
     r"\1 mercados passam pelos filtros da Aurora. O perfil de risco é \2 — "
     r"dimensione as stakes de acordo."),
    (r"This is a selective, single-market opportunity\. Only one market clears "
     r"Aurora's full filter at a (.+?)\.",
     r"Esta é uma oportunidade seletiva, de mercado único. Apenas um mercado "
     r"passa pelo filtro completo da Aurora com um \1."),
    (r"No markets currently pass Aurora's full methodology filter\. The "
     r"analysis below explains the key blockers and what would need to change\.",
     r"Nenhum mercado passa atualmente pelo filtro metodológico completo da "
     r"Aurora. A análise abaixo explica os principais bloqueios e o que "
     r"precisaria mudar."),

    # ── risk-factor lines (intelligence_engine _risk_factors) ───────────────
    (r"\*\*(.+?)\*\* scores only ([\d.]+)/10 — this is a critical weakness in "
     r"the current analysis: (.+)",
     r"**\1** pontua apenas \2/10 — esta é uma fraqueza crítica na análise "
     r"atual: \3"),
    (r"\*\*Methodology score ([\d.]+)/10 is below the recommended threshold of "
     r"([\d.]+)\.\*\* Aurora's gate is set to block recommendations below this "
     r"level\. Any bet in this fixture carries above-average model uncertainty\.",
     r"**A pontuação metodológica de \1/10 está abaixo do limite recomendado "
     r"de \2.** O filtro da Aurora bloqueia recomendações abaixo deste nível. "
     r"Qualquer aposta nesta partida carrega incerteza acima da média do modelo."),
    (r"\*\*Early live data \(minute (\d+)\)\*\* — fewer than 30 minutes played "
     r"means statistical signals are still volatile\. Wait until minute 30\+ "
     r"for higher reliability\.",
     r"**Dados iniciais ao vivo (minuto \1)** — menos de 30 minutos jogados "
     r"significa que os sinais estatísticos ainda são voláteis. Aguarde o "
     r"minuto 30+ para maior confiabilidade."),

    # ── positive/negative factor suffix ─────────────────────────────────────
    (r" — this category is dragging the overall score down\.",
     r" — esta categoria está puxando a pontuação geral para baixo."),

    # ── confidence explanation ──────────────────────────────────────────────
    (r"Aurora's \*\*([\d.]+)/10 confidence score\*\* \((\w+)\) reflects both "
     r"the quality of available data and the strength of the underlying signals\.",
     r"A **pontuação de confiança de \1/10** da Aurora (\2) reflete tanto a "
     r"qualidade dos dados disponíveis quanto a força dos sinais subjacentes."),
    (r"\*\*Methodology score:\*\* ([\d.]+)/10 \((\w+)\) — this is the average "
     r"of 15 weighted category scores\. The strongest contributions came from "
     r"(.+?)\. The weakest areas were (.+?)\.",
     r"**Pontuação metodológica:** \1/10 (\2) — esta é a média de 15 "
     r"pontuações de categoria ponderadas. As contribuições mais fortes vieram "
     r"de \3. As áreas mais fracas foram \4."),
    (r"Confidence is not win probability\. A ([\d.]+)/10 confidence score means "
     r"Aurora has (\w+) data quality and signal consistency — not that the "
     r"outcome is (\d+)% certain\. Football is inherently probabilistic\.",
     r"Confiança não é probabilidade de vitória. Uma pontuação de confiança de "
     r"\1/10 significa que a Aurora tem qualidade de dados e consistência de "
     r"sinais \2 — não que o resultado seja \3% garantido. O futebol é "
     r"inerentemente probabilístico."),

    # ── track record / learning references ──────────────────────────────────
    (r"\*\*Overall track record\*\*: (\d+) predictions logged — (\d+) wins, "
     r"(\d+) losses, (\d+) pending\. Current accuracy: ([\d.]+)%\. ROI: "
     r"([\+\-\d.]+)%\.",
     r"**Histórico geral**: \1 previsões registradas — \2 vitórias, \3 "
     r"derrotas, \4 pendentes. Precisão atual: \5%. ROI: \6%."),
    (r"\*\*Aurora's best-performing market\*\*: (.+?) — highest historical "
     r"accuracy\.",
     r"**Mercado de melhor desempenho da Aurora**: \1 — maior precisão "
     r"histórica."),
    (r"\*\*Highest-accuracy league\*\*: (.+?) — current fixture league may "
     r"differ\.",
     r"**Liga de maior precisão**: \1 — a liga da partida atual pode ser "
     r"diferente."),

    # ── stake sizing (recommended_stake) ────────────────────────────────────
    (r"\*\*Aurora recommends a ([\d.]+)% stake\*\* on \*\*(.+?)\*\* using "
     r"quarter-Kelly bankroll methodology\.",
     r"**A Aurora recomenda uma stake de \1%** em **\2** usando a metodologia "
     r"de banca quarter-Kelly."),
    (r"£1,000 bankroll → \*\*£(\d+)\*\*", r"banca de £1.000 → **£\1**"),
    (r"£5,000 bankroll → \*\*£(\d+)\*\*", r"banca de £5.000 → **£\1**"),
    (r"£10,000 bankroll → \*\*£(\d+)\*\*", r"banca de £10.000 → **£\1**"),

    # ── methodology_v1 reason fragments (interpolated) ──────────────────────
    (r"Live at (\d+)' — full data available \((\d+)% signal coverage\)\.",
     r"Ao vivo aos \1' — dados completos disponíveis (\2% de cobertura de sinal)."),
    (r"Upcoming fixture — (\d+)/4 pre-match signals available\.",
     r"Partida futura — \1/4 sinais pré-jogo disponíveis."),
    (r"win rate ([\d.]+%)", r"taxa de vitória de \1"),
    (r"(\d+) corners in (\d+)' → ([\d.]+)/90 \(above ([\d.]+) baseline — "
     r"high-corner match\)\.",
     r"\1 escanteios em \2' → \3/90 (acima da referência de \4 — partida de "
     r"muitos escanteios)."),
    (r"(\d+) corners in (\d+)' → ([\d.]+)/90 \(below ([\d.]+) baseline — "
     r"low-corner match\)\.",
     r"\1 escanteios em \2' → \3/90 (abaixo da referência de \4 — partida de "
     r"poucos escanteios)."),
    (r"(\d+) corners in (\d+)' → ([\d.]+)/90 \(on-baseline\)\.",
     r"\1 escanteios em \2' → \3/90 (na referência)."),
    (r"(\d+) cards, (\d+) fouls in (\d+)' \(([\d.]+) fouls/min — "
     r"high-intensity disciplinary match\)\.",
     r"\1 cartões, \2 faltas em \3' (\4 faltas/min — partida disciplinarmente "
     r"intensa)."),
    (r"(\d+) cards, (\d+) fouls in (\d+)' \(([\d.]+) fouls/min — clean match "
     r"so far\)\.",
     r"\1 cartões, \2 faltas em \3' (\4 faltas/min — partida limpa até agora)."),
    (r"(\d+) cards, (\d+) fouls in (\d+)' \(([\d.]+) fouls/min — average "
     r"discipline\)\.",
     r"\1 cartões, \2 faltas em \3' (\4 faltas/min — disciplina média)."),
    (r"Value detected: (.+?) at (\d+)% \(≥(\d+)% gate\), confidence ([\d.]+)/10\.",
     r"Valor detectado: \1 a \2% (limite ≥\3%), confiança \4/10."),

    # ── confidence-explanation data-availability line (interpolated) ────────
    (r"live match data \(minute (\d+)\) ✓",
     r"dados da partida ao vivo (minuto \1) ✓"),

    # ── decision_center market rationales (interpolated) ────────────────────
    (r"(.+?) probability from three-layer Poisson model\.",
     r"\1 — probabilidade a partir do modelo de Poisson de três camadas."),
    (r"(.+?) to win outright — draw excluded from market\.",
     r"\1 vence sem empate — empate excluído do mercado."),
    (r"(.+?) or Draw — only (.+?) win loses\.",
     r"\1 ou Empate — apenas a vitória de \2 perde."),
    (r"Draw or (.+?) — only (.+?) win loses\.",
     r"Empate ou \1 — apenas a vitória de \2 perde."),
    (r"(.+?) or (.+?) win — draw loses\. Draw probability: (\d+)%\.",
     r"\1 ou \2 vencem — empate perde. Probabilidade de empate: \3%."),
    (r"(.+?) AH ([+\-−][\d.]+): must win outright by any margin\.",
     r"\1 HA \2: precisa vencer por qualquer margem."),
    (r"(.+?) AH ([+\-−][\d.]+): away win or draw both return a profit\.",
     r"\1 HA \2: vitória do visitante ou empate retornam lucro."),
    (r"(.+?) AH ([+\-−][\d.]+): home win or draw both return a profit\.",
     r"\1 HA \2: vitória do mandante ou empate retornam lucro."),
    (r"Over ([\d.]+) goals\.", r"Mais de \1 gols."),
    (r"Under ([\d.]+) goals\.", r"Menos de \1 gols."),
    (r"(\d+) corners in (\d+)' → pace ([\d.]+)/90 \(baseline ([\d.]+)\)\.",
     r"\1 escanteios em \2' → ritmo \3/90 (referência \4)."),
    (r"Pre-match estimate — baseline ([\d.]+) corners/90\.",
     r"Estimativa pré-jogo — referência de \1 escanteios/90."),
    (r"(\d+) cards in (\d+)' \((\d+) fouls, ([\d.]+)/min\)\.",
     r"\1 cartões em \2' (\3 faltas, \4/min)."),
    (r"Pre-match estimate — baseline ([\d.]+) cards/90\.",
     r"Estimativa pré-jogo — referência de \1 cartões/90."),
    (r"(.+?) anytime scorer — estimated (\d+)% of team goals\.",
     r"\1 marca a qualquer momento — estimado em \2% dos gols da equipe."),
    (r"(.+?) anytime assist — estimated from expected goals\.",
     r"\1 assistência a qualquer momento — estimada a partir dos gols esperados."),
    (r"Probability ([\d.]+)% < minimum (\d+)%",
     r"Probabilidade \1% < mínimo \2%"),
    (r"Confidence ([\d.]+) < minimum ([\d.]+)",
     r"Confiança \1 < mínimo \2"),

    # ── invalidation conditions (interpolated) ──────────────────────────────
    (r"\*\*Lineup change\*\*: If a key striker or starting goalkeeper is ruled "
     r"out for either (.+?) or (.+?) in the confirmed lineup, re-run this "
     r"analysis with the updated team news — player availability can shift goal "
     r"market probabilities by 8–15%\.",
     r"**Mudança de escalação**: Se um atacante importante ou o goleiro titular "
     r"for desfalque em \1 ou \2 na escalação confirmada, refaça esta análise "
     r"com as notícias atualizadas das equipes — a disponibilidade de jogadores "
     r"pode alterar as probabilidades dos mercados de gols em 8–15%."),
    (r"\*\*Rotation or tactical change\*\*: The (.+?) knowledge rule flags that "
     r"squad rotation or a new manager's first appearances create high variance "
     r"not modelled by season averages\.",
     r"**Rodízio ou mudança tática**: A regra de conhecimento \1 sinaliza que o "
     r"rodízio do elenco ou as primeiras partidas de um novo técnico criam alta "
     r"variância não modelada pelas médias da temporada."),
    (r"\*\*Methodology score improvement\*\*: The current score of ([\d.]+)/10 "
     r"is below Aurora's high-confidence threshold of ([\d.]+)\. If more data "
     r"becomes available \(live stats, referee confirmed, lineups released\), "
     r"run again — the recommendation may strengthen or disappear\.",
     r"**Melhora da pontuação metodológica**: A pontuação atual de \1/10 está "
     r"abaixo do limite de alta confiança da Aurora, de \2. Se mais dados "
     r"ficarem disponíveis (estatísticas ao vivo, árbitro confirmado, escalações "
     r"divulgadas), rode novamente — a recomendação pode se fortalecer ou "
     r"desaparecer."),

    # ── standalone market names (anchored; team names preserved) ────────────
    (r"^(.+?) Asian Handicap ([+\-−][\d.]+)$", r"\1 Handicap Asiático \2"),
    (r"^(.+?) Draw No Bet$", r"\1 Empate Anula Aposta"),
    (r"^(.+?) or Draw \(1X\)$", r"\1 ou Empate (1X)"),
    (r"^Draw or (.+?) \(X2\)$", r"Empate ou \1 (X2)"),
    (r"^(.+?) or (.+?) \(12 — No Draw\)$", r"\1 ou \2 (12 — Sem Empate)"),
    (r"^(.+?) Win$", r"Vitória de \1"),
]

_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(p), r) for p, r in _RAW_PATTERNS
]


# ---------------------------------------------------------------------------
# 3. PHRASE DICTIONARY — literal multi-word fragments (longest first)
# ---------------------------------------------------------------------------

TEXT_TRANSLATIONS: dict[str, str] = {
    # ── structural tags (knowledge notes) ───────────────────────────────────
    "[GOLDEN RULE]": "[REGRA DE OURO]",
    "[RED FLAG]": "[ALERTA]",

    # ── raw snake_case category keys that leak into prose when a methodology_v1
    #    category has no display label in intelligence_engine._CATEGORY_LABELS
    #    (e.g. the confidence explanation's strongest/weakest contributions) ──
    "value_bet_detection": "Detecção de Aposta de Valor",
    "corners_pattern": "Padrão de Escanteios",
    "cards_pattern": "Padrão de Cartões",
    "referee_influence": "Influência da Arbitragem",
    "tactical_style": "Estilo Tático",
    "historical_learning": "Aprendizado Histórico",

    # ── methodology_v1 neutral-score reason ─────────────────────────────────
    "Insufficient resolved predictions for this market — score neutral.":
        "Previsões resolvidas insuficientes para este mercado — pontuação "
        "neutra.",
    "xG not available — scoring rates inferred from season standings only.":
        "sem dados de xG — as taxas de gols são inferidas apenas pela "
        "classificação da temporada.",

    # ── knowledge descriptions ──────────────────────────────────────────────
    # Knowledge notes (golden rules + relevant items) are translated in full by
    # knowledge_engine.to_notes() BEFORE truncation. Each key below is the
    # opening sentence(s) of a knowledge_db description — long enough to cover
    # the truncated window ([:120] golden / [:100] relevant) so the visible
    # prefix renders as natural PT.
    # golden_rules
    "This is Aurora's first and most important rule. Every bet placed must "
    "have positive expected value. Gut feeling, loyalty, and narrative do not "
    "create positive EV.":
        "Esta é a primeira e mais importante regra da Aurora. Toda aposta "
        "feita deve ter valor esperado positivo. Instinto, lealdade e "
        "narrativa não geram VE positivo.",
    "Aurora's confidence score measures data quality. Below 5.0 means Aurora "
    "is guessing. Guesses are not bets. No exceptions, no overrides.":
        "A pontuação de confiança da Aurora mede a qualidade dos dados. Abaixo "
        "de 5.0 significa que a Aurora está adivinhando. Palpites não são "
        "apostas. Sem exceções, sem substituições.",
    "The Aurora Evolution Engine suggests weight changes after every match. "
    "However, a single match result is statistically insignificant.":
        "O Aurora Evolution Engine sugere mudanças de peso após cada partida. "
        "No entanto, o resultado de uma única partida é estatisticamente "
        "insignificante.",
    "Capital preservation comes before profit. A 50% bankroll loss requires "
    "100% return to recover. A 20% bankroll loss requires 25% return to "
    "recover.":
        "A preservação do capital vem antes do lucro. Uma perda de 50% da "
        "banca exige 100% de retorno para recuperar. Uma perda de 20% da "
        "banca exige 25% de retorno para recuperar.",
    "Aurora always prioritises statistical evidence over match narratives. A "
    "compelling story about a team does not override what the numbers say.":
        "A Aurora sempre prioriza evidências estatísticas sobre narrativas de "
        "partidas. Uma história convincente sobre uma equipe não anula o que "
        "os números dizem.",
    # betting_rules
    "Only consider bets with EV > +5%. EV = (probability × decimal_odds) − 1. "
    "Bets with negative EV are mathematically losing bets over the long run, "
    "regardless of short-term results.":
        "Considere apenas apostas com VE > +5%. VE = (probabilidade × "
        "odds_decimais) − 1. Apostas com VE negativo são matematicamente "
        "perdedoras no longo prazo, independentemente dos resultados de curto "
        "prazo.",
    "Teams on a 4+ match winning streak continue to win in approximately 72% "
    "of cases.":
        "Equipes em uma sequência de 4+ vitórias continuam vencendo em "
        "aproximadamente 72% dos casos.",
    "Pre-match odds are most accurate 60–90 minutes before kickoff after "
    "lineups are confirmed.":
        "As odds pré-jogo são mais precisas 60–90 minutos antes do início, "
        "após a confirmação das escalações.",
    # bankroll_rules
    "Use 25% of full Kelly stake to reduce variance while preserving edge.":
        "Use 25% da stake Kelly completa para reduzir a variância preservando "
        "a vantagem.",
    "Stop betting after 3 consecutive losses and review methodology.":
        "Pare de apostar após 3 derrotas consecutivas e revise a metodologia.",
    "Total exposure per day must not exceed 15% of bankroll.":
        "A exposição total por dia não deve exceder 15% da banca.",
    # league_rules
    "The Premier League averages 10.1 corners per match.":
        "A Premier League tem média de 10.1 escanteios por partida.",
    "La Liga away teams score in only 52% of matches, the lowest among top 5 "
    "leagues.":
        "As equipes visitantes da La Liga marcam em apenas 52% das partidas, o "
        "menor índice entre as 5 grandes ligas.",
    "Serie A has the lowest average goals/match among top 5 leagues (2.48).":
        "A Serie A tem a menor média de gols por partida entre as 5 grandes "
        "ligas (2.48).",
    # live_rules
    "A red card changes the tactical shape of the match entirely.":
        "Um cartão vermelho muda completamente a forma tática da partida.",
    "Live match data becomes statistically reliable from minute 30 onwards.":
        "Os dados da partida ao vivo tornam-se estatisticamente confiáveis a "
        "partir do minuto 30.",
    "The current score creates momentum signals.":
        "O placar atual cria sinais de momentum.",
    # market_rules
    "BTTS Yes is reliable only when both teams have scored in 60%+ of recent "
    "matches.":
        "Ambas Marcam — Sim é confiável apenas quando ambas as equipes "
        "marcaram em 60%+ das partidas recentes.",
    "Corner markets depend on team tactical style, not just possession.":
        "Os mercados de escanteios dependem do estilo tático da equipe, não "
        "apenas da posse de bola.",
    "Asian Handicap bets are only +EV when there is a clear quality gap of 3+ "
    "goal levels.":
        "As apostas de Handicap Asiático só têm +VE quando há uma diferença "
        "clara de qualidade de 3+ níveis de gol.",
    # methodology
    "Goals in football follow a Poisson distribution.":
        "Os gols no futebol seguem uma distribuição de Poisson.",
    "Aurora uses three data tiers in priority order:":
        "A Aurora usa três camadas de dados em ordem de prioridade:",
    "Aurora confidence (1–10) measures data richness, NOT certainty.":
        "A confiança da Aurora (1–10) mede a riqueza dos dados, NÃO a certeza.",
    # pre_match_rules
    "Never bet on markets that depend on a specific player before lineups are "
    "confirmed.":
        "Nunca aposte em mercados que dependem de um jogador específico antes "
        "de as escalações serem confirmadas.",
    "Teams playing 3+ matches in 7 days frequently rotate.":
        "Equipes que jogam 3+ partidas em 7 dias frequentemente fazem "
        "rodízio.",
    "Heavy rain reduces passing accuracy and increases long balls.":
        "Chuva forte reduz a precisão dos passes e aumenta os lançamentos "
        "longos.",
    # psychology
    "Bettors consistently over-weight recent results vs season averages.":
        "Os apostadores supervalorizam consistentemente os resultados recentes "
        "em relação às médias da temporada.",
    "The public systematically over-bets favorites, compressing their odds by "
    "5–12%.":
        "O público sistematicamente aposta demais nos favoritos, comprimindo "
        "suas odds em 5–12%.",
    "Increasing stake sizes to recover losses is the most common cause of "
    "bankroll ruin.":
        "Aumentar o tamanho das stakes para recuperar perdas é a causa mais "
        "comum de ruína da banca.",
    # referee_rules
    "Some referees average 5+ cards per match and consistently affect card "
    "markets.":
        "Alguns árbitros têm média de 5+ cartões por partida e afetam "
        "consistentemente os mercados de cartões.",
    "Penalty award rates vary by 3x between different referees in the same "
    "league.":
        "As taxas de pênaltis marcados variam 3x entre diferentes árbitros na "
        "mesma liga.",
    # risk_management
    "When bankroll drawdown reaches 20%, enter protection mode: halve all "
    "stake sizes and only bet on High Confidence (≥7.0) recommendations.":
        "Quando o drawdown da banca atinge 20%, entre em modo de proteção: "
        "reduza pela metade todos os tamanhos de stake e aposte apenas em "
        "recomendações de Alta Confiança (≥7.0).",
    "Over 2.5 goals and BTTS Yes are positively correlated (r ≈ 0.72).":
        "Mais de 2.5 Gols e Ambas Marcam — Sim são positivamente "
        "correlacionados (r ≈ 0.72).",
    "Aurora never recommends markets with confidence score < 5.0/10.":
        "A Aurora nunca recomenda mercados com pontuação de confiança "
        "< 5.0/10.",
    # team_rules
    "Some teams are dramatically stronger at home than away.":
        "Algumas equipes são drasticamente mais fortes em casa do que fora.",
    "Some teams score 35%+ of their goals from set pieces.":
        "Algumas equipes marcam 35%+ dos seus gols em bolas paradas.",

    # ── risk-factor / data-gap lines ────────────────────────────────────────
    "**No xG data** — goal market probabilities are based on season-average "
    "goals per game rather than shot quality. All goal and BTTS estimates carry "
    "an additional 15–20% margin of uncertainty.":
        "**Sem dados de xG** — as probabilidades dos mercados de gols se baseiam "
        "na média de gols por jogo da temporada, e não na qualidade das "
        "finalizações. Todas as estimativas de gols e de ambas marcam carregam "
        "uma margem adicional de 15–20% de incerteza.",
    "**No standings data** — team strength cannot be calibrated against their "
    "league position. Aurora falls back to default league priors.":
        "**Sem dados de classificação** — a força das equipes não pode ser "
        "calibrada pela posição na liga. A Aurora recorre às referências padrão "
        "da liga.",
    "**Referee unassigned** — card and penalty markets cannot be calibrated to "
    "a specific official. Card market confidence is reduced.":
        "**Árbitro não definido** — os mercados de cartões e pênaltis não podem "
        "ser calibrados a um árbitro específico. A confiança do mercado de "
        "cartões é reduzida.",
    "**Risk Level: High** — even with a passing methodology score, the market "
    "risk level is elevated. Use smaller-than-normal stake sizes.":
        "**Nível de Risco: Alto** — mesmo com uma pontuação metodológica "
        "aprovada, o nível de risco do mercado está elevado. Use stakes menores "
        "que o normal.",
    "No critical risk flags identified. Standard model uncertainty applies to "
    "all predictions (football outcomes are inherently probabilistic — even "
    "80% probability bets lose 20% of the time).":
        "Nenhum alerta de risco crítico identificado. A incerteza padrão do "
        "modelo se aplica a todas as previsões (os resultados no futebol são "
        "inerentemente probabilísticos — mesmo apostas com 80% de probabilidade "
        "perdem 20% das vezes).",

    # ── positive/negative fallback lines ────────────────────────────────────
    "No category scores above 7.0 in this fixture — the overall opportunity is "
    "marginal across all dimensions.":
        "Nenhuma categoria pontua acima de 7.0 nesta partida — a oportunidade "
        "geral é marginal em todas as dimensões.",
    "All methodology categories score above 5.5 — there are no significant "
    "negative signals in this fixture.":
        "Todas as categorias metodológicas pontuam acima de 5.5 — não há sinais "
        "negativos significativos nesta partida.",

    # ── stake reasoning blocks ──────────────────────────────────────────────
    "**No stake recommended.** Aurora's methodology has not identified a market "
    "with positive expected value that passes all confidence and risk gates. "
    "Placing a bet in this fixture would be acting against the model's advice. "
    "Wait for richer data (live stats, confirmed lineups) before reconsidering.":
        "**Nenhuma stake recomendada.** A metodologia da Aurora não identificou "
        "um mercado com valor esperado positivo que passe por todos os filtros "
        "de confiança e risco. Apostar nesta partida seria agir contra a "
        "recomendação do modelo. Aguarde dados mais ricos (estatísticas ao "
        "vivo, escalações confirmadas) antes de reconsiderar.",
    "Reference stake sizes by bankroll:": "Stakes de referência por banca:",
    "**Never exceed 5% of your bankroll on a single bet, regardless of "
    "confidence.**":
        "**Nunca exceda 5% da sua banca em uma única aposta, independentemente "
        "da confiança.**",
    "This sizing applies Aurora's quarter-Kelly discipline: full Kelly × 0.25, "
    "adjusted for confidence and risk, capped at 5% per bet.":
        "Este dimensionamento aplica a disciplina quarter-Kelly da Aurora: "
        "Kelly completo × 0.25, ajustado para confiança e risco, limitado a 5% "
        "por aposta.",

    # ── invalidation conditions ─────────────────────────────────────────────
    "**In-play goal early**: A goal in the first 20 minutes significantly "
    "changes the tactical shape of the match. All pre-match probability "
    "estimates should be treated as invalidated and the live analysis "
    "re-consulted.":
        "**Gol cedo durante o jogo**: Um gol nos primeiros 20 minutos muda "
        "significativamente a estrutura tática da partida. Todas as estimativas "
        "de probabilidade pré-jogo devem ser consideradas invalidadas e a "
        "análise ao vivo reconsultada.",
    "**Red card**: A red card completely reshapes the match. Aurora's current "
    "analysis does not account for a numerical disadvantage. If a red card "
    "occurs, discard this recommendation and run a live re-analysis.":
        "**Cartão vermelho**: Um cartão vermelho reformula completamente a "
        "partida. A análise atual da Aurora não considera desvantagem numérica. "
        "Se ocorrer um cartão vermelho, descarte esta recomendação e faça uma "
        "nova análise ao vivo.",
    "**xG data becomes available**: Once live expected-goals data is present, "
    "the Poisson model will produce materially different probability estimates. "
    "Re-run the analysis when xG data is populated.":
        "**Dados de xG ficam disponíveis**: Assim que os dados de gols esperados "
        "ao vivo estiverem presentes, o modelo de Poisson produzirá estimativas "
        "de probabilidade materialmente diferentes. Refaça a análise quando os "
        "dados de xG forem preenchidos.",
    "**Late odds movement (>15% shortening)**: If bookmaker odds shorten by "
    "more than 15% without public news explaining it, this may indicate inside "
    "information about team news or match conditions. Treat sharp late movement "
    "as a caution signal.":
        "**Movimentação tardia das odds (>15% de queda)**: Se as odds da casa "
        "caírem mais de 15% sem notícias públicas que expliquem, isso pode "
        "indicar informação privilegiada sobre notícias das equipes ou "
        "condições do jogo. Trate movimentos bruscos tardios como sinal de "
        "cautela.",

    # ── historical / memory fallback ────────────────────────────────────────
    "No historical match data found in Aurora's memory for these teams or "
    "league. Predictions are based solely on current-season data and league "
    "priors. Memory will populate as Aurora tracks more fixtures.":
        "Nenhum dado histórico de partidas encontrado na memória da Aurora para "
        "estas equipes ou liga. As previsões se baseiam apenas nos dados da "
        "temporada atual e nas referências da liga. A memória será preenchida à "
        "medida que a Aurora acompanhar mais partidas.",

    # ── methodology_v1 reason fragments (phrase level) ──────────────────────
    "No referee information available — influence cannot be assessed.":
        "Nenhuma informação de árbitro disponível — a influência não pode ser "
        "avaliada.",
    "No lineup data available — tactical style cannot be assessed.":
        "Nenhum dado de escalação disponível — o estilo tático não pode ser "
        "avaliado.",
    "no venue split available": "sem separação por mando de campo",
    "no standings data, using prior": "sem dados de classificação, usando referência",
    "combined strength": "força combinada",
    "home record": "aproveitamento em casa",
    "away record": "aproveitamento fora",
    "overall win rate": "taxa de vitória geral",
    "home advantage": "vantagem de jogar em casa",
    "away performance": "desempenho fora de casa",
    "strong home fortress": "forte fortaleza em casa",
    "weak home fortress": "fraca fortaleza em casa",
    "solid away form": "forma sólida fora de casa",
    "poor away form": "forma ruim fora de casa",
    "peak motivation expected": "motivação máxima esperada",
    "elevated motivation": "motivação elevada",
    "standard motivation level": "nível de motivação padrão",
    "High-stakes fixture": "Partida de alta importância",
    "Important league phase": "Fase importante da liga",
    "Regular season match": "Partida de temporada regular",
    "complete momentum picture available": "quadro de momentum completo disponível",
    "Final score": "Placar final",
    "Live momentum": "Momentum ao vivo",
    "recent goal(s)": "gol(s) recente(s)",
    "lead team at": "equipe líder em",
    "high attacking intent": "alta intenção ofensiva",
    "low attacking intent": "baixa intenção ofensiva",
    "healthy bankroll profile": "perfil de banca saudável",
    "acceptable bankroll exposure": "exposição de banca aceitável",
    "Reduced stakes advised": "stakes reduzidas recomendadas",
    "high overall portfolio risk": "alto risco geral da carteira",
    "portfolio exposure critical": "exposição da carteira crítica",
    "strong historical performance": "forte desempenho histórico",
    "poor track record, caution flagged": "histórico ruim, cautela sinalizada",
    "acceptable but not strong": "aceitável, mas não forte",
    "no value edge detected": "nenhuma vantagem de valor detectada",
    "probability qualifies but confidence": "probabilidade qualifica, mas confiança",
    "below": "abaixo de",
    "value threshold": "limite de valor",

    # ── risk-phrase fragments (_risk_phrase) ────────────────────────────────
    "well-controlled risk profile": "perfil de risco bem controlado",
    "moderate risk level": "nível de risco moderado",
    "elevated risk": "risco elevado",

    # ── red-flag trigger suffixes (knowledge_engine) ────────────────────────
    "— no xG data available": "— sem dados de xG disponíveis",
    "— referee unassigned": "— árbitro não definido",
    "— methodology score": "— pontuação metodológica",

    # ── knowledge rule TITLES (knowledge_db) ────────────────────────────────
    "Poisson Model Foundation": "Fundamento do Modelo de Poisson",
    "Three-Layer Data Hierarchy": "Hierarquia de Dados em Três Camadas",
    "Confidence Score Interpretation": "Interpretação da Pontuação de Confiança",
    "Positive Expected Value Requirement": "Exigência de Valor Esperado Positivo",
    "Form Streak Continuation Rule": "Regra de Continuação de Sequência de Forma",
    "Market Timing Rule": "Regra de Momento do Mercado",
    "Kelly Criterion — Quarter Kelly": "Critério de Kelly — Quarter Kelly",
    "Consecutive Loss Stop Rule": "Regra de Parada por Derrotas Consecutivas",
    "Maximum Daily Exposure": "Exposição Diária Máxima",
    "BTTS — Both Teams Must Have Attacked": "Ambas Marcam — As Duas Equipes Devem Ter Atacado",
    "Corners — Tactical Pattern Over Volume": "Escanteios — Padrão Tático Acima do Volume",
    "Asian Handicap — Only Bet When >3 Goal Class Difference":
        "Handicap Asiático — Apostar Apenas com Diferença de Classe Superior a 3 Gols",
    "Minutes 30–60 Reliability Window": "Janela de Confiabilidade dos Minutos 30–60",
    "Red Card — Complete Market Recalibration": "Cartão Vermelho — Recalibração Completa do Mercado",
    "Score State Momentum Rule": "Regra de Momentum pelo Placar",
    "Lineup Confirmation Is Mandatory": "Confirmação da Escalação é Obrigatória",
    "Fixture Congestion — Rotation Risk": "Congestionamento de Jogos — Risco de Rodízio",
    "Weather Impact on Physical Markets": "Impacto do Clima nos Mercados Físicos",
    "High-Card Referee Profile": "Perfil de Árbitro de Muitos Cartões",
    "Penalty Rate by Referee": "Taxa de Pênaltis por Árbitro",
    "Premier League Corners Baseline": "Referência de Escanteios da Premier League",
    "La Liga — Low Scoring Away Matches": "La Liga — Jogos Fora de Casa com Poucos Gols",
    "Serie A — Defensive Structure": "Serie A — Estrutura Defensiva",
    "Home Fortress Teams": "Equipes Fortaleza em Casa",
    "Set Piece Dependent Teams": "Equipes Dependentes de Bola Parada",
    "Recency Bias — Don't Over-Weight Last 3 Results":
        "Viés de Recência — Não Supervalorize os Últimos 3 Resultados",
    "Favourite Bias — Public Over-Bets Big Teams":
        "Viés de Favorito — O Público Aposta Demais nas Grandes Equipes",
    "Sunk Cost — Do Not Chase Losses": "Custo Afundado — Não Persiga Prejuízos",
    "Drawdown Stop-Loss": "Stop-Loss de Drawdown",
    "Market Correlation Risk": "Risco de Correlação de Mercado",
    "Minimum Confidence Gate": "Filtro de Confiança Mínima",
    "No xG Data Available": "Sem Dados de xG Disponíveis",
    "New Manager Effect — First 3 Matches": "Efeito de Novo Técnico — Primeiras 3 Partidas",
    "Low Methodology Score — Blocked Recommendation":
        "Pontuação Metodológica Baixa — Recomendação Bloqueada",
    "Match Postponement or Rearrangement Risk": "Risco de Adiamento ou Remarcação da Partida",
    "Never Bet Without Positive Expected Value": "Nunca Aposte Sem Valor Esperado Positivo",
    "Never Bet When Confidence Is Below 5.0": "Nunca Aposte Quando a Confiança Está Abaixo de 5.0",
    "Never Change Methodology Based on a Single Match":
        "Nunca Mude a Metodologia com Base em uma Única Partida",
    "Protect the Bankroll Above All Else": "Proteja a Banca Acima de Tudo",
    "Data Before Narrative": "Dados Antes da Narrativa",

    # ── confidence-explanation fragments ────────────────────────────────────
    "**Data availability:**": "**Disponibilidade de dados:**",
    "**Methodology score:**": "**Pontuação metodológica:**",
    "xG data ✗ (using goals-per-game fallback)":
        "dados de xG ✗ (usando média de gols por jogo)",
    "standings data ✗ (using league priors)":
        "dados de classificação ✗ (usando referências da liga)",
    "referee unassigned ✗": "árbitro não definido ✗",
    "live expected-goals (xG) data ✓": "dados de gols esperados (xG) ao vivo ✓",
    "league standings ✓": "classificação da liga ✓",
    "referee profile ✓": "perfil do árbitro ✓",

    # ── invalidation: red card + venue/weather (no interpolation) ────────────
    "**Red card**: A red card completely reshapes the match. Aurora's current "
    "analysis does not account for a numerical disadvantage. If a red card "
    "occurs, discard this recommendation and run a live re-analysis.":
        "**Cartão vermelho**: Um cartão vermelho reformula completamente a "
        "partida. A análise atual da Aurora não considera desvantagem numérica. "
        "Se ocorrer um cartão vermelho, descarte esta recomendação e faça uma "
        "nova análise ao vivo.",
    "**Venue or weather change**: A neutral venue removes the home advantage "
    "component entirely. Heavy rain (>5mm/h) or wind above 30 mph can shift "
    "corner and goal market baselines by 5–20%.":
        "**Mudança de local ou clima**: Um estádio neutro remove completamente "
        "o componente de vantagem de jogar em casa. Chuva forte (>5mm/h) ou "
        "vento acima de 30 mph podem alterar as referências dos mercados de "
        "escanteios e gols em 5–20%.",

    # ── decision_center rationale fragments ─────────────────────────────────
    "BTTS No — at least one team fails to score":
        "Ambas Marcam — Não — pelo menos uma equipe não marca",
    "Combined xG": "xG combinado",
    "G/game": "G/jogo",
    "— higher threshold than 8.5 line": "— limite superior à linha de 8.5",
    "— lower threshold": "— limite inferior",

    # ── confidence / score adjective parentheticals ─────────────────────────
    "(exceptional)": "(excepcional)",
    "(strong)": "(forte)",
    "(solid)": "(sólida)",
    "(moderate)": "(moderada)",
    "(limited)": "(limitada)",
    "(low)": "(baixa)",
    "(weak)": "(fraca)",
    "(poor)": "(ruim)",
    "(excellent)": "(excelente)",
    "(good)": "(boa)",
    "(adequate)": "(adequada)",

    # ── connectors / misc ───────────────────────────────────────────────────
    " and ": " e ",
    "team news": "notícias das equipes",

    # ── data-source label ───────────────────────────────────────────────────
    "Expected Goals (xG)": "Gols Esperados (xG)",
}


# ---------------------------------------------------------------------------
# 4. WORD DICTIONARY — English-only words safe for global replacement
# ---------------------------------------------------------------------------
# These never collide with Portuguese, so a whole-word replace is safe even
# when the translator runs over already-Portuguese text.

WORD_TRANSLATIONS: dict[str, str] = {
    "goals": "gols",
    "goal": "gol",
    "corners": "escanteios",
    "corner": "escanteio",
    "cards": "cartões",
    "card": "cartão",
    "fouls": "faltas",
    "foul": "falta",
    "wins": "vitórias",
    "losses": "derrotas",
    "pending": "pendentes",
    "predictions": "previsões",
    "prediction": "previsão",
    "accuracy": "precisão",
    "logged": "registradas",
    "markets": "mercados",
    "market": "mercado",
    "threshold": "limite",
    "baseline": "referência",
    "available": "disponível",
    "unavailable": "indisponível",
    "referee": "árbitro",
    "lineup": "escalação",
    "standings": "classificação",
    "gate": "filtro",
    "confidence": "confiança",
    "strength": "força",
    # confidence / score adjectives (English-only in this context)
    "exceptional": "excepcional",
    "limited": "limitada",
    "moderate": "moderada",
    "excellent": "excelente",
    "strong": "forte",
    "solid": "sólida",
}

# Embedded labels — market + category DISPLAY names that appear inside prose
# (e.g. "**Corners Pattern** scores only..."). We only take keys that are not
# all-lowercase, so snake_case category keys and ambiguous single lowercase
# words never trigger here. Sorted longest-first for correct overlap handling.
_EMBEDDED_LABELS: dict[str, str] = {
    **MARKET_TRANSLATIONS,
    **{k: v for k, v in CATEGORY_TRANSLATIONS.items() if not k.islower()},
}
_EMBEDDED_SORTED: list[tuple[str, str]] = sorted(
    _EMBEDDED_LABELS.items(), key=lambda kv: -len(kv[0])
)

# Pre-sort by length (desc) so longer fragments win over shorter overlaps.
_PHRASES_SORTED: list[tuple[str, str]] = sorted(
    TEXT_TRANSLATIONS.items(), key=lambda kv: -len(kv[0])
)
_WORDS_SORTED: list[tuple[str, str]] = sorted(
    WORD_TRANSLATIONS.items(), key=lambda kv: -len(kv[0])
)


# ---------------------------------------------------------------------------
# 5. PUBLIC FUNCTIONS
# ---------------------------------------------------------------------------


def _match_case(src: str, dst: str) -> str:
    """Preserve simple capitalization from the matched source token."""
    if src.isupper():
        return dst.upper()
    if src[:1].isupper():
        return dst[:1].upper() + dst[1:]
    return dst


def translate_label(label: Any) -> Any:
    """Translate a market / generic label. Unknown labels pass through prose."""
    if not isinstance(label, str) or not label.strip():
        return label
    if label in MARKET_TRANSLATIONS:
        return MARKET_TRANSLATIONS[label]
    if label in CATEGORY_TRANSLATIONS:
        return CATEGORY_TRANSLATIONS[label]
    if label in RISK_TRANSLATIONS:
        return RISK_TRANSLATIONS[label]
    if label in CONFIDENCE_TRANSLATIONS:
        return CONFIDENCE_TRANSLATIONS[label]
    # Market names carry interpolated team names → fall through to prose pass.
    return translate_text(label)


def translate_category(cat: Any) -> Any:
    """Translate a knowledge / methodology category key or display name."""
    if not isinstance(cat, str) or not cat.strip():
        return cat
    if cat in CATEGORY_TRANSLATIONS:
        return CATEGORY_TRANSLATIONS[cat]
    return CATEGORY_TRANSLATIONS.get(cat.strip().lower(), cat)


def translate_text(text: Any) -> Any:
    """Translate free-form prose to PT — patterns, then phrases, then words."""
    if not isinstance(text, str) or not text.strip():
        return text

    out = text

    # Pass 1 — templated sentence frames (numbers/names preserved).
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)

    # Pass 2 — literal multi-word phrases (longest first, case-insensitive).
    # Runs before the embedded-label pass so full-sentence reason strings
    # (which use lowercase category names) match before those names are
    # individually replaced.
    for en, pt in _PHRASES_SORTED:
        if en.lower() in out.lower():
            out = re.sub(re.escape(en), lambda _m, _pt=pt: _pt, out,
                         flags=re.IGNORECASE)

    # Pass 3 — embedded market / category DISPLAY labels inside prose
    # (e.g. "**Corners Pattern** scores only 3.0/10 ..."). CASE-SENSITIVE:
    # category labels/tags always appear Title/UPPER case at their source, so
    # this never mangles lowercase words (e.g. "methodology") in reason prose.
    for en, pt in _EMBEDDED_SORTED:
        out = re.sub(rf"\b{re.escape(en)}\b", lambda _m, _pt=pt: _pt, out)

    # Pass 4 — standalone English-only words.
    for en, pt in _WORDS_SORTED:
        out = re.sub(
            rf"\b{re.escape(en)}\b",
            lambda m, _pt=pt: _match_case(m.group(0), _pt),
            out,
            flags=re.IGNORECASE,
        )

    return out


def _translate_str_list(items: Any) -> Any:
    if not isinstance(items, list):
        return items
    return [translate_text(x) if isinstance(x, str) else x for x in items]


def translate_report(payload: dict) -> dict:
    """
    Translate all user-facing string fields of a copilot payload to PT.

    Numbers, scores, probabilities, EV, odds, and all structural/numeric
    fields are left completely untouched. Unknown fields pass through.
    """
    if not isinstance(payload, dict):
        return payload

    p = payload

    # ── top-level prose ──────────────────────────────────────────────────
    if isinstance(p.get("executive_summary"), str):
        p["executive_summary"] = translate_text(p["executive_summary"])
    if isinstance(p.get("final_recommendation"), str):
        p["final_recommendation"] = translate_text(p["final_recommendation"])

    # ── best_markets ─────────────────────────────────────────────────────
    for mkt in p.get("best_markets", []) or []:
        if not isinstance(mkt, dict):
            continue
        for key in ("market", "market_name", "label"):
            if isinstance(mkt.get(key), str):
                mkt[key] = translate_label(mkt[key])
        if isinstance(mkt.get("risk"), str):
            mkt["risk"] = RISK_TRANSLATIONS.get(mkt["risk"], mkt["risk"])
        for key in ("rationale", "explanation"):
            if isinstance(mkt.get(key), str):
                mkt[key] = translate_text(mkt[key])

    # ── confidence ───────────────────────────────────────────────────────
    conf = p.get("confidence")
    if isinstance(conf, dict):
        if isinstance(conf.get("label"), str):
            conf["label"] = CONFIDENCE_TRANSLATIONS.get(
                conf["label"], conf["label"]
            )
        if isinstance(conf.get("explanation"), str):
            conf["explanation"] = translate_text(conf["explanation"])
        conf["data_sources"] = _translate_str_list(conf.get("data_sources"))

    # ── risk ─────────────────────────────────────────────────────────────
    risk = p.get("risk")
    if isinstance(risk, dict):
        if isinstance(risk.get("level"), str):
            risk["level"] = RISK_TRANSLATIONS.get(risk["level"], risk["level"])
        risk["flags"] = _translate_str_list(risk.get("flags"))
        risk["invalidation_conditions"] = _translate_str_list(
            risk.get("invalidation_conditions")
        )

    # ── bankroll ─────────────────────────────────────────────────────────
    bank = p.get("bankroll_recommendation")
    if isinstance(bank, dict) and isinstance(bank.get("reasoning"), str):
        bank["reasoning"] = translate_text(bank["reasoning"])

    # ── factor / reference / knowledge lists ─────────────────────────────
    for key in (
        "positive_factors",
        "negative_factors",
        "historical_references",
        "knowledge_notes",
    ):
        if key in p:
            p[key] = _translate_str_list(p.get(key))

    return p
