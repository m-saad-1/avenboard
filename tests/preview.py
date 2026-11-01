"""Explicit loopback QA fixture. Never imported or copied into the production image.

Run: python -m uvicorn tests.preview:app --host 127.0.0.1 --port 8080
The production app has no fixture authentication or in-memory persistence.
"""

from pathlib import Path
import sys

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1] / "app"),
    str(Path(__file__).parent),
]
from boards.application.use_cases import Boards
from boards.domain.model import Person
from boards.main import create_app
from fakes import MemoryRepository, FakeAI

owner = Person("qa-owner", "ana@qa.invalid", "qa/users", "Ana Morgan")
viewer = Person("qa-viewer", "cy@qa.invalid", "qa/users", "Cy Viewer")
member = Person("qa-member", "sarah@qa.invalid", "qa/users", "Sarah Chen")


class PreviewBoards(Boards):
    def me(self, person):
        return dict(super().me(person), test_fixture=True)


service = PreviewBoards(MemoryRepository(), FakeAI())


def execute(action, actor=owner, **data):
    return service.execute(actor, dict(action=action, **data))


wid = execute(
    "create_workspace", name="Acme Studio", timezone="Asia/Karachi", demo=True
)["workspace_id"]
for person, role in ((viewer, "VIEWER"), (member, "MEMBER")):
    invitation = execute(
        "invite_member", email=person.email, workspace_id=wid, role=role
    )
    execute("accept_invite", actor=person, token=invitation["token"])
    execute(
        "approve_invite", invitation_id=invitation["invitation_id"], workspace_id=wid
    )
for board in service.list_my_boards(owner, wid):
    execute("favorite", board_id=board["id"], value=True)


def identify(headers):
    cookie = headers.get("cookie", "")
    return (
        viewer
        if "qa-role=viewer" in cookie
        else member
        if "qa-role=member" in cookie
        else owner
    )


app = create_app(service, identify)


@app.middleware("http")
async def loopback_only(request, call_next):
    from fastapi.responses import JSONResponse

    if request.client.host not in ("127.0.0.1", "::1", "testclient"):
        return JSONResponse({"error": "QA fixtures are loopback-only"}, status_code=403)
    return await call_next(request)
