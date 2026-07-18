"""
Frustration analytics scenarios — user utterances only.

Never invents match odds/scores. Uses known fixtures as user text.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

REAL_FIXTURES = (
    "Argentina x Brasil",
    "Flamengo x Palmeiras",
    "Barcelona x Real Madrid",
)

FRUSTRATION_PHRASES = (
    "não entendeu",
    "você não entendeu",
    "não foi isso",
    "preste atenção",
    "releia",
    "???",
    "aff",
    "hã?",
    "pensa um pouco",
    "não respondeu",
    "isso está errado",
)


@dataclass
class FrustTurn:
    message: str
    tag: str = ""
    inject_frustration: bool = False


@dataclass
class FrustScript:
    id: str
    name: str
    turns: list[FrustTurn] = field(default_factory=list)
    seed: int = 0


def _pick(rng: random.Random, seq: tuple[str, ...] | list[str]) -> str:
    return seq[rng.randrange(len(seq))]


def script_misunderstanding(rng: random.Random, seed: int) -> FrustScript:
    fx = _pick(rng, REAL_FIXTURES)
    return FrustScript(
        id="misunderstanding",
        name="Misunderstanding after fixture",
        seed=seed,
        turns=[
            FrustTurn(fx, "fixture"),
            FrustTurn("mercados?", "bridge"),
            FrustTurn(_pick(rng, ("não entendeu", "você não entendeu", "hã?")), "frustration", True),
            FrustTurn("e dele?", "after"),
        ],
    )


def script_wrong_intent(rng: random.Random, seed: int) -> FrustScript:
    return FrustScript(
        id="wrong_intent",
        name="Wrong intent complaint",
        seed=seed,
        turns=[
            FrustTurn("o que você faz?", "capabilities"),
            FrustTurn(_pick(rng, ("não foi isso", "isso está errado")), "frustration", True),
            FrustTurn("suas funcionalidades", "after"),
        ],
    )


def script_too_generic(rng: random.Random, seed: int) -> FrustScript:
    return FrustScript(
        id="too_generic",
        name="Generic / aff / ???",
        seed=seed,
        turns=[
            FrustTurn("oi", "greet"),
            FrustTurn(_pick(rng, ("aff", "???", "pensa um pouco")), "frustration", True),
            FrustTurn(_pick(rng, REAL_FIXTURES), "after"),
        ],
    )


def script_lost_context(rng: random.Random, seed: int) -> FrustScript:
    fx = _pick(rng, REAL_FIXTURES)
    return FrustScript(
        id="lost_context",
        name="Lost context then frustration",
        seed=seed,
        turns=[
            FrustTurn(fx, "fixture"),
            FrustTurn("e esse?", "weak_pronoun"),
            FrustTurn(_pick(rng, ("não entendeu", "preste atenção", "releia")), "frustration", True),
            FrustTurn("mercados?", "after"),
        ],
    )


def script_repeated(rng: random.Random, seed: int) -> FrustScript:
    fx = _pick(rng, REAL_FIXTURES)
    return FrustScript(
        id="repeated",
        name="Repeated frustration",
        seed=seed,
        turns=[
            FrustTurn(fx, "fixture"),
            FrustTurn("não entendeu", "frustration", True),
            FrustTurn("não foi isso", "frustration", True),
            FrustTurn("aff", "frustration", True),
        ],
    )


def script_no_answer(rng: random.Random, seed: int) -> FrustScript:
    return FrustScript(
        id="no_answer",
        name="Não respondeu complaint",
        seed=seed,
        turns=[
            FrustTurn(_pick(rng, REAL_FIXTURES), "fixture"),
            FrustTurn("não respondeu", "frustration", True),
            FrustTurn("xg?", "after"),
        ],
    )


_BUILDERS = (
    script_misunderstanding,
    script_wrong_intent,
    script_too_generic,
    script_lost_context,
    script_repeated,
    script_no_answer,
)


def generate_frustration_batch(
    n: int,
    *,
    base_seed: int = 42,
) -> list[FrustScript]:
    scripts: list[FrustScript] = []
    for i in range(n):
        seed = base_seed + i * 7919
        rng = random.Random(seed)
        builder = _BUILDERS[i % len(_BUILDERS)]
        scripts.append(builder(rng, seed))
    return scripts
