#!/usr/bin/env python3
"""Smoke-test Aurora ASGI app without binding a port (TestClient)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


def main() -> int:
    client = TestClient(app)
    checks = [
        ("/aurora/healthz", 200),
        ("/aurora", 200),
        ("/aurora/", 200),
        ("/docs", 200),
        ("/redoc", 200),
        ("/openapi.json", 200),
    ]
    failed = 0
    for path, expected in checks:
        r = client.get(path, follow_redirects=False)
        ok = r.status_code == expected
        print(f"{'OK' if ok else 'FAIL'} {r.status_code} {path}")
        if not ok:
            failed += 1
            print(" ", r.text[:300])
        if path == "/aurora/healthz" and ok:
            body = r.json()
            assert body.get("status") == "ok", body
            print(" ", json.dumps(body, ensure_ascii=False)[:200])
        if path == "/openapi.json" and ok:
            schema = r.json()
            print(f"  openapi paths={len(schema.get('paths', {}))}")

    if failed:
        print(f"SMOKE FAILED ({failed})")
        return 1
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
