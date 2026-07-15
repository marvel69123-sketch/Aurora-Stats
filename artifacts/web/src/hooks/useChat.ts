import { useCallback, useEffect, useRef, useState } from "react";
import { generateConversationTitle } from "@/lib/conversationTitle";
import {
  applyLiveToMatchCard,
  buildLiveCacheFromFixture,
  buildLiveStatsView,
  extractFixtureIdHint,
  fetchLiveFixtures,
  resolveLiveFixture,
} from "@/lib/liveMatch";
import type { CopilotResponse, LiveFixtureCache, Message, Session } from "@/types/chat";

const STORAGE_KEY = "aurora_chat_sessions";
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
/** Soft FE guard — late context follow-ups (does not change FollowUp engine). */
const LATE_FOLLOWUP_MS = 2 * 60 * 60 * 1000;

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

function migrateMessage(m: Message): Message {
  return {
    ...m,
    // Prevent sticky "Atualizando…" after crash / multi-tab race
    refreshing: false,
  };
}

function migrateSession(raw: Session): Session {
  return {
    ...raw,
    pinned: Boolean(raw.pinned),
    titleLocked: Boolean(raw.titleLocked),
    title: raw.title || "Nova conversa",
    messages: Array.isArray(raw.messages)
      ? raw.messages.map((m) => migrateMessage(m as Message))
      : [],
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

function isLiveIdentityMessage(m: Message): boolean {
  if (m.role !== "aurora" || !m.response?.match_card) return false;
  if (m.response.match_card.is_live) return true;
  if (m.liveFixtureId && m.liveFixtureId > 0) return true;
  if (m.liveCache?.lastFixtureId && m.liveCache.lastFixtureId > 0) return true;
  return false;
}

function isLateContextQuery(text: string): boolean {
  const t = text.trim().toLowerCase();
  return /^(e agora\??|como est[aá]\??|atualiz(?:e|ar)?(?:\s+novamente)?(?:\s+a\s+partida)?|ainda vale\??|ainda v[aá]lido\??)$/i.test(
    t,
  );
}

function messageAgeMs(m: Message): number | null {
  const stamp = m.refreshedAt || m.response?.generated_at || m.createdAt;
  if (!stamp) return null;
  const t = Date.parse(stamp);
  if (!Number.isFinite(t)) return null;
  return Math.max(0, Date.now() - t);
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

  // Multi-tab: keep in-memory sessions aligned with localStorage writes from other tabs
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== STORAGE_KEY || e.newValue == null) return;
      try {
        const parsed = JSON.parse(e.newValue) as Session[];
        if (!Array.isArray(parsed)) return;
        setSessions(sortSessions(parsed.map(migrateSession)));
      } catch {
        // ignore corrupt payloads from other tabs
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

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

    // FE intercept: live refresh by identity (live OR locked fixture) — avoid FollowUp wipe
    if (/^atualiza(?:r)?\s+(?:a\s+)?partida\s*$/i.test(text.trim())) {
      const sessionId = activeId;
      const session = sessionId
        ? sessionsRef.current.find((s) => s.id === sessionId)
        : null;
      const liveMsg = [...(session?.messages ?? [])]
        .reverse()
        .find(isLiveIdentityMessage);
      if (liveMsg) {
        await refreshLiveMatchRef.current(liveMsg.id);
        return;
      }
    }

    // Soft late-context guard (>2h) — friendly FE reply, no MatchHeader wipe
    if (isLateContextQuery(text) && activeId) {
      const session = sessionsRef.current.find((s) => s.id === activeId);
      const lastAurora = [...(session?.messages ?? [])]
        .reverse()
        .find((m) => m.role === "aurora" && m.response);
      const age = lastAurora ? messageAgeMs(lastAurora) : null;
      if (age != null && age > LATE_FOLLOWUP_MS) {
        const userMsgId = uid();
        const auroraId = uid();
        const soft: CopilotResponse = {
          intent: "follow_up",
          entities: { late_context: true },
          request_id: uid(),
          generated_at: now(),
          match: lastAurora?.response?.match ?? null,
          status: lastAurora?.response?.status ?? null,
          is_live: false,
          minute: lastAurora?.response?.minute ?? null,
          match_card: lastAurora?.response?.match_card
            ? { ...lastAurora.response.match_card, is_live: false }
            : null,
          fixture_quality: lastAurora?.response?.fixture_quality ?? null,
          fixture_status: lastAurora?.response?.fixture_status ?? null,
          executive_summary:
            "Este contexto tem mais de 2 horas. Peça uma nova análise da partida para dados atualizados.",
          best_markets: [],
          confidence: {
            score: 0,
            label: "indisponível",
            explanation: "",
            data_sources: [],
          },
          risk: { level: "Unknown", flags: [], invalidation_conditions: [] },
          bankroll_recommendation: {
            recommended_stake_pct: 0,
            method: "",
            examples: {},
            reasoning: "",
            no_bet: true,
          },
          positive_factors: [],
          negative_factors: [],
          historical_references: [],
          knowledge_notes: [],
          final_recommendation:
            "Contexto antigo — solicite uma nova análise para continuar com segurança.",
          aurora_version: lastAurora?.response?.aurora_version ?? "Aurora",
          brain: {},
        };
        setSessions((prev) =>
          sortSessions(
            prev.map((s) => {
              if (s.id !== activeId) return s;
              return {
                ...s,
                lastActive: now(),
                messages: [
                  ...s.messages,
                  {
                    id: userMsgId,
                    role: "user",
                    userText: text.trim(),
                    createdAt: now(),
                  } satisfies Message,
                  {
                    id: auroraId,
                    role: "aurora",
                    userText: "",
                    response: soft,
                    createdAt: now(),
                    // Preserve prior live identity on the soft reply? Better leave empty —
                    // MatchHeader comes from soft.match_card copy above.
                  } satisfies Message,
                ],
              };
            }),
          ),
        );
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
        err instanceof Error ? err.message : "Erro desconhecido. Tente novamente.";
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
   * Live refresh — fixture_id → liveCache → nome (último recurso).
   * Never silent re-analyze. Never wipe to INVALID.
   */
  const refreshLiveMatch = useCallback(async (messageId: string) => {
    const sessionId = activeId;
    if (!sessionId) return;

    // Multi-tab: prefer latest persisted snapshot before mutating
    const latest = sortSessions(loadSessions());
    sessionsRef.current = latest;

    const session = latest.find((s) => s.id === sessionId);
    const msg = session?.messages.find((m) => m.id === messageId);
    const card = msg?.response?.match_card;
    if (!msg?.response || !card?.home?.name || !card?.away?.name) {
      return;
    }
    const lockedId = extractFixtureIdHint({
      liveFixtureId: msg.liveFixtureId,
      liveStats: msg.liveStats,
      liveCache: msg.liveCache,
      response: msg.response,
    });
    if (!card.is_live && !lockedId) return;
    if (msg.refreshing) return;

    setSessions(() =>
      patchMessage(sortSessions(loadSessions()), sessionId, messageId, (m) => ({
        ...m,
        refreshing: true,
        liveStatusNote: null,
        error: undefined,
      })),
    );

    const home = card.home.name;
    const away = card.away.name;
    const cache = msg.liveCache ?? null;
    const hasIdentity = Boolean(lockedId || cache?.lastFixtureId);

    try {
      const fixtures = await fetchLiveFixtures();
      const live = resolveLiveFixture(fixtures, {
        fixtureId: lockedId,
        homeName: home,
        awayName: away,
        // Once identity is known, never rematch by free text.
        idOnly: hasIdentity,
        cache,
      });

      if (live) {
        const nextCard = applyLiveToMatchCard(card, live);
        const liveStats = buildLiveStatsView(live);
        const liveCache: LiveFixtureCache = buildLiveCacheFromFixture(live, nextCard);
        const stamped = now();
        setSessions(() =>
          patchMessage(sortSessions(loadSessions()), sessionId, messageId, (m) => {
            if (!m.response) return { ...m, refreshing: false };
            return {
              ...m,
              refreshing: false,
              refreshedAt: stamped,
              liveFixtureId: live.fixture_id,
              liveCache,
              liveStats,
              liveStatusNote: null,
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
        return;
      }

      // Not in live feed — keep MatchHeader/context; never INVALID.
      // Clear liveStats so stale statistics are never reused.
      setSessions(() =>
        patchMessage(sortSessions(loadSessions()), sessionId, messageId, (m) => {
          if (!m.response) return { ...m, refreshing: false };
          const prevCard = m.response.match_card;
          return {
            ...m,
            refreshing: false,
            refreshedAt: now(),
            liveStats: null,
            liveStatusNote:
              "Partida encerrada ou não está mais ao vivo.",
            response: {
              ...m.response,
              is_live: false,
              match_card: prevCard
                ? { ...prevCard, is_live: false }
                : prevCard,
            },
          };
        }),
      );
    } catch {
      // Never keep stale liveStats after a failed refresh — credibility first.
      setSessions(() =>
        patchMessage(sortSessions(loadSessions()), sessionId, messageId, (m) => ({
          ...m,
          refreshing: false,
          liveStats: null,
          liveStatusNote: "⚠️ Dados temporariamente indisponíveis.",
        })),
      );
    }
  }, [activeId]);

  /** Lock fixture identity as soon as /live matches (before first refresh). */
  const lockLiveContext = useCallback(
    (messageId: string, cache: LiveFixtureCache, stats?: Message["liveStats"]) => {
      const sessionId = activeId;
      if (!sessionId || !cache.lastFixtureId) return;
      setSessions(() =>
        patchMessage(sortSessions(loadSessions()), sessionId, messageId, (m) => {
          if (m.liveFixtureId && m.liveFixtureId === cache.lastFixtureId) {
            return {
              ...m,
              liveCache: m.liveCache ?? cache,
              liveStats: stats ?? m.liveStats,
            };
          }
          return {
            ...m,
            liveFixtureId: cache.lastFixtureId,
            liveCache: cache,
            liveStats: stats ?? m.liveStats,
          };
        }),
      );
    },
    [activeId],
  );

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
    lockLiveContext,
  };
}
