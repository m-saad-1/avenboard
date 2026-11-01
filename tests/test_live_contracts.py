"""Opt-in LIVE checks. Use only the explicitly designated disposable test organization.

DODIL_CONTRACT_TESTS=1 plus normal service credentials enable data/model tests.
TEST_APP_URL and TEST_POOL_USER_TOKEN enable the genuine gateway identity check.
Never commit those values or paste tokens in evidence.
"""

import os, uuid, math
import httpx, pytest
from boards.infrastructure.dodil import connect, ModelsAssistant
from boards.infrastructure.migrate import migrate
from boards.infrastructure.repository import SqlBoards
from boards.domain.model import timestamp

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("DODIL_CONTRACT_TESTS") != "1",
        reason="Live Dodil test access not supplied",
    ),
]


def test_live_schema_transaction_rollback_and_vector_contract():
    migrate()
    key = "contract-" + str(uuid.uuid4())
    with connect() as conn:
        with pytest.raises(RuntimeError):
            with conn.transaction():
                conn.execute(
                    "INSERT INTO ab_schema_versions (id,applied_at) VALUES (%s,%s)",
                    (key, timestamp()),
                )
                raise RuntimeError("Intentional rollback")
        assert (
            conn.execute(
                "SELECT id FROM ab_schema_versions WHERE id=%s", (key,)
            ).fetchone()
            is None
        )
        assert (
            conn.execute("SELECT '[1,0]'::vector <=> '[1,0]'::vector").fetchone()[0]
            == 0
        )
    assert SqlBoards().diagnostics()["ok"]


def test_live_models_envelopes_and_dimensions():
    model = ModelsAssistant()
    items = model.checklist(
        {
            "title": "Prepare a launch review",
            "description": "Confirm owners and blockers.",
        }
    )
    assert (
        isinstance(items, list)
        and 1 <= len(items) <= 20
        and all(isinstance(i, str) and i.strip() for i in items)
    )
    for query in (False, True):
        vector = model.embed("Prepare a launch review", query=query)
        assert len(vector) == 512 and all(math.isfinite(v) for v in vector)


def test_live_gateway_discovery_and_real_pool_user():
    url = os.environ["TEST_APP_URL"].rstrip("/")
    with httpx.Client(base_url=url, timeout=30, follow_redirects=False) as client:
        assert client.get("/healthz").status_code == 200
        assert (
            client.get("/.well-known/oauth-protected-resource/mcp").status_code == 200
        )
        denied = client.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )
        assert denied.status_code == 401 and "www-authenticate" in denied.headers
        forged = client.get(
            "/api/me",
            headers={"x-dodil-auth-source": "pool", "x-dodil-user": '{"sub":"forged"}'},
        )
        assert forged.status_code == 401
        actual = client.get(
            "/api/me",
            headers={"Authorization": "Bearer " + os.environ["TEST_POOL_USER_TOKEN"]},
        )
        assert (
            actual.status_code == 200 and actual.json()["user"]["subject"] != "forged"
        )
