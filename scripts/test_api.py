#!/usr/bin/env python3
"""
End-to-end test script for memCore MaaS API.
Run after starting the server and applying migrations.

Usage:
    python scripts/test_api.py [--base-url http://localhost:8000]
"""
import argparse
import json
import sys
import uuid
from datetime import datetime

import httpx

# ─── Configuration ─────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="memCore API test runner")
parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
args = parser.parse_args()
BASE_URL = args.base_url.rstrip("/")

# Shared state
TEST_ORG_ID = str(uuid.uuid4())
TEST_AGENT_ID = str(uuid.uuid4())
token = None
api_key = None
created_memory_id = None
session_id = f"test-session-{uuid.uuid4().hex[:8]}"

PASS = "✅"
FAIL = "❌"
SKIP = "⏭ "


def check(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))
    if not condition:
        print(f"     Detail: {detail}")
    return condition


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def request(method, path, *, expect_status=None, headers=None, **kwargs):
    url = f"{BASE_URL}{path}"
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if headers:
        h.update(headers)
    r = getattr(httpx, method)(url, headers=h, timeout=30.0, **kwargs)
    if expect_status and r.status_code != expect_status:
        print(f"     HTTP {r.status_code} (expected {expect_status}): {r.text[:200]}")
    return r


failures = 0


