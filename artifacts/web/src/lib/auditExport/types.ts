/** Conversation Audit Export — public JSON contract (FE observability). */

export interface AuditExportMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  message_id?: string;
}

export interface AuditResolvedEntity {
  input: string;
  resolved: string;
  confidence: number;
}

export interface AuditTurnDiagnostics {
  turn_index: number;
  user_message?: string;
  intent?: string;
  resolved_entities?: AuditResolvedEntity[];
  expected_information?: string[];
  response_planner?: {
    response_type?: string;
    sections?: string[];
  };
  research?: {
    web_used: boolean;
    memory_used: boolean;
    sources: string[];
  };
  reflection?: {
    meta_reasoning_detected: boolean;
    template_detected: boolean;
    usefulness_score: number | null;
    human_similarity_score: number | null;
  };
  metadata?: {
    response_time_ms: number | null;
    deepthinking_used: boolean;
    fallback_used: boolean;
    fixture_status?: string | null;
    routing_confidence?: number | null;
  };
  /** Scrubbed snapshot — never includes raw secrets. */
  entities_snapshot?: Record<string, unknown>;
  brain_snapshot?: Record<string, unknown>;
}

export interface AuditExportDocument {
  version: string;
  session_id: string;
  created_at: string;
  exported_at: string;
  developer_audit_mode: boolean;
  title?: string;
  messages: AuditExportMessage[];
  diagnostics: {
    turns: AuditTurnDiagnostics[];
    summary?: Record<string, unknown>;
  };
  metadata: {
    frontend_commit?: string | null;
    backend_commit?: string | null;
    aurora_version?: string | null;
    message_count: number;
    backend_session_id?: string | null;
  };
}
