import { casualProfile } from "./casual";
import { technicalProfile } from "./technical";
import type { ConversationProfileId, ConversationProfileMeta } from "../types";

/**
 * Extensible registry. Future profiles go here — do not implement yet.
 * conversation_profiles/ → technical | casual | future...
 */
export const CONVERSATION_PROFILES: Record<
  ConversationProfileId,
  ConversationProfileMeta
> = {
  technical: technicalProfile,
  casual: casualProfile,
};

export const CONVERSATION_PROFILE_LIST: ConversationProfileMeta[] = [
  technicalProfile,
  casualProfile,
];

export function getProfileMeta(
  id: ConversationProfileId,
): ConversationProfileMeta {
  return CONVERSATION_PROFILES[id] ?? technicalProfile;
}
