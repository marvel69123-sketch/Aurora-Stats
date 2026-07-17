/**
 * Build aurora_audit_*.json from a Session.
 * Additive FE observability — does not alter engines / memory / DT.
 */

import type { CopilotResponse, Message, Session } from "@/types/chat";
import { scrubSecrets } from "./scrubSecrets";
import type {
  AuditExportDocument,
  AuditExportMessage,
  AuditResolvedEntity,
  AuditTurnDiagnostics,
} from "./types";

const PHILOSOPHY_RE =
  /evitaria opini[aã]o engessada|olharia menos o hype|n[aã]o s[oó] a camisa/i;
const TEMPLATE_HEADER_RE = /(📊|📰|📅|🎯|⚔|📈|📉)/;

function assistantContent(m: Message): string {
  if (m.error) return `[error] ${m.error}`;
  if (m.loading) return "";
  const r = m.response;
  if (!r) return "";
  return String(r.executive_summary || r.final_recommendation || "").trim();
}

function extractEntities(response?: CopilotResponse): AuditResolvedEntity[] {
  if (!response?.entities || typeof response.entities !== "object") return [];
  const ents = response.entities as Record<string, unknown>;
  const out: AuditResolvedEntity[] = [];
  const conf = Number(response.routing_confidence ?? 0.5);

  const push = (input: string, resolved: unknown) => {
    if (resolved == null || resolved === "") return;
    out.push({
      input,
      resolved: String(resolved),
      confidence: Number.isFinite(conf) ? conf : 0.5,
    });
  };

  push("home", ents.home);
  push("away", ents.away);
  push("team", ents.team);
  if (Array.isArray(ents.teams)) {
    ents.teams.forEach((t, i) => push(`teams[${i}]`, t));
  }

  const brain = (response.brain || {}) as Record<string, unknown>;
  const hie = (brain.human_inference || ents.human_inference) as
    | Record<string, unknown>
    | undefined;
  if (hie?.team) push("human_inference.team", hie.team);
  if (hie?.home) push("human_inference.home", hie.home);
  if (hie?.away) push("human_inference.away", hie.away);

  return out;
}

function extractExpected(response?: CopilotResponse): string[] {
  const ents = (response?.entities || {}) as Record<string, unknown>;
  const brain = (response?.brain || {}) as Record<string, unknown>;
  const ue =
    (brain.user_expectation as Record<string, unknown> | undefined) ||
    (ents.user_expectation as Record<string, unknown> | undefined);
  const wants =
    (ue?.user_probably_wants as string[] | undefined) ||
    (ue?.expects as string[] | undefined) ||
    (ents.expected_information as string[] | undefined);
  if (Array.isArray(wants)) return wants.map(String);

  // Infer lightly from intent for audit readability (FE-only hint)
  const intent = String(response?.intent || ents.natural_kind || "");
  if (intent.includes("analyze") || ents.human_inference) {
    const hi = ents.human_inference as Record<string, unknown> | undefined;
    if (hi?.intent === "match_analysis") {
      return ["análise", "forças", "cenário"];
    }
    if (hi?.intent === "team_moment") {
      return ["fase", "problemas", "perspectiva"];
    }
    if (hi?.intent === "general_team_talk") {
      return ["momento atual", "último resultado", "próximos jogos", "notícias"];
    }
  }
  if (ents.opinion_time || ents.natural_kind === "team_opinion") {
    return ents.moment_now
      ? ["fase", "problemas", "perspectiva"]
      : ["momento atual", "último resultado", "próximos jogos", "notícias"];
  }
  return [];
}

function extractPlanner(response?: CopilotResponse): AuditTurnDiagnostics["response_planner"] {
  const ents = (response?.entities || {}) as Record<string, unknown>;
  const brain = (response?.brain || {}) as Record<string, unknown>;
  const plan =
    (brain.response_plan as Record<string, unknown> | undefined) ||
    (ents.response_plan as Record<string, unknown> | undefined);

  if (plan && typeof plan === "object") {
    return {
      response_type: String(plan.answer_type || plan.response_type || ""),
      sections: Array.isArray(plan.sections)
        ? plan.sections.map(String)
        : undefined,
    };
  }

  const intent = String(
    (ents.human_inference as Record<string, unknown> | undefined)?.intent ||
      response?.intent ||
      "",
  );
  if (intent === "match_analysis" || response?.intent === "analyze_match") {
    return { response_type: "match_analysis", sections: ["contexto", "tática", "expectativa"] };
  }
  if (ents.moment_now || intent === "team_moment") {
    return { response_type: "team_moment", sections: ["fase", "atenção", "expectativa"] };
  }
  if (ents.opinion_time || ents.response_intelligence) {
    return {
      response_type: "team_summary",
      sections: ["momento", "próximos jogos", "perspectiva"],
    };
  }
  return { response_type: response?.intent || "unknown", sections: [] };
}

function extractResearch(response?: CopilotResponse): AuditTurnDiagnostics["research"] {
  const brain = (response?.brain || {}) as Record<string, unknown>;
  const web = (brain.web_thinking || brain.last_need_web) as
    | Record<string, unknown>
    | undefined;
  const sources: string[] = [];
  if (Array.isArray(web?.sources_used)) {
    sources.push(...web!.sources_used.map(String));
  }
  const dataSources = response?.confidence?.data_sources || [];
  for (const s of dataSources) {
    if (s && !sources.includes(String(s))) sources.push(String(s));
  }
  const webUsed = Boolean(
    web?.summary_used ||
      web?.changed_reasoning ||
      (web?.status && web.status !== "skipped" && web.status !== "fallback_no_web"),
  );
  const memoryUsed = Boolean(
    brain.prediction_memory || entsHas(response, "prediction_memory"),
  );
  return {
    web_used: webUsed,
    memory_used: memoryUsed,
    sources,
  };
}

