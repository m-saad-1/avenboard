"""The MCP door: the same use cases as the web routes, as tools Claude or ChatGPT can call.

Each tool acts as the person who connected (their gateway identity), so an agent sees exactly
the boards its person sees. Tools are actions, never raw table access.
"""
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from boards.application.use_cases import Boards, NotFound
from boards.doors.identity import person_from
from boards.domain.model import Forbidden, Invalid

INSTRUCTIONS = ("A team task board. Lists are 'To do', 'Doing' and 'Done'. Use my_boards first "
                "to find board ids, then show_board to see its cards.")


def build_mcp(boards: Boards) -> MCPServer:
    server = MCPServer(name="boards", instructions=INSTRUCTIONS)

    def call(ctx: Context, fn, *args):
        person = person_from(ctx.headers or {})
        if person is None:
            raise ToolError("401: sign in first")
        try:
            return fn(person, *args)
        except (NotFound, Forbidden, Invalid) as e:
            raise ToolError(str(e))

    @server.tool()
    def my_boards(ctx: Context) -> list:
        """The boards you are on, with your role on each."""
        return call(ctx, boards.my_boards)

    @server.tool()
    def show_board(board_id: str, ctx: Context) -> dict:
        """A board and all its cards, grouped by list."""
        return call(ctx, boards.show_board, board_id)

    @server.tool()
    def create_board(title: str, ctx: Context) -> dict:
        """Create a board. You become its owner."""
        return call(ctx, boards.create_board, title)

    @server.tool()
    def add_card(board_id: str, title: str, ctx: Context, list_name: str = "To do") -> dict:
        """Add a card to a list on a board."""
        return call(ctx, boards.add_card, board_id, title, list_name)

    @server.tool()
    def move_card(card_id: str, list_name: str, ctx: Context) -> dict:
        """Move a card to 'To do', 'Doing' or 'Done'."""
        return call(ctx, boards.move_card, card_id, list_name)

    @server.tool()
    def add_member(board_id: str, email: str, ctx: Context, role: str = "member") -> dict:
        """Owner only: add someone to a board as 'member' or 'viewer'."""
        return call(ctx, boards.add_member, board_id, email, role)

    @server.tool()
    def suggest_checklist(card_id: str, ctx: Context) -> dict:
        """AI suggestion of a checklist for a card. Changes nothing; you decide what to keep."""
        return call(ctx, boards.suggest_checklist, card_id)

    return server
