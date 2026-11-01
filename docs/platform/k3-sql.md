# K3 Tables — SQL · Vector · Graph (one engine, one copy of your data)

A bucket's tables are a **reliable, transactional HTAP engine** with **three
pillars over the same rows**: relational **SQL**, **vector** KNN
(pgvector-native), and **graph** traversal (Cypher) — plus S3-native
**objects** in the same bucket. A row you `INSERT` is immediately a SQL row, a
vector-search candidate, AND a graph node — no ETL, no sync, no second copy.
There is **no engine to enable**: the pillars are implicit per bucket (create a
table and go). Every surface is addressed by the **bucket name** (the gateway
qualifies it from your token; on the pg wire the database name IS the bucket).

**This is a system of record, not an analytics-only lakehouse.** Writes are
ACID: durable in object storage *before* they ack, atomic across multiple
tables inside `BEGIN…COMMIT`, and concurrency-safe via optimistic conflict
detection (SQLSTATE `40001`). You can run an OLTP workload — e.g. a
double-entry ledger — directly on it; the same rows are also your reporting,
vector, and graph surfaces, so there is no separate OLTP store to bolt on.

## Adapters — how a query reaches the engine

| Tool / verb | Wire | Use it for |
|---|---|---|
| `data_table_query` / `data sql` (default `--via direct`) | typed `dodil.tables.v1` gRPC | one SQL statement, structured rows back |
| `data pg` / `data sql --via pg` | Postgres wire | psql / drivers / BI tools; pgvector operators; multi-statement txns |
| `data_vsearch` | typed gRPC (`TablesVector`) | vector KNN by column, Qdrant-style |
| `data bolt` | typed gRPC (`TablesGraph`) / Bolt | Cypher graph traversal |
| `data connect <bucket>` | — | print the pg / bolt / grpc endpoints so you can bring your own client |

All of SQL, vector, and graph are reachable from a **single pg connection**
too (pgvector operators + `graph_*()` / `cypher()` table functions run inline),
so a BI tool or driver gets all three pillars over plain Postgres.

## SQL — Postgres compatibility

### Types — write Postgres, trust the declaration

**Treat this as Postgres and design schemas accordingly — do not dumb them
down.** Type fidelity is a TESTED contract (engine >= v0.1.39, re-verified
per release by the cross-door wire matrix): a value the declared column can
hold round-trips **exactly** on every path — SQL literal, text bind, binary
bind, `COPY FROM STDIN`, read back in text or binary — or the write is
**refused loudly** with a real SQLSTATE (`22003` overflow, `22P02` bad input,
`23505` duplicate key, `23514` CHECK, `40001` write conflict). Silent
truncation is never a legal outcome.

Concretely, that means the usual agent hedges are wrong here:

- **Money and quantities go in `DECIMAL(p,s)` with an explicit scale** —
  exact to precision 38 (Decimal128 end to end, no float detour). Never
  store money as DOUBLE, TEXT, or integer-cents-out-of-caution. Exponent
  forms (`1e-6`) and 19-significant-digit mantissas land exactly on every
  entry path, through one shared parser. **Crypto scale is exact, not
  approximate**: `DECIMAL(38,18)` stores wei-scale token amounts exactly
  and `DECIMAL(38,0)` stores raw wei (27 integer digits); the digits you
  wrote come back on every entry and read path, verified per release.
  Bare `NUMERIC` = `DECIMAL(38,9)` (announced by a
  NOTICE); an engine-chosen scale refuses what it would round, a
  user-declared scale rounds exactly like pg.
- **Integer widths are real and advertised truthfully** (`SMALLINT`/int2 21,
  `INTEGER`/int4 23, `BIGINT`/int8 20), `UUID` is a real type (OID 2950, 16
  raw bytes on the binary wire, a non-uuid refused `22P02`), and a `BIGINT`
  past 2^53 survives every path.
- **Constraints are enforced, not decorative**: PRIMARY KEY, UNIQUE, CHECK
  (`23514`), FOREIGN KEY on INSERT, `FOR UPDATE`, multi-table
  `BEGIN...COMMIT`. Do not re-implement them client-side.

