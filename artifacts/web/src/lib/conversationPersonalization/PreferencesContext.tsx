import { createContext, useContext } from "react";
import {
  DEFAULT_CONVERSATION_PREFERENCES,
  type ConversationPreferences,
} from "@/lib/conversationPersonalization";

/** Presentation chrome prefs only — never fed to engines. */
export const ConversationPreferencesContext =
  createContext<ConversationPreferences>(DEFAULT_CONVERSATION_PREFERENCES);

export function useConversationPreferencesContext(): ConversationPreferences {
  return useContext(ConversationPreferencesContext);
}
