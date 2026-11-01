import copy
import json
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from boards.domain.model import (
    Forbidden,
    NotFound,
    Invalid,
    Conflict,
    task_group,
    calendar_date,
)
from conftest import OWNER, MEMBER, VIEWER, STRANGER, command


def test_member_create_move_reorder_and_chronological_audit(setup):
    s, w, b, lanes, c = setup
    changed = command(
        s,
        MEMBER,
        "move_card",
        card_id=c["id"],
        list_id=lanes[-1]["id"],
        expected_version=c["version"],
    )
    assert changed["list_id"] == lanes[-1]["id"]
    events = s.activity(MEMBER, c["id"])["items"]
    move = next(e for e in events if e["action"] == "move_card")
    assert json.loads(move["before_json"])["list_id"] == lanes[1]["id"]
    assert json.loads(move["after_json"])["list_id"] == lanes[-1]["id"]
    assert move["actor_id"] == MEMBER.id
    assert events == sorted(events, key=lambda e: (e["created_at"], e["id"]))
    assert s.snapshot(MEMBER, w)["counts"]["completed"] == 1


@pytest.mark.parametrize(
    "action",
    [
        "create_card",
        "update_card",
        "move_card",
        "archive_card",
        "delete_card",
        "save_checklist",
        "create_list",
        "save_label",
    ],
)
def test_viewer_cannot_write_or_create_history(setup, action):
    s, w, b, lanes, c = setup
    payload = {
        "create_card": dict(list_id=lanes[0]["id"], title="No"),
        "update_card": dict(
            card_id=c["id"], expected_version=1, changes={"title": "No"}
        ),
        "move_card": dict(card_id=c["id"], expected_version=1, list_id=lanes[-1]["id"]),
        "archive_card": dict(card_id=c["id"], expected_version=1),
        "delete_card": dict(card_id=c["id"], expected_version=1),
        "save_checklist": dict(
            card_id=c["id"], expected_version=1, items=[{"title": "No"}]
        ),
        "create_list": dict(board_id=b, title="No"),
        "save_label": dict(board_id=b, name="No", color="blue"),
    }[action]
    before = copy.deepcopy(s.repo.tables)
    with pytest.raises(Forbidden):
        command(s, VIEWER, action, **payload)
    assert s.repo.tables == before


@pytest.mark.parametrize("person", [MEMBER, VIEWER])
def test_only_owner_controls_members_boards_and_workspace(setup, person):
    s, w, b, lanes, c = setup
    with pytest.raises(Forbidden):
        command(s, person, "invite_member", workspace_id=w, email="new@example.test")
    with pytest.raises(Forbidden):
        command(s, person, "create_board", workspace_id=w, title="No")
    with pytest.raises(Forbidden):
        command(s, person, "remove_member", workspace_id=w, user_id=OWNER.id)


def test_workspace_and_private_board_isolation_on_every_read(setup):
    s, w, b, lanes, c = setup
    with pytest.raises(NotFound):
        s.snapshot(STRANGER, w)
    assert s.list_my_boards(STRANGER) == []
    private = command(
        s, OWNER, "create_board", workspace_id=w, title="Secret", visibility="private"
    )
    lane = s.show_board(OWNER, private["id"])["lists"][0]
    secret = command(s, OWNER, "create_card", list_id=lane["id"], title="Confidential")
    for read in (
        lambda: s.show_board(MEMBER, private["id"]),
        lambda: s.generate_checklist(MEMBER, secret["id"]),
        lambda: s.activity(MEMBER, secret["id"]),
        lambda: s.summarize_board(MEMBER, private["id"]),
    ):
        with pytest.raises(NotFound):
            read()
    snap = s.snapshot(MEMBER, w)
    assert private["id"] not in [x["id"] for x in snap["boards"]]
    assert secret["id"] not in [x["id"] for x in s.search_cards(MEMBER, w)["items"]]
    assert not any(e["board_id"] == private["id"] for e in snap["activity"])


def test_invites_store_hash_only_require_owner_approval_and_reject_reuse(setup):
    s, w, *_ = setup
    invite = command(s, OWNER, "invite_member", workspace_id=w, email=STRANGER.email)
    assert invite["token"] not in json.dumps(s.repo.tables)
    accepted = command(s, STRANGER, "accept_invite", token=invite["token"])
    assert accepted["status"] == "awaiting-owner-approval"
    with pytest.raises(NotFound):
        s.snapshot(STRANGER, w)
    with pytest.raises(Conflict):
        command(s, STRANGER, "accept_invite", token=invite["token"])
    command(
        s,
        OWNER,
        "approve_invite",
        workspace_id=w,
        invitation_id=invite["invitation_id"],
    )
    assert s.snapshot(STRANGER, w)["role"] == "MEMBER"


