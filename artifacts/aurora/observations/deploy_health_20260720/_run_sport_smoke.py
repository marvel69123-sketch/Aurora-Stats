import logging
import sys
import traceback
from pathlib import Path

# Capture WARNING+ from target namespaces
logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
for name in ("src.conversation", "src.routers", "aurora.pipeline_trace"):
    logging.getLogger(name).setLevel(logging.WARNING)

print("=== IMPORT APP ===", flush=True)
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

print("=== HEALTHZ ===", flush=True)
r = client.get("/aurora/healthz")
print("status", r.status_code, flush=True)
print("body", r.text[:800], flush=True)

print("=== SPORT CHAT ===", flush=True)
# try common chat endpoints
candidates = [
    ("POST", "/aurora/chat", {"message": "Flamengo x Palmeiras quem e favorito?", "user_id": "deploy_health_smoke"}),
    ("POST", "/aurora/copilot", {"message": "Flamengo x Palmeiras quem e favorito?", "user_id": "deploy_health_smoke"}),
    ("POST", "/chat", {"message": "Flamengo x Palmeiras quem e favorito?"}),
    ("POST", "/aurora/assistant/chat", {"message": "Flamengo x Palmeiras quem e favorito?"}),
]

# discover routes
paths = sorted({getattr(rt, "path", "") for rt in app.routes})
chatish = [p for p in paths if any(k in p.lower() for k in ("chat", "copilot", "message", "ask"))]
print("chatish_routes", chatish[:40], flush=True)

payload_tries = [
    {"message": "Flamengo x Palmeiras quem e favorito?"},
    {"text": "Flamengo x Palmeiras quem e favorito?"},
    {"query": "Flamengo x Palmeiras quem e favorito?"},
    {"message": "Flamengo x Palmeiras quem e favorito?", "user_id": "deploy_health_smoke"},
    {"messages": [{"role": "user", "content": "Flamengo x Palmeiras quem e favorito?"}]},
]

done = False
for path in chatish:
    methods = set()
    for rt in app.routes:
        if getattr(rt, "path", None) == path:
            methods |= set(getattr(rt, "methods", []) or [])
    if "POST" not in methods and methods:
        continue
    for body in payload_tries:
        try:
            resp = client.post(path, json=body)
            print(f"TRY {path} keys={list(body)} -> {resp.status_code}", flush=True)
            if resp.status_code < 500:
                print("RESP", resp.text[:1200], flush=True)
                if resp.status_code == 200:
                    done = True
                    break
        except Exception as e:
            print(f"EXC {path}: {e}", flush=True)
            traceback.print_exc()
    if done:
        break

if not done:
    print("NO_SUCCESSFUL_CHAT", flush=True)

print("=== DONE ===", flush=True)
