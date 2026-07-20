# P3-D.3 — Response Pattern Analysis

**Mode:** ANALYSIS ONLY (no implementation)
**Generated:** 2026-07-20T22:24:20.382267+00:00
**Corpus:** post–Commitment Recovery destroy — 81 sessions / 17349 replies / 3141 loop replies
**Global loop rate:** 0.182

---

## Verdict

- Dominant loop family: **`sport_analysis_boilerplate`** (71.0% of loop replies).
- Top 3: `sport_analysis_boilerplate`, `legacy_clarify_triage`, `other_content`.
- Escape still dominant? **False** (abandon_escape share 0.0%).
- Uncommitted explicit share of loops: **0.0%**.
- Ask-rate on loop replies: **20.8%** (all replies 30.2%).
- Top-10 fingerprints cover **93.6%** of loop replies.

## Loop families (ranked)

| Rank | Family | Loop # | Loop % | P(loop\|family) | Streak≥3 |
|-----:|--------|-------:|-------:|----------------:|---------:|
| 1 | `sport_analysis_boilerplate` | 2230 | 71.0% | 1.00 | 5 |
| 2 | `legacy_clarify_triage` | 485 | 15.4% | 0.82 | 31 |
| 3 | `other_content` | 318 | 10.1% | 0.04 | 7 |
| 4 | `soft_assume_goal` | 92 | 2.9% | 0.02 | 2 |
| 5 | `too_short` | 8 | 0.2% | 0.01 | 0 |
| 6 | `greeting_identity` | 7 | 0.2% | 0.32 | 0 |
| 7 | `sport_chat_soft` | 1 | 0.0% | 0.20 | 0 |

## Top loop fingerprints (concrete templates)

| Rank | Family | Loop # | Example |
|-----:|--------|-------:|---------|
| 1 | `sport_analysis_boilerplate` | 994 | Eu teria uma visão cautelosa. / O ponto que mais pesa para mim: / • há contexto suficiente |
| 2 | `sport_analysis_boilerplate` | 499 | Eu entraria só com filtro — e bem consciente do risco. / O que sustenta minha leitura: / • |
| 3 | `sport_analysis_boilerplate` | 494 | Vejo valor, mas com algumas ressalvas. / O que mais me chama atenção: / • há contexto sufi |
| 4 | `legacy_clarify_triage` | 485 | Você está falando de: /  Seleção / time? /  Jogo específico? /  Notícias? |
| 5 | `sport_analysis_boilerplate` | 243 | Há um caminho interessante, sem euforia. / O ponto que mais pesa para mim: / • há contexto |
| 6 | `other_content` | 73 | Se for outra coisa, pode falar. |
| 7 | `other_content` | 62 | O contexto esportivo anterior foi limpo. /  / Me diga um confronto real (Time A x Time B)  |
| 8 | `other_content` | 39 | Assumindo o time **Corinthians** (sem confronto completo). / Escopo de **time** — sem inve |
| 9 | `soft_assume_goal` | 26 | Sem o mesmo bloco: /  / Esse confronto parece **ficção / hipotético** não trato como parti |
| 10 | `soft_assume_goal` | 24 | Esse confronto parece **ficção / hipotético** não trato como partida real de futebol. /  / |
| 11 | `other_content` | 23 | Mantendo foco Bahia / Escopo de **time** — sem inventar adversário. / No-bet: sinais insuf |
| 12 | `soft_assume_goal` | 21 | Mudando o ângulo pra não repetir. /  / Esse confronto parece **ficção / hipotético** não t |
| 13 | `soft_assume_goal` | 15 | Outro formato, mesmo assunto: /  / Esse confronto parece **ficção / hipotético** não trato |
| 14 | `other_content` | 10 | Pode ser o que exatamente quer que eu salve? Ex.: *salve minha banca de 100 reais*. |
| 15 | `other_content` | 7 | Assumindo o time **Vitoria** (sem confronto completo). / Escopo de **time** — sem inventar |

## By persona (loop families)

| Persona | Loop events | #1 family | #2 |
|---------|------------:|-----------|----|
| emocional | 1505 | `sport_analysis_boilerplate` (99%) | `other_content` (1%) |
| poucas_palavras | 558 | `legacy_clarify_triage` (87%) | `other_content` (13%) |
| casual | 516 | `sport_analysis_boilerplate` (97%) | `other_content` (3%) |
| irritado | 253 | `sport_analysis_boilerplate` (96%) | `other_content` (4%) |
| esportivo | 98 | `other_content` (97%) | `soft_assume_goal` (2%) |
| caotico | 87 | `soft_assume_goal` (93%) | `other_content` (5%) |
| power_user | 73 | `other_content` (93%) | `soft_assume_goal` (4%) |
| exigente | 29 | `other_content` (79%) | `greeting_identity` (10%) |
| chatgpt_user | 22 | `other_content` (73%) | `greeting_identity` (18%) |

## By length

| L | Loop events | #1 family |
|--|------------:|-----------|
| 10 | 24 | `other_content` (88%) |
| 50 | 108 | `sport_analysis_boilerplate` (42%) |
| 100 | 63 | `other_content` (52%) |
| 200 | 293 | `sport_analysis_boilerplate` (68%) |
| 500 | 1193 | `sport_analysis_boilerplate` (83%) |
| 1000 | 1460 | `sport_analysis_boilerplate` (68%) |

## What this means (no fix here)

1. **Belief + commitment recovery** changed the *shape* of hollow replies (escape → uncommitted), but did not remove the largest sticky **content** family if sport analysis boilerplate still leads.
2. **Soft-assume** remains a mid-tier loop family — paraphrased goal continues can still Jaccard-collide on long sessions.
3. Pattern concentration: a small set of fingerprints explains a large share of loops → remaining collapse is **template-driven**, not diffuse randomness.

## Answers

**1_dominant_loop_family:** sport_analysis_boilerplate

**2_top3_families:** ['sport_analysis_boilerplate', 'legacy_clarify_triage', 'other_content']

**3_escape_still_dominant:** False

**4_uncommitted_share_of_loops:** 0.0

**5_sport_boilerplate_share:** 0.71

**6_soft_assume_share:** 0.0293

**7_ask_rate_on_loops:** 0.2076

**8_top10_fingerprint_concentration:** 0.9357

**9_commitment_recovery_effect:** abandon_escape_ask + uncommitted_explicit together are 0.0% of loops; sport_analysis_boilerplate remains the largest single sticky family if ranked #1, or second — see ranked table.

---

Artifacts: `response_pattern_analysis.json`, `response_pattern_analysis.md`