def test_revoked_expired_and_wrong_identity_invites(setup):
    s, w, *_ = setup
    invite = command(s, OWNER, "invite_member", workspace_id=w, email=STRANGER.email)
    with pytest.raises(Forbidden):
        command(s, MEMBER, "accept_invite", token=invite["token"])
    command(
        s, OWNER, "revoke_invite", workspace_id=w, invitation_id=invite["invitation_id"]
    )
    with pytest.raises(Conflict):
        command(s, STRANGER, "accept_invite", token=invite["token"])
    invite = command(s, OWNER, "invite_member", workspace_id=w, email=STRANGER.email)
    s.repo.tables["invitations"][invite["invitation_id"]]["expires_at"] = (
        "2020-01-01T00:00:00+00:00"
    )
    with pytest.raises(Conflict):
        command(s, STRANGER, "accept_invite", token=invite["token"])


def test_protected_owner_atomic_transfer_and_revocation(setup):
    s, w, b, lanes, c = setup
    with pytest.raises(Invalid):
        command(s, OWNER, "remove_member", workspace_id=w, user_id=OWNER.id)
    command(s, OWNER, "transfer_owner", workspace_id=w, user_id=MEMBER.id)
    assert s.snapshot(MEMBER, w)["role"] == "OWNER"
    with pytest.raises(Forbidden):
        command(s, OWNER, "invite_member", workspace_id=w, email="x@y.test")
    command(s, MEMBER, "remove_member", workspace_id=w, user_id=OWNER.id)
    with pytest.raises(NotFound):
        s.snapshot(OWNER, w)


def test_remove_member_unassigns_cards_and_records_actor(setup):
    s, w, b, lanes, c = setup
    command(s, OWNER, "remove_member", workspace_id=w, user_id=MEMBER.id)
    assert s.repo.tables["cards"][c["id"]]["assignee_id"] is None
    with pytest.raises(NotFound):
        s.show_board(MEMBER, b)
    assert any(
        e["action"] == "assignee_changed" and e["actor_id"] == OWNER.id
        for e in s.activity(OWNER, c["id"])["items"]
    )


def test_duplicate_retry_once_payload_conflict_and_revoked_replay(setup):
    s, w, b, lanes, c = setup
    payload = dict(
        action="create_card",
        operation_id="reliable-key-001",
        list_id=lanes[0]["id"],
        title="Once",
    )
    first = s.execute(MEMBER, payload)
    assert s.execute(MEMBER, payload) == first
    assert (
        len([c for c in s.repo.tables["cards"].values() if c["title"] == "Once"]) == 1
    )
    with pytest.raises(Conflict):
        s.execute(MEMBER, dict(payload, title="Different"))
    command(s, OWNER, "remove_member", workspace_id=w, user_id=MEMBER.id)
    with pytest.raises(NotFound):
        s.execute(MEMBER, payload)


def test_stale_and_failed_writes_leave_everything_unchanged(setup):
    s, w, b, lanes, c = setup
    command(
        s,
        MEMBER,
        "update_card",
        card_id=c["id"],
        expected_version=1,
        changes={"description": "Updated"},
    )
    before = copy.deepcopy(s.repo.tables)
    with pytest.raises(Conflict):
        command(
            s,
            MEMBER,
            "move_card",
            card_id=c["id"],
            expected_version=1,
            list_id=lanes[-1]["id"],
        )
    assert s.repo.tables == before
    s.repo.fail_commit = True
    with pytest.raises(Conflict):
        command(s, MEMBER, "create_card", list_id=lanes[0]["id"], title="Rollback")
    assert s.repo.tables == before


def test_cross_board_move_label_and_assignment_rejected(setup):
    s, w, b, lanes, c = setup
    other = command(s, OWNER, "create_board", workspace_id=w, title="Other")
    foreign = s.show_board(OWNER, other["id"])["lists"][0]
    with pytest.raises(Invalid):
        command(
            s,
            MEMBER,
            "move_card",
            card_id=c["id"],
            expected_version=1,
            list_id=foreign["id"],
        )
    label = command(
        s, MEMBER, "save_label", board_id=other["id"], name="Elsewhere", color="rose"
    )
    with pytest.raises(Invalid):
        command(
            s,
            MEMBER,
            "update_card",
            card_id=c["id"],
            expected_version=1,
            changes={"label_ids": [label["id"]]},
        )
    with pytest.raises(Invalid):
        command(
            s,
            MEMBER,
            "update_card",
            card_id=c["id"],
            expected_version=1,
            changes={"assignee_id": STRANGER.id},
        )


