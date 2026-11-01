import pytest
from boards.application.use_cases import Boards
from boards.domain.model import Person
from fakes import MemoryRepository, FakeAI

OWNER = Person("owner", "ana@example.test", "test/users", "Ana")
MEMBER = Person("member", "sarah@example.test", "test/users", "Sarah")
VIEWER = Person("viewer", "cy@example.test", "test/users", "Cy")
STRANGER = Person("stranger", "stranger@example.test", "other/users", "Stranger")


@pytest.fixture
def svc():
    return Boards(MemoryRepository(), FakeAI())


def command(svc, person, action, **kwargs):
    return svc.execute(person, dict(action=action, **kwargs))


@pytest.fixture
def setup(svc):
    wid = command(
        svc, OWNER, "create_workspace", name="Studio", timezone="Asia/Karachi"
    )["workspace_id"]
    for actor, role in ((MEMBER, "MEMBER"), (VIEWER, "VIEWER")):
        invite = command(
            svc, OWNER, "invite_member", workspace_id=wid, email=actor.email, role=role
        )
        result = command(svc, actor, "accept_invite", token=invite["token"])
        assert result["status"] == "awaiting-owner-approval"
        command(
            svc,
            OWNER,
            "approve_invite",
            workspace_id=wid,
            invitation_id=invite["invitation_id"],
        )
    board = command(svc, OWNER, "create_board", workspace_id=wid, title="Operations")
    lanes = svc.show_board(OWNER, board["id"])["lists"]
    card = command(
        svc,
        MEMBER,
        "create_card",
        list_id=lanes[1]["id"],
        title="Send invoice",
        assignee_id=MEMBER.id,
        due_date="2020-01-01",
    )
    return svc, wid, board["id"], lanes, card
