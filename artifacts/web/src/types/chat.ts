export interface MarketEntry {
  rank: number;
  market: string;
  probability: number;
  expected_value: number;
  confidence: number;
  risk: string;
  rationale: string;
}

export interface MatchCard {
  home: { name: string; logo?: string | null };
  away: { name: string; logo?: string | null };
  score?: { home: number; away: number } | null;
  competition?: {
    name: string;
    logo?: string | null;
    country?: string | null;
    round?: string | null;
  } | null;
  venue?: { name: string; city?: string | null } | null;
  status_label?: string | null;
  minute?: number | null;
  is_live: boolean;
  momentum?: {
    label: string;
    side?: "home" | "away" | "neutral" | string | null;
    detail?: string | null;
  } | null;
  predictability?: {
    score: number;
    label: string;
    summary: string;
  } | null;
}

export interface CopilotResponse {
  intent: string;
  entities: Record<string, unknown>;
  request_id: string;
  generated_at: string;
  session_id?: string;
  routing_confidence?: number;
  match: string | null;
  status: string | null;
  is_live: boolean;
  minute: number | null;
  match_card?: MatchCard | null;
  /** FOUND | PARTIAL | NOT_FOUND | FICTIONAL */
  fixture_status?: "FOUND" | "PARTIAL" | "NOT_FOUND" | "FICTIONAL" | string | null;
  /** True only when a real sports fixture was resolved */
  fixture_found?: boolean | null;
  /** VALID | PARTIAL | INVALID */
  fixture_quality?: "VALID" | "PARTIAL" | "INVALID" | string | null;
  /** Temporary production audit — short backend git SHA */
  backend_commit?: string | null;
  /** Temporary production audit — UI build id / bundle hash */
  frontend_commit?: string | null;
  executive_summary: string;
  best_markets: MarketEntry[];
  confidence: {
    score: number;
    label: string;
    explanation: string;
    data_sources: string[];
  };
  risk: {
    level: string;
    flags: string[];
    invalidation_conditions: string[];
  };
  bankroll_recommendation: {
    recommended_stake_pct: number;
    method: string;
    examples: Record<string, number>;
    reasoning: string;
    no_bet: boolean;
  };
  positive_factors: string[];
  negative_factors: string[];
  historical_references: string[];
  knowledge_notes: string[];
  final_recommendation: string;
  aurora_version: string;
  brain: Record<string, unknown>;
  suggested_follow_ups?: string[];
  response_metadata?: {
    public_strengths?: string[];
    presentation?: string;
    mode?: string;
    source?: string;
    show_header?: boolean;
    crl_mode?: string;
    /** v4.4 — Credibility Layer display contract */
    credibility?: {
      display_mode?: "SOCIAL" | "FOLLOW_UP" | "REASONING" | "FULL_ANALYSIS" | string;
      show_confidence?: boolean;
      show_resumo_chrome?: boolean;
      show_header?: boolean;
      show_badges?: boolean;
      thinking_label?: string | null;
      source?: string;
    };
    reflection?: {
      user_real_intent?: string;
      why_this_answer?: string;
      confidence?: number;
      position?: string;
      risks?: string[];
      display_mode?: string;
    };
  };
  /** Present when request.debug / AURORA_DEBUG / #debug — audit provenance */
  debug?: DebugAudit | null;
}

export interface DebugAudit {
  fixture_found?: boolean | "DATA_MISSING" | string;
  fixture_id?: number | "DATA_MISSING" | string;
  data_source?: string;
  markets_source?: string;
  market_reasoning?: string;
  fallback_used?: boolean | "DATA_MISSING" | string;
  confidence_source?: string;
  corner_average?: number | "DATA_MISSING" | string;
  goal_average?: number | "DATA_MISSING" | string;
  xg_home?: number | "DATA_MISSING" | string;
  xg_away?: number | "DATA_MISSING" | string;
  form_score?: number | "DATA_MISSING" | string;
  fixture_resolver?: string;
  entity_match_score?: number | "DATA_MISSING" | string;
  market_generation_enabled?: boolean | "DATA_MISSING" | string;
  fixture_quality?: string;
}

/** FE-only live stats snapshot (not a backend payload field). */
export interface LiveStatsSnapshot {
  homeName: string;
  awayName: string;
  rows: Array<{ label: string; home: string; away: string }>;
  fixtureId: number;
  minute: number | null;
}

/** FE-only live identity cache — survives refresh without re-resolving by free text. */
export interface LiveFixtureCache {
  lastFixtureId: number;
  lastHome: string;
  lastAway: string;
  lastCompetition?: string | null;
  kickoff?: string | null;
}

/** FE-only presentation stamp (v3.6) — never sent to engines. */
export interface MessagePresentationSnapshot {
  profile: "technical" | "casual";
  emojis: "none" | "low" | "medium" | "high";
  enthusiasm: "low" | "medium" | "high";
  structure: "conversational" | "balanced" | "technical";
  headersLists: "few" | "normal" | "many";
  detail: "short" | "normal" | "detailed";
  capturedAt: number;
}

export interface Message {
  id: string;
  role: "user" | "aurora";
  userText: string;
  response?: CopilotResponse;
  error?: string;
  createdAt: string;
  loading?: boolean;
  /**
   * FE-only: prefs captured at send-time so history is never reshaped
   * when the user later changes personalization. Applied only when the
   * conversationPersonalization feature flag is enabled.
   */
  presentationSnapshot?: MessagePresentationSnapshot | null;
  /** FE-only: last successful live refresh timestamp (ISO). */
  refreshedAt?: string;
  /** FE-only: locked fixture id for stable live refresh (from /aurora/live). */
  liveFixtureId?: number | null;
  /** FE-only: richer identity cache for refresh (id → cache → name). */
  liveCache?: LiveFixtureCache | null;
  /** FE-only: soft status after refresh (e.g. match ended) — never INVALID wipe. */
  liveStatusNote?: string | null;
  /** FE-only: live statistics table from GET /aurora/live. */
  liveStats?: LiveStatsSnapshot | null;
  /** FE-only: refresh in progress for this message. */
  refreshing?: boolean;
}

export interface Session {
  id: string;
  title: string;
  /** When true, auto-title will not overwrite a manual rename. */
  titleLocked?: boolean;
  pinned?: boolean;
  messages: Message[];
  createdAt: string;
  lastActive: string;
  backendSessionId?: string;
}
