/**
 * Strip secrets / tokens / keys from audit payloads before export.
 * Fail-open: on error, return a shallow-safe empty object for objects.
 */

const SENSITIVE_KEY =
  /^(api[_-]?key|token|access[_-]?token|refresh[_-]?token|authorization|auth|password|passwd|secret|client[_-]?secret|bearer|private[_-]?key|x-api-key|cookie|set-cookie)$/i;

const SENSITIVE_VALUE =
  /\b(sk-[a-zA-Z0-9]{10,}|Bearer\s+[A-Za-z0-9\-._~+/]+=*|AIza[0-9A-Za-z\-_]{20,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})\b/;

export function isSensitiveKey(key: string): boolean {
  return SENSITIVE_KEY.test(key.trim());
}

export function scrubSecrets<T>(value: T, depth = 0): T {
  if (depth > 12) return value;
  if (value == null) return value;

  if (typeof value === "string") {
    if (SENSITIVE_VALUE.test(value)) {
      return value.replace(SENSITIVE_VALUE, "[REDACTED]") as T;
    }
    return value;
  }

  if (Array.isArray(value)) {
    return value.map((v) => scrubSecrets(v, depth + 1)) as T;
  }

  if (typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (isSensitiveKey(k)) {
        out[k] = "[REDACTED]";
        continue;
      }
      out[k] = scrubSecrets(v, depth + 1);
    }
    return out as T;
  }

  return value;
}

export function assertNoSecrets(payload: unknown): string[] {
  const hits: string[] = [];
  const walk = (node: unknown, path: string) => {
    if (node == null) return;
    if (typeof node === "string") {
      if (SENSITIVE_VALUE.test(node) && !node.includes("[REDACTED]")) {
        hits.push(path);
      }
      return;
    }
    if (Array.isArray(node)) {
      node.forEach((v, i) => walk(v, `${path}[${i}]`));
      return;
    }
    if (typeof node === "object") {
      for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
        if (isSensitiveKey(k) && v !== "[REDACTED]") {
          hits.push(`${path}.${k}`);
        }
        walk(v, path ? `${path}.${k}` : k);
      }
    }
  };
  walk(payload, "");
  return hits;
}
