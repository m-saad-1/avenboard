"""Concurrency, rollback, indexing and platform configuration regressions."""

import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import pytest, yaml
from psycopg.errors import SerializationFailure
from boards.domain.model import Conflict, NotFound, Unavailable, task_group
from boards.infrastructure.repository import SqlBoards, normalize
from boards.infrastructure.schema import TABLES, schema_sql
from conftest import OWNER, MEMBER, command


def test_concurrent_moves_into_empty_list_are_serialized(setup):
    s, w, b, lanes, c = setup
    other = command(s, MEMBER, "create_card", list_id=lanes[0]["id"], title="Other")

    def move(card):
        return command(
            s,
            MEMBER,
            "move_card",
            card_id=card["id"],
            expected_version=1,
            list_id=lanes[3]["id"],
            position=0,
        )

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(move, [c, other]))
    cards = [
        r for r in s.show_board(OWNER, b)["cards"] if r["list_id"] == lanes[3]["id"]
    ]
    assert sorted(r["position"] for r in cards) == [0, 1]
    assert len({r["id"] for r in cards}) == 2


def test_two_edits_of_same_version_only_one_commits(setup):
    s, w, b, lanes, c = setup

    def edit(value):
        try:
            command(
                s,
                MEMBER,
                "update_card",
                card_id=c["id"],
                expected_version=1,
                changes={"title": value},
            )
            return "saved"
        except Conflict:
            return "conflict"

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(edit, ["First", "Second"])) == ["conflict", "saved"]
    assert (
        sum(e["action"] == "title_changed" for e in s.activity(OWNER, c["id"])["items"])
        == 1
    )


def test_transfer_revokes_former_owner_implicit_private_assignment(setup):
    s, w, *_ = setup
    board = command(
        s, OWNER, "create_board", workspace_id=w, title="Private", visibility="private"
    )
    lane = s.show_board(OWNER, board["id"])["lists"][0]
    c = command(
        s,
        OWNER,
        "create_card",
        list_id=lane["id"],
        title="Private work",
        assignee_id=OWNER.id,
    )
    command(s, OWNER, "transfer_owner", workspace_id=w, user_id=MEMBER.id)
    assert s.repo.tables["cards"][c["id"]]["assignee_id"] is None
    with pytest.raises(NotFound):
        s.show_board(OWNER, board["id"])


def test_noop_edit_keeps_version_and_does_not_invent_activity(setup):
    s, w, b, lanes, c = setup
    before = copy.deepcopy(s.repo.tables["activity"])
    same = command(
        s,
        MEMBER,
        "update_card",
        card_id=c["id"],
        expected_version=1,
        changes={"title": c["title"]},
    )
    assert same["version"] == 1
    assert s.repo.tables["activity"] == before


def test_checklist_edit_order_delete_is_atomic(setup):
    s, w, b, lanes, c = setup
    command(
        s,
        MEMBER,
        "save_checklist",
        card_id=c["id"],
        expected_version=1,
        items=[{"title": "One"}, {"title": "Two"}],
    )
    items = s.snapshot(OWNER, w)["cards"][0]["checklist"]
    command(
        s,
        MEMBER,
        "save_checklist",
        card_id=c["id"],
        expected_version=2,
        mode="replace",
        items=[{"id": items[1]["id"], "title": "Second edited", "completed": True}],
    )
    rows = list(s.repo.tables["checklist_items"].values())
    assert (
        len(rows) == 1
        and rows[0]["title"] == "Second edited"
        and rows[0]["position"] == 0
    )


@pytest.mark.parametrize("value", [None, {}, [""], [1], [], ["x"] * 101])
def test_malformed_ai_cannot_save_or_change_card(setup, value):
    s, w, b, lanes, c = setup
    s.assistant.checklist = lambda card: value
    before = copy.deepcopy(s.repo.tables)
    with pytest.raises(Unavailable):
        s.generate_checklist(MEMBER, c["id"])
    assert s.repo.tables == before


