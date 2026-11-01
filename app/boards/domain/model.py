"""Domain vocabulary and deterministic rules, independent of HTTP and storage."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class AppError(Exception):
    status, code = 422, "invalid"


class Invalid(AppError):
    pass


class Forbidden(AppError):
    status, code = 403, "forbidden"


class NotFound(AppError):
    status, code = 404, "not_found"


class Conflict(AppError):
    status, code = 409, "conflict"


class Unavailable(AppError):
    status, code = 503, "unavailable"


class Role(str, Enum):
    OWNER = "OWNER"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


@dataclass(frozen=True)
class Person:
    subject: str
    email: str
    pool: str
    name: str = ""
    email_verified: bool = False

    @property
    def id(self):
        return f"{self.pool}:{self.subject}"


PALETTE = (
    "indigo",
    "blue",
    "teal",
    "green",
    "amber",
    "orange",
    "rose",
    "purple",
    "slate",
)
DEFAULT_LISTS = (
    ("Backlog", "TODO"),
    ("Todo", "TODO"),
    ("In Progress", "IN_PROGRESS"),
    ("Review", "IN_PROGRESS"),
    ("Done", "DONE"),
)


def utcnow():
    return datetime.now(timezone.utc)


def timestamp():
    return utcnow().isoformat()


def title(value, maximum=160):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise Invalid(f"Enter between 1 and {maximum} characters")
    return value.strip()


def valid_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise Invalid("Choose a valid IANA timezone")
    return value


def calendar_date(value):
    if value in (None, ""):
        return None
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
        return value
    except (TypeError, ValueError):
        raise Invalid("Due date must be a valid YYYY-MM-DD calendar date")


def today(zone, now=None):
    return (now or utcnow()).astimezone(ZoneInfo(zone)).date()


def task_group(card, zone, now=None):
    if card["status"] == "DONE":
        return "Completed"
    if not card.get("due_date"):
        return "No Due Date"
    due, current = date.fromisoformat(card["due_date"]), today(zone, now)
    if due < current:
        return "Overdue"
    if due == current:
        return "Today"
    if due <= current + timedelta(days=6 - current.weekday()):
        return "This Week"
    return "Upcoming"


def check_version(row, expected):
    if expected is None or row["version"] != expected:
        raise Conflict("Changed since you opened it. Refresh and try again.")


def assert_no_cycle(edges, card_id, prerequisite_id):
    if card_id == prerequisite_id:
        raise Invalid("A task cannot depend on itself")
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge["card_id"], []).append(edge["prerequisite_id"])
    pending, seen = [prerequisite_id], set()
    while pending:
        node = pending.pop()
        if node == card_id:
            raise Invalid("This dependency would create a cycle")
        if node not in seen:
            seen.add(node)
            pending.extend(adjacency.get(node, []))
