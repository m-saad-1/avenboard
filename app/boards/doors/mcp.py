"""One action-based MCP door to the same application services used by the web."""

import json
from uuid import uuid4
from pydantic import ValidationError
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from boards.doors.identity import person_from
from boards.domain.model import AppError


def build_mcp(boards, identify=person_from):
    server = MCPServer(
        name="Avenboard",
        instructions=(
            "First list_my_boards. Use show_board for list/card IDs, versions and members. "
            "Never guess IDs or ambiguous names. Doing is an explicit alias of the seeded In Progress list. "
            "Mutations accept operation_id: reuse it only when retrying the SAME request. "
            "Generate checklist previews without saving; ask the user before save_checklist. "
            "Every action uses the signed-in person's permissions."
        ),
    )

    def call(ctx, fn, *args, **kwargs):
        person = identify(ctx.headers or {})
        if not person:
            raise ToolError(
                json.dumps(
                    {"code": "unauthenticated", "message": "Sign in through appid"}
                )
            )
        try:
            return fn(person, *args, **kwargs)
        except AppError as exc:
            raise ToolError(json.dumps({"code": exc.code, "message": str(exc)}))
        except ValidationError:
            raise ToolError(
                json.dumps({"code": "invalid", "message": "Invalid action parameters"})
            )

    def execute(ctx, action, operation_id="", **kwargs):
        return call(
            ctx,
            boards.execute,
            dict(action=action, operation_id=operation_id or str(uuid4()), **kwargs),
        )

    @server.tool()
    def list_my_boards(ctx: Context, workspace_id: str | None = None) -> list:
        """List only boards accessible to the signed-in person."""
        return call(ctx, boards.list_my_boards, workspace_id)

    @server.tool()
    def show_board(board_id: str, ctx: Context) -> dict:
        """Board details, versioned lists/cards, labels, dependencies and eligible members."""
        return call(ctx, boards.show_board, board_id)

    @server.tool()
    def list_my_cards(
        ctx: Context,
        workspace_id: str | None = None,
        due_from: str | None = None,
        due_to: str | None = None,
        period: str | None = None,
        offset: int = 0,
        status: str | None = None,
    ) -> dict:
        """Assigned tasks; use workspace-local YYYY-MM-DD bounds for this week."""
        return call(
            ctx,
            boards.list_my_cards,
            workspace_id,
            period=period,
            due_from=due_from,
            due_to=due_to,
            offset=offset,
            status=status,
        )

    @server.tool()
    def list_overdue(ctx: Context, workspace_id: str | None = None) -> dict:
        """Incomplete overdue cards, computed from server time and workspace timezone."""
        return call(ctx, boards.list_overdue, workspace_id)

    @server.tool()
    def create_board(
        workspace_id: str,
        title: str,
        ctx: Context,
        description: str = "",
        visibility: str = "workspace",
        operation_id: str = "",
    ) -> dict:
        """Owner only: create a board and its initial five lists."""
        return execute(
            ctx,
            "create_board",
            operation_id,
            workspace_id=workspace_id,
            title=title,
            description=description,
            visibility=visibility,
        )

    @server.tool()
    def create_card(
        board_id: str,
        title: str,
        list_name: str,
        ctx: Context,
        description: str = "",
        operation_id: str = "",
    ) -> dict:
        """Create a card in an accessible board; resolve exact list names or its Doing alias."""
        lane = call(ctx, boards.resolve_list, board_id, list_name)
        return execute(
            ctx,
            "create_card",
            operation_id,
            list_id=lane["id"],
            title=title,
            description=description,
        )

    @server.tool()
    def move_card(
        card_id: str,
        list_id: str,
        expected_version: int,
        ctx: Context,
        position: int = 0,
        operation_id: str = "",
    ) -> dict:
        """Move/reorder a card. Read show_board first for IDs and expected_version."""
        return execute(
            ctx,
            "move_card",
            operation_id,
            card_id=card_id,
            list_id=list_id,
            expected_version=expected_version,
            position=position,
        )

    @server.tool()
    def assign_card(
        card_id: str,
        assignee_id: str,
        expected_version: int,
        ctx: Context,
        operation_id: str = "",
    ) -> dict:
        """Assign an eligible member ID from list_board_members; never guess by name."""
        return execute(
            ctx,
            "update_card",
            operation_id,
            card_id=card_id,
            expected_version=expected_version,
            changes={"assignee_id": assignee_id},
        )

    @server.tool()
    def update_card(
        card_id: str,
        expected_version: int,
        changes: dict,
        ctx: Context,
        operation_id: str = "",
    ) -> dict:
        """Patch title, description, assignee_id, due_date, label_ids. Null clears due date/assignee."""
        return execute(
            ctx,
            "update_card",
            operation_id,
            card_id=card_id,
            expected_version=expected_version,
            changes=changes,
        )

    @server.tool()
    def add_label(
        card_id: str,
        label_id: str,
        expected_version: int,
        ctx: Context,
        operation_id: str = "",
    ) -> dict:
        """Add one label from the card's own board."""
        return execute(
            ctx,
            "add_label",
            operation_id,
            card_id=card_id,
            label_id=label_id,
            expected_version=expected_version,
        )

    @server.tool()
    def generate_checklist(card_id: str, ctx: Context) -> dict:
        """Generate a reviewable checklist. Does not save or overwrite anything."""
        return call(ctx, boards.generate_checklist, card_id)

    @server.tool()
    def summarize_board(board_id: str, ctx: Context) -> dict:
        """Summarize real board facts; suggestions are explicitly AI generated."""
        return call(ctx, boards.summarize_board, board_id)

    @server.tool()
    def list_board_members(board_id: str, ctx: Context) -> list:
        """Eligible assignees with stable IDs. Ask for clarification when names collide."""
        return call(ctx, lambda p: boards.show_board(p, board_id)["members"])

    @server.tool()
    def search_cards(
        workspace_id: str,
        ctx: Context,
        query: str = "",
        assignee_id: str | None = None,
        label_id: str | None = None,
        status: str | None = None,
        offset: int = 0,
        card_number: int | None = None,
    ) -> dict:
        """Search authorized cards by title/description, assignee, label or completion status."""
        if card_number is not None:
            card = call(ctx, boards.resolve_card, workspace_id, card_number)
            return {"items": [card], "total": 1, "offset": 0, "limit": 1}
        return call(
            ctx,
            boards.search_cards,
            workspace_id,
            query=query,
            assignee_id=assignee_id,
            label_id=label_id,
            status=status,
            offset=offset,
        )

    @server.tool()
    def list_blockers(board_id: str, ctx: Context, card_id: str | None = None) -> list:
        """Trace incomplete prerequisites, including unresolved archived/deleted dependencies."""
        return call(ctx, boards.list_blockers, board_id, card_id)

    @server.tool()
    def save_checklist(
        card_id: str,
        expected_version: int,
        items: list[str],
        ctx: Context,
        operation_id: str = "",
    ) -> dict:
        """Only after explicit user approval: append reviewed checklist items."""
        return execute(
            ctx,
            "save_checklist",
            operation_id,
            card_id=card_id,
            expected_version=expected_version,
            items=[{"title": item} for item in items],
            mode="append",
        )

    return server
