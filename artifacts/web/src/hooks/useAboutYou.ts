import { useCallback, useEffect, useState } from "react";
import {
  type AboutYouProfile,
  ABOUT_YOU_STORAGE_KEY,
  clearAboutYou,
  loadAboutYou,
  saveAboutYou,
  sanitizeAboutYou,
} from "@/lib/auroraIdentity";

export function useAboutYou() {
  const [aboutYou, setAboutYouState] = useState<AboutYouProfile>(() =>
    loadAboutYou(),
  );

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === ABOUT_YOU_STORAGE_KEY) {
        setAboutYouState(loadAboutYou());
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const setAboutYou = useCallback((next: AboutYouProfile) => {
    const clean = sanitizeAboutYou(next);
    saveAboutYou(clean);
    setAboutYouState(clean);
  }, []);

  const clear = useCallback(() => {
    const empty = clearAboutYou();
    setAboutYouState(empty);
  }, []);

  return { aboutYou, setAboutYou, clear };
}
