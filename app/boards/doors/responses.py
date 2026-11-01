"""Public response contracts, independent of storage implementation."""

from typing import Literal
from pydantic import BaseModel

Role = Literal["OWNER", "MEMBER", "VIEWER"]
Status = Literal["TODO", "IN_PROGRESS", "DONE"]


class User(BaseModel):
    id: str
    subject: str
    pool: str
    email: str
    name: str
    role: Role | None = None


class Identity(BaseModel):
    user: User
    theme: Literal["system", "light", "dark"]
    test_fixture: bool = False


class Workspace(BaseModel):
    id: str
    name: str
    owner_id: str
    timezone: str
    version: int
    is_demo: bool
    role: Role | None = None


class Board(BaseModel):
    id: str
    workspace_id: str
    title: str
    description: str
    color: str
    visibility: Literal["workspace", "private"]
    version: int
    archived: bool
    deleted: bool


class Lane(BaseModel):
    id: str
    board_id: str
    title: str
    category: Status
    alias: str
    position: int
    version: int
    archived: bool


class Item(BaseModel):
    id: str
    title: str
    completed: bool
    position: int


class Card(BaseModel):
    id: str
    workspace_id: str
    board_id: str
    list_id: str
    number: int
    title: str
    description: str
    assignee_id: str | None
    due_date: str | None
    position: int
    version: int
    status: Status
    label_ids: list[str]
    checklist: list[Item]
    inactive: bool
    archived: bool
    deleted: bool
    overdue: bool
    due_soon: bool
    group: str
    created_by: str
    created_at: str
    updated_at: str


class Label(BaseModel):
    id: str
    board_id: str
    name: str
    color: str
    description: str


class Activity(BaseModel):
    id: str
    board_id: str | None
    card_id: str | None
    actor_name: str
    action: str
    before_json: str
    after_json: str
    created_at: str


class DependencyRecord(BaseModel):
    id: str
    board_id: str
    card_id: str
    prerequisite_id: str


class Invitation(BaseModel):
    id: str
    email: str
    role: str
    status: str
    expires_at: str
    applicant_id: str | None


class BoardMember(BaseModel):
    board_id: str
    user_id: str


class Counts(BaseModel):
    boards: int
    tasks: int
    completed: int
    in_progress: int
    overdue: int
    assigned: int


class Snapshot(BaseModel):
    workspace: Workspace
    role: Role
    boards: list[Board]
    lists: list[Lane]
    cards: list[Card]
    labels: list[Label]
    dependencies: list[DependencyRecord]
    members: list[User]
    invitations: list[Invitation]
    board_members: list[BoardMember]
    favorites: list[str]
    activity: list[Activity]
    server_today: str
    counts: Counts


class ActivityPage(BaseModel):
    items: list[Activity]
    total: int


class CardPage(BaseModel):
    items: list[Card]
    total: int
    offset: int
    limit: int
