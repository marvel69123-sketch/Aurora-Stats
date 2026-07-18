"""
FASE 7.9-E — Smoke misroute (classifiers only).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conversation.emotional_presence import detect_emotional_intent
from src.conversation.general_assistant import try_general_assistant
from src.conversation.master_intent_router import classify_master_intent


EXPECTED = {
    "quais jogos estão ao vivo?": ("LIVE_MATCH", True),
    "quais partidas estão acontecendo agora?": ("LIVE_MATCH", True),
    "que horas são?": ("UTILITY_QUERY", False),
    "horário atual": ("UTILITY_QUERY", False),
    "estou triste": ("EMOTIONAL_QUERY", False),
    "me sinto sozinho": ("EMOTIONAL_QUERY", False),
    "não vou desistir de você": ("EMOTIONAL_QUERY", False),
    "aurora é minha maior criação": ("EMOTIONAL_QUERY", False),
}

T1_T5 = {
    "T1": ["me ajuda com uma coisa", "não é isso", "quero outra coisa", "me escuta"],
    "T2": ["preciso de ajuda", "você não entendeu", "tenta de novo"],
    "T3": ["o que voce faz?", "e alem disso?", "me explica melhor"],
    "T4": ["quais jogos estão ao vivo?", "e ai", "me fala mais"],
    "T5": ["que horas são?", "ok e agora?", "então me ajuda"],
}


def main() -> int:
    print("FASE 7.9-E MISROUTE SMOKE")
    print()
    ok_n = 0
    total = 0
    print("=== Probes obrigatórios ===")
    for msg, (want_intent, want_sport) in EXPECTED.items():
        total += 1
        r = classify_master_intent(msg)
        emo = detect_emotional_intent(msg)
        hit = r.intent == want_intent and r.allow_sport_pipeline is want_sport
        ok_n += int(hit)
        ga = try_general_assistant(msg, r.intent, {})
        src = (
            "emotional"
            if r.intent == "EMOTIONAL_QUERY"
            else ("utility" if r.intent == "UTILITY_QUERY" else r.intent)
        )
        print(
            f"  [{'OK' if hit else 'FAIL'}] {msg!r}\n"
            f"       intent={r.intent} sport={r.allow_sport_pipeline} "
            f"reason={r.reason} emo={emo} source≈{src} "
            f"ga={'yes' if ga else 'none'}"
        )

    print()
    print("=== T1–T5 (intent por turno) ===")
    for title, turns in T1_T5.items():
        print(f"  {title}:")
        for t in turns:
            r = classify_master_intent(t)
            print(f"    {t!r} → {r.intent} ({r.reason})")

    # Baseline regressions
    for msg, sport in (("oi", False), ("Flamengo x Palmeiras", True), ("juventus joga que horas?", True)):
        total += 1
        r = classify_master_intent(msg)
        hit = r.allow_sport_pipeline is sport
        ok_n += int(hit)
        print(f"  [{'OK' if hit else 'FAIL'}] regress {msg!r} → {r.intent} sport={r.allow_sport_pipeline}")

    rate = 100.0 * ok_n / total if total else 0.0
    print()
    print(f"Taxa de acerto roteamento (probes+regress): {ok_n}/{total} = {rate:.0f}%")
    return 0 if ok_n == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
