import pytest
from boards.domain.model import NotFound, Invalid
from conftest import OWNER, MEMBER, command


@pytest.mark.parametrize("action", ["archive_card", "delete_card"])
def test_lifecycle_receipt_replays_after_resource_state_changes(setup, action):
    s, w, b, lanes, c = setup
    payload = dict(
        action=action,
        card_id=c["id"],
        expected_version=1,
        operation_id="card-lifecycle-retry",
    )
    first = s.execute(MEMBER, payload)
    assert s.execute(MEMBER, payload) == first
    command(s, OWNER, "remove_member", workspace_id=w, user_id=MEMBER.id)
    with pytest.raises(NotFound):
        s.execute(MEMBER, payload)


def test_board_delete_receipt_and_history_retained(setup):
    s, w, b, lanes, c = setup
    board = s.show_board(OWNER, b)
    payload = dict(
        action="delete_board",
        board_id=b,
        expected_version=board["version"],
        confirmation="Operations",
        operation_id="board-delete-retry",
    )
    first = s.execute(OWNER, payload)
    assert s.execute(OWNER, payload) == first
    assert s.snapshot(MEMBER, w)["counts"]["tasks"] == 0
    assert any(
        e["action"] == "delete_board" for e in s.workspace_activity(OWNER, w)["items"]
    )


def test_archive_compacts_order_and_restore_appends(setup):
    s, w, b, lanes, c = setup
    second = command(s, MEMBER, "create_card", list_id=lanes[1]["id"], title="Second")
    third = command(s, MEMBER, "create_card", list_id=lanes[1]["id"], title="Third")
    command(s, MEMBER, "archive_card", card_id=second["id"], expected_version=1)
    assert s.repo.tables["cards"][third["id"]]["position"] == 1
    command(s, MEMBER, "restore_card", card_id=second["id"], expected_version=2)
    rows = [
        r for r in s.show_board(MEMBER, b)["cards"] if r["list_id"] == lanes[1]["id"]
    ]
    assert [r["id"] for r in rows] == [c["id"], third["id"], second["id"]]
    assert [r["position"] for r in rows] == [0, 1, 2]


def test_supplied_label_ids_are_always_validated(setup):
    s, w, b, lanes, c = setup
    with pytest.raises(NotFound):
        command(
            s,
            MEMBER,
            "save_label",
            board_id=b,
            label_id="missing",
            name="No",
            color="blue",
        )
    with pytest.raises(Invalid):
        command(
            s,
            MEMBER,
            "remove_label",
            card_id=c["id"],
            expected_version=1,
            label_id="missing",
        )


def test_deleted_label_receipt_replays_but_rechecks_membership(setup):
    s, w, b, lanes, c = setup
    label = command(s, MEMBER, "save_label", board_id=b, name="Priority", color="blue")
    payload = dict(
        action="delete_label",
        board_id=b,
        label_id=label["id"],
        operation_id="delete-label-retry",
    )
    first = s.execute(MEMBER, payload)
    assert s.execute(MEMBER, payload) == first
    command(s, OWNER, "remove_member", workspace_id=w, user_id=MEMBER.id)
    with pytest.raises(NotFound):
        s.execute(MEMBER, payload)
