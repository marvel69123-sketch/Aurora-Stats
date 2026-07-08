import { useCallback, useEffect, useRef, useState } from "react";
import type { CopilotResponse, Message, Session } from "@/types/chat";

const STORAGE_KEY = "aurora_chat_sessions";
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

function now(): string {
  return new Date().toISOString();
}

function loadSessions(): Session[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as Session[];
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

async function callCopilot(message: string): Promise<CopilotResponse> {
  const res = await fetch(`${BASE}/aurora/copilot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(
      typeof err.detail === "string" ? err.detail : `HTTP ${res.status}`
    );
  }
  return res.json() as Promise<CopilotResponse>;
}

export function useChat() {
  const [sessions, setSessions] = useState<Session[]>(() => loadSessions());
  const [activeId, setActiveId] = useState<string | null>(
    () => loadSessions()[0]?.id ?? null
  );
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Persist on every change
  useEffect(() => {
    saveSessions(sessions);
  }, [sessions]);

  const activeSession = sessions.find((s) => s.id === activeId) ?? null;

  const createSession = useCallback((): string => {
    const id = uid();
    const session: Session = {
      id,
      title: "Nova conversa",
      messages: [],
      createdAt: now(),
      lastActive: now(),
    };
    setSessions((prev) => [session, ...prev]);
    setActiveId(id);
    return id;
  }, []);

  const selectSession = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const deleteSession = useCallback(
    (id: string) => {
      setSessions((prev) => {
        const next = prev.filter((s) => s.id !== id);
        if (activeId === id) {
          setActiveId(next[0]?.id ?? null);
        }
        return next;
      });
    },
    [activeId]
  );

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;

      let sessionId = activeId;
      if (!sessionId) {
        sessionId = uid();
        const newSession: Session = {
          id: sessionId,
          title: text.slice(0, 60) + (text.length > 60 ? "…" : ""),
          messages: [],
          createdAt: now(),
          lastActive: now(),
        };
        setSessions((prev) => [newSession, ...prev]);
        setActiveId(sessionId);
      }

      const userMsgId = uid();
      const auroraPlaceholderId = uid();

      // Add user message + loading aurora placeholder
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== sessionId) return s;
          const title =
            s.messages.length === 0
              ? text.slice(0, 60) + (text.length > 60 ? "…" : "")
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
        })
      );

      setLoading(true);
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      try {
        const response = await callCopilot(text);

        setSessions((prev) =>
          prev.map((s) => {
            if (s.id !== sessionId) return s;
            return {
              ...s,
              lastActive: now(),
              messages: s.messages.map((m) =>
                m.id === auroraPlaceholderId
                  ? { ...m, loading: false, response }
                  : m
              ),
            };
          })
        );
      } catch (err) {
        const errorMsg =
          err instanceof Error ? err.message : "Unknown error. Please try again.";
        setSessions((prev) =>
          prev.map((s) => {
            if (s.id !== sessionId) return s;
            return {
              ...s,
              messages: s.messages.map((m) =>
                m.id === auroraPlaceholderId
                  ? { ...m, loading: false, error: errorMsg }
                  : m
              ),
            };
          })
        );
      } finally {
        setLoading(false);
      }
    },
    [activeId, loading]
  );

  return {
    sessions,
    activeId,
    activeSession,
    loading,
    createSession,
    selectSession,
    deleteSession,
    sendMessage,
  };
}
