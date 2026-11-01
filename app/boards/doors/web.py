"""Typed HTTP commands and queries; application services own all business rules."""

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel, Field
from boards.domain.commands import Command
from boards.doors.identity import person_from
from boards.doors import responses as dto


class SearchRequest(BaseModel):
    workspace_id: str
    query: str = Field(min_length=1, max_length=1000)


def build_router(boards, identify=person_from):
    router = APIRouter(prefix="/api")

    def me(request):
        person = identify(request.headers)
        if person is None:
            raise HTTPException(
                401,
                detail={
                    "code": "unauthenticated",
                    "message": "Sign in through Dodil appid",
                    "login_url": "/.dodil/auth/login?return_to=/",
                },
            )
        return person

    @router.get("/me", response_model=dto.Identity)
    def identity(request: Request):
        return boards.me(me(request))

    @router.get("/workspaces", response_model=list[dto.Workspace])
    def workspaces(request: Request):
        return boards.workspaces(me(request))

    @router.post("/commands")
    def command(body: Command, request: Request):
        return boards.execute(me(request), body)

    @router.get("/workspaces/{workspace_id}/snapshot", response_model=dto.Snapshot)
    def snapshot(workspace_id: str, request: Request):
        return boards.snapshot(me(request), workspace_id)

    @router.get("/boards")
    def list_boards(request: Request, workspace_id: str | None = None):
        return boards.list_my_boards(me(request), workspace_id)

    @router.get("/workspaces/{workspace_id}/activity", response_model=dto.ActivityPage)
    def workspace_activity(
        workspace_id: str,
        request: Request,
        board_id: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
    ):
        return boards.workspace_activity(
            me(request), workspace_id, board_id, offset, limit
        )

    @router.get("/boards/{board_id}")
    def board(board_id: str, request: Request):
        return boards.show_board(me(request), board_id)

    @router.get("/cards", response_model=dto.CardPage)
    def cards(
        request: Request,
        workspace_id: str,
        query: str = "",
        assignee_id: str | None = None,
        label_id: str | None = None,
        list_id: str | None = None,
        due_from: str | None = None,
        due_to: str | None = None,
        status: str | None = None,
        overdue: bool = False,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
    ):
        return boards.search_cards(
            me(request),
            workspace_id,
            query,
            assignee_id,
            label_id,
            list_id,
            due_from,
            due_to,
            status,
            overdue,
            offset,
            limit,
        )

    @router.get("/my-tasks")
    def tasks(request: Request, workspace_id: str | None = None):
        return boards.list_my_cards(me(request), workspace_id)

    @router.get("/overdue")
    def overdue(request: Request, workspace_id: str | None = None):
        return boards.list_overdue(me(request), workspace_id)

    @router.get("/cards/{card_id}/activity", response_model=dto.ActivityPage)
    def activity(
        card_id: str,
        request: Request,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
    ):
        return boards.activity(me(request), card_id, offset, limit)

    @router.get("/boards/{board_id}/blockers")
    def blockers(board_id: str, request: Request, card_id: str | None = None):
        return boards.list_blockers(me(request), board_id, card_id)

    @router.post("/cards/{card_id}/generate-checklist")
    def checklist(card_id: str, request: Request):
        return boards.generate_checklist(me(request), card_id)

    @router.post("/boards/{board_id}/summary")
    def summary(board_id: str, request: Request):
        return boards.summarize_board(me(request), board_id)

    @router.post("/boards/{board_id}/recommendations")
    def recommendations(board_id: str, request: Request):
        return boards.summarize_board(me(request), board_id, recommendations=True)

    @router.post("/semantic-search")
    def semantic(body: SearchRequest, request: Request):
        return boards.semantic_search(me(request), body.workspace_id, body.query)

    return router
