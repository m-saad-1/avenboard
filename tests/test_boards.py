"""The board's rules, through the use cases and both doors. No Dodil account needed:
the repository and the AI are in-memory fakes."""
import json

import pytest
from fastapi.testclient import TestClient

from boards.application.use_cases import Boards, NotFound
from boards.domain.model import Forbidden, Invalid, Person
from boards.main import create_app

OWNER, MEMBER, VIEWER, STRANGER = (Person(e) for e in
                                   ("ana@x.io", "bo@x.io", "cy@x.io", "dee@x.io"))


class MemoryBoards:
    def __init__(self):
        self.boards, self.cards, self.events = {}, {}, []

    def get(self, board_id):
        return self.boards.get(board_id)

    def boards_for(self, email):
        return [b for b in self.boards.values() if b.owner_email == email or email in b.members]

    def save_board(self, board):
        self.boards[board.id] = board

    def get_card(self, card_id):
        return self.cards.get(card_id)

    def cards_on(self, board_id):
        return [c for c in self.cards.values() if c.board_id == board_id]

    def save_card(self, card):
        self.cards[card.id] = card

    def log(self, board_id, card_id, actor, action):
        self.events.append((board_id, card_id, actor, action))


class FakeAI:
    def checklist(self, title):
        return ["step one", "step two"]


@pytest.fixture
def svc():
    s = Boards(MemoryBoards(), FakeAI())
    b = s.create_board(OWNER, "Launch")
    s.add_member(OWNER, b["id"], MEMBER.email, "member")
    s.add_member(OWNER, b["id"], VIEWER.email, "viewer")
    return s, b["id"]


def test_member_adds_and_moves_cards_and_it_is_logged(svc):
    s, bid = svc
    card = s.add_card(MEMBER, bid, "Send invoice")
    moved = s.move_card(MEMBER, card["id"], "Done")
    assert moved["list_name"] == "Done"
    assert any("moved from To do to Done" in e[3] for e in s.repo.events)


def test_viewer_cannot_edit(svc):
    s, bid = svc
    with pytest.raises(Forbidden):
        s.add_card(VIEWER, bid, "nope")


def test_only_owner_manages_members(svc):
    s, bid = svc
    with pytest.raises(Forbidden):
        s.add_member(MEMBER, bid, "eve@x.io", "member")


def test_stranger_cannot_see_board(svc):
    s, bid = svc
    with pytest.raises(NotFound):
        s.show_board(STRANGER, bid)
    assert s.my_boards(STRANGER) == []


def test_unknown_list_is_refused(svc):
    s, bid = svc
    card = s.add_card(OWNER, bid, "x")
    with pytest.raises(Invalid):
        s.move_card(OWNER, card["id"], "Someday")


def _h(p):
    return {"X-Dodil-User": json.dumps({"sub": p.email, "email": p.email})}


def test_web_and_mcp_doors_share_the_rules(svc):
    s, bid = svc
    with TestClient(create_app(s)) as c:
        assert c.get("/api/boards").status_code == 401
        assert c.get("/api/boards", headers=_h(VIEWER)).json()[0]["role"] == "viewer"
        assert c.post(f"/api/boards/{bid}/cards", json={"title": "t"},
                      headers=_h(VIEWER)).status_code == 403
        r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert r.status_code == 401 and "resource_metadata" in r.headers["www-authenticate"]
        mcp_h = {**_h(MEMBER), "accept": "application/json, text/event-stream"}
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "t", "version": "0"}}}
        assert c.post("/mcp", json=init, headers=mcp_h).status_code == 200
        call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "add_card", "arguments": {"board_id": bid, "title": "via mcp"}}}
        out = c.post("/mcp", json=call, headers=mcp_h).json()
        assert not out["result"].get("isError"), out
        assert any(c.title == "via mcp" for c in s.repo.cards.values())