The limitation list is SHORT — check it instead of assuming lakehouse
caveats (full per-door matrix: the *Types* section of `dodil://recipes`):
precision caps at 38 digits (pg's unbounded NUMERIC does not exist here);
`VARCHAR(n)`/`CHAR(n)` are ENFORCED on every write lane — SQL, `COPY FROM
STDIN` and the gRPC/typed lanes (engine >= v0.1.44: an overlength value is
refused `22001`, never truncated); `TIMESTAMP(p)` rounds to p on the SQL
lanes (typed/COPY lanes: 0.1.45); timestamps are `timestamptz` semantics
(offsets converted, stored and served UTC; an offset-less literal is read as
UTC) — `TIMESTAMP WITHOUT TIME ZONE` is accepted with a NOTICE and stored the
same way, and `SET TimeZone` is accepted with no effect; division is
pg-exact (engine >= v0.1.44): decimal `/` rounds like pg (`2.01/2` → `1.01`
at scale 2), `int / int` truncates toward zero (`7/2 = 3`), and `/0` is
`22012` on both; `CREATE TRIGGER` / `CREATE FUNCTION … RETURNS trigger`,
`CREATE VIEW`, `CREATE SEQUENCE` and `ALTER TABLE … RENAME` are refused
`0A000` naming the alternatives (ingest rule → pipeline, Action, CHECK);
`COPY FROM` flushes in chunks (a mid-COPY refusal keeps earlier chunks — wrap
COPY in a transaction if you need all-or-nothing); `COPY TO` / `pg_dump` are
not served yet.

### A transaction sees its own writes

Inside `BEGIN…COMMIT` a statement **sees the block's own INSERT / UPDATE /
DELETE** (engine >= v0.1.39). The ledger pattern works as written: insert the
entries, `SELECT sum(...)` to verify the invariant, then `COMMIT`. The read
runs in the engine exactly as you wrote it, against `committed ∪ pending` —
so point reads, filters, scans, `ORDER BY`/`LIMIT`/`OFFSET`,
`count`/`sum`/`min`/`max`/`avg`, multi-statement sequences (insert → update
that same row → read it), and joins/subqueries mixing a written table with an
unwritten one all fold the pending rows. A `DELETE` in the block makes the
row invisible; an INSERT then DELETE of the same key shows nothing.
`RETURNING` sees the write too.

**Where exactness cannot be proven the read is REFUSED, naming the way out —
never answered from stale state.** The shapes that refuse: a CTE whose name
collides with a table the block wrote, a relation carrying a table-function /
time-travel / partition / JSON-path / `TABLESAMPLE` / index-hint modifier, a
read the parser cannot parse, and a written table with no declared schema.
There is no best-effort branch — treat the refusal as the signal to move that
one read outside the transaction.

*Deployments older than tabled v0.1.39 do not have this.* There, a read
inside the transaction returned the PRE-transaction state (a new row looked
absent, an updated value read stale, `count`/`sum` missed the pending rows),
so a read-back-to-decide proved nothing. If you must target one: use
`RETURNING`, compute the invariant client-side from the values you are
writing, or verify after `COMMIT`.

### Dialect

DuckDB-based, BigQuery-aligned. Front-load these:

- **One statement per call** on the typed path (`data_table_query` / `data sql
  --via direct`): send `CREATE`, `INSERT`, `SELECT` as separate calls. The
  **pg wire** (`data pg`) buffers a normal transaction, so a driver can send a
  batch; interactive `BEGIN/COMMIT` (atomic, all-or-nothing across tables)
  works there, not on the typed path.
- **Keyed plane — writes need a PRIMARY KEY.** `CREATE TABLE t (id BIGINT
  PRIMARY KEY, …)` (or `data_table_create` with `merge-key`). `INSERT`/`UPSERT`
  into a table with no PK is rejected (`no declared PRIMARY KEY`). The PK is
  how updates find rows and how compaction dedups.
- **Reads are read-your-writes by default.** A `SELECT` sees rows you just
  wrote (the engine overlays the un-drained write-log on Delta). There is **no
  `freshness` flag** anymore — it was removed; the CLI's `--freshness` is a
  deprecated no-op.
- **`DELETE` needs a `WHERE`** (`DELETE FROM t` errors; use `WHERE 1=1` to
  clear). **Aliases need `AS`**: `SELECT count(*) AS n`, not `count(*) n`.
- **Bind arrays with `= ANY(:array)`.** A bound array parameter works over the
  pg wire (`WHERE id = ANY(:ids)`) — bind the list directly instead of
  string-building `IN (1,2,3)` (which is also an injection footgun).
- **Double-quote identifiers that collide with a keyword.** The dialect is
  DuckDB, so a bare identifier matching a reserved keyword is a parse error when
  *referenced* — e.g. `SELECT at, offset, "table" …` fails at `at`. There is no
  short fixed list (it's DuckDB's keyword set; `at`/`offset`/`table` bite, while
  `zone`/`rows` currently don't), so **quote when in doubt**: `SELECT "at",
  "offset" FROM t`. Quoting always works; such a name is fine as a column
  definition or an `AS` alias unquoted — only a bare *reference* trips.
- **DDL is first-class.** `CREATE TABLE … PRIMARY KEY` registers a real keyed
  table; `CREATE OR REPLACE` and `ALTER TABLE … ADD COLUMN` work. `SHOW
  TABLES` and `DESCRIBE t` inspect the catalog (over the typed path use
  `data table list` / `data table describe`).

### Transactions, durability & concurrency (ACID, reliable)

K3 Tables is a durable system of record — safe for OLTP, including a
double-entry ledger — not just analytics. Over the **pg wire** (`data pg` /
`data sql --via pg`):

- **Atomic, multi-table commits.** `BEGIN; …; COMMIT;` buffers the statements
  and commits them as **one all-or-nothing unit — a single durable
  object-store write** — across as many tables as you touch. `ROLLBACK`
  discards everything; `SAVEPOINT` / `ROLLBACK TO` / `RELEASE` nest as a real
  stack. Both legs of a balanced posting land together or not at all.
- **Durable before ack.** A write is acknowledged only after it is durable in
  object storage (WAL-ack), so an acked write survives the loss of any node
  immediately — there is no "did it really commit?" window.
- **Optimistic concurrency (no lost updates).** A single writer owns each
  bucket's write order; `COMMIT` verifies what the transaction observed (row
  counts, `SELECT … FOR UPDATE` read watermarks) and aborts with SQLSTATE
  `40001` (serialization failure) if a concurrent write invalidated it —
  **retry the whole transaction**. Two writers racing the same row resolve to
  exactly one winner, never a silent overwrite.
- **Read-your-writes** is a hard guarantee (automatic on the pg wire): a
  session always sees its own acked writes, even across writer failover — and
  inside an open block it sees its own PENDING writes too (see *A transaction
  sees its own writes* above). `RETURNING` returns the written row and is what
  SQLAlchemy-2.0 Session flows rely on.
- **Isolation reports as `read committed`** (not full serializable/SSI). For a
  ledger, that is sufficient with the standard pattern: `SELECT balance …
  FOR UPDATE` (captures the watermark) → compute/assert → write both legs →
  `COMMIT`, wrapped in a **retry-on-`40001`** loop. Enforce invariants that
  need phantom-freedom with explicit constraints, not isolation level.
- **Typed path caveat:** `data_table_query` / `data sql --via direct` is **one
  statement per call** — no interactive `BEGIN/COMMIT`. Use the pg wire for
  multi-statement transactions. (A single `data_table_upsert` / `MERGE` is
  itself atomic for its row set.)
- **Retry the right SQLSTATEs.** Serialization conflicts are `40001` (retry the
  txn). Transient object-store / IO faults surface as a **retryable** class —
  `08006` / `58030` / `XX000` — so retry those too (with backoff). Do **not**
  retry genuine errors: bad SQL is `42601` (syntax) / `42703` (undefined column),
  a missing table is `42P01`, a duplicate key is `23505`, a CHECK violation is
  `23514`. Never key retry logic on error-message substrings — match the
  SQLSTATE.

```sql
-- money transfer: atomic, conflict-checked, self-verifying, retry on 40001
BEGIN;
SELECT balance FROM accounts WHERE id IN (:from, :to) FOR UPDATE;  -- watermark
UPDATE accounts SET balance = balance - :amt WHERE id = :from;
UPDATE accounts SET balance = balance + :amt WHERE id = :to;
INSERT INTO ledger_entries (txn_id, account_id, delta) VALUES
  (:txn, :from, -:amt), (:txn, :to, +:amt);   -- both legs, one commit
SELECT sum(delta) FROM ledger_entries WHERE txn_id = :txn;  -- sees the rows above: 0
COMMIT;   -- 40001 here → retry the whole transaction
```

### Writes — `data_table_upsert` first

- **`data_table_upsert`** is the managed keyed write: `{table, row:[…]}`. It
  matches on the table's PRIMARY KEY by default (override with `match-column`);
  full-row upsert by default or partial-column with `merge:true`. Rows are
  immediately visible to subsequent reads. An upsert to a non-existent table
  errors (NOT_FOUND) — create the table first.
- Or plain SQL `UPDATE … WHERE` / `DELETE … WHERE` / `MERGE`.
- **A plain `INSERT` is NOT an idempotent upsert.** Re-inserting an existing
  PRIMARY KEY raises `duplicate key value violates unique constraint` (SQLSTATE
  **`23505`**) — by design; it is not a no-op. For an idempotent keyed write use
  either `data_table_upsert` or, over the pg wire,
  `INSERT … ON CONFLICT (<pk>) DO UPDATE SET …`. `DO UPDATE SET` takes
  `EXCLUDED.col` **or** a literal/expression (`SET status = 'posted'`,
  `SET n = n + 1`).
```sql
-- idempotent insert-or-update over pg (safe to replay):
INSERT INTO accounts (id, balance) VALUES (:id, :bal)
  ON CONFLICT (id) DO UPDATE SET balance = EXCLUDED.balance;
```
- Run `data_table_compact` to fold the write-log into base files (optimizes
  scans; not required for correctness — reads already merge the log).

## VECTOR — pgvector-native KNN

A vector is a **column**, not a separate store: `embedding VECTOR(<dim>)`
(dimension mandatory, float32). Make it with SQL DDL or the typed
`data_table_create` `columns-json` (`{"name":"embedding","type":"VECTOR(768)"}`).

```sql
CREATE TABLE docs (id BIGINT PRIMARY KEY, body VARCHAR, embedding VECTOR(768));
INSERT INTO docs VALUES (1, 'hello', '[0.12, 0.03, …]');   -- pgvector text literal
-- KNN is ORDER BY <op> … LIMIT k.  <=> cosine · <-> L2/euclidean · <#> neg inner product
SELECT id, body FROM docs ORDER BY embedding <=> '[0.12,0.03,…]' LIMIT 5;
```

Or the typed tool: `data_vsearch bucket:"docs" table:"docs" column:"embedding"
vector:"0.12,0.03,…" metric:"cosine" top-k:5` (metric: cosine | euclidean |
dot) — its ranking + scores match the pgvector `<=>` SQL exactly. Vectors are
**float32**, so a round-tripped value differs slightly from a float64 input.
Text → embedding is not done here — embed with `ignite_models_embed` and pass
the vector. `data_vector_collection_add` builds a template-driven embed
pipeline (auto-embeds ingested docs into a vector table) — see dodil://recipes.

**Six things you can promise about vectors, each checkable:** (1) no vector
you store can be silently lost — an index build that cannot prove every
stored vector reachable FAILS instead of serving; (2) a distance you see is
the true distance — ANN and quantized indexes only select candidates, which
are re-ranked at full f32 precision; (3) a vector acked is a vector
searchable, no settle window (verify it yourself: insert an embedding and
query it back in the same session — it is there); (4) recall HOLDS as a
collection grows — vectors live in immutable ~100k-vector segments, each
indexed once, so measured recall@10 goes 0.695 → 0.960 at 50,000 x 2048
dimensions when the same rows are segmented, while the build that took
44.5s as one graph takes 3.4s per segment, admitted against the node's
auto-detected memory budget so a build cannot OOM the node; (5) growth and
deletion never trigger a rebuild — new data seals new segments, a delete
masks at read; (6) combinations that would produce wrong answers are
refused with the correct alternative named. **(1), (2) and (6) hold today;
(3)-(5) need tabled >= v0.1.40.**

**The distances in your results are always exact.** With no index a KNN query
is an exact brute-force scan — correct at any size, linear in table size. With
an index, the index only SELECTS candidates and they are **re-ranked exactly**
before returning: an ANN index can change *which* rows you get, never the
distance reported for a row you got.

### Indexes — the kinds, and how to pick one

pgvector DDL, one column per index. The table needs a **single-column PRIMARY
KEY** (integer or string — a string PK builds a surrogate dictionary index and
KNN returns the real string ids); a **composite** key serves exact scan.

```sql
CREATE INDEX ON docs USING hnsw    (embedding vector_cosine_ops) WITH (m = 32, ef_construction = 200);
CREATE INDEX ON docs USING ivfflat (embedding vector_l2_ops)     WITH (lists = 200);
-- quantized tiers (smaller resident footprint):
CREATE INDEX ON docs USING hnsw    (embedding vector_l2_ops) WITH (quantization = 'f16');  -- or 'i8'
CREATE INDEX ON docs USING ivfflat (embedding vector_l2_ops) WITH (lists = 200, quantization = 'sq8');
CREATE INDEX ON docs USING hnsw    (embedding vector_l2_ops) WITH (async);  -- register + return now
SHOW VECTOR INDEXES;   -- table | column | kind | metric | dim | state | built_at_version | row_count | error
```

Kinds: **`hnsw`** (default) · **`hnsw_sq_f16`** · **`hnsw_sq_i8`** ·
**`ivfflat`** · **`ivf_sq8`** — the kind name is also accepted directly after
`USING`. Operator classes `vector_l2_ops` (default) / `vector_cosine_ops` /
`vector_ip_ops`; the index metric must match the operator your queries use.
Unknown `WITH` keys, unknown opclasses and invalid method/quantization pairs
are rejected at DDL. An index moves `building → ready | failed`; a failed
build keeps its error and is retried by re-running `CREATE INDEX` (no
automatic retry — deliberate, to avoid rebuild storms).

Choosing a kind — measured against brute-force ground truth (the v0.1.39
recall matrix, recall@10 at the serve defaults, realistic clustered
embeddings):

- **Under ~20,000 vectors: `hnsw`.** Every engine measures >= 0.99 there and
  `hnsw` builds fastest. It is the default — do not override it for a small
  collection.
- **At or above ~50,000 realistic embeddings: `hnsw_sq_f16`.** Plain `hnsw`
  degrades steeply with size at embedding dimensions (0.998 → 0.869 → 0.434
  at 20k / 50k / 200k × 768) while `hnsw_sq_f16` holds >= 0.987 across the
  same range. At 200k × 768 that is 0.434 vs 0.987 — not a margin. Cost: an
  f16 build at 768+ dims is several times slower. **The fleet default is
  still `hnsw`** — f16 at scale is an explicit choice you make.
- **`i8` is not a cheaper `f16`.** They tie on realistic clustered data and
  diverge badly on uniformly-random vectors (0.578 vs 0.788 at 20k × 768).
  Reach for f16 unless you have measured your own corpus.
- **`hnsw_sq_i8` + inner product is REFUSED at DDL.** i8 quantization does not
  preserve the magnitudes an inner-product metric ranks by, and the graph
  builds fragmented (22% of vectors unreachable at 768 dims). The error names
  the fix: `hnsw_sq_f16` (same memory tier, clean on this metric) or `hnsw`.
- **`ivf_sq8`** is ~4× smaller than `ivfflat` and now scores identically to it
  in every measured cell; IVF recall depends on `ivfflat.probes` — raise it if
  your vectors are not well clustered.

**Every index is reachability-verified at build time.** A build that cannot
prove every stored vector reachable **fails** — a lossy index is not a
constructible artifact. HNSW declares its exact residual as a scan tail and a
tail past 2% of the corpus fails the build; every IVF build verifies that
every vector lands in exactly one posting list.

### Serving

```sql
SET hnsw.ef_search = 512;                 -- HNSW beam width (server default 384)
SET ivfflat.probes = 40;                  -- IVF probes (server default ~sqrt(lists))
SET dodil.vector_consistency = eventual;  -- default: strong
SET dodil.vector_exact_scan = on;         -- permit exact scans on large tables
LOAD VECTOR INDEX docs (embedding);       -- pin; RELEASE evicts (a latency event, not a data event)
```

Under the default **strong** consistency a KNN query is served from the index
only when it is `ready` and current with no un-compacted writes pending;
otherwise it falls back to an exact scan and schedules a rebuild —
correctness never depends on index freshness. `eventual` always uses the
index and accepts a snapshot that may trail your latest writes. **Filtered
KNN** (`WHERE … ORDER BY emb <op> … LIMIT k`) over-fetches candidates,
re-checks the predicate exactly, escalates the pool once, and falls back to
exact scan for highly selective filters — the result is never silently
under-filled.

## GRAPH — Cypher over the same rows

A graph is a **catalog object over two ordinary tables**: a node table with an
integer KEY column, an edge table with integer SRC/DST columns. Properties
stay in the tables.

```sql
CREATE TABLE person (id BIGINT PRIMARY KEY, name VARCHAR, born DATE);
CREATE TABLE knows  (src BIGINT, dst BIGINT, PRIMARY KEY (src, dst));
CREATE GRAPH social NODES (person KEY id) EDGES (knows SRC src DST dst);
DROP GRAPH social;   -- teardown (then DROP TABLE the node/edge tables)
```

**Graph writes are SQL DML on the edge/node tables — never Cypher.** An edge
is an ordinary row, so transactions, optimistic guards, durability-through-
drain and atomic multi-table commits apply to graph mutations for free. Write
Cypher (`CREATE`/`MERGE`/`SET`/`DELETE`) is refused pointing at the SQL path.

Two ways to run Cypher:

- **SQL:** `SELECT * FROM cypher('social', $$ … $$ [, 'strong'|'eventual'])`.
  `'strong'` merges the un-drained edge WAL, so a traversal sees edges you
  just inserted — read-your-writes inside Cypher; properties are read at the
  traversal's own freshness.
- **Bolt:** `data bolt -b <bucket> -g social "MATCH …"`, or any official Neo4j
  driver over the `bolt+s://` / `neo4j+s://` URI from `data connect` — the
  **driver username is the bucket (db_id)** and the session `database=` names
  the **graph**. Autocommit only (`RUN`/`PULL`); explicit driver transactions
  are refused.

### The accepted subset (v1 + v2)

```cypher
-- 1. k-hop, variable length -> (node, hop_distance); each node ONCE at its min depth
MATCH (a)-[:knows*1..2]->(b) WHERE id(a) = 1 RETURN b
-- 2. 1-hop neighbours -> (neighbor);  -->  <--  --  also work
MATCH (a)-[]->(b) WHERE id(a) = 1 RETURN b
-- 3. shortest path -> (step, node); unreachable = empty, not an error
MATCH p = shortestPath((a)-[*]-(b)) WHERE id(a) = 1 AND id(b) = 9 RETURN p
-- 4. fixed 2-3 hop chain, direction per hop -> the DEDUPLICATED terminal set
MATCH (a)-[:knows]->(b)-[:works_at]->(c) WHERE id(a) = 1 RETURN c
-- 5. property projection: the LABEL names the node table the properties come from
MATCH (a)-[:knows*1..2]->(b:person) WHERE id(a) = 1 RETURN b.name, b.born AS year
-- 6. WHERE on properties (AND-joined with the id anchor), typed ORDER BY, LIMIT
MATCH (a)-[:knows]->(b:person) WHERE id(a) = 1 AND b.born < date('2000-01-01')
  RETURN b.name, b.born ORDER BY b.born DESC LIMIT 10
-- 7. count(*) -- alone in the RETURN list, counts what survives the whole pipeline
MATCH (a)-[:knows*1..3]->(b) WHERE id(a) = 1 RETURN count(*)
-- 8. parameters -- Bolt only: session.run(q, start=1, min=date(2000,1,1), n=10)
MATCH (a)-[:knows]->(b:person) WHERE id(a) = $start AND b.born >= $min
  RETURN b.name ORDER BY b.name LIMIT $n
```

Rules inside the fence:

- **Anchor on the pattern's LEFT node** — `id(a) = K` (or the `a.id = K`
  spelling), integer keys only. An anchored right node is refused with the
  rewrite rather than guessed at.
- `*1..k`, `*..k` and `*k` all mean **depth <= k**. Note `*k` means *exactly*
  k in Neo4j — filter on `hop_distance` for exact depth.
- A **label is a no-op filter for a bare `RETURN`** (a v1 graph has one node
  and one edge table) but **load-bearing for a projection / WHERE / ORDER
  BY**: it names the table the properties and their declared types come from.
  A key with no row there is filtered out, a row with no value projects NULL,
  and an unknown property name is refused naming the table's actual columns.
- Projected columns come FIRST; the traversal's own `hop_distance` / `step`
  survives after them. Each column keeps its **declared type**, so over Bolt a
  `DATE` arrives as a PackStream `Date`, a `TIMESTAMP` as a `DateTime` (UTC)
  and a `BYTEA` as real `Bytes` — not text that happens to look like them.
- **Values bind to the column's declared type exactly, or are refused at plan
  time**: `32768` against a `SMALLINT` refuses rather than wrapping; a
  `DECIMAL(p,s)` compares as decimal digits and refuses a fractional float; a
  `DATE`/`TIMESTAMP` takes `date('…')` / `datetime('…')` and refuses a bare
  string, naming the constructor; strings compare binary-collated, the same
  order the SQL door gives. NULL is not a match for any operator, `<>`
  included.
- **Parameters are a typed channel over Bolt.** An `Integer` stays exact past
  2^53, a `Float` stays fractional, a driver `date`/`datetime` crosses as
  itself, and your query text is never rewritten. A refusal **names the
  parameter** (*"parameter `$start` is a string — an id anchor and a LIMIT
  take an integer"*). `None`, bytes, lists, maps, `LocalDateTime`, `Time`,
  `Duration` and `Point` are refused by name at the door. SQL's `cypher()` has
  **no** parameter channel — inline the value there.
- **Stated deviation from openCypher: `ORDER BY` puts NULLs LAST in BOTH
  directions** (openCypher puts them first on `DESC`). Ordering is typed (a
  `DATE` orders by the day, not its text) and stable; ties keep traversal order.
- Chains cap at **3 hops**, and a per-hop frontier cap **refuses naming the
  hop** rather than truncating an answer.

**Every unsupported shape is refused BY NAME, with the supported alternative
in the message** — never a guessed mapping, never a silently wrong answer.
Outside the fence: write Cypher; `WITH` / `UNWIND` / `CALL` / `UNION` /
`OPTIONAL MATCH`; multiple MATCH clauses or patterns; `OR` / `NOT` / `IS NULL`
/ `STARTS WITH` / `IN`; functions and expressions anywhere; aggregations other
than `count(*)`; `DISTINCT`; `SKIP`; inline property maps; `allShortestPaths`;
unbounded expands outside `shortestPath`; anonymous nodes; string keys; and
returning an INTERMEDIATE node of a chain. Read the error — it names the shape
and the way around it (usually: do that part in the enclosing SQL).

### Traversals as rowsets

The same primitives as SQL table functions, composable in one statement:
`graph_khop('g', start, depth [, dir [, freshness]])` → `(node, hop_distance)`
· `graph_neighbors('g', node [, dir [, freshness]])` → `(neighbor)` ·
`graph_shortest_path('g', a, b [, dir [, freshness]])` → `(step, node)` ·
whole-graph `graph_pagerank('g' [, damping [, max_iters]])` → `(node, rank)` ·
`graph_components('g')` → `(node, component)` · `graph_bfs('g', start [, dir])`
→ `(node, level)`. `dir` is `out` | `in` | `both`; `freshness` is `strong` |
`eventual`.

**They take a constant OR a bound parameter as the start-node argument** —
`graph_khop('accts', :root, 5)` binds. The call is served coordinator-side off
the resident graph, so the start key is fixed per statement. What you still
CANNOT do is pass a **correlated column** whose value changes per outer row —
`JOIN graph_neighbors('g', other.col)` isn't supported; a per-row anchor needs
a per-row step.

## Combining pillars

With a constant or bound start key, a graph traversal composes in ONE statement —
the traversal is inlined plane-side, and its output can feed a join, a filter, a
**subquery / CTE / set-op**, or an **aggregate**:
```sql
-- neighbours of node 1, hydrated with their names, in one query
SELECT p.name FROM graph_neighbors('social', 1) n JOIN person p ON p.id = n.neighbor;
-- traverse → aggregate in a single query (no traverse-then-stitch in app code):
SELECT SUM(amount) FROM deals
 WHERE account_id IN (SELECT node FROM graph_khop('accts', :root, 5));
```
Only a **per-row** start key needs multiple steps — e.g. a vector KNN where each
hit seeds its own traversal: get the keys first, then traverse per key (each a
constant or bound param).
```sql
-- 1) vector KNN → author ids
SELECT id, author_id FROM docs ORDER BY embedding <=> '[…]' LIMIT 5;
-- 2) then, per author id (bind it), traverse + join in one statement:
SELECT p.name FROM graph_neighbors('social', :author_id) n JOIN person p ON p.id = n.neighbor;
```