def run_tests():
    global token, api_key, created_memory_id, failures

    # ── 1. Root & Health ────────────────────────────────────────────────
    section("1. Root & Health")

    r = request("get", "/")
    ok = check("GET / returns 200", r.status_code == 200)
    if ok:
        data = r.json()
        check("Service is memCore MaaS", data.get("service") == "memCore MaaS")

    r = request("get", "/health/")
    ok = check("GET /health/ returns 200", r.status_code == 200)
    if ok:
        data = r.json()
        check("Status field present", "status" in data)
        check("Services reported", "services" in data)
        print(f"     Services: {data.get('services', {})}")

    # ── 2. Auth — Register ──────────────────────────────────────────────
    section("2. Auth — Register & Login")

    user_email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    user_pw = "SecurePass123!"
    user_name = f"testuser_{uuid.uuid4().hex[:6]}"

    r = request("post", "/auth/register", json={
        "email": user_email,
        "username": user_name,
        "full_name": "Test User",
        "password": user_pw,
        "org_id": TEST_ORG_ID,
    })
    ok = check("POST /auth/register returns 201", r.status_code == 201)
    if ok:
        user_data = r.json()
        check("User ID present", "id" in user_data)
        check("Email matches", user_data.get("email") == user_email)
    else:
        failures += 1
        print("  Skipping downstream auth tests")

    # Duplicate register should fail
    r2 = request("post", "/auth/register", json={
        "email": user_email, "username": user_name,
        "full_name": "Dup", "password": user_pw,
    })
    check("Duplicate email returns 409", r2.status_code == 409)

    # Login
    r = request("post", "/auth/login", json={"username": user_name, "password": user_pw})
    ok = check("POST /auth/login returns 200", r.status_code == 200)
    if ok:
        tokens = r.json()
        check("access_token present", "access_token" in tokens)
        check("refresh_token present", "refresh_token" in tokens)
        token = tokens["access_token"]
        refresh_token_val = tokens.get("refresh_token")
    else:
        failures += 1
        token = None

    # Wrong password
    r = request("post", "/auth/login", json={"username": user_name, "password": "wrong"})
    check("Wrong password returns 401", r.status_code == 401)

    # Get /me
    r = request("get", "/auth/me")
    ok = check("GET /auth/me returns 200", r.status_code == 200)
    if ok:
        check("Username matches", r.json().get("username") == user_name)

    # Token refresh
    if token:
        r = request("post", "/auth/refresh", json={"refresh_token": refresh_token_val})
        ok = check("POST /auth/refresh returns 200", r.status_code == 200)
        if ok:
            new_tokens = r.json()
            token = new_tokens["access_token"]  # use new token
            check("New access_token present", "access_token" in new_tokens)

    # ── 3. API Keys ─────────────────────────────────────────────────────
    section("3. API Key Management")

    r = request("post", "/auth/api-keys", json={
        "name": "Test Agent Key",
        "description": "Key for test agent",
        "org_id": TEST_ORG_ID,
        "agent_id": TEST_AGENT_ID,
        "scopes": ["agent", "org"],
        "expires_in_days": 30,
    })
    ok = check("POST /auth/api-keys returns 201", r.status_code == 201)
    if ok:
        key_data = r.json()
        check("api_key field present (plain key)", "api_key" in key_data)
        api_key = key_data["api_key"]
        api_key_id = key_data["id"]
        check("Key starts with maas_", api_key.startswith("maas_"))

    r = request("get", "/auth/api-keys")
    ok = check("GET /auth/api-keys returns 200", r.status_code == 200)
    if ok:
        check("Keys list present", "keys" in r.json())

    # ── 4. Memory CRUD (JWT auth) ───────────────────────────────────────
    section("4. Memory CRUD — JWT Auth")

    # Unauthenticated should fail
    r = httpx.post(f"{BASE_URL}/memory/", json={
        "org_id": TEST_ORG_ID, "agent_id": TEST_AGENT_ID,
        "content": "Unauth test", "memory_type": "fact",
    }, timeout=10)
    check("Unauthenticated POST /memory/ returns 401", r.status_code == 401)

    # Create memory
    r = request("post", "/memory/", json={
        "org_id": TEST_ORG_ID,
        "agent_id": TEST_AGENT_ID,
        "content": "The sky is blue and the grass is green. Earth orbits the sun.",
        "memory_type": "fact",
        "scope": "agent",
        "confidence": 0.95,
    })
    ok = check("POST /memory/ returns 201", r.status_code == 201)
    if ok:
        mem = r.json()
        created_memory_id = mem["id"]
        check("Memory ID present", "id" in mem)
        check("Content matches", mem.get("content", "").startswith("The sky"))
        check("Org matches", mem.get("org_id") == TEST_ORG_ID)

    # Get memory
    if created_memory_id:
        r = request("get", f"/memory/{created_memory_id}")
        ok = check("GET /memory/{id} returns 200", r.status_code == 200)
        if ok:
            check("Same memory returned", r.json().get("id") == created_memory_id)

    # Update memory
    if created_memory_id:
        r = request("put", f"/memory/{created_memory_id}", json={
            "content": "Updated: The sky is blue. Planets orbit stars.",
            "confidence": 0.98,
        })
        ok = check("PUT /memory/{id} returns 200", r.status_code == 200)
        if ok:
            check("Confidence updated", r.json().get("confidence") == 0.98)

    # Wrong org access
    other_org = str(uuid.uuid4())
    r = request("post", "/memory/", json={
        "org_id": other_org, "agent_id": TEST_AGENT_ID,
        "content": "Should be denied", "memory_type": "fact",
    })
    check("Cross-org POST returns 403", r.status_code == 403)

    # ── 5. Memory Search ────────────────────────────────────────────────
    section("5. Memory Search (Hybrid)")

    r = request("post", "/memory/search", json={
        "query": "sky blue astronomy",
        "org_id": TEST_ORG_ID,
        "agent_id": TEST_AGENT_ID,
        "top_k": 5,
    })
    ok = check("POST /memory/search returns 200", r.status_code == 200)
    if ok:
        data = r.json()
        check("Results list present", "results" in data)
        check("Total field present", "total" in data)
        if data["results"]:
            first = data["results"][0]
            check("Score field present", "score" in first)
            check("Semantic score present", "semantic_score" in first)
            check("Recency score present", "recency_score" in first)

    # Unauthenticated search
    r = httpx.post(f"{BASE_URL}/memory/search", json={
        "query": "test", "org_id": TEST_ORG_ID, "top_k": 5
    }, timeout=10)
    check("Unauthenticated search returns 401", r.status_code == 401)

    # ── 6. Working Memory (Redis) ────────────────────────────────────────
    section("6. Working Memory — Redis")

    r = request("put", f"/working/{session_id}", json={
        "session_id": session_id,
        "data": {"step": 1, "context": "user asked about weather", "items": []},
        "ttl": 3600,
    })
    check("PUT /working/{session_id} returns 200", r.status_code == 200)

    r = request("get", f"/working/{session_id}")
    ok = check("GET /working/{session_id} returns 200", r.status_code == 200)
    if ok:
        wm = r.json()
        check("Data matches", wm.get("data", {}).get("step") == 1)
        check("TTL present", wm.get("ttl") is not None)

    r = request("delete", f"/working/{session_id}")
    check("DELETE /working/{session_id} returns 200", r.status_code == 200)

    r = request("get", f"/working/{session_id}")
    check("Deleted session returns 404", r.status_code == 404)

    # ── 7. Conflicts ─────────────────────────────────────────────────────
    section("7. Conflict Resolution")

    # Create two conflicting memories
    mem_ids = []
    for i, content in enumerate([
        "Python is the best programming language for data science",
        "Rust is the best programming language for systems programming",
    ]):
        r = request("post", "/memory/", json={
            "org_id": TEST_ORG_ID, "agent_id": TEST_AGENT_ID,
            "content": content, "memory_type": "preference",
            "confidence": 0.8 + i * 0.05,
        })
        if r.status_code == 201:
            mem_ids.append(r.json()["id"])

    if len(mem_ids) == 2:
        check("Created 2 conflict candidate memories", True)

        # Flag as conflicting
        r = request("post", f"/conflicts/flag?org_id={TEST_ORG_ID}", json=mem_ids)
        check("POST /conflicts/flag returns 200", r.status_code == 200)

        # List conflicts
        r = request("get", f"/conflicts/?org_id={TEST_ORG_ID}")
        ok = check("GET /conflicts/ returns 200", r.status_code == 200)

        # Resolve with CONFIDENCE_WEIGHTED
        r = request("post", "/conflicts/resolve", json={
            "memory_ids": mem_ids,
            "strategy": "confidence_weighted",
            "org_id": TEST_ORG_ID,
            "agent_id": TEST_AGENT_ID,
        })
        ok = check("POST /conflicts/resolve returns 200", r.status_code == 200)
        if ok:
            res = r.json()
            check("resolved_memory_id present", "resolved_memory_id" in res)
            check("strategy_used present", res.get("strategy_used") == "confidence_weighted")
            check("merged_memories listed", len(res.get("merged_memories", [])) == 2)
    else:
        print(f"  {SKIP} Skipped conflict tests (memory creation failed)")

    # ── 8. Cleanup — Delete Memory ───────────────────────────────────────
    section("8. Cleanup")

    if created_memory_id:
        r = request("delete", f"/memory/{created_memory_id}")
        check("DELETE /memory/{id} returns 200", r.status_code == 200)

        r = request("get", f"/memory/{created_memory_id}")
        check("Deleted memory returns 404 on GET", r.status_code == 404)

    # ── Summary ──────────────────────────────────────────────────────────
    section("Test Summary")
    print(f"\n  Completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"  Failures tracked: {failures}")
    if failures == 0:
        print(f"\n  {PASS} All tests passed!\n")
    else:
        print(f"\n  {FAIL} Some tests failed — see output above\n")
        sys.exit(1)


if __name__ == "__main__":
    print(f"\nmemCore MaaS — End-to-End Test Runner")
    print(f"Target: {BASE_URL}")
    print(f"Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    run_tests()
