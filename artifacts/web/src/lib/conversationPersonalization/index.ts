/**
 * Aurora v3.6.0 — Conversation Personalization foundation (FE-only).
 *
 * Sacred rules:
 * - Never alter engines / payloads / frozen Premium Live surfaces.
 * - Personalization changes presentation only.
 * - Feature flag defaults to false (inactive until explicitly enabled).
 * - Casual failures fall back to Technical.
 */

export { conversationPersonalizationEnabled } from "./flags";
export { DEFAULT_CONVERSATION_PREFERENCES } from "./defaults";
export type {
  ConversationPreferences,
  ConversationProfileId,
  ConversationProfileMeta,
  DetailLevel,
  EmojiLevel,
  EnthusiasmLevel,
  FollowUpPresentationHints,
  HeadersListsLevel,
  PresentationSnapshot,
  StructureLevel,
} from "./types";
export {
  CONVERSATION_PREFS_STORAGE_KEY,
  loadConversationPreferences,
  saveConversationPreferences,
  sanitizePreferences,
  snapshotFromPreferences,
} from "./storage";
export {
  CONVERSATION_PROFILES,
  CONVERSATION_PROFILE_LIST,
  getProfileMeta,
} from "./profiles";
export { applyPresentation } from "./formatters/apply";
export { formatTechnical } from "./formatters/technical";
export { formatCasual } from "./formatters/casual";
export { getFollowUpPresentationHints } from "./followUpPrep";
export { chromeHeading, showChromeHeader, chromeTitleClass, chromeInlineMarker, isTechnicalReportLayout } from "./visualChrome";
export type { ChromeKind } from "./visualChrome";
export {
  ConversationPreferencesContext,
  useConversationPreferencesContext,
} from "./PreferencesContext";
