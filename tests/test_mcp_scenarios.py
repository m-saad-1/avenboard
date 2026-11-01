"""Deterministic tool sequences for all eight requested scenarios.

These exercise real Streamable HTTP with fixtures, not an actual LLM connector.
The live Claude/ChatGPT conversational check remains a separate release gate.
"""

import json
from fastapi.testclient import TestClient
from boards.main import create_app
from conftest import MEMBER, command
from test_doors import headers


def test_all_eight_scenario_tool_sequences(setup, monkeypatch):
    monkeypatch.setenv("DODIL_USER_POOL", "test/users")
    s, w, b, lanes, c = setup
    for i in range(11):
        command(
            s,
            MEMBER,
            "create_card",
            list_id=lanes[1]["id"],
            title="Homepage redesign"
            if i == 0
            else "Website redesign"
            if i == 1
            else f"Work {i}",
        )
    with TestClient(create_app(s)) as client:
        auth = {**headers(MEMBER), "accept": "application/json, text/event-stream"}

        def call(name, **arguments):
            response = client.post(
                "/mcp/",
                headers=auth,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                },
            )
            assert response.status_code == 200, response.text
            result = response.json()["result"]
            assert not result.get("isError"), result
            if result.get("structuredContent") is not None:
                value = result["structuredContent"]
                return value.get("result", value) if isinstance(value, dict) else value
            values = [
                json.loads(block["text"])
                for block in result["content"]
                if block["type"] == "text"
            ]
            return (
                values
                if name in ("list_my_boards", "list_board_members", "list_blockers")
                else values[0]
            )

        # 1. Server-local Monday-Sunday assignment window.
        assert w in call("list_my_cards", workspace_id=w, period="this_week")
        # 2. Overdue tasks.
        assert call("list_overdue", workspace_id=w)[w]["items"][0]["id"] == c["id"]
        # 3. Exact board and Doing alias resolution.
        assert any(x["id"] == b for x in call("list_my_boards"))
        new = call("create_card", board_id=b, title="Send invoice", list_name="Doing")
        assert new["list_id"] == lanes[2]["id"]
        # 4. Card 12 resolved only inside the authorized workspace.
        twelve = call("search_cards", workspace_id=w, card_number=12)["items"][0]
        moved = call(
            "move_card",
            card_id=twelve["id"],
            expected_version=twelve["version"],
            list_id=lanes[-1]["id"],
        )
        assert moved["list_id"] == lanes[-1]["id"]
        # 5. Resolve Sarah by eligible membership; pass stable ID as target.
        sarah = next(
            m for m in call("list_board_members", board_id=b) if m["id"] == MEMBER.id
        )
        redesign = call("search_cards", workspace_id=w, query="Website redesign")[
            "items"
        ][0]
        assigned = call(
            "assign_card",
            card_id=redesign["id"],
            expected_version=redesign["version"],
            assignee_id=sarah["id"],
        )
        assert assigned["assignee_id"] == MEMBER.id
        # 6. Actual dependency query.
        command(
            s,
            MEMBER,
            "add_dependency",
            card_id=new["id"],
            expected_version=1,
            prerequisite_id=redesign["id"],
        )
        assert call("list_blockers", board_id=b, card_id=new["id"])
        # 7. Facts and generated suggestions are separate.
        summary = call("summarize_board", board_id=b)
        assert summary["facts"]["total"] == 13 and summary["generated"]
        # 8. Preview first; saving requires a second explicit operation.
        homepage = call("search_cards", workspace_id=w, query="Homepage redesign")[
            "items"
        ][0]
        preview = call("generate_checklist", card_id=homepage["id"])
        assert not preview["saved"] and not s.repo.tables["checklist_items"]
        call(
            "save_checklist",
            card_id=homepage["id"],
            expected_version=preview["expected_version"],
            items=preview["items"],
        )
        assert len(s.repo.tables["checklist_items"]) == len(preview["items"])
