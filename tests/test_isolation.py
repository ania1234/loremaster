import json
import os
import subprocess

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app.limiter import limiter
from app.main import app

load_dotenv()

_REQUIRED = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "TEST_USER_A_EMAIL",
    "TEST_USER_A_PASSWORD",
    "TEST_USER_B_EMAIL",
    "TEST_USER_B_PASSWORD",
    "DOC_ID_USER_A",
)
_missing = [k for k in _REQUIRED if not os.environ.get(k)]
if _missing:
    pytest.skip(
        f"isolation tests need env vars: {', '.join(_missing)}",
        allow_module_level=True,
    )

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]


def _login(email: str, password: str) -> str:
    """Exchange email/password for a fresh Supabase access token.

    Runs the same password-grant call as:
        curl -s -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
             -H "apikey: $SUPABASE_ANON_KEY" \
             -H "Content-Type: application/json" \
             -d '{"email": "...", "password": "..."}'
    """
    result = subprocess.run(
        [
            "curl", "-s", "-X", "POST",
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            "-H", f"apikey: {SUPABASE_ANON_KEY}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"email": email, "password": password}),
        ],
        capture_output=True, text=True, check=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"login for {email} returned non-JSON: {result.stdout!r}")
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"login for {email} failed: {result.stdout}")
    return token


client = TestClient(app)

TOKEN_A = _login(os.environ["TEST_USER_A_EMAIL"], os.environ["TEST_USER_A_PASSWORD"])
TOKEN_B = _login(os.environ["TEST_USER_B_EMAIL"], os.environ["TEST_USER_B_PASSWORD"])
A = {"Authorization": f"Bearer {TOKEN_A}"}
B = {"Authorization": f"Bearer {TOKEN_B}"}
DOC_A = os.environ["DOC_ID_USER_A"]
QUESTION = "What is a solo TTRPG?"


@pytest.fixture(autouse=True)
def _no_rate_limit():
    limiter.enabled = False
    yield
    limiter.enabled = True


def test_b_cannot_read_a_document():
    status_code_get_b = client.get(f"/api/documents/{DOC_A}", headers=B).status_code
    assert status_code_get_b == 404, f"expected 404, got {status_code_get_b}"


def test_b_cannot_delete_a_document():
    status_code_delete_b = client.delete(f"/api/documents/{DOC_A}", headers=B).status_code
    assert status_code_delete_b == 404, f"expected 404, got {status_code_delete_b}"
    status_code_get_a = client.get(f"/api/documents/{DOC_A}", headers=A).status_code
    assert status_code_get_a == 200, f"expected 200, got {status_code_get_a}"


def test_b_retrieval_cannot_see_a_content():
    r = client.post("/api/chat", headers=B,
                    json={"question": QUESTION})
    assert "couldn't find that" in r.text.lower()

def test_a_retrieval_can_see_a_content():
    r = client.post("/api/chat", headers=A,
                    json={"question": QUESTION})
    print(r.text)
    assert "couldn't find that" not in r.text.lower()


def test_no_token_is_rejected():
    for method, path in [("get", "/api/documents"),
                         ("post", "/api/chat"),
                         ("get", f"/api/documents/{DOC_A}")]:
        assert getattr(client, method)(path).status_code == 401


def test_forged_token_is_rejected():
    forged = TOKEN_B[:-4] + "AAAA"
    r = client.get("/api/documents", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401
