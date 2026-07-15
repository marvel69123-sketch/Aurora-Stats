import { useCallback, useEffect, useRef, useState } from "react";
import { generateConversationTitle } from "@/lib/conversationTitle";
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
  // Temporary audit: stamp JS bundle id when API cannot see the static build file.
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
  // If backend is old and omitted debug but user asked #debug, still flag for UI
  if (
    (isDebugMode() || messageRequestsDebug(message)) &&
    !data.debug
  ) {
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

export function useChat() {
  const [sessions, setSessions] = useState<Session[]>(() => sortSessions(loadSessions()));
  const [activeId, setActiveId] = useState<string | null>(
    () => loadSessions()[0]?.id ?? null,
  );
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const sessionsRef = useRef(sessions);
  sessionsRef.current = sessions;

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
            // Prefer match name from API for auto title on first reply
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
  };
}
