import logging, sys, traceback
logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
for name in ("src.conversation", "src.routers", "aurora.pipeline_trace", "src.core"):
    logging.getLogger(name).setLevel(logging.WARNING)

from fastapi.testclient import TestClient
from src.main import app
client = TestClient(app)

r = client.get("/aurora/healthz")
print("HEALTHZ", r.status_code, flush=True)

msg = "o que voce acha do Flamengo x Palmeiras?"
print("MSG", msg, flush=True)
resp = client.post("/aurora/chat", json={"message": msg, "user_id": "deploy_health_smoke2"})
print("STATUS", resp.status_code, flush=True)
print("RESP", resp.text[:1500], flush=True)

resp2 = client.post("/aurora/copilot", json={"message": msg, "user_id": "deploy_health_smoke2"})
print("COPILOT", resp2.status_code, flush=True)
print("COPILOT_RESP", resp2.text[:800], flush=True)
