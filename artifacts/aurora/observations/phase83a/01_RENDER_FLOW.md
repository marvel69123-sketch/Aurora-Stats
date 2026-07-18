# Fase 8.3-A — Render Flow

```
User (recent-match opinion ask)
  → routing 8.2-E OK (opinion_time / recent_match)
  → NaturalConversation kind=team_opinion
       ↓
  ANTES (bug): compose_intelligent_reply(force_type=team_summary)
       → UserExpectation bias=team_summary
       → ResponsePlanner answer_type=team_summary
       → templates Momento / Agenda / próximos jogos
       ↓
  DEPOIS (8.3-A): wants_match_opinion_render?
       SIM → match_opinion_renderer.render_match_opinion
            response_type=match_opinion
       NÃO → RI legado (team_summary / team_moment) para papo genérico de time
```

## Quem decidia team_summary

1. `natural_conversation.py` — `force_type="team_summary"`  
2. `user_expectation.py` — default bias panorama  
3. `response_planner.py` — `answer_type=team_summary` quando `kind=opinion`  
4. `response_templates.py` — seções momento/agenda  

Não era override de ownership/7.9 — era o **pipeline de Response Intelligence** usado como “opinião”.