def test_archive_parent_restore_preserves_child_flags(setup):
    s, w, b, lanes, c = setup
    command(s, MEMBER, "archive_card", card_id=c["id"], expected_version=1)
    board = s.show_board(OWNER, b)
    command(s, OWNER, "archive_board", board_id=b, expected_version=board["version"])
    assert s.snapshot(MEMBER, w)["counts"]["tasks"] == 0
    board = s.show_board(OWNER, b)
    command(s, OWNER, "restore_board", board_id=b, expected_version=board["version"])
    assert s.snapshot(MEMBER, w)["counts"]["tasks"] == 0
    command(s, MEMBER, "restore_card", card_id=c["id"], expected_version=2)
    assert s.snapshot(MEMBER, w)["counts"]["tasks"] == 1


def test_list_order_and_card_order_persist(setup):
    s, w, b, lanes, c = setup
    second = command(s, MEMBER, "create_card", list_id=lanes[1]["id"], title="Second")
    command(
        s,
        MEMBER,
        "move_card",
        card_id=second["id"],
        expected_version=1,
        list_id=lanes[1]["id"],
        position=0,
    )
    rows = [
        r for r in s.show_board(MEMBER, b)["cards"] if r["list_id"] == lanes[1]["id"]
    ]
    assert [r["title"] for r in rows] == ["Second", "Send invoice"]
    board = s.show_board(MEMBER, b)
    command(
        s,
        MEMBER,
        "reorder_lists",
        board_id=b,
        expected_version=board["version"],
        list_ids=[l["id"] for l in reversed(lanes)],
    )
    assert s.show_board(MEMBER, b)["lists"][0]["title"] == "Done"


def test_checklist_review_before_save_and_stale_save(setup):
    s, w, b, lanes, c = setup
    preview = s.generate_checklist(VIEWER, c["id"])
    assert not s.repo.tables["checklist_items"]
    command(
        s,
        MEMBER,
        "save_checklist",
        card_id=c["id"],
        expected_version=preview["expected_version"],
        items=[{"title": t} for t in preview["items"]],
    )
    assert len(s.repo.tables["checklist_items"]) == 3
    with pytest.raises(Conflict):
        command(
            s,
            MEMBER,
            "save_checklist",
            card_id=c["id"],
            expected_version=preview["expected_version"],
            items=[],
        )


def test_dependency_cycles_and_archived_blockers(setup):
    s, w, b, lanes, c = setup
    prerequisite = command(
        s, MEMBER, "create_card", list_id=lanes[0]["id"], title="Prerequisite"
    )
    command(
        s,
        MEMBER,
        "add_dependency",
        card_id=c["id"],
        expected_version=1,
        prerequisite_id=prerequisite["id"],
    )
    with pytest.raises(Invalid):
        command(
            s,
            MEMBER,
            "add_dependency",
            card_id=prerequisite["id"],
            expected_version=1,
            prerequisite_id=c["id"],
        )
    command(s, MEMBER, "archive_card", card_id=prerequisite["id"], expected_version=1)
    assert s.list_blockers(MEMBER, b, c["id"])[0]["unresolved"]


def test_demo_is_idempotent_real_data_and_no_fake_members(svc):
    first = command(svc, OWNER, "create_workspace", name="Acme Studio", demo=True)
    second = command(svc, OWNER, "create_workspace", name="Acme Studio", demo=True)
    assert first == second
    snap = svc.snapshot(OWNER, first["workspace_id"])
    assert len(snap["boards"]) == 3
    assert len(snap["cards"]) == 12
    assert len(snap["members"]) == 1
    assert {c["number"] for c in snap["cards"]} == set(range(1, 13))
    assert (
        svc.resolve_list(OWNER, snap["boards"][0]["id"], "Doing")["title"]
        == "In Progress"
    )


def test_calendar_dates_dst_and_completion():
    assert calendar_date("2020-02-29") == "2020-02-29"
    for value in ("2025-02-29", "2026-13-01", "2026-01-01T00:00:00Z"):
        with pytest.raises(Invalid):
            calendar_date(value)
    now = datetime(2026, 3, 8, 7, 30, tzinfo=timezone.utc)
    card = dict(status="TODO", due_date="2026-03-08")
    assert task_group(card, "America/New_York", now) == "Today"
    assert (
        task_group(dict(card, due_date="2026-03-07"), "America/New_York", now)
        == "Overdue"
    )
    assert (
        task_group(dict(card, status="DONE", due_date="2020-01-01"), "UTC", now)
        == "Completed"
    )


def test_client_cannot_supply_actor_identity(setup):
    s, w, b, lanes, c = setup
    with pytest.raises(ValidationError):
        command(
            s,
            MEMBER,
            "create_card",
            list_id=lanes[0]["id"],
            title="No",
            actor_id=OWNER.id,
        )
