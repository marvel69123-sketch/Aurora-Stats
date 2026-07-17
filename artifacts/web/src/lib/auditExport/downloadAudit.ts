import type { Session } from "@/types/chat";
import {
  buildAuditExport,
  buildAuditFilename,
  serializeAuditExport,
} from "./buildAuditExport";
import { isDeveloperAuditMode } from "./developerMode";

export function downloadConversationAudit(
  session: Session,
  options?: { developerAuditMode?: boolean; appVersion?: string },
): { filename: string; bytes: number } {
  const developer =
    options?.developerAuditMode ?? isDeveloperAuditMode();
  const doc = buildAuditExport(session, {
    developerAuditMode: developer,
    appVersion: options?.appVersion,
  });
  const body = serializeAuditExport(doc);
  const filename = buildAuditFilename();
  const blob = new Blob([body], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
  return { filename, bytes: body.length };
}
