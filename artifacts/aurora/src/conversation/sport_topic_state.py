"""
LANGGRAPH-STATE-POC-001 — SportTopicState (SSOT shape for conversational sport subject).

Phase 1: model + helpers only. Does NOT replace CSL/SRF/short_mem writers in
production.

Flags (independent):
  - ENABLE_LANGGRAPH_STATE (default OFF) — production LangGraph write path (Phase 3+).
  - ENABLE_LANGGRAPH_STATE_SHADOW (default OFF) — Phase 2 log-only OLD vs NEW compare.
    Shadow ≠ production activation. Enabling shadow does NOT enable the write path.

Never invents fixtures/odds. Engines and Response Selector untouched.
"""

from __future__ import annotations

import copy
import os
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

_FLAG_ENV = "ENABLE_LANGGRAPH_STATE"
_SHADOW_FLAG_ENV = "ENABLE_LANGGRAPH_STATE_SHADOW"


def _flag_truthy(env_name: str) -> bool:
    """Same parse pattern as topic_boundary_v2: off unless 1/true/on/yes."""
    raw = (os.environ.get(env_name) or "0").strip().lower()
    return raw in {"1", "true", "on", "yes"}


def langgraph_state_enabled() -> bool:
    """Production write-path gate. Default OFF. Independent of shadow."""
    return _flag_truthy(_FLAG_ENV)


def langgraph_state_shadow_enabled() -> bool:
    """
    Phase 2 shadow compare gate. Default OFF.

    When ON: read-only / side-effect-log-only OLD_STATE vs NEW_STATE compare.
    Does NOT activate ENABLE_LANGGRAPH_STATE or any production writer.
    """
    return _flag_truthy(_SHADOW_FLAG_ENV)

@dataclass
class SportTopicState:
    """
    Canonical sport conversational subject snapshot (design SSOT).

    Phase 1 holds this in-memory / in the LangGraph host; production ctx
    writers remain multi-owner until later phases.
    """

    episode_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    fixture: str | None = None
    teams: list[str] = field(default_factory=list)
    subject: str | None = None
    topic: str | None = None
    owner: str | None = None
    date_context: str | None = None
    followup_context: dict[str, Any] = field(default_factory=dict)
    boundary_reason: str | None = None

    def snapshot(self) -> dict[str, Any]:
        """Read-only deep copy of the state dict."""
        return copy.deepcopy(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["teams"] = list(self.teams)[:4]
        d["followup_context"] = dict(self.followup_context or {})
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SportTopicState:
        data = dict(data or {})
        teams = data.get("teams") or []
        if not isinstance(teams, list):
            teams = []
        clean = [str(t).strip() for t in teams if isinstance(t, str) and t.strip()][:4]
        fu = data.get("followup_context")
        if not isinstance(fu, dict):
            fu = {}
        return cls(
            episode_id=str(data.get("episode_id") or uuid.uuid4()),
            fixture=data.get("fixture") if isinstance(data.get("fixture"), str) else None,
            teams=clean,
            subject=data.get("subject") if isinstance(data.get("subject"), str) else None,
            topic=data.get("topic") if isinstance(data.get("topic"), str) else None,
            owner=data.get("owner") if isinstance(data.get("owner"), str) else None,
            date_context=(
                data.get("date_context")
                if isinstance(data.get("date_context"), str)
                else None
            ),
            followup_context=dict(fu),
            boundary_reason=(
                data.get("boundary_reason")
                if isinstance(data.get("boundary_reason"), str)
                else None
            ),
        )

    def clear_for_new_episode(
        self,
        *,
        reason: str = "new_episode",
        seed_teams: list[str] | None = None,
        seed_fixture: str | None = None,
    ) -> SportTopicState:
        """
        Rotate episode_id and replace subject slots (no prior preserve).
        Mutates self; returns self for chaining.
        """
        teams = [str(t).strip() for t in (seed_teams or []) if isinstance(t, str) and t.strip()][
            :4
        ]
        fixture = seed_fixture if isinstance(seed_fixture, str) and seed_fixture.strip() else None
        if not fixture and len(teams) >= 2:
            fixture = f"{teams[0]} x {teams[1]}"
        topic = "comparison" if len(teams) >= 2 else ("calendar" if teams else None)
        subject = fixture or (teams[0] if teams else None)
        self.episode_id = str(uuid.uuid4())
        self.teams = teams
        self.fixture = fixture
        self.subject = subject
        self.topic = topic
        self.boundary_reason = reason
        self.followup_context = {}
        self.date_context = None
        # owner lock is external (OS module); clear STS projection only
        self.owner = None
        return self

    def replace_subject(
        self,
        *,
        teams: list[str] | None = None,
        fixture: str | None = None,
        topic: str | None = None,
        subject: str | None = None,
        date_context: str | None = None,
        keep_episode: bool = True,
    ) -> SportTopicState:
        """
        Replace subject fields. By default keeps episode_id (same episode refresh).
        Mutates self; returns self for chaining.
        """
        if teams is not None:
            self.teams = [
                str(t).strip() for t in teams if isinstance(t, str) and t.strip()
            ][:4]
        if fixture is not None:
            self.fixture = fixture.strip() if isinstance(fixture, str) and fixture.strip() else None
        if topic is not None:
            self.topic = topic
        if subject is not None:
            self.subject = subject
        elif self.fixture:
            self.subject = self.fixture
        elif self.teams:
            self.subject = self.teams[0]
        if date_context is not None:
            self.date_context = date_context
        if not keep_episode:
            self.episode_id = str(uuid.uuid4())
        if self.topic is None and self.teams:
            self.topic = "comparison" if len(self.teams) >= 2 else "calendar"
        return self
