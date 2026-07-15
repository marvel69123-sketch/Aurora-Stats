import { useCallback, useEffect, useRef, useState } from "react";
import { generateConversationTitle } from "@/lib/conversationTitle";
import {
  applyLiveToMatchCard,
  buildLiveStatsView,
  fetchLiveFixtures,
  findLiveFixture,
} from "@/lib/liveMatch";
import type { CopilotResponse, Message, Session } from "@/types/chat";

const STORAGE_KEY = "aurora_chat_sessions";
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

function isDebugMode(): boolean {
  try {
    if (typeof window === "undefined") return false;
    const q = new URLSearchParams(window.location.search);
    if (q.get("debug") === "1" || q.get("debug") === "true") return true;
    if (localStorage.getItem("aurora_debug") === "1") return true;
  } catch {
    // ignore
  }
  return import.meta.env.DEV === true && import.meta.env.VITE_AURORA_DEBUG === "1";
}

function messageRequestsDebug(message: string): boolean {
  const msg = message.toLowerCase();
  return msg.includes("#debug") || msg.includes("modo debug");
}

function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

function now(): string {
  return new Date().toISOString();
}

function migrateSession(raw: Session): Session {
  return {
    ...raw,
    pinned: Boolean(raw.pinned),
    titleLocked: Boolean(raw.titleLocked),
    title: raw.title || "Nova conversa",
    messages: Array.isArray(raw.messages) ? raw.messages : [],
  };
}

function loadSessions(): Session[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Session[];
    if (!Array.isArray(parsed)) return [];
    return parsed.map(migrateSession);
  } catch {
    return [];
  }
}

function saveSessions(sessions: Session[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // ignore storage errors
  }
}

function sortSessions(sessions: Session[]): Session[] {
  return [...sessions].sort((a, b) => {
    if (Boolean(a.pinned) !== Boolean(b.pinned)) return a.pinned ? -1 : 1;
    return new Date(b.lastActive).getTime() - new Date(a.lastActive).getTime();
  });
}

