"""Transactional DataK3 repository. Buffered writes make pending-read semantics irrelevant."""

import copy
import random
import threading
import time
from datetime import date, datetime, timezone
from psycopg import sql, Error
from psycopg.rows import dict_row
from boards.infrastructure.dodil import connect
from boards.infrastructure.schema import TABLES
from boards.domain.model import Conflict, Unavailable


def normalize(value):
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


class SqlTransaction:
    def __init__(self, conn):
        self.conn, self.cache, self.writes, self.inserts, self.removed = (
            conn,
            {},
            {},
            set(),
            set(),
        )

    def _table(self, table):
        if table not in TABLES:
            raise ValueError("Unknown internal table")
        return sql.Identifier("ab_" + table)

    def get(self, table, key, guard=False):
        identity = (table, key)
        if identity in self.removed:
            return None
        if identity in self.writes:
            return copy.deepcopy(self.writes[identity])
        if identity not in self.cache or guard:
            query = sql.SQL('SELECT * FROM {} WHERE "id" = %s').format(
                self._table(table)
            )
            if guard:
                query += sql.SQL(" FOR UPDATE")
            row = self.conn.execute(query, (key,)).fetchone()
            self.cache[identity] = (
                {k: normalize(v) for k, v in row.items()} if row else None
            )
        return copy.deepcopy(self.cache[identity])

    def find(self, table, **filters):
        for key in filters:
            if key not in TABLES[table]:
                raise ValueError("Unknown internal column")
        clauses, values = [], []
        for key, value in filters.items():
            if isinstance(value, list):
                clauses.append(sql.SQL("{} = ANY(%s)").format(sql.Identifier(key)))
            else:
                clauses.append(
                    sql.SQL("{} IS NOT DISTINCT FROM %s").format(sql.Identifier(key))
                )
            values.append(value)
        query = sql.SQL("SELECT * FROM {}").format(self._table(table))
        if clauses:
            query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses)
        rows = {
            row["id"]: {k: normalize(v) for k, v in row.items()}
            for row in self.conn.execute(query, values).fetchall()
        }
        for (name, key), row in self.writes.items():
            if name == table:
                rows[key] = copy.deepcopy(row)

        def matches(row):
            return all(
                row.get(k) in v if isinstance(v, list) else row.get(k) == v
                for k, v in filters.items()
            )

        return [
            r
            for key, r in rows.items()
            if (table, key) not in self.removed and matches(r)
        ]

    def put(self, table, row):
        key = (table, row["id"])
        was_removed = key in self.removed
        self.removed.discard(key)
        if not was_removed and not self.get(table, row["id"]):
            self.inserts.add(key)
        self.writes[key] = copy.deepcopy(row)
        self.removed.discard(key)

    def search_card_ids(self, board_ids, filters, current_date, offset, limit):
        if not board_ids:
            return [], 0
        clauses = [
            "c.board_id = ANY(%s)",
            "c.archived = FALSE",
            "c.deleted = FALSE",
            "l.archived = FALSE",
            "b.archived = FALSE",
            "b.deleted = FALSE",
        ]
        values = [board_ids]
        if filters.get("query"):
            clauses.append(
                "contains(lower(c.title || ' ' || c.description), lower(%s))"
            )
            values.append(filters["query"].strip())
        for key, column in (
            ("assignee_id", "c.assignee_id"),
            ("list_id", "c.list_id"),
            ("status", "l.category"),
        ):
            if filters.get(key):
                clauses.append(column + " = %s")
                values.append(filters[key])
        if filters.get("label_id"):
            clauses.append(
                "EXISTS (SELECT 1 FROM ab_card_labels cl WHERE cl.card_id=c.id AND cl.label_id=%s)"
            )
            values.append(filters["label_id"])
        for key, operator in (("due_from", ">="), ("due_to", "<=")):
            if filters.get(key):
                clauses.append("c.due_date " + operator + " %s::date")
                values.append(filters[key])
        if filters.get("overdue"):
            clauses.extend(["c.due_date < %s::date", "l.category <> 'DONE'"])
            values.append(current_date)
        source = (
            " FROM ab_cards c JOIN ab_lists l ON l.id=c.list_id JOIN ab_boards b ON b.id=c.board_id WHERE "
            + " AND ".join(clauses)
        )
        total = self.conn.execute(
            "SELECT COUNT(*) AS total" + source, values
        ).fetchone()["total"]
        rows = self.conn.execute(
            "SELECT c.id"
            + source
            + " ORDER BY c.due_date ASC NULLS LAST,c.number LIMIT %s OFFSET %s",
            values + [limit, offset],
        ).fetchall()
        return [r["id"] for r in rows], total

    def insert(self, table, row):
        key = (table, row["id"])
        if self.get(table, row["id"]):
            raise Conflict("This record already exists")
        self.inserts.add(key)
        self.writes[key] = copy.deepcopy(row)

    def delete(self, table, key):
        identity = (table, key)
        if identity in self.inserts:
            self.inserts.remove(identity)
        else:
            self.removed.add(identity)
        self.writes.pop(identity, None)

    def flush(self):
        for (table, key), row in self.writes.items():
            columns = list(row)
            if any(c not in TABLES[table] for c in columns):
                raise ValueError("Unknown persisted column")
            values = [row[c] for c in columns]
            if (table, key) in self.inserts:
                query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    self._table(table),
                    sql.SQL(",").join(map(sql.Identifier, columns)),
                    sql.SQL(",").join(sql.Placeholder() for _ in columns),
                )
            else:
                columns = [c for c in columns if c != "id"]
                values = [row[c] for c in columns] + [key]
                query = sql.SQL('UPDATE {} SET {} WHERE "id" = %s').format(
                    self._table(table),
                    sql.SQL(",").join(
                        sql.SQL("{} = %s").format(sql.Identifier(c)) for c in columns
                    ),
                )
            self.conn.execute(query, values)
        for table, key in self.removed:
            self.conn.execute(
                sql.SQL('DELETE FROM {} WHERE "id" = %s').format(self._table(table)),
                (key,),
            )


