# TOPIC-BOUNDARY-002 — Live router validation

**Flag session:** `ENABLE_TOPIC_BOUNDARY_V2=1` (code default unchanged / still off)
**All pass:** True
**Recommendation:** ENABLE_TOPIC_BOUNDARY_V2=1

## Scenario 1 — Flamengo x Palmeiras → Liverpool x Chelsea

**PASS:** True

### T1: Flamengo x Palmeiras
- episode_id: `422215e9-607f-4487-a4cb-7ada2be1e92e`
- csl_fixture: `Flamengo vs Palmeiras`
- csl_teams: `['Flamengo', 'Palmeiras']`
- home/away: `Flamengo` / `Palmeiras`
- flamengo=True liverpool=False inter=False
- mantendo_foco_flamengo=False
- summary: Com **dados parciais**… | Sinais disponíveis: times reconhecidos. | Ainda não tenho: xG, estatísticas da partida, eventos. | No-bet: sinais insuficientes para stake. | Para subir confiança: xG, estatísticas da partida, eventos. |  | **Flamengo x Palmeiras** — leitura preliminar |  | Confronto re

### T2: Liverpool x Chelsea
- episode_id: `4675b349-15e8-4728-a790-98ee1db9fced`
- csl_fixture: `Chelsea vs Liverpool`
- csl_teams: `['Chelsea', 'Liverpool']`
- home/away: `Chelsea` / `Liverpool`
- flamengo=False liverpool=True inter=False
- mantendo_foco_flamengo=False
- summary: Com **dados parciais**… | Sinais disponíveis: times reconhecidos. | Ainda não tenho: xG, estatísticas da partida, eventos. | No-bet: sinais insuficientes para stake. | Para subir confiança: xG, estatísticas da partida, eventos. |  | **Chelsea x Liverpool** — leitura preliminar |  | Confronto rec

Judgment detail: `{"pass": true, "episode_rotated": true, "subject_liverpool_chelsea": true, "no_flamengo_contamination": true, "no_mantendo_foco_flamengo": true, "csl_fixture_clean": true, "evidence": {"ep1": "422215e9-607f-4487-a4cb-7ada2be1e92e", "ep2": "4675b349-15e8-4728-a790-98ee1db9fced", "csl_fixture_t2": "Chelsea vs Liverpool", "csl_teams_t2": ["Chelsea", "Liverpool"], "flamengo_t2": false, "prefix_t2": "Com **dados parciais**… | Sinais disponíveis: times reconhecidos. | Ainda não tenho: xG, estatísticas da partida, eventos. | No-bet: sinais insuficientes para stake. | Para subir confiança: xG, estatísticas da partida, eventos. |  | **Chelsea x Liverpool** — leitura preliminar |  | Confronto rec"}}`

## Scenario 2 — … → Quem está melhor?

**PASS:** True

### T1: Flamengo x Palmeiras
- episode_id: `28e1a114-bc48-4caa-b139-95fa5666b7fa`
- csl_fixture: `Flamengo vs Palmeiras`
- csl_teams: `['Flamengo', 'Palmeiras']`
- home/away: `Flamengo` / `Palmeiras`
- flamengo=True liverpool=False inter=False
- mantendo_foco_flamengo=False
- summary: Com **dados parciais**… | Sinais disponíveis: times reconhecidos. | Ainda não tenho: xG, estatísticas da partida, eventos. | No-bet: sinais insuficientes para stake. | Para subir confiança: xG, estatísticas da partida, eventos. |  | **Flamengo x Palmeiras** — leitura preliminar |  | Confronto re

### T2: Liverpool x Chelsea
- episode_id: `7f9b014c-fadb-4008-a6ee-cfe7d1fce011`
- csl_fixture: `Chelsea vs Liverpool`
- csl_teams: `['Chelsea', 'Liverpool']`
- home/away: `Chelsea` / `Liverpool`
- flamengo=False liverpool=True inter=False
- mantendo_foco_flamengo=False
- summary: Com **dados parciais**… | Sinais disponíveis: times reconhecidos. | Ainda não tenho: xG, estatísticas da partida, eventos. | No-bet: sinais insuficientes para stake. | Para subir confiança: xG, estatísticas da partida, eventos. |  | **Chelsea x Liverpool** — leitura preliminar |  | Confronto rec

