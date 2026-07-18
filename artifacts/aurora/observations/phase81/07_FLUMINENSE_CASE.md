# Fase 8.1 — Caso Fluminense

---

## Input

> oque voce achou do jogo do fluminense ontem?

## Output observado

```
⚽ Jogos do Fluminense hoje
🕒 15:00
Vitória U20 x Fluminense de Feira U20
```

Audit: `intent=team_calendar`, `natural_kind=team_calendar`, `calendar_date=2026-07-18`, `fixture_count=1`.

---

## Por que virou `team_calendar` e não opinion?

### 1) Precedência no detector (`natural_conversation.py`)

Ordem relevante em `detect_natural_kind` (nomes aproximados no fluxo):

1. … kicks / research …
2. **Bloco calendar** — regex inclui:
   ```
   tem jogo | jogo d[oe] | jogos? d[oe] | proximo jogo | quero saber … jogo | agenda | …
   ```
3. Só **depois**: bloco `team_opinion` com `o que achou d[oe]` / `achou d[oe] …`

A frase do user contém **`jogo do`** → casa o bloco calendar **antes** de chegar em “achou”.

### 2) “ontem” é ignorado

No retorno calendar:
```python
offset = 0
if re.search(r"\bamanha\b", folded):
    offset = 1
```
- Só trata `amanha`.
- **Não há** `ontem` → `date_offset=0` → “hoje” → `2026-07-18`.

### 3) `last_match_opinion` / opinion de jogo passado

- Grep no repo: **não existe** intent/kind `last_match_opinion`.
- `team_opinion` existe, mas **não foi avaliado** por causa do early-return calendar.

### 4) Entidade errada (efeito colateral)

Filtro por nome “Fluminense” pegou **Fluminense de Feira U20**, não o Fluminense-RJ — reforça a sensação de “não entendeu”.

### 5) Repetição no turno 5

> quero saber oque voce achou do ultimo jogo do fluminense

Ainda contém padrão de agenda (`jogo` + time) → **mesmo** `team_calendar` / mesma agenda.

---

## Cadeia causal

```
"achou do jogo do fluminense ontem"
        ↓
regex calendar casa "jogo do"          ← bug de precedência/semântica
        ↓
date_offset=0 (ontem ignorado)
        ↓
agenda de HOJE + time homônimo U20
        ↓
user: "não entendeu"
        ↓
GENERAL_CHAT → reply_general (Entendi…)
```

---

## Conclusão

Não foi “falta de dados do jogo”. Foi **classificação errada por regex**: pedido de **opinião retrospectiva** capturado como **agenda do dia**. Intent correto desejado: `team_opinion` (ou um kind de last-match opinion — **ainda inexistente**).
