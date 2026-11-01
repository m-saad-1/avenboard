import json
from fastapi.testclient import TestClient
from boards.main import create_app
from boards.doors.identity import person_from
from conftest import OWNER, MEMBER, VIEWER


def headers(person):
    return {
        "x-dodil-user": json.dumps({"sub": person.subject, "email": person.email}),
        "x-dodil-auth-source": "pool",
        "x-avenboard-request": "1",
    }


def test_gateway_identity_requires_pool_source_and_configuration(monkeypatch):
    monkeypatch.setenv("DODIL_USER_POOL", "test/users")
    assert person_from(headers(OWNER)).id == OWNER.id
    assert person_from({"x-dodil-user": json.dumps({"sub": "owner"})}) is None
    assert (
        person_from(dict(headers(OWNER), **{"x-dodil-auth-source": "platform"})) is None
    )
    assert (
        person_from({"x-dodil-auth-source": "pool", "x-dodil-user": "broken"}) is None
    )
    monkeypatch.delenv("DODIL_USER_POOL")
    assert person_from(headers(OWNER)) is None


def test_web_security_and_shared_card_actions(setup, monkeypatch):
    monkeypatch.setenv("DODIL_USER_POOL", "test/users")
    s, w, b, lanes, c = setup
    with TestClient(create_app(s)) as client:
        assert client.get("/api/boards").status_code == 401
        assert (
            client.post(
                "/api/commands", json={"action": "create_workspace", "name": "No"}
            ).status_code
            == 403
        )
        payload = {
            "action": "create_card",
            "list_id": lanes[0]["id"],
            "title": "From web",
        }
        assert (
            client.post(
                "/api/commands", json=payload, headers=headers(VIEWER)
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/commands",
                json=payload,
                headers={**headers(OWNER), "origin": "https://evil.test"},
            ).status_code
            == 403
        )
        response = client.post("/api/commands", json=payload, headers=headers(MEMBER))
        assert response.status_code == 200, response.text
        assert response.json()["created_by"] == MEMBER.id
        assert (
            client.get(f"/api/workspaces/{w}/snapshot", headers=headers(VIEWER)).json()[
                "counts"
            ]["tasks"]
            == 2
        )


def test_required_mcp_tools_real_transport_and_viewer_denial(setup, monkeypatch):
    monkeypatch.setenv("DODIL_USER_POOL", "test/users")
    s, w, b, lanes, c = setup
    with TestClient(create_app(s)) as client:
        discovery = client.get("/.well-known/oauth-protected-resource/mcp")
        assert discovery.status_code == 200
        denied = client.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )
        assert denied.status_code == 401
        assert "resource_metadata" in denied.headers["www-authenticate"]
        auth = {**headers(MEMBER), "accept": "application/json, text/event-stream"}
        init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "qa", "version": "1"},
            },
        }
        assert client.post("/mcp", json=init, headers=auth).status_code == 200
        listed = client.post(
            "/mcp",
            headers=auth,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ).json()
        names = {t["name"] for t in listed["result"]["tools"]}
        assert {
            "list_my_boards",
            "show_board",
            "list_my_cards",
            "list_overdue",
            "create_board",
            "create_card",
            "move_card",
            "assign_card",
            "update_card",
            "add_label",
            "generate_checklist",
            "summarize_board",
            "list_board_members",
            "search_cards",
            "list_blockers",
            "save_checklist",
        } <= names
        call = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "create_card",
                "arguments": {
                    "board_id": b,
                    "title": "MCP invoice",
                    "list_name": "Doing",
                },
            },
        }
        success = client.post("/mcp", headers=auth, json=call).json()
        assert not success["result"].get("isError"), success
        denied = client.post(
            "/mcp", headers={**headers(VIEWER), "accept": auth["accept"]}, json=call
        ).json()
        assert denied["result"]["isError"]
        assert (
            len(
                [
                    c
                    for c in s.snapshot(OWNER, w)["cards"]
                    if c["title"] == "MCP invoice"
                ]
            )
            == 1
        )
