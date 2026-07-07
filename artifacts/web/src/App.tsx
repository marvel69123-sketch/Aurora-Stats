import { useState, useEffect } from "react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

function useHealth() {
  const [status, setStatus] = useState<"checking" | "ok" | "error">("checking");
  useEffect(() => {
    fetch(`${BASE}/aurora/healthz`)
      .then((r) => (r.ok ? setStatus("ok") : setStatus("error")))
      .catch(() => setStatus("error"));
  }, []);
  return status;
}

const endpoints = [
  { method: "GET", path: "/aurora/live", desc: "Live matches with enriched stats" },
  { method: "GET", path: "/aurora/fixtures/", desc: "Query fixtures by league, date, team" },
  { method: "GET", path: "/aurora/standings/", desc: "League standings table" },
  { method: "GET", path: "/aurora/teams/", desc: "Search & get team info" },
  { method: "GET", path: "/aurora/players/top-scorers", desc: "Top scorers in a league" },
  { method: "GET", path: "/aurora/leagues/", desc: "Search & list leagues" },
];

export default function App() {
  const health = useHealth();

  return (
    <div style={{ minHeight: "100vh", background: "#0f1117", color: "#e2e8f0", fontFamily: "'Inter', system-ui, sans-serif" }}>
      <div style={{ maxWidth: 800, margin: "0 auto", padding: "60px 24px" }}>

        {/* Header */}
        <div style={{ marginBottom: 48 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <div style={{ width: 40, height: 40, borderRadius: 10, background: "linear-gradient(135deg, #6366f1, #8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>⚡</div>
            <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0, letterSpacing: "-0.5px" }}>Aurora</h1>
            <span style={{
              fontSize: 12, fontWeight: 600, padding: "3px 10px", borderRadius: 20,
              background: health === "ok" ? "rgba(34,197,94,0.15)" : health === "error" ? "rgba(239,68,68,0.15)" : "rgba(100,116,139,0.2)",
              color: health === "ok" ? "#4ade80" : health === "error" ? "#f87171" : "#94a3b8",
              border: `1px solid ${health === "ok" ? "rgba(34,197,94,0.3)" : health === "error" ? "rgba(239,68,68,0.3)" : "rgba(100,116,139,0.2)"}`,
            }}>
              {health === "ok" ? "● Live" : health === "error" ? "● Offline" : "● Checking…"}
            </span>
          </div>
          <p style={{ fontSize: 16, color: "#94a3b8", margin: 0, lineHeight: 1.6 }}>
            Football statistics API — live matches, standings, player stats, and more, powered by API-Football.
          </p>
        </div>

        {/* CTA buttons */}
        <div style={{ display: "flex", gap: 12, marginBottom: 48, flexWrap: "wrap" }}>
          <a href="/aurora/docs" style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "11px 20px", borderRadius: 8, fontSize: 14, fontWeight: 600, textDecoration: "none",
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff",
          }}>
            📖 Swagger Docs
          </a>
          <a href="/aurora/live" style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "11px 20px", borderRadius: 8, fontSize: 14, fontWeight: 600, textDecoration: "none",
            background: "rgba(255,255,255,0.06)", color: "#e2e8f0", border: "1px solid rgba(255,255,255,0.1)",
          }}>
            ⚽ Live JSON
          </a>
          <a href="/aurora/redoc" style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "11px 20px", borderRadius: 8, fontSize: 14, fontWeight: 600, textDecoration: "none",
            background: "rgba(255,255,255,0.06)", color: "#e2e8f0", border: "1px solid rgba(255,255,255,0.1)",
          }}>
            📄 ReDoc
          </a>
        </div>

        {/* Endpoints */}
        <div style={{ marginBottom: 48 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: 1, marginBottom: 16 }}>Key Endpoints</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {endpoints.map((ep) => (
              <a key={ep.path} href={ep.path} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", borderRadius: 8, textDecoration: "none", background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)", transition: "background 0.15s" }}
                onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,255,255,0.07)")}
                onMouseLeave={e => (e.currentTarget.style.background = "rgba(255,255,255,0.03)")}
              >
                <span style={{ fontSize: 11, fontWeight: 700, color: "#4ade80", background: "rgba(34,197,94,0.1)", padding: "2px 7px", borderRadius: 4, fontFamily: "monospace", minWidth: 36, textAlign: "center" }}>{ep.method}</span>
                <code style={{ fontSize: 13, color: "#a5b4fc", flex: "0 0 auto" }}>{ep.path}</code>
                <span style={{ fontSize: 13, color: "#64748b" }}>{ep.desc}</span>
              </a>
            ))}
          </div>
        </div>

        {/* Quick start */}
        <div>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: 1, marginBottom: 16 }}>Quick Start</h2>
          <pre style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, padding: 20, fontSize: 13, color: "#a5b4fc", overflowX: "auto", lineHeight: 1.7 }}>
{`# Live matches (cached 30s)
curl https://${window.location.host}/aurora/live

# Premier League standings (season 2024)
curl "https://${window.location.host}/aurora/standings/?league=39&season=2024"

# Top scorers
curl "https://${window.location.host}/aurora/players/top-scorers?league=39&season=2024"`}
          </pre>
        </div>

        <p style={{ marginTop: 48, fontSize: 13, color: "#334155", textAlign: "center" }}>
          Built with FastAPI + API-Football
        </p>
      </div>
    </div>
  );
}
