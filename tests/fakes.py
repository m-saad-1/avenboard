"""Isolated test adapters. Never imported by the production application."""

import copy
import threading
from boards.infrastructure.schema import TABLES
from boards.domain.model import Conflict


class MemoryTransaction:
    def __init__(self, tables):
        self.tables = tables

    def get(self, table, key, guard=False):
        return copy.deepcopy(self.tables[table].get(key))

    def find(self, table, **filters):
        return [
            copy.deepcopy(r)
            for r in self.tables[table].values()
            if all(
                r.get(k) in v if isinstance(v, list) else r.get(k) == v
                for k, v in filters.items()
            )
        ]

    def put(self, table, row):
        assert set(row) == set(TABLES[table]), (table, set(row) ^ set(TABLES[table]))
        self.tables[table][row["id"]] = copy.deepcopy(row)

    def insert(self, table, row):
        if row["id"] in self.tables[table]:
            raise Conflict("Duplicate primary key")
        self.put(table, row)

    def delete(self, table, key):
        self.tables[table].pop(key, None)

    def search_card_ids(self, board_ids, filters, current_date, offset, limit):
        cards = []
        for c in self.find("cards", board_id=board_ids, archived=False, deleted=False):
            lane = self.get("lists", c["list_id"])
            board = self.get("boards", c["board_id"])
            if lane["archived"] or board["archived"] or board["deleted"]:
                continue
            q = filters.get("query", "").strip().casefold()
            if q and q not in (c["title"] + " " + c["description"]).casefold():
                continue
            if any(
                filters.get(k) and c[k] != filters[k]
                for k in ("assignee_id", "list_id")
            ):
                continue
            if filters.get("status") and lane["category"] != filters["status"]:
                continue
            if filters.get("label_id") and not self.find(
                "card_labels", card_id=c["id"], label_id=filters["label_id"]
            ):
                continue
            if filters.get("due_from") and (
                not c["due_date"] or c["due_date"] < filters["due_from"]
            ):
                continue
            if filters.get("due_to") and (
                not c["due_date"] or c["due_date"] > filters["due_to"]
            ):
                continue
            if filters.get("overdue") and (
                not c["due_date"]
                or c["due_date"] >= current_date
                or lane["category"] == "DONE"
            ):
                continue
            cards.append(c)
        cards.sort(key=lambda c: (c["due_date"] or "9999", c["number"]))
        return [c["id"] for c in cards[offset : offset + limit]], len(cards)


class MemoryRepository:
    def __init__(self):
        self.tables = {t: {} for t in TABLES}
        self.lock = threading.RLock()
        self.fail_commit = False

    def run(self, work):
        with self.lock:
            draft = copy.deepcopy(self.tables)
            result = work(MemoryTransaction(draft))
            if self.fail_commit:
                raise Conflict("Simulated transaction failure")
            self.tables = draft
            return copy.deepcopy(result)

    def semantic(self, ids, vector, limit):
        return []


class FakeAI:
    semantic_enabled = False

    def checklist(self, card):
        return [
            "Clarify the expected outcome",
            "Complete the implementation",
            "Review with the team",
        ]

    def summary(self, facts):
        return (
            "Suggestions: review the outstanding tasks. This is a test model response."
        )

    def recommendations(self, facts):
        return "Suggestions: assign unowned tasks. This is a test model response."
