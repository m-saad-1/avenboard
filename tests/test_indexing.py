from boards.domain.model import Unavailable
from conftest import OWNER, MEMBER, command
from fakes import FakeAI


class Embeddings(FakeAI):
    semantic_enabled = True
    embedding_model = "test-only-512"

    def __init__(self):
        self.inputs = []

    def embed(self, text, query=False):
        self.inputs.append(text)
        return [1.0] + [0.0] * 511


def test_indexing_private_board_scope_stale_content_and_search_filter(setup):
    s, w, b, lanes, c = setup
    private = command(
        s, OWNER, "create_board", workspace_id=w, title="Private", visibility="private"
    )
    lane = s.show_board(OWNER, private["id"])["lists"][0]
    secret = command(s, OWNER, "create_card", list_id=lane["id"], title="Secret launch")
    s.assistant = Embeddings()
    scopes = []

    def rank(ids, vector, limit):
        scopes.append(ids)
        # A deliberately hostile repository response must still be reauthorized.
        return [
            {"card_id": c["id"], "content_version": 1, "distance": 0},
            {"card_id": secret["id"], "content_version": 1, "distance": 0},
        ]

    s.repo.semantic = rank
    result = s.semantic_search(MEMBER, w, "invoice")
    assert [item["id"] for item in result["items"]] == [c["id"]]
    assert private["id"] not in scopes[0]
    assert not any("Secret launch" in text for text in s.assistant.inputs)
    command(
        s,
        MEMBER,
        "update_card",
        card_id=c["id"],
        expected_version=1,
        changes={"title": "Revised invoice"},
    )
    assert s.repo.tables["embedding_jobs"][c["id"]]["status"] == "pending"
    assert (
        s.semantic_search(MEMBER, w, "invoice")["items"] == []
    )  # stale rank version is rejected
    assert s.repo.tables["embeddings"][c["id"]]["content_version"] == 2


def test_failed_embedding_leases_retry_and_expired_lease_recovers(setup):
    s, w, b, lanes, c = setup
    s.assistant = Embeddings()

    def fail(*args, **kwargs):
        raise Unavailable("Simulated timeout")

    s.assistant.embed = fail
    assert s.process_embeddings([b]) == 0
    job = s.repo.tables["embedding_jobs"][c["id"]]
    assert job["status"] == "pending" and job["attempts"] == 1 and job["lease_until"]
    job.update(status="working", lease_until="2020-01-01T00:00:00+00:00")
    s.assistant = Embeddings()
    assert s.process_embeddings([b]) == 1
    assert s.repo.tables["embedding_jobs"][c["id"]]["status"] == "done"


def test_search_pagination_filters_and_literal_wildcards(setup):
    s, w, b, lanes, c = setup
    command(
        s,
        MEMBER,
        "create_card",
        list_id=lanes[0]["id"],
        title="100% ready",
        due_date="2026-12-01",
    )
    assert s.search_cards(MEMBER, w, query="%")["total"] == 1
    assert (
        s.search_cards(MEMBER, w, query="invoice", assignee_id=MEMBER.id, overdue=True)[
            "total"
        ]
        == 1
    )
    assert (
        s.search_cards(MEMBER, w, limit=1, offset=1)["items"][0]["title"]
        == "100% ready"
    )
    assert s.search_cards(MEMBER, w, status="DONE")["items"] == []
