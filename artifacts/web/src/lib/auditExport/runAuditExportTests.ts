/**
 * Node-runnable audit export tests (observability only).
 * Run: npx --yes tsx src/lib/auditExport/runAuditExportTests.ts
 */
import type { Session } from "../../types/chat";
import {
  buildAuditExport,
  buildAuditFilename,
  replayMessagesFromAudit,
  serializeAuditExport,
} from "./buildAuditExport";
import { assertNoSecrets, scrubSecrets } from "./scrubSecrets";

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg);
}

function makeSession(count: number): Session {
  const messages = [];
  for (let i = 0; i < count; i++) {
    if (i % 2 === 0) {
      messages.push({
        id: `u${i}`,
        role: "user" as const,
        userText: i === 0 ? "oi" : i === 2 ? "botafogo" : i === 4 ? "e o londrina?" : `msg-${i}`,
        createdAt: new Date(Date.UTC(2026, 6, 17, 12, 0, i)).toISOString(),
      });
    } else {
      messages.push({
        id: `a${i}`,
        role: "aurora" as const,
        userText: "",
        createdAt: new Date(Date.UTC(2026, 6, 17, 12, 0, i)).toISOString(),
        response: {
          intent: "conversation_assist",
          entities: {
            natural_kind: "team_opinion",
            team: i === 3 ? "Botafogo" : i === 5 ? "Londrina" : "Time",
            opinion_time: true,
            api_key: "sk-SHOULD_NOT_LEAK_1234567890",
            human_inference: {
              intent: "general_team_talk",
              team: i === 3 ? "Botafogo" : "Londrina",
            },
          },
          request_id: "req",
          generated_at: new Date().toISOString(),
          match: null,
          status: null,
          is_live: false,
          minute: null,
          executive_summary: `Resposta ${i} com seções.\n\n📊 **Momento**\nFase ok.`,
          best_markets: [],
          confidence: {
            score: 5,
            label: "cautelosa",
            explanation: "",
            data_sources: ["local"],
          },
          risk: { level: "low", flags: [], invalidation_conditions: [] },
          bankroll_recommendation: {
            recommended_stake_pct: 0,
            method: "",
            examples: {},
            reasoning: "",
            no_bet: true,
          },
          positive_factors: [],
          negative_factors: [],
          historical_references: [],
          knowledge_notes: [],
          final_recommendation: `Resposta ${i}`,
          aurora_version: "test",
          brain: {
            deep_thinking: { topic_kind: "opinion", topic_team: "Botafogo" },
            web_thinking: { status: "fallback_no_web", sources_used: [] },
          },
        },
      });
    }
  }
  return {
    id: "sess-audit-1",
    title: "Audit test",
    messages,
    createdAt: "2026-07-17T12:00:00.000Z",
    lastActive: "2026-07-17T12:05:00.000Z",
    backendSessionId: "be-123",
  };
}

function testShortConversation() {
  const session = makeSession(6); // oi, reply, botafogo, reply, londrina, reply
  const basic = buildAuditExport(session, { developerAuditMode: false });
  assert(basic.messages.length === 6, "short: message count");
  assert(basic.diagnostics.turns.length === 0, "basic mode has empty turns");
  assert(basic.messages[0].role === "user" && basic.messages[0].content === "oi", "first user");
  assert(basic.messages[2].content === "botafogo", "botafogo preserved");
  assert(basic.messages[4].content === "e o londrina?", "londrina preserved");

  const full = buildAuditExport(session, { developerAuditMode: true });
  assert(full.diagnostics.turns.length >= 1, "dev mode has turns");
  assert(full.developer_audit_mode === true, "dev flag");
  const leaked = JSON.stringify(full).includes("sk-SHOULD_NOT_LEAK");
  assert(!leaked, "api_key must be scrubbed from export");
  console.log("OK short conversation");
}

function testLongConversation() {
  const session = makeSession(60); // 30 user + 30 assistant
  const doc = buildAuditExport(session, { developerAuditMode: true });
  assert(doc.messages.length === 60, `long: expected 60 got ${doc.messages.length}`);
  assert(doc.metadata.message_count === 60, "metadata count");
  for (let i = 0; i < doc.messages.length; i++) {
    assert(doc.messages[i] != null, `msg ${i} present`);
  }
  const body = serializeAuditExport(doc);
  assert(body.length > 1000, "large payload serialized");
  console.log("OK long conversation", { bytes: body.length });
}

function testReplayOrder() {
  const session = makeSession(10);
  const doc = buildAuditExport(session, { developerAuditMode: false });
  const replayed = replayMessagesFromAudit(doc);
  assert(replayed.length === doc.messages.length, "replay length");
  for (let i = 0; i < replayed.length; i++) {
    assert(replayed[i].content === doc.messages[i].content, `order ${i}`);
    assert(replayed[i].role === doc.messages[i].role, `role ${i}`);
  }
  console.log("OK replay order");
}

function testSecurity() {
  const dirty = {
    api_key: "sk-abc1234567890xyz",
    token: "secret-token-value",
    nested: { authorization: "Bearer abc.def.ghi", ok: "safe" },
    text: "Authorization Bearer sk-leakleakleakleak",
  };
  const clean = scrubSecrets(dirty);
  assert(clean.api_key === "[REDACTED]", "api_key redacted");
  assert(clean.token === "[REDACTED]", "token redacted");
  assert(clean.nested.authorization === "[REDACTED]", "auth redacted");
  assert(clean.nested.ok === "safe", "safe kept");
  const hits = assertNoSecrets(clean);
  assert(hits.length === 0, `secret hits: ${hits.join(",")}`);

  const session = makeSession(4);
  session.messages[1].response!.entities = {
    ...(session.messages[1].response!.entities || {}),
    access_token: "tok_12345678901234567890",
    password: "hunter2",
  };
  const doc = buildAuditExport(session, { developerAuditMode: true });
  const raw = JSON.stringify(doc);
  assert(!raw.includes("hunter2"), "password scrubbed");
  assert(!raw.includes("tok_12345678901234567890"), "access_token scrubbed");
  console.log("OK security");
}

function testFilename() {
  const name = buildAuditFilename(new Date("2026-07-17T19:30:45"));
  assert(/^aurora_audit_\d{8}_\d{6}\.json$/.test(name), `filename ${name}`);
  console.log("OK filename", name);
}

function main() {
  testShortConversation();
  testLongConversation();
  testReplayOrder();
  testSecurity();
  testFilename();
  console.log("\n======== AUDIT EXPORT TESTS OK ========");
}

main();