class SqlBoards:
    def __init__(self, connector=connect):
        self.connector = connector
        self.slots = threading.BoundedSemaphore(6)

    def run(self, work):
        for attempt in range(3):
            try:
                with self.slots, self.connector() as conn:
                    conn.row_factory = dict_row
                    with conn.transaction():
                        tx = SqlTransaction(conn)
                        result = work(tx)
                        tx.flush()
                    return result
            except Error as exc:
                if exc.sqlstate in ("40001", "23505") and attempt < 2:
                    time.sleep(random.uniform(0.02, 0.08) * (attempt + 1))
                    continue
                if exc.sqlstate in ("40001", "23505"):
                    raise Conflict(
                        "Concurrent changes detected. Refresh and retry."
                    ) from exc
                raise Unavailable(
                    "Data service unavailable. No success has been confirmed."
                ) from exc
            except OSError as exc:
                raise Unavailable(
                    "DataK3 service credentials are not configured."
                ) from exc

    def semantic(self, board_ids, vector, limit=20):
        if not board_ids:
            return []
        literal = "[" + ",".join(str(float(x)) for x in vector) + "]"
        with self.slots, self.connector() as conn:
            conn.row_factory = dict_row
            # Access is constrained before vector ranking. Hydration rechecks current access.
            return conn.execute(
                """
                SELECT e.card_id, e.content_version, e.embedding <=> %s::vector AS distance
                FROM ab_embeddings AS e
                JOIN ab_cards AS c ON c.id = e.card_id
                JOIN ab_lists AS l ON l.id = c.list_id
                JOIN ab_boards AS b ON b.id = c.board_id
                WHERE e.board_id = ANY(%s) AND e.content_version = c.content_version
                  AND c.archived = FALSE AND c.deleted = FALSE
                  AND l.archived = FALSE AND b.archived = FALSE AND b.deleted = FALSE
                ORDER BY distance LIMIT %s
                """,
                (literal, board_ids, min(limit, 100)),
            ).fetchall()

    def diagnostics(self):
        with self.slots, self.connector() as conn:
            counts = {
                table: conn.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(
                        sql.Identifier("ab_" + table)
                    )
                ).fetchone()[0]
                for table in TABLES
            }
            return {"ok": True, "tables": counts}
