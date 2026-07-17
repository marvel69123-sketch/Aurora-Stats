/**
 * Aurora Identity Center — About You profile (local, no login).
 * Separate from frozen conversationPersonalization module.
 */

export interface AboutYouProfile {
  name: string;
  role: string;
  favorite_team: string;
  project: string;
}

export const EMPTY_ABOUT_YOU: AboutYouProfile = {
  name: "",
  role: "",
  favorite_team: "",
  project: "",
};

export const ABOUT_YOU_STORAGE_KEY = "aurora_about_you_v1";

export function sanitizeAboutYou(raw: unknown): AboutYouProfile {
  const base = { ...EMPTY_ABOUT_YOU };
  if (!raw || typeof raw !== "object") return base;
  const o = raw as Record<string, unknown>;
  for (const k of Object.keys(base) as (keyof AboutYouProfile)[]) {
    if (typeof o[k] === "string") {
      base[k] = o[k].trim().slice(0, 80);
    }
  }
  return base;
}

export function loadAboutYou(): AboutYouProfile {
  try {
    const raw = localStorage.getItem(ABOUT_YOU_STORAGE_KEY);
    if (!raw) return { ...EMPTY_ABOUT_YOU };
    return sanitizeAboutYou(JSON.parse(raw));
  } catch {
    return { ...EMPTY_ABOUT_YOU };
  }
}

export function saveAboutYou(profile: AboutYouProfile): void {
  try {
    localStorage.setItem(
      ABOUT_YOU_STORAGE_KEY,
      JSON.stringify(sanitizeAboutYou(profile)),
    );
  } catch {
    /* ignore quota */
  }
}

export function clearAboutYou(): AboutYouProfile {
  const empty = { ...EMPTY_ABOUT_YOU };
  try {
    localStorage.setItem(ABOUT_YOU_STORAGE_KEY, JSON.stringify(empty));
  } catch {
    /* ignore */
  }
  return empty;
}

export function aboutYouHasAny(p: AboutYouProfile): boolean {
  return Boolean(p.name || p.role || p.favorite_team || p.project);
}
