import { useCallback, useEffect, useState } from "react";
import {
  fileToAvatarDataUrl,
  loadAuroraAvatar,
  saveAuroraAvatar,
} from "@/lib/avatarSettings";

export function useAuroraAvatar() {
  const [avatarUrl, setAvatarUrl] = useState<string | null>(() => loadAuroraAvatar());

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === "aurora_avatar_data_url") setAvatarUrl(e.newValue);
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const setFromFile = useCallback(async (file: File) => {
    const dataUrl = await fileToAvatarDataUrl(file);
    saveAuroraAvatar(dataUrl);
    setAvatarUrl(dataUrl);
    return dataUrl;
  }, []);

  const clear = useCallback(() => {
    saveAuroraAvatar(null);
    setAvatarUrl(null);
  }, []);

  return { avatarUrl, setFromFile, clear };
}
