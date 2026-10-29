"""The board's language and rules. No database, no HTTP: plain Python you can test in a second.

Extend HERE first: a rule written in the domain holds for the web page and for Claude alike.
"""
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

LISTS = ("To do", "Doing", "Done")


class Role(str, Enum):
    OWNER = "owner"
    MEMBER = "member"
    VIEWER = "viewer"


class Forbidden(Exception):
    """The person may not do this. The doors turn it into 403 (web) or a tool error (MCP)."""


class Invalid(Exception):
    """The request breaks a rule of the board itself. 422 / tool error."""


@dataclass(frozen=True)
class Person:
    """Who is acting: taken from the gateway's sign-in, never from the request body."""
    email: str


@dataclass
class Card:
    id: str
    board_id: str
    title: str
    list_name: str = LISTS[0]
    assignee: Optional[str] = None
    due_date: Optional[date] = None

    def move_to(self, list_name: str) -> None:
        if list_name not in LISTS:
            raise Invalid(f"unknown list {list_name!r}; lists are {', '.join(LISTS)}")
        self.list_name = list_name


@dataclass
class Board:
    id: str
    title: str
    owner_email: str
    members: dict = field(default_factory=dict)  # email -> Role

    def role_of(self, person: Person) -> Optional[Role]:
        if person.email == self.owner_email:
            return Role.OWNER
        return self.members.get(person.email)

    def require_view(self, person: Person) -> None:
        if self.role_of(person) is None:
            raise Forbidden("you are not on this board")

    def require_edit(self, person: Person) -> None:
        role = self.role_of(person)
        if role is None:
            raise Forbidden("you are not on this board")
        if role is Role.VIEWER:
            raise Forbidden("viewers can't change the board")

    def add_member(self, by: Person, email: str, role: Role) -> None:
        if self.role_of(by) is not Role.OWNER:
            raise Forbidden("only the owner manages members")
        if role is Role.OWNER:
            raise Invalid("a board has one owner")
        self.members[email.strip().lower()] = role
