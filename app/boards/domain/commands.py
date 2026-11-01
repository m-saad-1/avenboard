"""Typed public command contract shared by HTTP, MCP and tests."""

from typing import Annotated, Literal, Union
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CommandBase(Strict):
    operation_id: str = Field(
        default_factory=lambda: str(uuid4()), min_length=8, max_length=128
    )


class CreateWorkspace(CommandBase):
    action: Literal["create_workspace"]
    name: str = Field(min_length=1, max_length=80)
    timezone: str = "UTC"
    demo: bool = False


class UpdateWorkspace(CommandBase):
    action: Literal["update_workspace"]
    workspace_id: str
    expected_version: int
    name: str
    timezone: str


class InviteMember(CommandBase):
    action: Literal["invite_member"]
    workspace_id: str
    email: str = Field(min_length=3, max_length=254)
    role: Literal["MEMBER", "VIEWER"] = "MEMBER"


class AcceptInvite(CommandBase):
    action: Literal["accept_invite"]
    token: str = Field(min_length=20, max_length=256)


class ReviewInvite(CommandBase):
    action: Literal["approve_invite", "revoke_invite"]
    workspace_id: str
    invitation_id: str


class ManageMember(CommandBase):
    action: Literal["change_role", "remove_member", "transfer_owner"]
    workspace_id: str
    user_id: str
    role: Literal["MEMBER", "VIEWER"] = "MEMBER"


class CreateBoard(CommandBase):
    action: Literal["create_board"]
    workspace_id: str
    title: str
    description: str = Field(default="", max_length=10000)
    visibility: Literal["workspace", "private"] = "workspace"
    color: str = "indigo"


class BoardPatch(Strict):
    title: str | None = None
    description: str | None = Field(default=None, max_length=10000)
    visibility: Literal["workspace", "private"] | None = None
    color: str | None = None


class UpdateBoard(CommandBase):
    action: Literal["update_board"]
    board_id: str
    expected_version: int
    changes: BoardPatch


class BoardLifecycle(CommandBase):
    action: Literal["archive_board", "restore_board", "delete_board"]
    board_id: str
    expected_version: int
    confirmation: str = ""


class BoardAccess(CommandBase):
    action: Literal["board_access"]
    board_id: str
    expected_version: int
    user_id: str
    allow: bool


class CreateList(CommandBase):
    action: Literal["create_list"]
    board_id: str
    title: str
    category: Literal["TODO", "IN_PROGRESS", "DONE"] = "TODO"


class UpdateList(CommandBase):
    action: Literal["update_list"]
    list_id: str
    expected_version: int
    title: str
    category: Literal["TODO", "IN_PROGRESS", "DONE"]


class ListLifecycle(CommandBase):
    action: Literal["archive_list", "restore_list"]
    list_id: str
    expected_version: int


class ReorderLists(CommandBase):
    action: Literal["reorder_lists"]
    board_id: str
    expected_version: int
    list_ids: list[str]


class CreateCard(CommandBase):
    action: Literal["create_card"]
    list_id: str
    title: str
    description: str = Field(default="", max_length=20000)
    assignee_id: str | None = None
    due_date: str | None = None
    label_ids: list[str] = Field(default_factory=list, max_length=30)


class CardPatch(Strict):
    title: str | None = None
    description: str | None = Field(default=None, max_length=20000)
    assignee_id: str | None = None
    due_date: str | None = None
    label_ids: list[str] | None = Field(default=None, max_length=30)


class UpdateCard(CommandBase):
    action: Literal["update_card"]
    card_id: str
    expected_version: int
    changes: CardPatch


class MoveCard(CommandBase):
    action: Literal["move_card"]
    card_id: str
    expected_version: int
    list_id: str
    position: int = Field(default=0, ge=0)


class CardLifecycle(CommandBase):
    action: Literal["archive_card", "restore_card", "delete_card"]
    card_id: str
    expected_version: int


class SaveLabel(CommandBase):
    action: Literal["save_label"]
    board_id: str
    label_id: str | None = None
    name: str
    color: str
    description: str = Field(default="", max_length=1000)


class DeleteLabel(CommandBase):
    action: Literal["delete_label"]
    board_id: str
    label_id: str


class ChecklistItem(Strict):
    id: str | None = None
    title: str = Field(min_length=1, max_length=300)
    completed: bool = False


class SaveChecklist(CommandBase):
    action: Literal["save_checklist"]
    card_id: str
    expected_version: int
    items: list[ChecklistItem] = Field(max_length=100)
    mode: Literal["append", "replace"] = "append"


class Dependency(CommandBase):
    action: Literal["add_dependency", "remove_dependency"]
    card_id: str
    expected_version: int
    prerequisite_id: str


class CardLabel(CommandBase):
    action: Literal["add_label", "remove_label"]
    card_id: str
    expected_version: int
    label_id: str


class Favorite(CommandBase):
    action: Literal["favorite"]
    board_id: str
    value: bool


class Preference(CommandBase):
    action: Literal["preference"]
    theme: Literal["light", "dark", "system"]


Command = Annotated[
    Union[
        CreateWorkspace,
        UpdateWorkspace,
        InviteMember,
        AcceptInvite,
        ReviewInvite,
        ManageMember,
        CreateBoard,
        UpdateBoard,
        BoardLifecycle,
        BoardAccess,
        CreateList,
        UpdateList,
        ListLifecycle,
        ReorderLists,
        CreateCard,
        UpdateCard,
        MoveCard,
        CardLifecycle,
        SaveLabel,
        DeleteLabel,
        SaveChecklist,
        Dependency,
        CardLabel,
        Favorite,
        Preference,
    ],
    Field(discriminator="action"),
]
