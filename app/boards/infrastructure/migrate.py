"""Compatible, additive schema setup. Safe to retry after a partial DDL failure."""

import time
from psycopg import sql, Error
from boards.infrastructure.dodil import connect
from boards.infrastructure.schema import TABLES, schema_sql
from boards.domain.model import timestamp

VERSION = "001"


def migrate(connector=connect):
    for attempt in range(3):
        try:
            with connector() as conn:
                # DDL is idempotent, but deliberately never pretends CREATE IF NOT EXISTS
                # upgrades an existing table. Future changes need explicit ALTER files.
                for statement in schema_sql().split(";"):
                    if statement.strip():
                        conn.execute(statement)
                for table, columns in TABLES.items():
                    # Verify every required column, even when the table already existed.
                    conn.execute(
                        sql.SQL("SELECT {} FROM {} LIMIT 0").format(
                            sql.SQL(",").join(map(sql.Identifier, columns)),
                            sql.Identifier("ab_" + table),
                        )
                    )
                with conn.transaction():
                    if not conn.execute(
                        "SELECT id FROM ab_schema_versions WHERE id=%s FOR UPDATE",
                        (VERSION,),
                    ).fetchone():
                        conn.execute(
                            "INSERT INTO ab_schema_versions (id,applied_at) VALUES (%s,%s)",
                            (VERSION, timestamp()),
                        )
                return
        except Error as exc:
            if exc.sqlstate not in ("40001", "23505") or attempt == 2:
                raise
            time.sleep(0.1 * (attempt + 1))


if __name__ == "__main__":
    migrate()
