"""
User personas and script generators for the Conversation Simulator.

Only invents **user utterances** from fixed banks. Never invents match odds,
scores, or fixture facts for Aurora to "know".
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


# Real / known fixture labels used as user text only (no fabricated stats).
REAL_FIXTURES = (
    "Argentina x Brasil",
    "Flamengo x Palmeiras",
    "Barcelona x Real Madrid",
    "Brasil x França",
)

TEAM_ONLY = (
    "argentina",
    "flamengo",
    "barcelona",
    "brasil",
)

INVALID_FIXTURES = (
    "Goku x Naruto",
    "Harry Potter x Voldemort",
)

SHORT_FOLLOWUPS = (
    "mercados?",
    "placar?",
    "estatísticas?",
    "favorito?",
    "e dele?",
    "e dela?",
    "e o outro?",
    "e desse?",
    "e esse time?",
    "e ele?",
)

CONFUSED = (
    "não entendeu",
    "você não entendeu",
    "pensa",
    "releia",
    "aff",
    "não foi isso",
)

ADVANCED = (
    "critério de kelly",
    "xg?",
    "pressão?",
    "valor esperado",
    "over 2.5",
    "ambas marcam",
    "kelly?",
    "qual o edge?",
    "stake?",
    "confiança?",
)

# Permanent simulator gate for 8.4-A.11
ADVANCED_V2 = (
    "xg?",
    "pressão?",
    "kelly?",
    "qual o edge?",
    "expected goals",
    "odd justa",
    "probabilidade?",
    "value?",
    "momentum?",
    "stake?",
    "confiança?",
)

CAPABILITY = (
    "o que você faz?",
    "suas funcionalidades",
    "o que sabe fazer?",
)

GREETINGS = ("oi", "olá", "e aí", "bom dia")


@dataclass
class TurnSpec:
    message: str
    expect: dict[str, Any] = field(default_factory=dict)
    tag: str = ""


@dataclass
class Script:
    persona_id: str
    persona_name: str
    turns: list[TurnSpec]
    seed: int


PERSONAS: dict[str, dict[str, Any]] = {
    "beginner": {
        "id": "beginner",
        "name": "Usuário iniciante",
        "description": "Greeting → capabilities → simple fixture",
    },
    "short_followup": {
        "id": "short_followup",
        "name": "Usuário de followups curtos",
        "description": "Fixture then short pronoun/market follow-ups",
    },
    "confused": {
        "id": "confused",
        "name": "Usuário confuso",
        "description": "Sport ask then repair / frustration signals",
    },
    "chaotic": {
        "id": "chaotic",
        "name": "Usuário caótico",
        "description": "Team-only, pronouns, fiction, mixed intents",
    },
    "advanced": {
        "id": "advanced",
        "name": "Usuário futebol avançado",
        "description": "Kelly / xG / pressão style asks after fixture",
    },
    "advanced_football_v2": {
        "id": "advanced_football_v2",
        "name": "Advanced Football Continuity v2",
        "description": "8.4-A.11 permanent gate — advanced terms after fixture",
    },
}


def _pick(rng: random.Random, seq: tuple[str, ...] | list[str]) -> str:
    return seq[rng.randrange(len(seq))]


def script_beginner(rng: random.Random) -> list[TurnSpec]:
    fx = _pick(rng, REAL_FIXTURES)
    return [
        TurnSpec(_pick(rng, GREETINGS), {"soft_intent": ["small_talk", "general_chat", "identity"]}, "greet"),
        TurnSpec(
            _pick(rng, CAPABILITY),
            {"intent": "assistant_capabilities", "no_loop": True},
            "capabilities",
        ),
        TurnSpec(
            fx,
            {"sportish": True, "no_loop": True},
            "fixture",
        ),
    ]


def script_short_followup(rng: random.Random) -> list[TurnSpec]:
    fx = _pick(rng, REAL_FIXTURES)
    fu1 = _pick(rng, SHORT_FOLLOWUPS)
    fu2 = _pick(rng, SHORT_FOLLOWUPS)
    while fu2 == fu1 and len(SHORT_FOLLOWUPS) > 1:
        fu2 = _pick(rng, SHORT_FOLLOWUPS)
    turns = [
        TurnSpec(fx, {"sportish": True}, "fixture"),
        TurnSpec(
            fu1,
            {
                "context_expected": True,
                "no_loop": True,
                "no_ga_steal": True,
            },
            "followup",
        ),
    ]
    if rng.random() < 0.7:
        turns.append(
            TurnSpec(
                fu2,
                {
                    "context_expected": True,
                    "no_loop": True,
                    "no_ga_steal": True,
                },
                "followup",
            )
        )
    return turns


def script_confused(rng: random.Random) -> list[TurnSpec]:
    fx = _pick(rng, REAL_FIXTURES)
    return [
        TurnSpec(fx, {"sportish": True}, "fixture"),
        TurnSpec(
            _pick(rng, ("mercados?", "e dele?", "o que você faz?")),
            {},
            "bridge",
        ),
        TurnSpec(
            _pick(rng, CONFUSED),
            {"frustration_or_repair": True, "no_loop": True},
            "confused",
        ),
    ]


def script_chaotic(rng: random.Random) -> list[TurnSpec]:
    return [
        TurnSpec(_pick(rng, TEAM_ONLY), {"no_loop": True}, "team_only"),
        TurnSpec(
            _pick(rng, ("e esse?", "e dele?", "e o outro?")),
            {"no_loop": True},
            "pronoun_early",
        ),
        TurnSpec(
            _pick(rng, INVALID_FIXTURES),
            {"fixture_quality": "INVALID", "entity_invalid": True, "no_invention": True},
            "fiction",
        ),
        TurnSpec(
            "e dele?",
            {
                "fixture_quality": "INVALID",
                "entity_invalid": True,
                "no_invention": True,
                "no_loop": True,
            },
            "pronoun_after_invalid",
        ),
    ]


def script_advanced(rng: random.Random) -> list[TurnSpec]:
    fx = _pick(rng, REAL_FIXTURES)
    a1 = _pick(rng, ADVANCED)
    a2 = _pick(rng, ADVANCED)
    while a2 == a1 and len(ADVANCED) > 1:
        a2 = _pick(rng, ADVANCED)
    return [
        TurnSpec(fx, {"sportish": True}, "fixture"),
        TurnSpec(
            a1,
            {
                "no_loop": True,
                "useful_reply": True,
                "context_expected": True,
                "no_ga_steal": True,
            },
            "advanced",
        ),
        TurnSpec(
            a2,
            {
                "no_loop": True,
                "useful_reply": True,
                "context_expected": True,
                "no_ga_steal": True,
            },
            "advanced",
        ),
    ]


def script_advanced_football_v2(rng: random.Random) -> list[TurnSpec]:
    fx = _pick(rng, REAL_FIXTURES)
    a1 = _pick(rng, ADVANCED_V2)
    a2 = _pick(rng, ADVANCED_V2)
    while a2 == a1 and len(ADVANCED_V2) > 1:
        a2 = _pick(rng, ADVANCED_V2)
    return [
        TurnSpec(fx, {"sportish": True}, "fixture"),
        TurnSpec(
            a1,
            {
                "no_loop": True,
                "useful_reply": True,
                "context_expected": True,
                "no_ga_steal": True,
            },
            "advanced",
        ),
        TurnSpec(
            a2,
            {
                "no_loop": True,
                "useful_reply": True,
                "context_expected": True,
                "no_ga_steal": True,
            },
            "advanced",
        ),
    ]


_GENERATORS = {
    "beginner": script_beginner,
    "short_followup": script_short_followup,
    "confused": script_confused,
    "chaotic": script_chaotic,
    "advanced": script_advanced,
    "advanced_football_v2": script_advanced_football_v2,
}


def generate_script(
    persona_key: str,
    *,
    rng: random.Random,
    seed: int,
) -> Script:
    meta = PERSONAS[persona_key]
    turns = _GENERATORS[persona_key](rng)
    return Script(
        persona_id=meta["id"],
        persona_name=meta["name"],
        turns=turns,
        seed=seed,
    )


def choose_persona(rng: random.Random, persona_filter: str | None = None) -> str:
    keys = list(PERSONAS.keys())
    if persona_filter:
        if persona_filter not in PERSONAS:
            raise ValueError(f"unknown persona: {persona_filter}")
        return persona_filter
    return _pick(rng, keys)


def generate_batch(
    n: int,
    *,
    base_seed: int = 42,
    persona: str | None = None,
) -> list[Script]:
    scripts: list[Script] = []
    for i in range(n):
        seed = base_seed + i * 9973
        rng = random.Random(seed)
        key = choose_persona(rng, persona)
        scripts.append(generate_script(key, rng=rng, seed=seed))
    return scripts
