const AVATAR_KEY = "aurora_avatar_data_url";

export function loadAuroraAvatar(): string | null {
  try {
    return localStorage.getItem(AVATAR_KEY);
  } catch {
    return null;
  }
}

export function saveAuroraAvatar(dataUrl: string | null): void {
  try {
    if (!dataUrl) localStorage.removeItem(AVATAR_KEY);
    else localStorage.setItem(AVATAR_KEY, dataUrl);
  } catch {
    // ignore quota / private mode
  }
}

/** Read an image file and return a resized data URL (max 256px). */
export function fileToAvatarDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith("image/")) {
      reject(new Error("Selecione uma imagem"));
      return;
    }
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Falha ao ler o arquivo"));
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const size = 256;
        const canvas = document.createElement("canvas");
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          resolve(String(reader.result));
          return;
        }
        const scale = Math.max(size / img.width, size / img.height);
        const w = img.width * scale;
        const h = img.height * scale;
        ctx.drawImage(img, (size - w) / 2, (size - h) / 2, w, h);
        resolve(canvas.toDataURL("image/jpeg", 0.88));
      };
      img.onerror = () => reject(new Error("Imagem inválida"));
      img.src = String(reader.result);
    };
    reader.readAsDataURL(file);
  });
}
