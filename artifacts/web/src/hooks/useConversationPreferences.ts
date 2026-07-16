import { useCallback, useEffect, useState } from "react";
import {
  CONVERSATION_PREFS_STORAGE_KEY,
  conversationPersonalizationEnabled,
  loadConversationPreferences,
  saveConversationPreferences,
  sanitizePreferences,
  type ConversationPreferences,
} from "@/lib/conversationPersonalization";

/**
 * Loads/saves conversation presentation prefs (localStorage).
 * Safe to call when flag is false — still no-ops for UI consumers that gate on the flag.
 */
export function useConversationPreferences() {
  const [prefs, setPrefsState] = useState<ConversationPreferences>(() =>
    loadConversationPreferences(),
  );

  useEffect(() => {
    // Multi-tab sync
    const onStorage = (e: StorageEvent) => {
      if (e.key !== CONVERSATION_PREFS_STORAGE_KEY) return;
      setPrefsState(loadConversationPreferences());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const setPreferences = useCallback((next: ConversationPreferences) => {
    const safe = sanitizePreferences(next);
    setPrefsState(safe);
    saveConversationPreferences(safe);
  }, []);

  const patchPreferences = useCallback(
    (patch: Partial<ConversationPreferences>) => {
      setPrefsState((prev) => {
        const merged = sanitizePreferences({ ...prev, ...patch });
        saveConversationPreferences(merged);
        return merged;
      });
    },
    [],
  );

  return {
    enabled: conversationPersonalizationEnabled,
    preferences: prefs,
    setPreferences,
    patchPreferences,
  };
}
