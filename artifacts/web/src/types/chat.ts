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
  };
}

export interface Message {
  id: string;
  role: "user" | "aurora";
  userText: string;
  response?: CopilotResponse;
  error?: string;
  createdAt: string;
  loading?: boolean;
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
