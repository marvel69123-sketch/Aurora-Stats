/** developer_audit_mode — localStorage flag for full diagnostic export. */

export const DEVELOPER_AUDIT_STORAGE_KEY = "aurora_developer_audit_mode";

export function isDeveloperAuditMode(): boolean {
  try {
    if (typeof window === "undefined") return false;
    const v = localStorage.getItem(DEVELOPER_AUDIT_STORAGE_KEY);
    if (v === "1" || v === "true") return true;
    const q = new URLSearchParams(window.location.search);
    if (q.get("developer_audit") === "1" || q.get("developer_audit") === "true") {
      return true;
    }
  } catch {
    // ignore
  }
  return false;
}

export function setDeveloperAuditMode(enabled: boolean): void {
  try {
    if (enabled) {
      localStorage.setItem(DEVELOPER_AUDIT_STORAGE_KEY, "true");
    } else {
      localStorage.removeItem(DEVELOPER_AUDIT_STORAGE_KEY);
    }
  } catch {
    // ignore
  }
}
