"""
Aurora Copilot — conversational endpoint.

POST /aurora/chat             — send a message, get a professional response
GET  /aurora/chat/history     — paginated conversation history (all sessions)
GET  /aurora/chat/session     — messages for a specific session
"""
from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from src.brain import get_brain_meta
from src.chat_db import (
    count_messages,
    count_sessions,
    create_session,
    get_history,
    get_session,
    get_session_messages,
    save_message,
    search_history,
    update_session_context,
)
from src.core.copilot_engine import detect_intent, dispatch

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message:    str   = Field(..., min_length=1, max_length=2000,
                              description="Natural-language message to Aurora")
    session_id: str | None = Field(
        None,
        description="Continue an existing session. Omit to start a new one.",
    )


class ChatResponse(BaseModel):
    session_id: str
    intent:     str
    entities:   dict[str, Any]
    response:   str
    message_id: int
    brain:      dict[str, Any]


class SessionMessage(BaseModel):
    id:         int
    session_id: str
    role:       str
    content:    str
    intent:     str | None
    entities:   dict[str, Any]
    created_at: str


class SessionInfo(BaseModel):
    session_id:     str
    started_at:     str
    last_active:    str
    message_count:  int
    last_intent:    str | None
    last_home:      str | None
    last_away:      str | None


class HistoryResponse(BaseModel):
    total:    int
    limit:    int
    offset:   int
    sessions: list[dict[str, Any]]
    stats:    dict[str, Any]
    brain:    dict[str, Any]


class SessionResponse(BaseModel):
    session:  dict[str, Any]
    messages: list[SessionMessage]
    total:    int
    brain:    dict[str, Any]


# ---------------------------------------------------------------------------
# POST /aurora/chat
# ---------------------------------------------------------------------------


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=200,
    summary="Aurora Copilot — Conversational Interface",
)
async def chat(body: ChatRequest) -> ChatResponse:
    """
    Aurora Copilot — send any natural-language message and get a professional response.

    Aurora automatically detects your intent and calls the right pipeline:

    | What you ask | What Aurora does |
    |---|---|
    | *\"Analyze Arsenal vs Chelsea\"* | Full intelligence report — 11 NL sections |
    | *\"Best live opportunities\"* | Fetches live matches, ranks opportunities |
    | *\"Review bankroll\"* | Performance summary, accuracy, ROI |
    | *\"What did Aurora learn today?\"* | Learning stats, market accuracy recap |
    | *\"What do you know about BTTS?\"* | Knowledge base search |
    | *\"Explain recommendation\"* | Deep-dive into last call for this session |
    | *\"Help\"* | Full command reference |

    **Session management:**
    - Omit `session_id` to start a new conversation.
    - Pass the returned `session_id` in subsequent requests to continue the conversation.
    - Aurora remembers the last analyzed fixture within a session,
      so *\"explain the recommendation\"* always refers to the most recent call.

    **Every response is:**
    - Written in natural language — no raw JSON arrays
    - Grounded in Aurora's full methodology (Poisson model, 15-category scoring,
      39 knowledge rules, learning history, memory)
    - Stored permanently and searchable via `GET /aurora/chat/history`
    """
    raw_message = body.message.strip()

    # ── Session setup ─────────────────────────────────────────────────────
    session_id = body.session_id or secrets.token_hex(4)
    create_session(session_id)
    session_ctx = get_session(session_id) or {}

    # ── Intent detection ──────────────────────────────────────────────────
    intent, entities = detect_intent(raw_message)
    entities["_raw"] = raw_message

    # ── Save user message ─────────────────────────────────────────────────
    save_message(
        session_id=session_id,
        role="user",
        content=raw_message,
        intent=intent,
        entities={k: v for k, v in entities.items() if k != "_raw"},
    )

    # ── Dispatch ──────────────────────────────────────────────────────────
    response_text = await dispatch(
        intent=intent,
        entities=entities,
        session_ctx=session_ctx,
        session_id=session_id,
    )

    # ── Save Aurora response + update session context ─────────────────────
    msg_id = save_message(
        session_id=session_id,
        role="aurora",
        content=response_text,
        intent=intent,
        entities={},
    )

    # Update session with last fixture context if this was a match analysis
    home = entities.get("home")
    away = entities.get("away")
    update_session_context(
        session_id=session_id,
        home=home,
        away=away,
        intent=intent,
    )

    return ChatResponse(
        session_id=session_id,
        intent=intent,
        entities={k: v for k, v in entities.items() if k != "_raw"},
        response=response_text,
        message_id=msg_id,
        brain=get_brain_meta(),
    )


# ---------------------------------------------------------------------------
# GET /aurora/chat/history
# ---------------------------------------------------------------------------


@router.get(
    "/chat/history",
    response_model=HistoryResponse,
    summary="Conversation History",
)
async def chat_history(
    limit:  int      = Query(20, ge=1, le=100),
    offset: int      = Query(0,  ge=0),
    intent: str | None = Query(None, description="Filter by intent (e.g. analyze_match, bankroll_review)"),
    q:      str | None = Query(None, description="Full-text search across all messages"),
) -> HistoryResponse:
    """
    Return Aurora's full conversation history — all sessions, all messages.

    **Filtering:**
    - `intent` — filter sessions by intent type (e.g. `analyze_match`, `live_opportunities`)
    - `q` — full-text search across message content

    **Every conversation is stored permanently.** Aurora's memory deepens with
    every session, and the history is searchable for auditing, review, or
    referencing past analyses.
    """
    if q:
        msgs = search_history(q, limit=limit)
        return HistoryResponse(
            total=len(msgs),
            limit=limit,
            offset=offset,
            sessions=[],
            stats={
                "search_query": q,
                "results": len(msgs),
                "messages": msgs,
            },
            brain=get_brain_meta(),
        )

    history = get_history(limit=limit, offset=offset, intent_filter=intent)
    return HistoryResponse(
        total=history["total"],
        limit=limit,
        offset=offset,
        sessions=history["sessions"],
        stats={
            "total_sessions": count_sessions(),
            "total_messages": count_messages(),
            "filter_intent":  intent,
        },
        brain=get_brain_meta(),
    )


# ---------------------------------------------------------------------------
# GET /aurora/chat/session
# ---------------------------------------------------------------------------


@router.get(
    "/chat/session",
    response_model=SessionResponse,
    summary="Session Messages",
)
async def chat_session(
    session_id: str = Query(..., description="Session ID returned by POST /aurora/chat"),
    limit:  int     = Query(50, ge=1, le=200),
    offset: int     = Query(0,  ge=0),
) -> SessionResponse:
    """
    Return all messages for a specific conversation session.

    Pass the `session_id` returned by `POST /aurora/chat` to continue
    or review a previous conversation.

    Messages are returned in chronological order (oldest first).
    Alternating `user` → `aurora` roles reconstruct the full conversation.
    """
    session = get_session(session_id)
    if not session:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. "
                   "Start a new conversation via POST /aurora/chat.",
        )

    messages = get_session_messages(session_id, limit=limit, offset=offset)
    total = session.get("message_count", len(messages))

    return SessionResponse(
        session=session,
        messages=[
            SessionMessage(
                id=m["id"],
                session_id=m["session_id"],
                role=m["role"],
                content=m["content"],
                intent=m.get("intent"),
                entities=m.get("entities") or {},
                created_at=m["created_at"],
            )
            for m in messages
        ],
        total=total,
        brain=get_brain_meta(),
    )
