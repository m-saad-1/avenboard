"""Every action a person can take. The web routes and the MCP tools both call these and nothing
else, so a rule cannot be skipped by using the other door.

Add a use case here, then expose it in doors/web.py and doors/mcp.py (one line each).
"""
import uuid
from dataclasses import asdict
from typing import Optional

from boards.application.ports import Assistant, BoardRepository
from boards.domain.model import Board, Card, Forbidden, Invalid, Person, Role


class NotFound(Exception):
    pass


def _card(c: Card) -> dict:
    d = asdict(c)
    d["due_date"] = c.due_date.isoformat() if c.due_date else None
    return d


class Boards:
    def __init__(self, repo: BoardRepository, assistant: Optional[Assistant] = None):
        self.repo, self.assistant = repo, assistant

    def _board(self, board_id: str, person: Person) -> Board:
        board = self.repo.get(board_id)
        if board is None:
            raise NotFound("no such board")
        try:
            board.require_view(person)
        except Forbidden:
            raise NotFound("no such board")  # a board you can't see doesn't exist for you
        return board

    def _find_card(self, card_id: str, person: Person) -> tuple:
        card = self.repo.get_card(card_id)
        if card is None:
            raise NotFound("no such card")
        return self._board(card.board_id, person), card

    def create_board(self, person: Person, title: str) -> dict:
        if not title.strip():
            raise Invalid("a board needs a title")
        board = Board(id=uuid.uuid4().hex[:12], title=title.strip(), owner_email=person.email)
        self.repo.save_board(board)
        self.repo.log(board.id, None, person.email, f"created board {board.title!r}")
        return {"id": board.id, "title": board.title}

    def my_boards(self, person: Person) -> list:
        return [{"id": b.id, "title": b.title, "role": b.role_of(person).value}
                for b in self.repo.boards_for(person.email)]

    def show_board(self, person: Person, board_id: str) -> dict:
        board = self._board(board_id, person)
        cards = [_card(c) for c in self.repo.cards_on(board.id)]
        return {"id": board.id, "title": board.title, "role": board.role_of(person).value,
                "cards": cards}

    def add_member(self, person: Person, board_id: str, email: str, role: str) -> dict:
        board = self._board(board_id, person)
        board.add_member(person, email, Role(role))
        self.repo.save_board(board)
        self.repo.log(board.id, None, person.email, f"added {email} as {role}")
        return {"board_id": board.id, "email": email, "role": role}

    def add_card(self, person: Person, board_id: str, title: str,
                 list_name: str = "To do") -> dict:
        board = self._board(board_id, person)
        board.require_edit(person)
        card = Card(id=uuid.uuid4().hex[:12], board_id=board.id, title=title.strip())
        card.move_to(list_name)
        self.repo.save_card(card)
        self.repo.log(board.id, card.id, person.email, f"added card {card.title!r}")
        return _card(card)

    def move_card(self, person: Person, card_id: str, list_name: str) -> dict:
        board, card = self._find_card(card_id, person)
        board.require_edit(person)
        before = card.list_name
        card.move_to(list_name)
        self.repo.save_card(card)
        self.repo.log(board.id, card.id, person.email, f"moved from {before} to {list_name}")
        return _card(card)

    def suggest_checklist(self, person: Person, card_id: str) -> dict:
        """An AI suggestion only: it changes nothing. A person decides what to keep."""
        _, card = self._find_card(card_id, person)
        if self.assistant is None:
            raise Invalid("no AI assistant configured")
        return {"card_id": card.id, "suggested_checklist": self.assistant.checklist(card.title)}
