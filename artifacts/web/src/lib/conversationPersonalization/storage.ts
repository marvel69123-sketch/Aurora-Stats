import { DEFAULT_CONVERSATION_PREFERENCES } from "./defaults";
import type { ConversationPreferences, PresentationSnapshot } from "./types";

export const CONVERSATION_PREFS_STORAGE_KEY =
  "aurora_conversation_preferences_v1";

const STORAGE_KEY = CONVERSATION_PREFS_STORAGE_KEY;

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function pickEnum<T extends string>(
  value: unknown,
  allowed: readonly T[],
  fallback: T,
): T {
  return typeof value === "string" && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : fallback;
}

/** Sanitize any JSON into a valid preferences object (fallback-safe). */
export function sanitizePreferences(raw: unknown): ConversationPreferences {
  const base = DEFAULT_CONVERSATION_PREFERENCES;
  if (!isRecord(raw)) return { ...base };

  return {
    profile: pickEnum(raw.profile, ["technical", "casual"] as const, base.profile),
    emojis: pickEnum(
      raw.emojis,
      ["none", "low", "medium", "high"] as const,
      base.emojis,
    ),
    enthusiasm: pickEnum(
      raw.enthusiasm,
      ["low", "medium", "high"] as const,
      base.enthusiasm,
    ),
    structure: pickEnum(
      raw.structure,
      ["conversational", "balanced", "technical"] as const,
      base.structure,
    ),
    headersLists: pickEnum(
      raw.headersLists,
      ["few", "normal", "many"] as const,
      base.headersLists,
    ),
    detail: pickEnum(
      raw.detail,
      ["short", "normal", "detailed"] as const,
      base.detail,
    ),
  };
}

export function loadConversationPreferences(): ConversationPreferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_CONVERSATION_PREFERENCES };
    return sanitizePreferences(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_CONVERSATION_PREFERENCES };
  }
}

export function saveConversationPreferences(
  prefs: ConversationPreferences,
): void {
  try {
    const safe = sanitizePreferences(prefs);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(safe));
  } catch {
    // private mode / quota — ignore; in-memory prefs still work
  }
}

export function snapshotFromPreferences(
  prefs: ConversationPreferences,
): PresentationSnapshot {
  const safe = sanitizePreferences(prefs);
  return {
    ...safe,
    capturedAt: Date.now(),
  };
}
