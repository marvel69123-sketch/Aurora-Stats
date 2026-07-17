"""
Aurora v4.5.2+ — Natural Conversation Intents (calendar, team opinion, capabilities).

Additive short-circuit layer. Fail-open.
Does NOT edit State / Reasoner / CIL / CRL / Resolver / Engines.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Brasileirão Série A — API-Football league id
BRASILEIRAO_LEAGUE_ID = 71
_BR_TZ = timezone(timedelta(hours=-3))

_TEAM_BLURBS: dict[str, str] = {
    "Botafogo": (
        "Olha… o Botafogo é daqueles times que eu gosto de acompanhar com atenção, "
        "não só pela tabela. Quando encontra identidade ofensiva e joga com coragem, "
        "parece um time que força o adversário a se adaptar o tempo todo — pressão, "
        "transição, ritmo alto.\n\n"
        "Ao mesmo tempo, é um clube de fases bem marcadas: numa semana transmite "
        "confiança, na outra a leitura muda e a conversa da torcida muda junto. "
        "Isso não é demérito; é personalidade.\n\n"
        "Se eu fosse resumir numa frase: o Fogão rende papo bom — de jogo, de momento "
        "e de expectativa — sem precisar virar tip cego."
    ),
    "Bahia": (
        "O Bahia tem um charme próprio. Tem fases em que aparece com intensidade, "
        "transição afiada e uma cara de time que quer impor o jogo; em outras, o ritmo "
        "fica mais truncado e a partida pede paciência.\n\n"
        "Eu gosto de olhar o momento do elenco e se o time sustenta pressão nos 90 "
        "minutos — porque aí a conversa deixa de ser só “ganhou/perdeu” e vira leitura "
        "de identidade.\n\n"
        "É um clube que conversa bem: tem história, tem torcida e tem nuance. "
        "Não trato como número frio."
    ),
    "Flamengo": (
        "O Flamengo quase sempre chega com expectativa alta e elenco profundo — "
        "e isso muda a conversa antes mesmo do apito. Quando encaixa ritmo e volume, "
        "fica pesado para qualquer adversário; quando trava, a frustração aparece "
        "rápido, justamente porque a barra é outra.\n\n"
        "Eu olharia menos o hype e mais o jogo: consegue sustentar pressão? O meio "
        "segura o ritmo? O adversário acha espaço nas costas?\n\n"
        "É daqueles times em que a conversa nunca fica fria — e por isso merece "
        "leitura com calma, não só narrativa de arquibancada."
    ),
    "Palmeiras": (
        "O Palmeiras me passa organização e consistência. Mesmo em noites menos "
        "brilhosas, costuma ter um plano — e isso, em futebol brasileiro, já é "
        "uma assinatura forte.\n\n"
        "Eu olharia o equilíbrio entre controle e criação: dominar não basta se não "
        "vira chance clara. Quando esse equilíbrio aparece, o time parece maduro; "
        "quando falta, a partida fica mais aberta do que a fama sugere.\n\n"
        "É um clube que pede nuance na conversa — não rótulo pronto."
    ),
    "Santos": (
        "O Santos é um clube de fases bem distintas — e isso faz parte do fascínio. "
        "Dependendo do momento, muda o humor da torcida, o jeito de jogar e até o "
        "peso emocional de cada jogo.\n\n"
        "Eu evitaria cravar sem olhar o confronto do dia: o mesmo Santos pode "
        "parecer ousado numa semana e mais contido na outra.\n\n"
        "Em conversa, eu separaria romance da camisa da leitura do momento. "
        "Os dois importam — só não podem se misturar sem filtro."
    ),
    "Corinthians": (
        "O Corinthians muitas vezes joga no detalhe e no clima da temporada. "
        "Tem jogos em que a narrativa pesa tanto quanto o placar — e quem acompanha "
        "sabe que isso não é exagero.\n\n"
        "Eu gosto de separar paixão de leitura fria: a torcida puxa emoção, mas o "
        "jogo ainda pede ritmo, transição e clareza no terço final.\n\n"
        "É um time que rende conversa longa — justamente porque raramente é só "
        "estatística."
    ),
    "Sao Paulo": (
        "O São Paulo tende a ter trechos de posse e construção. A pergunta que eu "
        "faço é quase sempre a mesma: isso vira chance clara ou só domínio estéril?\n\n"
        "Quando a criação acompanha o controle, o time fica elegante e perigoso; "
        "quando não, a partida pede paciência — e a conversa fica mais técnica do "
        "que apaixonada.\n\n"
        "Em resumo: é um clube que pede nuance. Eu conversaria sobre momento e "
        "estilo antes de qualquer conclusão rígida."
    ),
}


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _soft_payload(reply: str, *, intent: str, entities: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from src.conversation.message_intelligence import build_conversational_payload

        payload = build_conversational_payload(reply, {})
    except Exception:
        payload = {
            "intent": intent,
            "entities": {},
            "best_markets": [],
            "match_card": None,
            "executive_summary": reply,
            "final_recommendation": reply,
            "confidence": {
                "score": 0.0,
                "label": "insufficient",
                "explanation": "",
                "data_sources": [],
            },
            "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
            "bankroll_recommendation": {
                "recommended_stake_pct": 0.0,
                "method": "quarter-Kelly",
                "examples": {},
                "no_bet": True,
                "reasoning": "",
            },
            "positive_factors": [],
            "negative_factors": [],
            "historical_references": [],
            "knowledge_notes": [],
            "brain": {},
        }
    payload["intent"] = intent
    ents = dict(payload.get("entities") or {})
    ents.update(entities or {})
    ents["show_header"] = False
    ents["has_analysis"] = False
    ents["natural_conversation"] = True
    payload["entities"] = ents
    payload["best_markets"] = []
    payload["match_card"] = None
    meta = dict(payload.get("response_metadata") or {})
    meta.update(
        {
            "mode": "natural_conversation",
            "source": "conversation.natural_conversation",
            "show_header": False,
            "has_analysis": False,
            "crl_mode": "QUICK_REPLY",
        }
    )
    payload["response_metadata"] = meta
    return payload


def detect_natural_intent(message: str) -> dict[str, Any] | None:
    """
    Return {kind, ...} or None.
    kinds: calendar_today | calendar_tomorrow | calendar_round |
           had_games_today | team_opinion | capabilities | hobbies
    """
    folded = _fold(message)
    if not folded:
        return None

    # Capabilities / what can you do (incl. "consegue")
    if re.search(
        r"\b("
        r"o\s+que\s+(?:voce\s+)?(?:consegue|pode|sabe)\s+fazer|"
        r"o\s+que\s+voce\s+faz|"
        r"quais\s+(?:suas\s+)?(?:funcoes|recursos|capacidades)|"
        r"no\s+que\s+(?:voce\s+)?pode\s+ajudar|"
        r"what\s+can\s+you\s+do"
        r")\b",
        folded,
    ):
        return {"kind": "capabilities"}

    # Hobbies / what do you like
    if re.search(
        r"\b(o\s+que\s+(?:voce\s+)?gosta\s+de\s+fazer|do\s+que\s+voce\s+gosta|"
        r"quais\s+seus\s+hobbies|voce\s+gosta\s+de\s+futebol)\b",
        folded,
    ):
        return {"kind": "hobbies"}

    # Calendar — today / tomorrow / round / had games
    if re.search(
        r"\b("
        r"hoje\s+teve\s+jogo|teve\s+jogo\s+hoje|teve\s+jogos\s+hoje|"
        r"jogos?\s+de\s+hoje|partidas?\s+de\s+hoje|quais\s+jogos\s+hoje|"
        r"jogos?\s+hoje|agenda\s+de\s+hoje"
        r")\b",
        folded,
    ):
        # "teve" → finished-leaning; still list today's slate
        kind = "had_games_today" if "teve" in folded else "calendar_today"
        return {"kind": kind, "date_offset": 0, "brasileirao": "brasileir" in folded}

    if re.search(
        r"\b("
        r"jogos?\s+(?:de\s+)?amanha|partidas?\s+(?:de\s+)?amanha|"
        r"quais\s+jogos\s+amanha|agenda\s+(?:de\s+)?amanha|"
        r"jogos?\s+do\s+brasileir(?:ao)?\s+amanha|"
        r"brasileir(?:ao)?\s+amanha"
        r")\b",
        folded,
    ):
        return {
            "kind": "calendar_tomorrow",
            "date_offset": 1,
            "brasileirao": "brasileir" in folded,
        }

    if re.search(r"\b(proxima\s+rodada|rodada\s+de\s+amanha|calendario)\b", folded):
        return {"kind": "calendar_round", "date_offset": 1, "brasileirao": True}

    # Generic "quais jogos amanha" already covered. "quais jogos" alone → tomorrow-ish ask
    if re.search(r"\bquais\s+jogos\b", folded) and re.search(r"\bamanha\b", folded):
        return {
            "kind": "calendar_tomorrow",
            "date_offset": 1,
            "brasileirao": "brasileir" in folded,
        }

    # Historical Copa opinion
    if re.search(
        r"\b(o\s+que\s+achou\s+da\s+copa|copa\s+(?:do\s+mundo\s+)?(?:de\s+)?20\d{2}|"
        r"mundial\s+de\s+20\d{2})\b",
        folded,
    ):
        return {"kind": "historical_copa"}

    # Team opinion / football chat — single club, no "x"
    if not re.search(r"\b\w+\s+[xX]\s+\w+\b", message or ""):
        if re.search(
            r"\b(o\s+que\s+(?:voce\s+)?acha\s+d[oe]|oq\s+acha\s+d[oe]|"
            r"o\s+que\s+achou\s+d[oe]|como\s+(?:esta|vai)\s+o|"
            r"e\s+ai\s+(?:do|de)|fala\s+(?:um\s+pouco\s+)?(?:do|sobre)\s+|"
            r"opiniao\s+sobre|momento\s+(?:atual\s+)?d[oe])\b",
            folded,
        ):
            team = _extract_one_team(folded)
            if team:
                return {
                    "kind": "team_opinion",
                    "team": team,
                    "moment": bool(
                        re.search(r"\b(agora|agr|momento|atualmente)\b", folded)
                    ),
                }
        # "o que acha/achou do bahia"
        m = re.search(
            r"\b(?:acha|achas|achando|achou)\s+d[oe]\s+([a-z0-9][a-z0-9\s-]{2,30})\b",
            folded,
        )
        if m:
            team = _extract_one_team(m.group(1)) or _title_team(m.group(1))
            if team:
                return {
                    "kind": "team_opinion",
                    "team": team,
                    "moment": bool(
                        re.search(r"\b(agora|agr|momento|atualmente)\b", folded)
                    ),
                }

    return None


def _title_team(raw: str) -> str | None:
    t = (raw or "").strip(" ?!.")
    if len(t) < 3:
        return None
    return t[:1].upper() + t[1:]


def _extract_one_team(folded: str) -> str | None:
    try:
        from src.conversation.conversational_understanding import _TEAM_NAMES, _extract_teams

        teams = _extract_teams(folded)
        if len(teams) == 1:
            return teams[0]
        # direct key search
        for key in sorted(_TEAM_NAMES.keys(), key=len, reverse=True):
            if re.search(rf"\b{re.escape(key)}\b", folded):
                return _TEAM_NAMES[key]
    except Exception:
        pass
    return None


def _target_date(offset_days: int) -> str:
    # Brazil-leaning calendar day (UTC-3 approx)
    now = datetime.now(_BR_TZ)
    d = now.date() + timedelta(days=int(offset_days))
    return d.isoformat()


def _kick_local(iso_date: str) -> tuple[str, str]:
    """Return (HH:MM local BR, sort key) from API ISO datetime."""
    raw = (iso_date or "").strip()
    if not raw:
        return ("—:—", "99:99")
    try:
        # API often returns ...Z or offset
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone(_BR_TZ)
        hhmm = local.strftime("%H:%M")
        return (hhmm, hhmm)
    except Exception:
        # Fallback: slice "2026-07-12T19:00:00"
        m = re.search(r"T(\d{2}:\d{2})", raw)
        if m:
            return (m.group(1), m.group(1))
        return ("—:—", "99:99")


def _clock_emoji(hhmm: str) -> str:
    try:
        h = int(hhmm.split(":")[0])
    except Exception:
        return "🕖"
    if h < 12:
        return "🕘"
    if h < 16:
        return "🕒"
    if h < 19:
        return "🕕"
    if h < 21:
        return "🕖"
    return "🕘"


def _is_brasileirao_fixture(fx: dict[str, Any]) -> bool:
    try:
        league = fx.get("league") or {}
        lid = league.get("id")
        if lid == BRASILEIRAO_LEAGUE_ID:
            return True
        name = _fold(str(league.get("name") or ""))
        country = _fold(str(league.get("country") or ""))
        if "brazil" in country or "brasil" in country:
            if "serie a" in name or "brasileir" in name:
                return True
        # Reject known foreign noise explicitly
        if any(
            x in name
            for x in ("nwsl", "mls", "boliv", "liga mx", "premier league", "la liga")
        ):
            return False
    except Exception:
        return False
    return False


def _filter_brasileirao_only(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [fx for fx in items if _is_brasileirao_fixture(fx)]


def _format_agenda_blocks(
    items: list[dict[str, Any]],
    *,
    title: str,
    limit: int = 14,
) -> str:
    """
    Card-like agenda:

    ⚽ Jogos do Brasileirão amanhã

    🕖 19:00
    Bahia x Flamengo
    """
    rows: list[tuple[str, str, str]] = []
    for fx in items[:limit]:
        try:
            teams = fx.get("teams") or {}
            home = ((teams.get("home") or {}).get("name")) or "?"
            away = ((teams.get("away") or {}).get("name")) or "?"
            kick_raw = ((fx.get("fixture") or {}).get("date") or "")
            hhmm, sort_k = _kick_local(kick_raw)
            rows.append((sort_k, hhmm, f"{home} x {away}"))
        except Exception:
            continue
    rows.sort(key=lambda r: r[0])
    if not rows:
        return title
    blocks = [title, ""]
    for _, hhmm, match in rows:
        blocks.append(f"{_clock_emoji(hhmm)} {hhmm}")
        blocks.append(match)
        blocks.append("")
    return "\n".join(blocks).rstrip()


def _format_fixture_lines(items: list[dict[str, Any]], *, limit: int = 12) -> list[str]:
    """Legacy one-liners — kept for tests; agenda uses _format_agenda_blocks."""
    lines: list[str] = []
    for fx in items[:limit]:
        try:
            teams = fx.get("teams") or {}
            home = ((teams.get("home") or {}).get("name")) or "?"
            away = ((teams.get("away") or {}).get("name")) or "?"
            hhmm, _ = _kick_local(((fx.get("fixture") or {}).get("date") or ""))
            lines.append(f"{_clock_emoji(hhmm)} {hhmm}\n{home} x {away}")
        except Exception:
            continue
    return lines


async def _fetch_fixtures_for_date(
    date_iso: str,
    *,
    league_id: int | None = None,
) -> list[dict[str, Any]]:
    try:
        from src.client import api_football_get

        params: dict[str, Any] = {"date": date_iso}
        if league_id:
            params["league"] = league_id
            # season guess: year of date
            params["season"] = int(date_iso[:4])
        data = await api_football_get("/fixtures", params)
        resp = data.get("response") or []
        return list(resp) if isinstance(resp, list) else []
    except Exception as exc:
        logger.warning("natural_conversation fixtures fetch fail-open: %s", exc)
        return []


def build_team_opinion_reply(team: str) -> str:
    blurb = _TEAM_BLURBS.get(team) or (
        f"Sobre o {team}, eu evitaria cravar sem um confronto específico na mesa. "
        f"Em geral, eu olharia o momento recente, o clima do elenco, o estilo de jogo "
        f"e o adversário do dia — como numa conversa de quem acompanha o campeonato "
        f"de verdade, não como um relatório automático.\n\n"
        f"Times mudam de cara em poucas semanas; por isso eu prefiro opinião com "
        f"contexto a veredito engessado."
    )
    return (
        f"{blurb}\n\n"
        f"Se quiser, a gente pega um jogo do {team} e aprofunda — pode ser só papo "
        f"de futebol ou uma leitura mais detalhada do confronto."
    )


def build_capabilities_reply() -> str:
    return (
        "Aqui está o que eu consigo fazer por você:\n\n"
        "⚽ **Análises de partidas** — diga um confronto (ex.: Bahia x Chapecoense)\n"
        "🔴 **Jogos ao vivo** — peço oportunidades em andamento\n"
        "📅 **Agenda** — pergunte jogos de hoje ou de amanhã\n"
        "💬 **Conversa de futebol** — opinião sobre times, sem forçar tip\n"
        "📊 **Banca / aprendizado** — quando você quiser revisar histórico\n\n"
        "Pode falar naturalmente — sem comando engessado."
    )


def build_hobbies_reply() -> str:
    return (
        "Eu gosto de conversar sobre futebol, ler o ritmo dos jogos e ajudar a pensar "
        "mercados com cautela — sem pressa de tip.\n\n"
        "Se quiser, a gente olha a agenda de hoje ou analisa um confronto."
    )


async def try_natural_conversation(
    message: str,
    ctx: dict[str, Any] | None = None,
    prefs: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Short-circuit payload or None. Fail-open → None.
    """
    try:
        detected = detect_natural_intent(message)
        if not detected:
            return None

        kind = detected["kind"]
        reply = ""
        intent = "conversation_assist"
        family = "casual"
        entities: dict[str, Any] = {"natural_kind": kind}

        if kind == "capabilities":
            reply = build_capabilities_reply()
            intent = "capabilities"
            family = "capabilities"
        elif kind == "hobbies":
            reply = build_hobbies_reply()
            intent = "small_talk"
            family = "casual"
        elif kind == "team_opinion":
            team = str(detected.get("team") or "esse time")
            reply = build_team_opinion_reply(team)
            # WEB alters reasoning (pre-draft weave)
            try:
                from src.conversation.web_intelligence import weave_web_into_draft

                reply, _ = weave_web_into_draft(reply, ctx, team=team)
            except Exception:
                pass
            intent = "conversation_assist"
            family = "team_opinion"
            entities["team"] = team
            entities["opinion_time"] = True
            if detected.get("moment"):
                entities["moment_now"] = True
        elif kind == "historical_copa":
            try:
                from src.conversation.intelligence_fallback import build_copa_opinion

                m = re.search(r"(20\d{2})", message or "")
                reply = build_copa_opinion(m.group(1) if m else "2026")
            except Exception:
                reply = (
                    "Sobre a Copa, eu penso em narrativa e momentos — "
                    "não só em placar. Quer aprofundar um jogo ou uma seleção?"
                )
            try:
                from src.conversation.web_intelligence import weave_web_into_draft

                reply, _ = weave_web_into_draft(reply, ctx, team="Copa do Mundo")
            except Exception:
                pass
            intent = "conversation_assist"
            family = "team_opinion"
            entities["opinion_time"] = True
            entities["historical_copa"] = True
        elif kind in {
            "calendar_today",
            "calendar_tomorrow",
            "calendar_round",
            "had_games_today",
        }:
            offset = int(detected.get("date_offset") or 0)
            date_iso = _target_date(offset)
            # Round / explicit Brasileirão → strict BR filter (no NWSL/MLS fallback)
            use_br = bool(detected.get("brasileirao")) or kind == "calendar_round"
            label = "hoje" if offset == 0 else "amanhã"

            if use_br:
                items = await _fetch_fixtures_for_date(
                    date_iso, league_id=BRASILEIRAO_LEAGUE_ID
                )
                # Secondary filter if API returns extras
                items = _filter_brasileirao_only(items) if items else []
                # Strict: do NOT open to world slate when user asked Brasileirão
                title = f"⚽ Jogos do Brasileirão {label}"
            else:
                # Default Brazilian product lean: try BR first, then open date
                items = await _fetch_fixtures_for_date(
                    date_iso, league_id=BRASILEIRAO_LEAGUE_ID
                )
                title = f"⚽ Jogos do Brasileirão {label}"
                if not items:
                    items = await _fetch_fixtures_for_date(date_iso, league_id=None)
                    title = f"⚽ Jogos de {label}"

            if kind == "had_games_today":
                title = f"⚽ Jogos de hoje" if not use_br else f"⚽ Jogos do Brasileirão hoje"

            body = _format_agenda_blocks(items, title=title)
            if items:
                reply = body + "\n\nQuer olhar algum desses comigo?"
            else:
                scope = "no Brasileirão" if use_br else "nessa data"
                reply = (
                    f"Não achei jogos {scope} para {label} agora.\n\n"
                    "Se quiser, me passa um confronto direto — "
                    "ex.: *Bahia x Flamengo* — que a gente conversa ou analisa."
                )
            intent = "conversation_assist"
            family = "calendar"
            entities["calendar_date"] = date_iso
            entities["fixture_count"] = len(items)
            entities["brasileirao_filter"] = use_br
            entities["agenda_formatted"] = True
        else:
            return None

        # Presence humanization
        try:
            from src.conversation.presence_humanization import apply_presence_humanization

            reply = apply_presence_humanization(reply, prefs, family_hint=family)
        except Exception:
            pass

        payload = _soft_payload(reply, intent=intent, entities=entities)
        # Force social-like credibility later via intent/metadata
        if intent == "capabilities":
            payload["knowledge_notes"] = []  # avoid empty analysis chrome from notes
        return payload
    except Exception as exc:
        logger.warning("try_natural_conversation fail-open: %s", exc)
        return None