def test_ai_model_latency_reauthorizes_and_rechecks_version(setup):
    s, w, b, lanes, c = setup

    def stale(card):
        command(
            s,
            OWNER,
            "update_card",
            card_id=c["id"],
            expected_version=1,
            changes={"title": "Changed"},
        )
        return ["Review", "Implement", "Check"]

    s.assistant.checklist = stale
    with pytest.raises(Conflict):
        s.generate_checklist(MEMBER, c["id"])

    def revoked(facts):
        command(s, OWNER, "remove_member", workspace_id=w, user_id=MEMBER.id)
        return "Suggestions"

    s.assistant.summary = revoked
    with pytest.raises(NotFound):
        s.summarize_board(MEMBER, b)


def test_private_activity_filter_including_history(setup):
    s, w, *_ = setup
    b = command(
        s, OWNER, "create_board", workspace_id=w, title="Secret", visibility="private"
    )
    assert not any(
        e["board_id"] == b["id"] for e in s.workspace_activity(MEMBER, w)["items"]
    )
    with pytest.raises(NotFound):
        s.workspace_activity(MEMBER, w, b["id"])


def test_calendar_week_midnight_and_database_timestamp_normalization():
    sunday = datetime(2026, 11, 1, 23, 59, tzinfo=timezone.utc)
    monday = datetime(2026, 11, 2, 0, 1, tzinfo=timezone.utc)
    card = {"status": "TODO", "due_date": "2026-11-02"}
    assert task_group(card, "UTC", sunday) == "Upcoming"
    assert task_group(card, "UTC", monday) == "Today"
    assert task_group(dict(card, due_date=None), "UTC", monday) == "No Due Date"
    assert normalize(datetime(2026, 1, 1)).endswith("+00:00")


def test_full_transaction_retried_after_commit_conflict():
    attempts = []

    class Connection:
        row_factory = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def transaction(self):
            class Transaction:
                def __enter__(self):
                    pass

                def __exit__(self, *args):
                    if len(attempts) < 3:
                        raise SerializationFailure("retry commit")

            return Transaction()

    repo = SqlBoards(Connection)
    assert repo.run(lambda tx: (attempts.append(len(attempts)), "done")[1]) == "done"
    assert len(attempts) == 3


def test_failed_database_commit_never_reports_success():
    class Connection:
        row_factory = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def transaction(self):
            return self

        def execute(self, *args):
            raise SerializationFailure("conflict")

    with pytest.raises(Conflict):
        SqlBoards(Connection).run(lambda tx: tx.get("cards", "id", True))


def test_schema_and_remix_contract_static():
    root = Path(__file__).parents[1]
    assert (root / "schema.sql").read_text() == schema_sql()
    assert {
        "users",
        "workspaces",
        "memberships",
        "invitations",
        "boards",
        "board_members",
        "lists",
        "cards",
        "labels",
        "card_labels",
        "checklist_items",
        "dependencies",
        "activity",
        "preferences",
        "favorites",
        "receipts",
        "embedding_jobs",
        "embeddings",
        "schema_versions",
    } == set(TABLES)
    assert all("PRIMARY KEY" in columns["id"] for columns in TABLES.values())
    remix = yaml.safe_load((root / ".dodil/remix.yaml").read_text())
    assert remix["topics"] == ["dodil-challenge", "dodil-challenge-boards"]
    for resource in ("buckets", "user_pools"):
        assert all(r["on_conflict"] == "fail" for r in remix["provision"][resource])
    deploy = yaml.safe_load((root / ".dodil/deploy.yaml").read_text())["apps"][0]
    assert deploy["port"] == 8080 and deploy["health"]["path"] == "/healthz"
    assert deploy["env"]["PG_PORT"] == "5432"
    assert "USER 10001" in (root / "app/Dockerfile").read_text()