### T3: Quem está melhor?
- episode_id: `7f9b014c-fadb-4008-a6ee-cfe7d1fce011`
- csl_fixture: `Chelsea vs Liverpool`
- csl_teams: `['Chelsea', 'Liverpool']`
- home/away: `None` / `None`
- flamengo=False liverpool=True inter=False
- mantendo_foco_flamengo=False
- summary: Comparando a **fase recente** de **Chelsea** e **Liverpool** (contexto: Chelsea vs Liverpool). |  | Ainda sem fechar um placar numérico inventado neste turno — posso afunilar em estatísticas, mando de campo ou mercados se você escolher o recorte.

Judgment detail: `{"pass": true, "episode_rotated_t1_t2": true, "t3_same_liverpool_episode": true, "t3_about_liverpool_chelsea": true, "no_flamengo_on_t3": true, "no_mantendo_foco": true, "evidence": {"ep1": "28e1a114-bc48-4caa-b139-95fa5666b7fa", "ep2": "7f9b014c-fadb-4008-a6ee-cfe7d1fce011", "ep3": "7f9b014c-fadb-4008-a6ee-cfe7d1fce011", "csl_fixture_t3": "Chelsea vs Liverpool", "csl_teams_t3": ["Chelsea", "Liverpool"], "flamengo_t3": false, "prefix_t3": "Comparando a **fase recente** de **Chelsea** e **Liverpool** (contexto: Chelsea vs Liverpool). |  | Ainda sem fechar um placar numérico inventado neste turno — posso afunilar em estatísticas, mando de campo ou mercados se você escolher o recorte."}}`

## Scenario 3 — Flamengo x Palmeiras → Inter joga hoje?

**PASS:** True

### T1: Flamengo x Palmeiras
- episode_id: `92ec4bc6-d125-4d2d-b95e-7fb5b7ce88f9`
- csl_fixture: `Flamengo vs Palmeiras`
- csl_teams: `['Flamengo', 'Palmeiras']`
- home/away: `Flamengo` / `Palmeiras`
- flamengo=True liverpool=False inter=False
- mantendo_foco_flamengo=False
- summary: Com **dados parciais**… | Sinais disponíveis: times reconhecidos. | Ainda não tenho: xG, estatísticas da partida, eventos. | No-bet: sinais insuficientes para stake. | Para subir confiança: xG, estatísticas da partida, eventos. |  | **Flamengo x Palmeiras** — leitura preliminar |  | Confronto re

### T2: Inter joga hoje?
- episode_id: `948985e8-b1bb-4b8c-944b-f6143d95ec5b`
- csl_fixture: `None`
- csl_teams: `['Internacional']`
- home/away: `None` / `None`
- flamengo=False liverpool=False inter=True
- mantendo_foco_flamengo=False
- summary: **Internacional** — leitura rápida 📊 **Momento** | Com o contexto atual do Internacional, priorizo fase e ritmo — sem cravar um veredito seco. 🗞️ **O que circula** | Ainda sem um placar recente amarrado aqui; o útil é cruzar fase e próximo desafio. 📅 **Agenda à frente** | O próximo des

Judgment detail: `{"pass": true, "episode_rotated_or_partial": true, "inter_subject": true, "no_flamengo_fixture_reuse": true, "no_mantendo_foco_flamengo": true, "evidence": {"ep1": "92ec4bc6-d125-4d2d-b95e-7fb5b7ce88f9", "ep2": "948985e8-b1bb-4b8c-944b-f6143d95ec5b", "csl_fixture_t2": null, "csl_teams_t2": ["Internacional"], "flamengo_t2": false, "boundary_t2": {}, "prefix_t2": "**Internacional** — leitura rápida 📊 **Momento** | Com o contexto atual do Internacional, priorizo fase e ritmo — sem cravar um veredito seco. 🗞️ **O que circula** | Ainda sem um placar recente amarrado aqui; o útil é cruzar fase e próximo desafio. 📅 **Agenda à frente** | O próximo des"}}`
