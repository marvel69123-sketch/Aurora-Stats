"""
P2.5 — Partial Inference Honesty composer.

Modes: BINDING_ASSUMED | DATA_PARTIAL | LIVE_UNCONFIRMED | PARTIAL_ANALYSIS |
       TEAM_ONLY_SCOPE | RATE_LIMITED | NO_BET_HARD

Never invents fixtures or opponents. Always discloses assumptions when used.
Does not change methodology/market/confidence formulas.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

MODES = frozenset(
    {
        "BINDING_ASSUMED",
        "DATA_PARTIAL",
        "LIVE_UNCONFIRMED",
        "PARTIAL_ANALYSIS",
        "TEAM_ONLY_SCOPE",
        "RATE_LIMITED",
        "NO_BET_HARD",
        "BINDING_AMBIGUOUS",
    }
)


def _human_signals(signals: list[str] | None) -> list[str]:
    mapping = {
        "teams": "times reconhecidos",
        "fixture": "partida identificada",
        "standings": "classificação / forma",
        "xg": "xG",
        "stats": "estatísticas da partida",
        "events": "eventos",
        "live": "dados ao vivo",
        "odds": "odds",
    }
    out: list[str] = []
    for s in signals or []:
        key = str(s).lower().strip()
        out.append(mapping.get(key, key))
    return out


def select_modes(
    *,
    assumptions: list[str] | None = None,
    binding_quality: str | None = None,
    focus_kind: str | None = None,
    preliminary: bool = False,
    fixture_quality: str | None = None,
    is_live: bool = False,
    has_live_stats: bool = False,
    rate_limited: bool = False,
    no_bet: bool = False,
    user_message: str | None = None,
) -> list[str]:
    modes: list[str] = []
    if assumptions:
        modes.append("BINDING_ASSUMED")
    bq = str(binding_quality or "").upper()
    fk = str(focus_kind or "").upper()
    fq = str(fixture_quality or "").upper()
    if fk == "TEAM" or bq == "TEAM_ONLY":
        modes.append("TEAM_ONLY_SCOPE")
    if bq == "AMBIGUOUS":
        modes.append("BINDING_AMBIGUOUS")
    if preliminary or fq in {"PARTIAL", "WEAK", "INCOMPLETE"}:
        modes.append("DATA_PARTIAL")
        modes.append("PARTIAL_ANALYSIS")
    msg = (user_message or "").lower()
    live_ask = bool(
        re.search(
            r"ao\s+vivo|e\s+agora|o\s+jogo\s+mudou|pression|minuto|placar\s*\?",
            msg,
        )
    )
    if (live_ask or "melhor" in msg) and not (is_live and has_live_stats):
        modes.append("LIVE_UNCONFIRMED")
    if rate_limited:
        modes.append("RATE_LIMITED")
    if no_bet:
        modes.append("NO_BET_HARD")
    # dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for m in modes:
        if m in MODES and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def build_honesty_block(
    *,
    modes: list[str],
    assumptions: list[str] | None = None,
    fixture_label: str | None = None,
    focus_team: str | None = None,
    available_signals: list[str] | None = None,
    missing_signals: list[str] | None = None,
    no_bet: bool = True,
) -> dict[str, Any]:
    have = _human_signals(available_signals)
    lack = _human_signals(missing_signals)
    if "DATA_PARTIAL" in modes or "PARTIAL_ANALYSIS" in modes:
        if "xG" not in " ".join(lack) and "xg" not in [s.lower() for s in (missing_signals or [])]:
            if "xg" not in [s.lower() for s in (available_signals or [])]:
                lack.append("xG")
        if not any("estat" in x for x in lack):
            if "stats" not in [s.lower() for s in (available_signals or [])]:
                lack.append("estatísticas da partida confirmadas")

    assumption_line = None
    if assumptions:
        assumption_line = assumptions[0]
    elif "BINDING_ASSUMED" in modes and fixture_label:
        assumption_line = f"Assumindo que você está falando de **{fixture_label}**."
    elif "TEAM_ONLY_SCOPE" in modes and focus_team:
        assumption_line = (
            f"Assumindo o time **{focus_team}** (sem confronto completo)."
        )

    mode_lines: list[str] = []
    if "DATA_PARTIAL" in modes or "PARTIAL_ANALYSIS" in modes:
        mode_lines.append("Com **dados parciais**…")
    if "LIVE_UNCONFIRMED" in modes:
        mode_lines.append("**Sem estatísticas ao vivo confirmadas**…")
    if "RATE_LIMITED" in modes:
        mode_lines.append("Fonte temporariamente limitada (rate limit).")
    if "TEAM_ONLY_SCOPE" in modes:
        mode_lines.append("Escopo de **time** — sem inventar adversário.")

    posture = "Sem stake recomendado até completar sinais." if no_bet else "Stake limitado."
    if "NO_BET_HARD" in modes:
        posture = "No-bet: sinais insuficientes para stake."

    next_signals = []
    for x in lack[:4]:
        next_signals.append(x)

    return {
        "modes": list(modes),
        "assumption_line": assumption_line,
        "mode_lines": mode_lines,
        "have": have,
        "lack": lack,
        "posture": posture,
        "next_signals": next_signals,
        "assumptions": list(assumptions or []),
    }


def render_honesty_prefix(block: dict[str, Any] | None) -> str:
    if not isinstance(block, dict):
        return ""
    parts: list[str] = []
    if block.get("assumption_line"):
        parts.append(str(block["assumption_line"]))
    for line in block.get("mode_lines") or []:
        parts.append(str(line))
    have = block.get("have") or []
    lack = block.get("lack") or []
    if have:
        parts.append("Sinais disponíveis: " + ", ".join(have[:6]) + ".")
    if lack:
        parts.append("Ainda não tenho: " + ", ".join(lack[:6]) + ".")
    if block.get("posture"):
        parts.append(str(block["posture"]))
    if block.get("next_signals"):
        parts.append(
            "Para subir confiança: " + ", ".join(block["next_signals"][:4]) + "."
        )
    return "\n".join(parts).strip()


def apply_honesty_to_payload(
    payload: dict[str, Any] | None,
    ctx: dict[str, Any] | None = None,
    *,
    user_message: str | None = None,
) -> dict[str, Any] | None:
    """Enrich sport/partial payloads with honesty block + optional executive prefix."""
    if not isinstance(payload, dict):
        return payload
    try:
        ents = dict(payload.get("entities") or {})
        intent = str(payload.get("intent") or "")
        # Never decorate pure clarification / identity turns
        if ents.get("clarification_mode") and not ents.get("has_analysis"):
            return payload
        if intent in {"clarification", "identity", "small_talk", "assistant_capabilities"}:
            if not ents.get("preliminary_analysis") and not ents.get("has_analysis"):
                return payload
        sportish = intent in {
            "analyze_match",
            "follow_up",
            "match_opinion",
            "live_opportunities",
        } or bool(ents.get("preliminary_analysis") or ents.get("continuity_followup"))
        if not sportish:
            return payload

        # RESPONSE-SELECTOR-001 — skill-authored replies must not be wrapped in
        # Mantendo foco / No-bet shells (presentation only; engines untouched).
        if ents.get("response_selector_skip_honesty") or ents.get(
            "sport_intent_authored"
        ):
            return payload

        assumptions = list(ents.get("bind_assumptions") or [])
        srf = ents.get("srf") if isinstance(ents.get("srf"), dict) else {}
        if isinstance(ctx, dict):
            last = ctx.get("entity_v2_last_bind")
            if isinstance(last, dict):
                assumptions = assumptions or list(last.get("bind_assumptions") or [])
                if not srf:
                    srf = last.get("srf") or {}

        br = payload.get("bankroll_recommendation") or {}
        no_bet = bool(br.get("no_bet", True)) if isinstance(br, dict) else True
        conf = payload.get("confidence") or {}
        avail = []
        missing = []
        if isinstance(conf, dict):
            # best-effort from explanation text / entities
            pass
        brain = payload.get("brain") if isinstance(payload.get("brain"), dict) else {}
        inf = brain.get("inference") if isinstance(brain.get("inference"), dict) else {}
        if isinstance(inf.get("available_signals"), list):
            avail = [str(x) for x in inf["available_signals"]]
        if isinstance(inf.get("missing_signals"), list):
            missing = [str(x) for x in inf["missing_signals"]]
        if ents.get("preliminary_analysis") and not missing:
            missing = ["xg", "stats", "events"]
        if ents.get("fixture_quality") in {"PARTIAL", "WEAK"} and "fixture" not in [
            a.lower() for a in avail
        ]:
            avail = avail or ["teams"]
            missing = missing or ["xg", "stats"]

        modes = select_modes(
            assumptions=assumptions,
            binding_quality=str(
                ents.get("binding_quality") or srf.get("binding_quality") or ""
            ),
            focus_kind=str(ents.get("focus_kind") or srf.get("focus_kind") or ""),
            preliminary=bool(ents.get("preliminary_analysis")),
            fixture_quality=str(ents.get("fixture_quality") or ""),
            is_live=bool(payload.get("is_live")),
            has_live_stats=bool(ents.get("has_stats") or payload.get("minute")),
            rate_limited=bool(ents.get("rate_limited")),
            no_bet=no_bet,
            user_message=user_message,
        )
        if not modes and not assumptions:
            return payload

        block = build_honesty_block(
            modes=modes,
            assumptions=assumptions,
            fixture_label=str(
                srf.get("fixture_label")
                or ents.get("referent_fixture")
                or payload.get("match")
                or ""
            )
            or None,
            focus_team=str(srf.get("focus_team") or ents.get("referent_team") or "")
            or None,
            available_signals=avail,
            missing_signals=missing,
            no_bet=no_bet,
        )
        prefix = render_honesty_prefix(block)
        ents["honesty_block"] = block
        ents["honesty_modes"] = list(modes)
        ents["p25_partial_honesty"] = True
        if prefix and not ents.get("honesty_prefix_applied"):
            summary = str(payload.get("executive_summary") or "")
            if prefix not in summary:
                payload["executive_summary"] = (prefix + "\n\n" + summary).strip()
            ents["honesty_prefix_applied"] = True
        payload["entities"] = ents
    except Exception as exc:
        logger.warning("partial_inference_honesty fail-open: %s", exc)
    return payload