async function callCopilot(
  message: string,
  backendSessionId?: string,
): Promise<CopilotResponse> {
  const res = await fetch(`${BASE}/aurora/copilot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      ...(backendSessionId ? { session_id: backendSessionId } : {}),
      ...(isDebugMode() || messageRequestsDebug(message) ? { debug: true } : {}),
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(
      typeof err.detail === "string" ? err.detail : `HTTP ${res.status}`,
    );
  }
  const data = (await res.json()) as CopilotResponse;
  const bundleId =
    typeof __AURORA_UI_BUILD__ === "string" && __AURORA_UI_BUILD__
      ? __AURORA_UI_BUILD__
      : null;
  if (
    bundleId &&
    (!data.frontend_commit ||
      data.frontend_commit === "unknown" ||
      data.frontend_commit === "DATA_MISSING")
  ) {
    data.frontend_commit = bundleId;
  }
  if ((isDebugMode() || messageRequestsDebug(message)) && !data.debug) {
    data.debug = {
      fixture_quality: data.fixture_quality ?? "DATA_MISSING",
      market_generation_enabled:
        typeof data.entities?.market_generation_enabled === "boolean"
          ? data.entities.market_generation_enabled
          : "DATA_MISSING",
      fixture_found:
        typeof data.fixture_found === "boolean"
          ? data.fixture_found
          : "DATA_MISSING",
    };
  }
  return data;
}

function patchMessage(
  sessions: Session[],
  sessionId: string,
  messageId: string,
  patch: (m: Message) => Message,
): Session[] {
  return sortSessions(
    sessions.map((s) => {
      if (s.id !== sessionId) return s;
      return {
        ...s,
        lastActive: now(),
        messages: s.messages.map((m) => (m.id === messageId ? patch(m) : m)),
      };
    }),
  );
}

export function useChat() {
  const [sessions, setSessions] = useState<Session[]>(() => sortSessions(loadSessions()));
  const [activeId, setActiveId] = useState<string | null>(
    () => loadSessions()[0]?.id ?? null,
  );
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const sessionsRef = useRef(sessions);
  sessionsRef.current = sessions;
  const refreshLiveMatchRef = useRef<(messageId: string) => Promise<void>>(
    async () => undefined,
  );

  useEffect(() => {
    saveSessions(sessions);
  }, [sessions]);

  const activeSession = sessions.find((s) => s.id === activeId) ?? null;

  const createSession = useCallback((): string => {
    const id = uid();
    const session: Session = {
      id,
      title: "Nova conversa",
      titleLocked: false,
      pinned: false,
      messages: [],
      createdAt: now(),
      lastActive: now(),
    };
    setSessions((prev) => sortSessions([session, ...prev]));
    setActiveId(id);
    return id;
  }, []);

  const selectSession = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const deleteSession = useCallback((id: string) => {
    setSessions((prev) => {
      const next = sortSessions(prev.filter((s) => s.id !== id));
      setActiveId((cur) => (cur === id ? (next[0]?.id ?? null) : cur));
      return next;
    });
  }, []);

  const renameSession = useCallback((id: string, title: string) => {
    const cleaned = title.trim() || "Nova conversa";
    setSessions((prev) =>
      sortSessions(
        prev.map((s) =>
          s.id === id
            ? { ...s, title: cleaned, titleLocked: true, lastActive: now() }
            : s,
        ),
      ),
    );
  }, []);

  const togglePinSession = useCallback((id: string) => {
    setSessions((prev) =>
      sortSessions(
        prev.map((s) =>
          s.id === id ? { ...s, pinned: !s.pinned, lastActive: now() } : s,
        ),
      ),
    );
  }, []);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;

    // FE intercept: avoid FollowUp live_update snapshot (stale minute).
    if (/^atualiza(?:r)?\s+(?:a\s+)?partida\s*$/i.test(text.trim())) {
      const sessionId = activeId;
      const session = sessionId
        ? sessionsRef.current.find((s) => s.id === sessionId)
        : null;
      const liveMsg = [...(session?.messages ?? [])]
        .reverse()
        .find((m) => m.role === "aurora" && m.response?.match_card?.is_live);
      if (liveMsg) {
        await refreshLiveMatchRef.current(liveMsg.id);
        return;
      }
    }

    let sessionId = activeId;
    if (!sessionId) {
      sessionId = uid();
      const newSession: Session = {
        id: sessionId,
        title: generateConversationTitle(text),
        titleLocked: false,
        pinned: false,
        messages: [],
        createdAt: now(),
        lastActive: now(),
      };
      setSessions((prev) => sortSessions([newSession, ...prev]));
      setActiveId(sessionId);
    }

    const userMsgId = uid();
    const auroraPlaceholderId = uid();
    const currentBackendId = sessionsRef.current.find(
      (s) => s.id === sessionId,
    )?.backendSessionId;

    setSessions((prev) =>
      sortSessions(
        prev.map((s) => {
          if (s.id !== sessionId) return s;
          const title =
            s.messages.length === 0 && !s.titleLocked
              ? generateConversationTitle(text)
              : s.title;
          return {
            ...s,
            title,
            lastActive: now(),
            messages: [
              ...s.messages,
              {
                id: userMsgId,
                role: "user",
                userText: text,
                createdAt: now(),
              } satisfies Message,
              {
                id: auroraPlaceholderId,
                role: "aurora",
                userText: "",
                loading: true,
                createdAt: now(),
              } satisfies Message,
            ],
          };
        }),
      ),
    );

    setLoading(true);
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      const response = await callCopilot(text, currentBackendId);

      setSessions((prev) =>
        sortSessions(
          prev.map((s) => {
            if (s.id !== sessionId) return s;
            let title = s.title;
            if (
              !s.titleLocked &&
              s.messages.filter((m) => m.role === "user").length <= 1 &&
              response.match
            ) {
              const live = response.is_live ? " ao vivo" : "";
              title = generateConversationTitle(`${response.match}${live}`);
            }
            return {
              ...s,
              title,
              lastActive: now(),
              ...(response.session_id
                ? { backendSessionId: response.session_id }
                : {}),
              messages: s.messages.map((m) =>
                m.id === auroraPlaceholderId
                  ? { ...m, loading: false, response }
                  : m,
              ),
            };
          }),
        ),
      );
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Unknown error. Please try again.";
      setSessions((prev) =>
        sortSessions(
          prev.map((s) => {
            if (s.id !== sessionId) return s;
            return {
              ...s,
              messages: s.messages.map((m) =>
                m.id === auroraPlaceholderId
                  ? { ...m, loading: false, error: errorMsg }
                  : m,
              ),
            };
          }),
        ),
      );
    } finally {
      setLoading(false);
    }
  }, [activeId, loading]);

  /**
   * Real live refresh (FE orchestration):
   * 1) GET /aurora/live → minute, score, stats, momentum (in-place)
   * 2) Silent re-analyze → markets / summary (existing copilot path; no FollowUp live_update)
   * Does not append chat bubbles.
   */
  const refreshLiveMatch = useCallback(async (messageId: string) => {
    const sessionId = activeId;
    if (!sessionId) return;

    const session = sessionsRef.current.find((s) => s.id === sessionId);
    const msg = session?.messages.find((m) => m.id === messageId);
    const card = msg?.response?.match_card;
    if (!msg?.response || !card?.is_live || !card.home?.name || !card.away?.name) {
      return;
    }
    if (msg.refreshing) return;

    setSessions((prev) =>
      patchMessage(prev, sessionId, messageId, (m) => ({ ...m, refreshing: true })),
    );

    const home = card.home.name;
    const away = card.away.name;
    const backendId = session?.backendSessionId;
    let liveApplied = false;

    try {
      const fixtures = await fetchLiveFixtures();
      const live = findLiveFixture(fixtures, home, away);
      if (live) {
        liveApplied = true;
        const nextCard = applyLiveToMatchCard(card, live);
        const liveStats = buildLiveStatsView(live);
        const stamped = now();
        setSessions((prev) =>
          patchMessage(prev, sessionId, messageId, (m) => {
            if (!m.response) return { ...m, refreshing: true };
            return {
              ...m,
              refreshedAt: stamped,
              liveStats,
              response: {
                ...m.response,
                match_card: nextCard,
                minute: nextCard.minute ?? m.response.minute,
                is_live: true,
                status: nextCard.status_label ?? m.response.status,
                match: m.response.match,
              },
            };
          }),
        );
      }
    } catch {
      // Live feed failed — still try silent re-analyze below
    }

    try {
      const fresh = await callCopilot(`Analisar ${home} x ${away}`, backendId);
      const stamped = now();
      setSessions((prev) =>
        patchMessage(prev, sessionId, messageId, (m) => {
          if (!m.response) return { ...m, refreshing: false };
          const prevCard = m.response.match_card;
          // Prefer live-updated clock/score when we already applied /live
          const mergedCard =
            liveApplied && prevCard
              ? {
                  ...(fresh.match_card ?? {}),
                  ...prevCard,
                  home: {
                    name: prevCard.home.name,
                    logo:
                      prevCard.home.logo ||
                      fresh.match_card?.home?.logo ||
                      null,
                  },
                  away: {
                    name: prevCard.away.name,
                    logo:
                      prevCard.away.logo ||
                      fresh.match_card?.away?.logo ||
                      null,
                  },
                  minute: prevCard.minute ?? fresh.match_card?.minute ?? null,
                  score: prevCard.score ?? fresh.match_card?.score ?? null,
                  is_live: true,
                  momentum:
                    prevCard.momentum ?? fresh.match_card?.momentum ?? null,
                }
              : fresh.match_card ?? prevCard;

          return {
            ...m,
            refreshing: false,
            refreshedAt: stamped,
            response: {
              ...m.response,
              ...fresh,
              session_id: fresh.session_id || m.response.session_id,
              match_card: mergedCard,
              minute: mergedCard?.minute ?? fresh.minute ?? m.response.minute,
              is_live: mergedCard?.is_live ?? fresh.is_live ?? m.response.is_live,
            },
          };
        }),
      );
      if (fresh.session_id) {
        setSessions((prev) =>
          sortSessions(
            prev.map((s) =>
              s.id === sessionId ? { ...s, backendSessionId: fresh.session_id } : s,
            ),
          ),
        );
      }
    } catch (err) {
      setSessions((prev) =>
        patchMessage(prev, sessionId, messageId, (m) => ({
          ...m,
          refreshing: false,
          // Keep live patch if it succeeded; surface soft error only if nothing worked
          ...(liveApplied
            ? {}
            : {
                error:
                  err instanceof Error
                    ? err.message
                    : "Não foi possível atualizar a partida.",
              }),
        })),
      );
    }
  }, [activeId]);

  refreshLiveMatchRef.current = refreshLiveMatch;

  return {
    sessions,
    activeId,
    activeSession,
    loading,
    createSession,
    selectSession,
    deleteSession,
    renameSession,
    togglePinSession,
    sendMessage,
    refreshLiveMatch,
  };
}
