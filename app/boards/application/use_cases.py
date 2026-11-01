"""Shared application operations. All authorization and mutation semantics live here."""

import copy
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from uuid import uuid4
from pydantic import TypeAdapter
from boards.domain.commands import Command
from boards.domain.model import (
    Invalid,
    Forbidden,
    NotFound,
    Conflict,
    Unavailable,
    PALETTE,
    DEFAULT_LISTS,
    timestamp,
    utcnow,
    today,
    title,
    valid_timezone,
    calendar_date,
    check_version,
    task_group,
    assert_no_cycle,
)

COMMANDS = TypeAdapter(Command)
OWNER_ACTIONS = {
    "update_workspace",
    "invite_member",
    "approve_invite",
    "revoke_invite",
    "change_role",
    "remove_member",
    "transfer_owner",
    "create_board",
    "update_board",
    "archive_board",
    "restore_board",
    "delete_board",
    "board_access",
}


def uid():
    return str(uuid4())


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Boards:
    def __init__(self, repo, assistant=None):
        self.repo, self.assistant = repo, assistant

    def _person(self, tx, person):
        current = tx.get("users", person.id)
        row = dict(
            id=person.id,
            subject=person.subject,
            pool=person.pool,
            email=person.email,
            name=person.name or person.email.split("@")[0] or "Teammate",
        )
        if row != current:
            tx.put("users", row)
        return row

    def _workspace(self, tx, person, key, guard=False):
        workspace = tx.get("workspaces", key, guard)
        membership = tx.get("memberships", f"{key}:{person.id}", guard)
        if not workspace or not membership or membership["status"] != "active":
            raise NotFound("Workspace not found")
        return workspace, membership

    def _board(self, tx, person, key, guard=False, inactive=False, allow_deleted=False):
        board = tx.get("boards", key, guard)
        if not board or (board["deleted"] and not allow_deleted):
            raise NotFound("Board not found")
        workspace, membership = self._workspace(
            tx, person, board["workspace_id"], guard
        )
        if (
            board["visibility"] == "private"
            and membership["role"] != "OWNER"
            and not tx.get("board_members", f"{key}:{person.id}", guard)
        ):
            raise NotFound("Board not found")
        if board["archived"] and not inactive:
            raise Conflict("Restore the board before changing its contents")
        return board, workspace, membership

    def _scope(self, tx, person, data):
        action, board, workspace, membership = data["action"], None, None, None
        if action in ("create_workspace", "preference", "accept_invite"):
            return board, workspace, membership
        board_id = data.get("board_id")
        for key, table in (
            ("card_id", "cards"),
            ("list_id", "lists"),
            ("label_id", "labels"),
        ):
            if data.get(key) and not board_id:
                resource = tx.get(table, data[key], True)
                if not resource:
                    raise NotFound("Resource not found")
                board_id = resource["board_id"]
        if board_id:
            board, workspace, membership = self._board(
                tx,
                person,
                board_id,
                True,
                inactive=True,
                allow_deleted=True,
            )
        elif data.get("workspace_id"):
            workspace, membership = self._workspace(
                tx, person, data["workspace_id"], True
            )
        else:
            raise Invalid("A workspace or board resource is required")
        if action in OWNER_ACTIONS and membership["role"] != "OWNER":
            raise Forbidden("Only the workspace owner can do this")
        if membership["role"] == "VIEWER" and action != "favorite":
            raise Forbidden("Viewers have read-only access")
        return board, workspace, membership

    def execute(self, person, command):
        model = COMMANDS.validate_python(command)
        data = model.model_dump()
        if hasattr(model, "changes"):
            data["changes"] = model.changes.model_dump(exclude_unset=True)
        fingerprint = digest(encoded(data))

        def work(tx):
            board, workspace, membership = self._scope(tx, person, data)
            self._person(tx, person)
            scope = workspace["id"] if workspace else ""
            receipt_id = digest(f"{person.id}:{scope}:{data['operation_id']}")
            receipt = tx.get("receipts", receipt_id, True)
            if receipt:
                if receipt["fingerprint"] != fingerprint:
                    raise Conflict(
                        "Operation key was already used for a different request"
                    )
                result = json.loads(receipt["result_json"])
                if data["action"] in ("create_workspace", "accept_invite"):
                    if (
                        result.get("workspace_id")
                        and result.get("status") != "awaiting-owner-approval"
                    ):
                        self._workspace(tx, person, result["workspace_id"])
                return result
            if board and board["deleted"]:
                raise NotFound("Board not found")
            if (
                board
                and board["archived"]
                and data["action"] not in ("restore_board", "delete_board", "favorite")
            ):
                raise Conflict("Restore the board before changing its contents")
            result = self._mutate(tx, person, data, board, workspace, membership)
            # Invitation links are disclosed once; receipts must not persist bearer tokens.
            saved = {k: v for k, v in result.items() if k != "token"}
            tx.insert(
                "receipts",
                dict(
                    id=receipt_id,
                    workspace_id=scope or None,
                    actor_id=person.id,
                    fingerprint=fingerprint,
                    result_json=encoded(saved),
                    created_at=timestamp(),
                ),
            )
            return result

        return self.repo.run(work)

    def _event(
        self,
        tx,
        person,
        workspace_id,
        action,
        before,
        after,
        board_id=None,
        card_id=None,
    ):
        tx.insert(
            "activity",
            dict(
                id=uid(),
                workspace_id=workspace_id,
                board_id=board_id,
                card_id=card_id,
                actor_id=person.id,
                actor_name=person.name or person.email,
                action=action,
                before_json=encoded(before),
                after_json=encoded(after),
                created_at=timestamp(),
            ),
        )

    def _touch(self, tx, table, row):
        row["version"] += 1
        if table == "cards":
            row["updated_at"] = timestamp()
        tx.put(table, row)

    def _card(self, tx, person, card_id, inactive=False):
        card = tx.get("cards", card_id, True)
        if not card or card["deleted"]:
            raise NotFound("Card not found")
        board, workspace, membership = self._board(
            tx, person, card["board_id"], True, inactive
        )
        lane = tx.get("lists", card["list_id"], True)
        if (
            not lane
            or (lane["archived"] and not inactive)
            or (card["archived"] and not inactive)
        ):
            raise Conflict("Restore the card and its list before editing")
        return card, board, workspace, membership

    def _assignment(self, tx, board, user_id):
        if not user_id:
            return None
        member = tx.get("memberships", f"{board['workspace_id']}:{user_id}", True)
        if not member or member["status"] != "active":
            raise Invalid("Assignee must be an active workspace member")
        if (
            board["visibility"] == "private"
            and member["role"] != "OWNER"
            and not tx.get("board_members", f"{board['id']}:{user_id}", True)
        ):
            raise Invalid("Assignee must have access to this board")
        return user_id

    def _labels(self, tx, person, card, ids):
        ids = list(dict.fromkeys(ids))
        for key in ids:
            label = tx.get("labels", key)
            if not label or label["board_id"] != card["board_id"]:
                raise Invalid("Labels must belong to this board")
        old = tx.find("card_labels", card_id=card["id"])
        for row in old:
            tx.delete("card_labels", row["id"])
        for key in ids:
            tx.put(
                "card_labels",
                dict(
                    id=f"{card['id']}:{key}",
                    workspace_id=card["workspace_id"],
                    board_id=card["board_id"],
                    card_id=card["id"],
                    label_id=key,
                ),
            )
        return [r["label_id"] for r in old]

    def _index_job(self, tx, card):
        tx.put(
            "embedding_jobs",
            dict(
                id=card["id"],
                workspace_id=card["workspace_id"],
                board_id=card["board_id"],
                card_id=card["id"],
                content_version=card["content_version"],
                status="pending",
                lease_until=None,
                attempts=0,
            ),
        )

    def me(self, person):
        def work(tx):
            user = self._person(tx, person)
            pref = tx.get("preferences", person.id)
            return dict(user=user, theme=pref["theme"] if pref else "system")

        return self.repo.run(work)

    def workspaces(self, person):
        def work(tx):
            memberships = tx.find("memberships", user_id=person.id, status="active")
            return [
                dict(tx.get("workspaces", m["workspace_id"]), role=m["role"])
                for m in memberships
            ]

        return self.repo.run(work)

    def _snapshot(self, tx, person, workspace_id, card_ids=None):
        workspace, member = self._workspace(tx, person, workspace_id)
        all_boards = tx.find("boards", workspace_id=workspace_id, deleted=False)
        grants = {
            r["board_id"]
            for r in tx.find(
                "board_members", workspace_id=workspace_id, user_id=person.id
            )
        }
        boards = [
            b
            for b in all_boards
            if b["visibility"] == "workspace"
            or member["role"] == "OWNER"
            or b["id"] in grants
        ]
        board_ids = [b["id"] for b in boards]
        active_boards = {b["id"] for b in boards if not b["archived"]}
        lists = tx.find("lists", board_id=board_ids) if board_ids else []
        lanes = {r["id"]: r for r in lists}
        selected = {} if card_ids is None else {"id": card_ids}
        children = {} if card_ids is None else {"card_id": card_ids}
        raw_cards = (
            tx.find("cards", board_id=board_ids, deleted=False, **selected)
            if board_ids
            else []
        )
        links = (
            tx.find("card_labels", board_id=board_ids, **children) if board_ids else []
        )
        items = (
            tx.find("checklist_items", board_id=board_ids, **children)
            if board_ids
            else []
        )
        current = today(workspace["timezone"])
        cards = []
        for row in raw_cards:
            lane = lanes.get(row["list_id"])
            if not lane:
                continue
            card = dict(
                row,
                status=lane["category"],
                list_name=lane["title"],
                label_ids=[r["label_id"] for r in links if r["card_id"] == row["id"]],
                checklist=sorted(
                    [r for r in items if r["card_id"] == row["id"]],
                    key=lambda r: r["position"],
                ),
                inactive=row["archived"]
                or lane["archived"]
                or row["board_id"] not in active_boards,
            )
            card["overdue"] = bool(
                card["due_date"]
                and card["due_date"] < current.isoformat()
                and card["status"] != "DONE"
                and not card["inactive"]
            )
            card["due_soon"] = bool(
                card["due_date"]
                and current.isoformat()
                <= card["due_date"]
                < (current + timedelta(days=7)).isoformat()
                and card["status"] != "DONE"
                and not card["inactive"]
            )
            card["group"] = task_group(card, workspace["timezone"])
            cards.append(card)
        members = []
        for m in tx.find("memberships", workspace_id=workspace_id, status="active"):
            user = tx.get("users", m["user_id"])
            if user:
                members.append(dict(user, role=m["role"]))
        active_cards = [c for c in cards if not c["inactive"]]
        events = [
            e
            for e in tx.find("activity", workspace_id=workspace_id)
            if e["board_id"] is None or e["board_id"] in board_ids
        ]
        events.sort(key=lambda e: (e["created_at"], e["id"]), reverse=True)
        invitations = []
        if member["role"] == "OWNER":
            invitations = [
                {k: v for k, v in r.items() if k != "token_hash"}
                for r in tx.find("invitations", workspace_id=workspace_id)
            ]
            for inv in invitations:
                if (
                    inv["status"] in ("pending", "awaiting-owner-approval")
                    and datetime.fromisoformat(inv["expires_at"]) <= utcnow()
                ):
                    inv["status"] = "expired"
        return dict(
            workspace=workspace,
            role=member["role"],
            boards=boards,
            lists=sorted(lists, key=lambda r: (r["position"], r["id"])),
            cards=sorted(cards, key=lambda r: (r["position"], r["id"])),
            labels=tx.find("labels", board_id=board_ids) if board_ids else [],
            dependencies=tx.find("dependencies", board_id=board_ids)
            if board_ids
            else [],
            members=members,
            invitations=invitations,
            board_members=tx.find("board_members", board_id=board_ids)
            if board_ids
            else [],
            favorites=[
                r["board_id"]
                for r in tx.find(
                    "favorites", workspace_id=workspace_id, user_id=person.id
                )
                if r["board_id"] in board_ids
            ],
            activity=events[:50],
            server_today=current.isoformat(),
            counts=dict(
                boards=len(active_boards),
                tasks=len(active_cards),
                completed=sum(c["status"] == "DONE" for c in active_cards),
                in_progress=sum(c["status"] == "IN_PROGRESS" for c in active_cards),
                overdue=sum(c["overdue"] for c in active_cards),
                assigned=sum(c["assignee_id"] == person.id for c in active_cards),
            ),
        )

    def snapshot(self, person, workspace_id):
        return self.repo.run(lambda tx: self._snapshot(tx, person, workspace_id))

    def list_my_boards(self, person, workspace_id=None):
        spaces = [
            w
            for w in self.workspaces(person)
            if not workspace_id or w["id"] == workspace_id
        ]
        return [
            dict(b, role=s["role"])
            for s in spaces
            for b in self.snapshot(person, s["id"])["boards"]
            if not b["archived"]
        ]

    def show_board(self, person, board_id):
        def work(tx):
            board, workspace, member = self._board(tx, person, board_id, inactive=True)
            snap = self._snapshot(tx, person, workspace["id"])
            result = dict(
                board,
                role=member["role"],
                server_today=snap["server_today"],
                timezone=workspace["timezone"],
            )
            for key in ("lists", "cards", "labels", "dependencies", "activity"):
                result[key] = [r for r in snap[key] if r["board_id"] == board_id]
            grants = {
                r["user_id"] for r in snap["board_members"] if r["board_id"] == board_id
            }
            result["members"] = [
                m
                for m in snap["members"]
                if board["visibility"] == "workspace"
                or m["role"] == "OWNER"
                or m["id"] in grants
            ]
            return result

        return self.repo.run(work)

    def search_cards(
        self,
        person,
        workspace_id,
        query="",
        assignee_id=None,
        label_id=None,
        list_id=None,
        due_from=None,
        due_to=None,
        status=None,
        overdue=False,
        offset=0,
        limit=50,
    ):
        due_from, due_to = calendar_date(due_from), calendar_date(due_to)
        if status and status not in ("TODO", "IN_PROGRESS", "DONE"):
            raise Invalid("Unknown completion status")
        if due_from and due_to and due_from > due_to:
            raise Invalid("The start date must precede the end date")
        offset, limit = max(0, offset), max(1, min(100, limit))
        filters = dict(
            query=query,
            assignee_id=assignee_id,
            label_id=label_id,
            list_id=list_id,
            due_from=due_from,
            due_to=due_to,
            status=status,
            overdue=overdue,
        )

        def work(tx):
            workspace, membership = self._workspace(tx, person, workspace_id, True)
            grants = {
                r["board_id"]
                for r in tx.find(
                    "board_members", workspace_id=workspace_id, user_id=person.id
                )
            }
            boards = tx.find(
                "boards", workspace_id=workspace_id, archived=False, deleted=False
            )
            allowed = [
                b["id"]
                for b in boards
                if b["visibility"] == "workspace"
                or membership["role"] == "OWNER"
                or b["id"] in grants
            ]
            for key in allowed:
                self._board(tx, person, key, True)
            ids, total = tx.search_card_ids(
                allowed,
                filters,
                today(workspace["timezone"]).isoformat(),
                offset,
                limit,
            )
            snap = self._snapshot(tx, person, workspace_id, ids)
            by_id = {c["id"]: c for c in snap["cards"] if not c["inactive"]}
            return dict(
                items=[by_id[key] for key in ids if key in by_id],
                total=total,
                offset=offset,
                limit=limit,
            )

        return self.repo.run(work)

    def list_my_cards(self, person, workspace_id=None, period=None, **filters):
        spaces = [
            w
            for w in self.workspaces(person)
            if not workspace_id or w["id"] == workspace_id
        ]
        result = {}
        if period not in (None, "this_week"):
            raise Invalid("Period must be this_week")
        for w in spaces:
            bounds = dict(filters)
            if period == "this_week":
                current = today(w["timezone"])
                start = current - timedelta(days=current.weekday())
                bounds.update(
                    due_from=start.isoformat(),
                    due_to=(start + timedelta(days=6)).isoformat(),
                )
            result[w["id"]] = self.search_cards(
                person, w["id"], assignee_id=person.id, **bounds
            )
        return result

    def list_overdue(self, person, workspace_id=None):
        spaces = [
            w
            for w in self.workspaces(person)
            if not workspace_id or w["id"] == workspace_id
        ]
        return {
            w["id"]: self.search_cards(person, w["id"], overdue=True) for w in spaces
        }

    def activity(self, person, card_id, offset=0, limit=50):
        def work(tx):
            card, _, _, _ = self._card(tx, person, card_id, inactive=True)
            events = tx.find("activity", card_id=card["id"])
            events.sort(key=lambda e: (e["created_at"], e["id"]))
            return dict(
                items=events[max(0, offset) : max(0, offset) + min(100, max(1, limit))],
                total=len(events),
            )

        return self.repo.run(work)

    def workspace_activity(
        self, person, workspace_id, board_id=None, offset=0, limit=50
    ):
        def work(tx):
            _, membership = self._workspace(tx, person, workspace_id)
            boards = tx.find("boards", workspace_id=workspace_id)
            grants = {
                g["board_id"]
                for g in tx.find(
                    "board_members", workspace_id=workspace_id, user_id=person.id
                )
            }
            allowed = {
                b["id"]
                for b in boards
                if membership["role"] == "OWNER"
                or b["visibility"] == "workspace"
                or b["id"] in grants
            }
            if board_id and board_id not in allowed:
                raise NotFound("Board not found")
            events = [
                e
                for e in tx.find("activity", workspace_id=workspace_id)
                if (not board_id or e["board_id"] == board_id)
                and (e["board_id"] is None or e["board_id"] in allowed)
            ]
            events.sort(key=lambda e: (e["created_at"], e["id"]), reverse=True)
            return dict(
                items=events[offset : offset + min(100, max(1, limit))],
                total=len(events),
            )

        return self.repo.run(work)

    def _mutate(self, tx, person, d, board, workspace, membership):
        action = d["action"]
        if action == "create_workspace":
            if d["demo"]:
                previous = tx.find("workspaces", owner_id=person.id, is_demo=True)
                if previous:
                    return dict(workspace_id=previous[0]["id"])
            workspace = dict(
                id=uid(),
                name=title(d["name"], 80),
                owner_id=person.id,
                timezone=valid_timezone(d["timezone"]),
                version=1,
                next_card=1,
                is_demo=d["demo"],
                created_at=timestamp(),
            )
            tx.insert("workspaces", workspace)
            membership = dict(
                id=f"{workspace['id']}:{person.id}",
                workspace_id=workspace["id"],
                user_id=person.id,
                role="OWNER",
                status="active",
            )
            tx.insert("memberships", membership)
            self._event(
                tx,
                person,
                workspace["id"],
                "workspace_created",
                None,
                {"name": workspace["name"]},
            )
            if d["demo"]:
                self._seed(tx, person, workspace, membership)
            return dict(workspace_id=workspace["id"])
        if action == "preference":
            tx.put(
                "preferences", dict(id=person.id, user_id=person.id, theme=d["theme"])
            )
            return dict(theme=d["theme"])
        if action == "update_workspace":
            check_version(workspace, d["expected_version"])
            before = copy.deepcopy(workspace)
            workspace.update(
                name=title(d["name"], 80), timezone=valid_timezone(d["timezone"])
            )
            self._touch(tx, "workspaces", workspace)
            self._event(tx, person, workspace["id"], action, before, workspace)
            return workspace
        if action == "invite_member":
            email = d["email"].strip().lower()
            if "@" not in email or any(c.isspace() for c in email):
                raise Invalid("Enter a valid email address")
            token = secrets.token_urlsafe(32)
            invitation = dict(
                id=uid(),
                workspace_id=workspace["id"],
                email=email,
                role=d["role"],
                token_hash=digest(token),
                status="pending",
                applicant_id=None,
                expires_at=(utcnow() + timedelta(days=7)).isoformat(),
                created_at=timestamp(),
            )
            tx.insert("invitations", invitation)
            self._touch(tx, "workspaces", workspace)
            self._event(
                tx,
                person,
                workspace["id"],
                action,
                None,
                {"email": email, "role": d["role"]},
            )
            return dict(invitation_id=invitation["id"], token=token)
        if action == "accept_invite":
            invitations = tx.find("invitations", token_hash=digest(d["token"]))
            if not invitations:
                raise NotFound("Invitation not found")
            invitation = tx.get("invitations", invitations[0]["id"], True)
            if (
                invitation["status"] != "pending"
                or datetime.fromisoformat(invitation["expires_at"]) <= utcnow()
            ):
                raise Conflict("This invitation has expired or has already been used")
            if invitation["email"] != person.email.lower():
                raise Forbidden(
                    "Sign in with the email address this invitation was sent to"
                )
            workspace = tx.get("workspaces", invitation["workspace_id"], True)
            invitation["applicant_id"] = person.id
            invitation["status"] = (
                "accepted" if person.email_verified else "awaiting-owner-approval"
            )
            tx.put("invitations", invitation)
            if invitation["status"] == "accepted":
                self._activate(tx, invitation)
            self._touch(tx, "workspaces", workspace)
            self._event(
                tx,
                person,
                workspace["id"],
                action,
                None,
                {"status": invitation["status"]},
            )
            return dict(workspace_id=workspace["id"], status=invitation["status"])
        if action in ("approve_invite", "revoke_invite"):
            invitation = tx.get("invitations", d["invitation_id"], True)
            if not invitation or invitation["workspace_id"] != workspace["id"]:
                raise NotFound("Invitation not found")
            if invitation["status"] not in ("pending", "awaiting-owner-approval"):
                raise Conflict("This invitation is no longer pending")
            if action == "approve_invite":
                if (
                    invitation["status"] != "awaiting-owner-approval"
                    or datetime.fromisoformat(invitation["expires_at"]) <= utcnow()
                ):
                    raise Invalid("A current acceptance request is required")
                self._activate(tx, invitation)
                invitation["status"] = "accepted"
            else:
                invitation["status"] = "revoked"
            tx.put("invitations", invitation)
            self._touch(tx, "workspaces", workspace)
            self._event(
                tx,
                person,
                workspace["id"],
                action,
                None,
                {"invitation_id": invitation["id"]},
            )
            return dict(status=invitation["status"])
        if action in ("change_role", "remove_member", "transfer_owner"):
            target = tx.get("memberships", f"{workspace['id']}:{d['user_id']}", True)
            if not target or target["status"] != "active":
                raise NotFound("Active member not found")
            if target["role"] == "OWNER":
                raise Invalid("Transfer ownership to another active member first")
            before = copy.deepcopy(target)
            if action == "transfer_owner":
                target["role"] = "OWNER"
                membership["role"] = "MEMBER"
                tx.put("memberships", membership)
                workspace["owner_id"] = target["user_id"]
                # The former owner's implicit access ends atomically with transfer.
                private = {
                    b["id"]
                    for b in tx.find(
                        "boards", workspace_id=workspace["id"], visibility="private"
                    )
                    if not tx.get("board_members", f"{b['id']}:{person.id}", True)
                }
                for card in tx.find(
                    "cards", workspace_id=workspace["id"], assignee_id=person.id
                ):
                    if card["board_id"] in private:
                        card["assignee_id"] = None
                        self._touch(tx, "cards", card)
                        self._event(
                            tx,
                            person,
                            workspace["id"],
                            "assignee_changed",
                            person.id,
                            None,
                            card["board_id"],
                            card["id"],
                        )
            elif action == "change_role":
                target["role"] = d["role"]
            else:
                target["status"] = "removed"
                for grant in tx.find(
                    "board_members",
                    workspace_id=workspace["id"],
                    user_id=target["user_id"],
                ):
                    tx.delete("board_members", grant["id"])
                for card in tx.find(
                    "cards", workspace_id=workspace["id"], assignee_id=target["user_id"]
                ):
                    card["assignee_id"] = None
                    self._touch(tx, "cards", card)
                    self._event(
                        tx,
                        person,
                        workspace["id"],
                        "assignee_changed",
                        target["user_id"],
                        None,
                        card["board_id"],
                        card["id"],
                    )
            tx.put("memberships", target)
            self._touch(tx, "workspaces", workspace)
            self._event(tx, person, workspace["id"], action, before, target)
            return dict(
                user_id=target["user_id"], role=target["role"], status=target["status"]
            )
        if action == "create_board":
            if d["color"] not in PALETTE:
                raise Invalid("Choose a label palette color")
            board = dict(
                id=uid(),
                workspace_id=workspace["id"],
                title=title(d["title"]),
                description=d["description"],
                visibility=d["visibility"],
                color=d["color"],
                version=1,
                archived=False,
                deleted=False,
                created_at=timestamp(),
            )
            tx.insert("boards", board)
            for position, (name, category) in enumerate(DEFAULT_LISTS):
                tx.insert(
                    "lists",
                    dict(
                        id=uid(),
                        workspace_id=workspace["id"],
                        board_id=board["id"],
                        title=name,
                        category=category,
                        alias="Doing" if name == "In Progress" else "",
                        position=position,
                        version=1,
                        archived=False,
                    ),
                )
            self._event(tx, person, workspace["id"], action, None, board, board["id"])
            return board
        if action in (
            "update_board",
            "archive_board",
            "restore_board",
            "delete_board",
            "board_access",
        ):
            check_version(board, d["expected_version"])
            before = copy.deepcopy(board)
            if action == "update_board":
                changes = d["changes"]
                if "title" in changes:
                    changes["title"] = title(changes["title"])
                if changes.get("color") is not None and changes["color"] not in PALETTE:
                    raise Invalid("Choose a palette color")
                if any(v is None for v in changes.values()):
                    raise Invalid("Board fields cannot be null")
                board.update(changes)
            elif action == "delete_board":
                if d["confirmation"] != board["title"]:
                    raise Invalid("Type the board name to confirm deletion")
                board["deleted"] = True
            elif action == "board_access":
                target = tx.get(
                    "memberships", f"{workspace['id']}:{d['user_id']}", True
                )
                if not target or target["status"] != "active":
                    raise Invalid("Choose an active workspace member")
                key = f"{board['id']}:{d['user_id']}"
                if d["allow"]:
                    tx.put(
                        "board_members",
                        dict(
                            id=key,
                            workspace_id=workspace["id"],
                            board_id=board["id"],
                            user_id=d["user_id"],
                        ),
                    )
                else:
                    tx.delete("board_members", key)
                self._event(
                    tx,
                    person,
                    workspace["id"],
                    action,
                    None,
                    {"user_id": d["user_id"], "allow": d["allow"]},
                    board["id"],
                )
            else:
                board["archived"] = action == "archive_board"
            self._touch(tx, "boards", board)
            # Visibility/ACL changes cannot leave a card assigned to someone without access.
            for card in tx.find("cards", board_id=board["id"]):
                if card["assignee_id"]:
                    try:
                        self._assignment(tx, board, card["assignee_id"])
                    except Invalid:
                        prior = card["assignee_id"]
                        card["assignee_id"] = None
                        self._touch(tx, "cards", card)
                        self._event(
                            tx,
                            person,
                            workspace["id"],
                            "assignee_changed",
                            prior,
                            None,
                            board["id"],
                            card["id"],
                        )
            self._event(tx, person, workspace["id"], action, before, board, board["id"])
            return board
        if action == "favorite":
            key = f"{board['id']}:{person.id}"
            if d["value"]:
                tx.put(
                    "favorites",
                    dict(
                        id=key,
                        workspace_id=workspace["id"],
                        board_id=board["id"],
                        user_id=person.id,
                    ),
                )
            else:
                tx.delete("favorites", key)
            return dict(value=d["value"])
        if action == "create_list":
            lane = dict(
                id=uid(),
                workspace_id=workspace["id"],
                board_id=board["id"],
                title=title(d["title"]),
                category=d["category"],
                alias="",
                position=1
                + max(
                    (r["position"] for r in tx.find("lists", board_id=board["id"])),
                    default=-1,
                ),
                version=1,
                archived=False,
            )
            tx.insert("lists", lane)
            self._touch(tx, "boards", board)
            self._event(tx, person, workspace["id"], action, None, lane, board["id"])
            return lane
        if action in ("update_list", "archive_list", "restore_list"):
            lane = tx.get("lists", d["list_id"], True)
            check_version(lane, d["expected_version"])
            before = copy.deepcopy(lane)
            if action == "update_list":
                lane.update(title=title(d["title"]), category=d["category"])
            else:
                lane["archived"] = action == "archive_list"
                if action == "restore_list" and before["archived"]:
                    lane["position"] = 1 + max(
                        (
                            r["position"]
                            for r in tx.find(
                                "lists", board_id=board["id"], archived=False
                            )
                        ),
                        default=-1,
                    )
            self._touch(tx, "lists", lane)
            self._touch(tx, "boards", board)
            self._event(tx, person, workspace["id"], action, before, lane, board["id"])
            if before["category"] != lane["category"]:
                for card in tx.find("cards", list_id=lane["id"]):
                    self._touch(tx, "cards", card)
                    self._event(
                        tx,
                        person,
                        workspace["id"],
                        "status_changed",
                        before["category"],
                        lane["category"],
                        board["id"],
                        card["id"],
                    )
            return lane
        if action == "reorder_lists":
            check_version(board, d["expected_version"])
            lanes = tx.find("lists", board_id=board["id"], archived=False)
            if len(set(d["list_ids"])) != len(lanes) or set(d["list_ids"]) != {
                r["id"] for r in lanes
            }:
                raise Invalid("Include every active list exactly once")
            for lane in lanes:
                lane["position"] = d["list_ids"].index(lane["id"])
                self._touch(tx, "lists", lane)
            self._touch(tx, "boards", board)
            self._event(
                tx, person, workspace["id"], action, None, d["list_ids"], board["id"]
            )
            return dict(version=board["version"])
        if action == "create_card":
            lane = tx.get("lists", d["list_id"], True)
            if lane["archived"]:
                raise Invalid("Cannot add a card to an archived list")
            now = timestamp()
            card = dict(
                id=uid(),
                workspace_id=workspace["id"],
                board_id=board["id"],
                list_id=lane["id"],
                number=workspace["next_card"],
                title=title(d["title"]),
                description=d["description"],
                assignee_id=self._assignment(tx, board, d["assignee_id"]),
                due_date=calendar_date(d["due_date"]),
                position=len(
                    tx.find("cards", list_id=lane["id"], archived=False, deleted=False)
                ),
                version=1,
                content_version=1,
                created_by=person.id,
                created_at=now,
                updated_at=now,
                archived=False,
                deleted=False,
            )
            workspace["next_card"] += 1
            self._touch(tx, "workspaces", workspace)
            tx.insert("cards", card)
            self._labels(tx, person, card, d["label_ids"])
            self._index_job(tx, card)
            self._touch(tx, "boards", board)
            self._event(
                tx,
                person,
                workspace["id"],
                action,
                None,
                dict(card, label_ids=d["label_ids"]),
                board["id"],
                card["id"],
            )
            return card
        if action in ("save_label", "delete_label"):
            label = tx.get("labels", d["label_id"], True) if d.get("label_id") else None
            if d.get("label_id") and not label:
                raise NotFound("Label not found")
            if label and label["board_id"] != board["id"]:
                raise NotFound("Label not found")
            if action == "delete_label":
                if not label:
                    raise NotFound("Label not found")
                tx.delete("labels", label["id"])
            else:
                if d["color"] not in PALETTE:
                    raise Invalid("Choose a palette color")
                previous = copy.deepcopy(label)
                label = dict(
                    id=label["id"] if label else uid(),
                    workspace_id=workspace["id"],
                    board_id=board["id"],
                    name=title(d["name"], 50),
                    color=d["color"],
                    description=d["description"],
                )
                tx.put("labels", label)
            for link in tx.find("card_labels", label_id=label["id"]):
                if action == "delete_label":
                    tx.delete("card_labels", link["id"])
                card = tx.get("cards", link["card_id"], True)
                self._touch(tx, "cards", card)
                self._event(
                    tx,
                    person,
                    workspace["id"],
                    action,
                    label if action == "delete_label" else previous,
                    None if action == "delete_label" else label,
                    board["id"],
                    card["id"],
                )
            self._touch(tx, "boards", board)
            self._event(tx, person, workspace["id"], action, None, label, board["id"])
            return label
        return self._mutate_card(tx, person, d, board, workspace)

    def _activate(self, tx, invitation):
        key = f"{invitation['workspace_id']}:{invitation['applicant_id']}"
        previous = tx.get("memberships", key, True)
        if previous and previous["status"] == "active":
            raise Conflict("This person is already an active member")
        tx.put(
            "memberships",
            dict(
                id=key,
                workspace_id=invitation["workspace_id"],
                user_id=invitation["applicant_id"],
                role=invitation["role"],
                status="active",
            ),
        )

    def _mutate_card(self, tx, person, d, board, workspace):
        action = d["action"]
        card, _, _, _ = self._card(
            tx, person, d["card_id"], inactive=action in ("restore_card", "delete_card")
        )
        check_version(card, d["expected_version"])
        lane = tx.get("lists", card["list_id"], True)
        if lane["archived"]:
            raise Conflict("Restore the parent list first")
        before = copy.deepcopy(card)
        if action == "update_card":
            changes = copy.deepcopy(d["changes"])
            labels_changed = False
            if "title" in changes:
                changes["title"] = title(changes["title"])
            if "description" in changes and changes["description"] is None:
                raise Invalid("Description cannot be null")
            if "due_date" in changes:
                changes["due_date"] = calendar_date(changes["due_date"])
            if "assignee_id" in changes:
                changes["assignee_id"] = self._assignment(
                    tx, board, changes["assignee_id"]
                )
            if "label_ids" in changes:
                ids = changes.pop("label_ids")
                if ids is None:
                    raise Invalid("Labels must be a list")
                old = self._labels(tx, person, card, ids)
                if sorted(old) != sorted(ids):
                    labels_changed = True
                    self._event(
                        tx,
                        person,
                        workspace["id"],
                        "labels_changed",
                        old,
                        ids,
                        board["id"],
                        card["id"],
                    )
            for field, value in changes.items():
                if card[field] != value:
                    self._event(
                        tx,
                        person,
                        workspace["id"],
                        field + "_changed",
                        card[field],
                        value,
                        board["id"],
                        card["id"],
                    )
                card[field] = value
            if card == before and not labels_changed:
                return card
            if any(card[k] != before[k] for k in ("title", "description")):
                card["content_version"] += 1
                self._index_job(tx, card)
        elif action == "move_card":
            target = tx.get("lists", d["list_id"], True)
            if not target or target["board_id"] != board["id"] or target["archived"]:
                raise Invalid("Choose an active list on this board")
            source = card["list_id"]
            for list_id in dict.fromkeys([source, target["id"]]):
                rows = sorted(
                    [
                        r
                        for r in tx.find(
                            "cards", list_id=list_id, archived=False, deleted=False
                        )
                        if r["id"] != card["id"]
                    ],
                    key=lambda r: (r["position"], r["id"]),
                )
                if list_id == target["id"]:
                    rows.insert(min(d["position"], len(rows)), card)
                for position, row in enumerate(rows):
                    if row["id"] == card["id"]:
                        card.update(list_id=target["id"], position=position)
                    elif row["position"] != position:
                        old_position = row["position"]
                        row["position"] = position
                        self._touch(tx, "cards", row)
                        self._event(
                            tx,
                            person,
                            workspace["id"],
                            "position_changed",
                            old_position,
                            position,
                            board["id"],
                            row["id"],
                        )
            self._event(
                tx,
                person,
                workspace["id"],
                action,
                {"list_id": source, "position": before["position"]},
                {"list_id": card["list_id"], "position": card["position"]},
                board["id"],
                card["id"],
            )
        elif action in ("archive_card", "restore_card", "delete_card"):
            if action == "delete_card":
                card["deleted"] = True
            else:
                card["archived"] = action == "archive_card"
            rows = sorted(
                (
                    r
                    for r in tx.find(
                        "cards", list_id=card["list_id"], archived=False, deleted=False
                    )
                    if r["id"] != card["id"]
                ),
                key=lambda r: (r["position"], r["id"]),
            )
            if action == "restore_card" and before["archived"]:
                card["position"] = len(rows)
            if action in ("archive_card", "delete_card"):
                for position, row in enumerate(rows):
                    if row["position"] != position:
                        old_position = row["position"]
                        row["position"] = position
                        self._touch(tx, "cards", row)
                        self._event(
                            tx,
                            person,
                            workspace["id"],
                            "position_changed",
                            old_position,
                            position,
                            board["id"],
                            row["id"],
                        )
            self._event(
                tx,
                person,
                workspace["id"],
                action,
                {
                    "archived": before["archived"],
                    "deleted": before["deleted"],
                    "position": before["position"],
                },
                {
                    "archived": card["archived"],
                    "deleted": card["deleted"],
                    "position": card["position"],
                },
                board["id"],
                card["id"],
            )
        elif action == "save_checklist":
            old = tx.find("checklist_items", card_id=card["id"])
            old_ids = {r["id"] for r in old}
            supplied = [r["id"] for r in d["items"] if r["id"]]
            if len(set(supplied)) != len(supplied) or any(
                key not in old_ids for key in supplied
            ):
                raise Invalid(
                    "Checklist item IDs must belong to this card and be unique"
                )
            if d["mode"] == "append" and supplied:
                raise Invalid("Append new items without existing item IDs")
            new = [] if d["mode"] == "replace" else copy.deepcopy(old)
            if len(new) + len(d["items"]) > 100:
                raise Invalid("A checklist can contain at most 100 items")
            for item in d["items"]:
                new.append(
                    dict(
                        id=item["id"] or uid(),
                        workspace_id=workspace["id"],
                        board_id=board["id"],
                        card_id=card["id"],
                        title=title(item["title"], 300),
                        completed=item["completed"],
                        position=len(new),
                    )
                )
            for row in old:
                tx.delete("checklist_items", row["id"])
            for row in new:
                tx.put("checklist_items", row)
            self._event(
                tx, person, workspace["id"], action, old, new, board["id"], card["id"]
            )
        elif action in ("add_label", "remove_label"):
            label = tx.get("labels", d["label_id"], True)
            if not label or label["board_id"] != board["id"]:
                raise Invalid("Labels must belong to this board")
            old = [r["label_id"] for r in tx.find("card_labels", card_id=card["id"])]
            ids = (
                list(dict.fromkeys(old + [d["label_id"]]))
                if action == "add_label"
                else [key for key in old if key != d["label_id"]]
            )
            self._labels(tx, person, card, ids)
            self._event(
                tx,
                person,
                workspace["id"],
                "labels_changed",
                old,
                ids,
                board["id"],
                card["id"],
            )
        elif action in ("add_dependency", "remove_dependency"):
            prerequisite = tx.get("cards", d["prerequisite_id"], True)
            if not prerequisite or prerequisite["board_id"] != board["id"]:
                raise NotFound("Dependency card not found")
            key = f"{card['id']}:{prerequisite['id']}"
            if action == "add_dependency":
                if prerequisite["deleted"]:
                    raise Invalid("Cannot add a deleted prerequisite")
                assert_no_cycle(
                    tx.find("dependencies", board_id=board["id"]),
                    card["id"],
                    prerequisite["id"],
                )
                if tx.get("dependencies", key):
                    raise Conflict("This dependency already exists")
                tx.insert(
                    "dependencies",
                    dict(
                        id=key,
                        workspace_id=workspace["id"],
                        board_id=board["id"],
                        card_id=card["id"],
                        prerequisite_id=prerequisite["id"],
                    ),
                )
            else:
                if not tx.get("dependencies", key):
                    raise NotFound("Dependency not found")
                tx.delete("dependencies", key)
            self._event(
                tx,
                person,
                workspace["id"],
                action,
                prerequisite["id"] if action == "remove_dependency" else None,
                prerequisite["id"] if action == "add_dependency" else None,
                board["id"],
                card["id"],
            )
        else:
            raise Invalid("Unsupported action")
        self._touch(tx, "cards", card)
        self._touch(tx, "boards", board)
        return card

    def _seed(self, tx, person, workspace, membership):
        board_names = ("Product Development", "Marketing Campaign", "Operations")
        task_sets = (
            (
                ("Design new landing page", 2, 2),
                ("Implement authentication", 1, 5),
                ("Review website performance", 3, -2),
                ("Complete API integration", 2, 1),
                ("Website redesign", 1, 7),
                ("Homepage redesign", 2, 3),
            ),
            (
                ("Prepare product launch campaign", 2, 4),
                ("Publish social media campaign", 4, -1),
                ("Launch the marketing website", 1, 8),
            ),
            (
                ("Send client invoice", 1, 0),
                ("Review launch readiness", 3, 2),
                ("Send invoice", 2, -1),
            ),
        )
        for index, name in enumerate(board_names):
            d = COMMANDS.validate_python(
                dict(
                    action="create_board",
                    workspace_id=workspace["id"],
                    title=name,
                    description=(
                        "Build thoughtful experiences, one focused task at a time."
                        if index == 0
                        else "A shared place for the team's next milestones."
                    ),
                )
            ).model_dump()
            board = self._mutate(tx, person, d, None, workspace, membership)
            lanes = sorted(
                tx.find("lists", board_id=board["id"]), key=lambda r: r["position"]
            )
            labels = []
            for label_name, color in (
                ("Design", "purple"),
                ("Engineering", "blue"),
                ("Priority", "rose"),
            ):
                label = self._mutate(
                    tx,
                    person,
                    dict(
                        action="save_label",
                        board_id=board["id"],
                        label_id=None,
                        name=label_name,
                        color=color,
                        description="Sample workspace label",
                    ),
                    board,
                    workspace,
                    membership,
                )
                labels.append(label["id"])
            made = []
            for task_name, list_index, days in task_sets[index]:
                d = COMMANDS.validate_python(
                    dict(
                        action="create_card",
                        list_id=lanes[list_index]["id"],
                        title=task_name,
                        description=f"Sample task: {task_name}. Define the outcome, coordinate with the team, and review the result. Example collaborators: Sarah Chen and Omar Ali (sample names, not accounts).",
                        due_date=(
                            today(workspace["timezone"]) + timedelta(days=days)
                        ).isoformat(),
                        assignee_id=person.id,
                        label_ids=[labels[len(made) % len(labels)]],
                    )
                ).model_dump()
                card = self._mutate(tx, person, d, board, workspace, membership)
                made.append(card)
            if len(made) > 2:
                self._mutate_card(
                    tx,
                    person,
                    dict(
                        action="add_dependency",
                        card_id=made[-1]["id"],
                        expected_version=made[-1]["version"],
                        prerequisite_id=made[0]["id"],
                    ),
                    board,
                    workspace,
                )

    def list_blockers(self, person, board_id, card_id=None):
        board = self.show_board(person, board_id)
        cards = {c["id"]: c for c in board["cards"]}
        if card_id and card_id not in cards:
            raise NotFound("Target card not found")
        roots = (
            [card_id]
            if card_id
            else [
                c["id"]
                for c in cards.values()
                if not c["inactive"] and c["status"] != "DONE"
            ]
        )
        adjacency = {}
        for edge in board["dependencies"]:
            adjacency.setdefault(edge["card_id"], []).append(edge["prerequisite_id"])
        result = {}
        for root in roots:
            pending = list(adjacency.get(root, []))
            seen = set()
            while pending:
                key = pending.pop()
                if key in seen:
                    continue
                seen.add(key)
                task = cards.get(key)
                if task is None or task["inactive"] or task["status"] != "DONE":
                    result[key] = dict(
                        card_id=key,
                        title=task["title"] if task else "Deleted prerequisite",
                        unresolved=task is None or task["inactive"],
                        blocks=root,
                    )
                    pending.extend(adjacency.get(key, []))
        return list(result.values())

    def resolve_card(self, person, workspace_id, reference):
        cards = self.snapshot(person, workspace_id)["cards"]
        matches = [
            c
            for c in cards
            if not c["inactive"]
            and (
                c["id"] == reference
                or str(c["number"]) == str(reference)
                or c["title"].casefold() == str(reference).casefold()
            )
        ]
        if len(matches) != 1:
            raise Invalid(
                "Specify one accessible card ID; the name or number is missing or ambiguous"
            )
        return matches[0]

    def resolve_list(self, person, board_id, reference):
        lanes = [
            r for r in self.show_board(person, board_id)["lists"] if not r["archived"]
        ]
        matches = [
            r
            for r in lanes
            if r["id"] == reference or r["title"].casefold() == reference.casefold()
        ]
        if not matches:
            matches = [
                r
                for r in lanes
                if r["alias"] and r["alias"].casefold() == reference.casefold()
            ]
        if len(matches) != 1:
            raise Invalid(
                "Specify one accessible list ID; the name is missing or ambiguous"
            )
        return matches[0]

    def generate_checklist(self, person, card_id):
        if not self.assistant:
            raise Unavailable("Dodil Models is not configured")
        card = self.repo.run(lambda tx: self._card(tx, person, card_id)[0])
        items = self.assistant.checklist(
            {"title": card["title"], "description": card["description"]}
        )
        current = self.repo.run(lambda tx: self._card(tx, person, card_id)[0])
        if current["version"] != card["version"]:
            raise Conflict(
                "The card changed while generating. Generate a new checklist."
            )
        if (
            not isinstance(items, list)
            or not 1 <= len(items) <= 20
            or any(
                not isinstance(x, str) or not x.strip() or len(x) > 300 for x in items
            )
        ):
            raise Unavailable("The model returned an invalid checklist. Please retry.")
        return dict(
            card_id=card_id,
            expected_version=card["version"],
            items=items,
            generated=True,
            saved=False,
        )

    def board_facts(self, person, board_id):
        board = self.show_board(person, board_id)
        cards = [c for c in board["cards"] if not c["inactive"]]
        return dict(
            board_id=board_id,
            title=board["title"],
            as_of=timestamp(),
            total=len(cards),
            completed=sum(c["status"] == "DONE" for c in cards),
            overdue=sum(c["overdue"] for c in cards),
            blockers=self.list_blockers(person, board_id),
            tasks=[
                {
                    k: c[k]
                    for k in (
                        "id",
                        "title",
                        "status",
                        "due_date",
                        "overdue",
                        "assignee_id",
                    )
                }
                for c in cards
            ],
        )

    def summarize_board(self, person, board_id, recommendations=False):
        if not self.assistant:
            raise Unavailable("Dodil Models is not configured")
        facts = self.board_facts(person, board_id)
        if len(facts["tasks"]) > 500:
            raise Invalid(
                "Select a board with at most 500 active cards for an AI summary"
            )
        result = (
            self.assistant.recommendations(facts)
            if recommendations
            else self.assistant.summary(facts)
        )
        self.show_board(person, board_id)  # Reauthorize after model latency.
        return dict(
            facts=facts, suggestions=result, generated=True, as_of=facts["as_of"]
        )

    def process_embeddings(self, board_ids=None, limit=5):
        if not self.assistant or not getattr(self.assistant, "semantic_enabled", False):
            return 0
        completed = 0
        for _ in range(limit):

            def claim(tx):
                jobs = tx.find(
                    "embedding_jobs",
                    **({"board_id": board_ids} if board_ids is not None else {}),
                )
                for candidate in jobs:
                    if candidate["status"] == "done" or candidate["attempts"] >= 5:
                        continue
                    if (
                        candidate["lease_until"]
                        and datetime.fromisoformat(candidate["lease_until"]) > utcnow()
                    ):
                        continue
                    job = tx.get("embedding_jobs", candidate["id"], True)
                    card = tx.get("cards", job["card_id"], True)
                    board = tx.get("boards", job["board_id"], True)
                    lane = tx.get("lists", card["list_id"], True) if card else None
                    if (
                        not card
                        or card["deleted"]
                        or card["archived"]
                        or not board
                        or board["deleted"]
                        or board["archived"]
                        or not lane
                        or lane["archived"]
                    ):
                        continue
                    job.update(
                        status="working",
                        lease_until=(utcnow() + timedelta(minutes=3)).isoformat(),
                        attempts=job["attempts"] + 1,
                    )
                    tx.put("embedding_jobs", job)
                    return job, card
                return None

            claimed = self.repo.run(claim)
            if not claimed:
                break
            job, card = claimed
            try:
                vector = self.assistant.embed(
                    card["title"] + "\n" + card["description"]
                )

                def finish(tx):
                    current = tx.get("cards", card["id"], True)
                    actual = tx.get("embedding_jobs", job["id"], True)
                    if (
                        not current
                        or current["content_version"] != job["content_version"]
                        or actual["lease_until"] != job["lease_until"]
                    ):
                        return False
                    tx.put(
                        "embeddings",
                        dict(
                            id=card["id"],
                            workspace_id=card["workspace_id"],
                            board_id=card["board_id"],
                            card_id=card["id"],
                            content_version=card["content_version"],
                            model=self.assistant.embedding_model,
                            dimensions=len(vector),
                            embedding="[" + ",".join(map(str, vector)) + "]",
                        ),
                    )
                    actual.update(status="done", lease_until=None)
                    tx.put("embedding_jobs", actual)
                    return True

                completed += bool(self.repo.run(finish))
            except Unavailable:

                def release(tx):
                    current = tx.get("embedding_jobs", job["id"], True)
                    if current and current["lease_until"] == job["lease_until"]:
                        current.update(
                            status="pending",
                            lease_until=(utcnow() + timedelta(minutes=2)).isoformat(),
                        )
                        tx.put("embedding_jobs", current)

                self.repo.run(release)
                break
        return completed

    def semantic_search(self, person, workspace_id, query):
        title(query, 1000)
        if not self.assistant or not getattr(self.assistant, "semantic_enabled", False):
            raise Unavailable(
                "Semantic search awaits the Dodil Models/DataK3 contract check. Keyword search is available."
            )
        snapshot = self.snapshot(person, workspace_id)
        ids = [b["id"] for b in snapshot["boards"] if not b["archived"]]
        self.process_embeddings(ids, limit=3)
        vector = self.assistant.embed(query, query=True)
        ranked = self.repo.semantic(ids, vector, 20)
        current = self.snapshot(person, workspace_id)
        current_ids = [b["id"] for b in current["boards"] if not b["archived"]]
        cards = {c["id"]: c for c in current["cards"] if not c["inactive"]}
        results = [
            dict(cards[r["card_id"]], distance=float(r["distance"]))
            for r in ranked
            if r["card_id"] in cards
            and cards[r["card_id"]]["content_version"] == r["content_version"]
        ]
        return dict(
            items=results,
            indexing=self.repo.run(
                lambda tx: sum(
                    r["status"] != "done"
                    for r in tx.find("embedding_jobs", board_id=current_ids)
                )
            ),
        )