function entsHas(response: CopilotResponse | undefined, key: string): boolean {
  return Boolean(response?.entities && key in (response.entities as object));
}

function extractReflection(
  response?: CopilotResponse,
  content?: string,
): AuditTurnDiagnostics["reflection"] {
  const brain = (response?.brain || {}) as Record<string, unknown>;
  const refl =
    (brain.response_reflection as Record<string, unknown> | undefined) ||
    (response?.response_metadata?.reflection as unknown as
      | Record<string, unknown>
      | undefined);
  const text = content || "";
  const usefulness =
    typeof refl?.usefulness_score === "number"
      ? Number(refl.usefulness_score) / (Number(refl.usefulness_score) > 1 ? 100 : 1)
      : null;
  return {
    meta_reasoning_detected: PHILOSOPHY_RE.test(text),
    template_detected: TEMPLATE_HEADER_RE.test(text),
    usefulness_score: usefulness,
    human_similarity_score:
      typeof refl?.human_similarity_score === "number"
        ? Number(refl.human_similarity_score)
        : null,
  };
}

function extractMetadata(response?: CopilotResponse): AuditTurnDiagnostics["metadata"] {
  const brain = (response?.brain || {}) as Record<string, unknown>;
  const debug = response?.debug;
  const deep =
    Boolean(brain.deep_thinking) ||
    Boolean((brain.deep_thinking as Record<string, unknown> | undefined)?.topic_kind);
  const fallback = Boolean(
    debug?.fallback_used === true ||
      (response?.entities as Record<string, unknown> | undefined)?.intelligence_fallback ||
      (response?.entities as Record<string, unknown> | undefined)
        ?.response_intelligence_repair,
  );
  return {
    response_time_ms: null,
    deepthinking_used: deep,
    fallback_used: fallback,
    fixture_status: response?.fixture_status ?? null,
    routing_confidence: response?.routing_confidence ?? null,
  };
}

function pairTurns(messages: Message[]): Array<{ user?: Message; assistant?: Message }> {
  const turns: Array<{ user?: Message; assistant?: Message }> = [];
  let current: { user?: Message; assistant?: Message } = {};
  for (const m of messages) {
    if (m.role === "user") {
      if (current.user || current.assistant) turns.push(current);
      current = { user: m };
    } else if (m.role === "aurora") {
      current.assistant = m;
      turns.push(current);
      current = {};
    }
  }
  if (current.user || current.assistant) turns.push(current);
  return turns;
}

export function buildAuditFilename(date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  const stamp =
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_` +
    `${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
  return `aurora_audit_${stamp}.json`;
}

export function buildAuditExport(
  session: Session,
  options?: {
    developerAuditMode?: boolean;
    appVersion?: string;
  },
): AuditExportDocument {
  const developer = Boolean(options?.developerAuditMode);
  const messages: AuditExportMessage[] = [];

  for (const m of session.messages) {
    if (m.role === "user") {
      messages.push({
        role: "user",
        content: m.userText || "",
        timestamp: m.createdAt,
        message_id: m.id,
      });
    } else {
      messages.push({
        role: "assistant",
        content: assistantContent(m),
        timestamp: m.createdAt,
        message_id: m.id,
      });
    }
  }

  const turns: AuditTurnDiagnostics[] = [];
  if (developer) {
    pairTurns(session.messages).forEach((turn, idx) => {
      const response = turn.assistant?.response;
      const content = turn.assistant ? assistantContent(turn.assistant) : "";
      const ents = (response?.entities || {}) as Record<string, unknown>;
      const hie = ents.human_inference as Record<string, unknown> | undefined;
      const intent = String(
        hie?.intent || ents.natural_kind || response?.intent || "",
      );
      turns.push({
        turn_index: idx,
        user_message: turn.user?.userText,
        intent,
        resolved_entities: extractEntities(response),
        expected_information: extractExpected(response),
        response_planner: extractPlanner(response),
        research: extractResearch(response),
        reflection: extractReflection(response, content),
        metadata: extractMetadata(response),
        entities_snapshot: response?.entities
          ? scrubSecrets({ ...(response.entities as object) })
          : undefined,
        brain_snapshot: response?.brain
          ? scrubSecrets({ ...(response.brain as object) })
          : undefined,
      });
    });
  }

  const lastAssistant = [...session.messages]
    .reverse()
    .find((m) => m.role === "aurora" && m.response);

  const doc: AuditExportDocument = {
    version: options?.appVersion || lastAssistant?.response?.aurora_version || "unknown",
    session_id: session.id,
    created_at: session.createdAt,
    exported_at: new Date().toISOString(),
    developer_audit_mode: developer,
    title: session.title,
    messages,
    diagnostics: developer
      ? {
          turns,
          summary: {
            turn_count: turns.length,
            intents: turns.map((t) => t.intent).filter(Boolean),
          },
        }
      : { turns: [] },
    metadata: {
      frontend_commit: lastAssistant?.response?.frontend_commit ?? null,
      backend_commit: lastAssistant?.response?.backend_commit ?? null,
      aurora_version: lastAssistant?.response?.aurora_version ?? null,
      message_count: messages.length,
      backend_session_id: session.backendSessionId ?? null,
    },
  };

  return scrubSecrets(doc);
}

export function serializeAuditExport(doc: AuditExportDocument): string {
  return `${JSON.stringify(doc, null, 2)}\n`;
}

/** Replay helper — preserve message order from exported JSON. */
export function replayMessagesFromAudit(doc: AuditExportDocument): AuditExportMessage[] {
  return (doc.messages || []).map((m) => ({
    role: m.role,
    content: m.content,
    timestamp: m.timestamp,
    message_id: m.message_id,
  }));
}
