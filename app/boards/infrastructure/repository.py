"""Boards and cards stored in DataK3 tables (schema.sql). Writes are keyed upserts, so a retry is
safe: INSERT ... ON CONFLICT (id) DO UPDATE SET col = EXCLUDED.col."""
import uuid
from typing import Optional

from boards.domain.model import Board, Card, Role
from boards.infrastructure.dodil import connect


class SqlBoards:
    def get(self, board_id: str) -> Optional[Board]:
        with connect() as c:
            row = c.execute("SELECT id, title, owner_email FROM boards WHERE id = %s",
                            (board_id,)).fetchone()
            if not row:
                return None
            members = c.execute("SELECT email, role FROM memberships WHERE board_id = %s",
                                (board_id,)).fetchall()
        return Board(id=row[0], title=row[1], owner_email=row[2],
                     members={e: Role(r) for e, r in members})

    def boards_for(self, email: str) -> list:
        with connect() as c:
            ids = [r[0] for r in c.execute(
                "SELECT id FROM boards WHERE owner_email = %s "
                "UNION SELECT board_id FROM memberships WHERE email = %s", (email, email))]
        return [b for b in (self.get(i) for i in ids) if b]

    def save_board(self, board: Board) -> None:
        with connect() as c:
            c.execute("INSERT INTO boards (id, title, owner_email, created_at) "
                      "VALUES (%s, %s, %s, now()) ON CONFLICT (id) DO UPDATE SET "
                      "title = EXCLUDED.title, owner_email = EXCLUDED.owner_email",
                      (board.id, board.title, board.owner_email))
            for email, role in board.members.items():
                c.execute("INSERT INTO memberships (id, board_id, email, role) "
                          "VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET "
                          "role = EXCLUDED.role",
                          (f"{board.id}:{email}", board.id, email, role.value))

    def get_card(self, card_id: str) -> Optional[Card]:
        with connect() as c:
            r = c.execute("SELECT id, board_id, title, list_name, assignee, due_date "
                          "FROM cards WHERE id = %s", (card_id,)).fetchone()
        return Card(*r) if r else None

    def cards_on(self, board_id: str) -> list:
        with connect() as c:
            rows = c.execute("SELECT id, board_id, title, list_name, assignee, due_date "
                             "FROM cards WHERE board_id = %s ORDER BY updated_at",
                             (board_id,)).fetchall()
        return [Card(*r) for r in rows]

    def save_card(self, card: Card) -> None:
        with connect() as c:
            c.execute("INSERT INTO cards (id, board_id, list_name, title, assignee, due_date, "
                      "updated_at) VALUES (%s, %s, %s, %s, %s, %s, now()) "
                      "ON CONFLICT (id) DO UPDATE SET list_name = EXCLUDED.list_name, "
                      "title = EXCLUDED.title, assignee = EXCLUDED.assignee, "
                      "due_date = EXCLUDED.due_date, updated_at = EXCLUDED.updated_at",
                      (card.id, card.board_id, card.list_name, card.title, card.assignee,
                       card.due_date))

    def log(self, board_id: str, card_id: Optional[str], actor: str, action: str) -> None:
        with connect() as c:
            c.execute("INSERT INTO activity (id, board_id, card_id, actor, action, event_at) "
                      "VALUES (%s, %s, %s, %s, %s, now())",
                      (uuid.uuid4().hex, board_id, card_id, actor, action))
