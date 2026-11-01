# Dodil task recipes

Conventions:
- Almost every K3 command needs a bucket. Pass it with the "bucket" parameter
  (the CLI flag is --bucket/-b). Tools that require it list "bucket" in their
  input schema's "required" array.
- Tool parameters map to CLI flags; positional values go in the "args" array.
- Output is JSON automatically.

The recipes below are minimal tool flows. For full, TESTED end-to-end builds
(CRM, lead pipeline, semantic agent cache, code knowledge base, ...) read the
live tutorial index at dodil://blog/recipes instead.

# dodil data — recipes

`dodil data` (alias `d`) is the CLI for **K3**: a bucket's data plane. One bucket
is one data instance holding **objects** (S3 raw bytes) and a **reliable,
transactional HTAP tables engine** that serves three pillars over ONE copy of the
rows:

- **SQL** (structured content) · **Vector** (meaning) · **Graph** (relationships)

A row you `INSERT` is immediately a SQL row, a vector-search candidate, and a
graph node — no ETL, no sync, no second copy, and **no engine to enable** (the
pillars are implicit per bucket). Query by content (`data sql` / `data pg`), by
meaning (`data vsearch`), or by relationships (`data bolt`).

K3 is a **system of record, not an analytics-only lakehouse**: writes are ACID
(durable in object storage before they ack; atomic across multiple tables inside
`BEGIN…COMMIT` on the pg wire; optimistic concurrency with SQLSTATE `40001` on
conflict; read-your-writes). OLTP workloads — e.g. a double-entry ledger — run
directly on it, with the same rows also serving reporting, vector, and graph. See
`dodil://k3/sql` → **Transactions, durability & concurrency**.

Tool names mirror the command path: `data bucket create` → `data_bucket_create`.
Flags map to named parameters; positional values go in `args`. `-o json` for
machine-readable output.

## Conventions
- **`-b/--bucket`** — almost every command needs it. Pass the SHORT bucket name;
  the gateway qualifies it from your token (never build `org--bucket` yourself).
  Tools that require it list `bucket` in their input schema's `required`.
- **`--via {direct|pg}`** — how a SQL query reaches the engine: `direct` (typed
  gRPC, default) or `pg` (Postgres wire). `data pg` and `data bolt` are their own
  verbs. `data vsearch` is typed vector KNN.
- **`-o table|json|yaml`** — `json` decodes rows/records into objects.
- **Auth** — a `dodil auth login` token by default. Local dev stack: `--local`.

## The query verbs (talk to the plane as data)
| Verb | Pillar / wire |
|---|---|
| `data sql -b B "<SQL>"` | SQL over tables (typed gRPC; `--via pg` for Postgres wire). One statement per call on the typed path. |
| `data pg -b B "<SQL>"` | SQL over the **Postgres wire** (pgx) — drivers, BI tools, **atomic `BEGIN…COMMIT` transactions** (all-or-nothing across tables; retry on SQLSTATE `40001`), pgvector operators. |
| `data search "…" -b B` | **Semantic** text search: server-side embed + hybrid + RRF over ingested content. |
| `data vsearch -b B -t T --column C --text "…"` | **Vector** KNN over a table's VECTOR column (typed; `--vector` for pre-embedded). |
| `data bolt -b B -g G "<CYPHER>"` | **Graph** Cypher over Bolt / typed gRPC. |
| `data connect B [-o psql\|env\|json]` | Print the pg / bolt / grpc endpoints — bring your own client (psql, cypher-shell). |
| *(no query)* | `data sql` / `data pg` / `data bolt` with no query → interactive REPL. |

## The management pillars
`bucket` (S3 + ACL/policy/CORS) · `object` (objects) · `source` + `credential`
(external data + OAuth) · `ingest` (rules + jobs) · `pipeline` + `template`
(Scriptum-backed) · `table` (SQL tables + vector columns + graphs) · `vector`
(embed collections) · `object destination` (blob-output pipelines) · `actions`
(curated Scriptum actions) · `reservation` (billed hot/warm capacity) · `recipe`
(one-command pipeline setups) · `mount` (FUSE/NFS).

## Data flow (how a file becomes queryable)
```
source ─▶ object lands in the bucket ─▶ ingest RULE matches it by glob
      ─▶ a PIPELINE runs (Scriptum) ─▶ writes to a destination:
           vector  → a table's VECTOR column   (query: data vsearch / pgvector SQL)
           tables  → a table                    (query: data sql / data pg)
           object  → transformed files under a prefix
```
Read `dodil://k3/sql` for the SQL · vector · graph model and adapters, and
`dodil://k3/enums` for column types + vector metrics, before creating tables. For
what each type is guaranteed to do on each wire — exact, degraded to a string, or
refused with a SQLSTATE — see **Types across the doors** below.

## Query the plane: SQL, vector, and graph — one bucket, three pillars

A bucket's tables, vectors, and graphs are the same rows. Query each in its
native language over the typed path or a standard wire adapter. There is no
engine to enable and no `freshness` flag — reads are read-your-writes by default.

### SQL — `data sql` (typed) / `data pg` (Postgres wire)
```
data sql -b sales "SELECT region, sum(amount) AS rev FROM orders GROUP BY region"
data pg  -b sales "SELECT count(*) FROM orders"     # over the Postgres wire (pgx)
data sql -b sales                                   # no query → interactive REPL
```
- `direct` (default) is the typed gRPC path — **one statement per call**. For
  multi-statement scripts or driver transactions use `data pg` (the pg wire
  buffers a real transaction; `BEGIN/COMMIT` work there).
- Dialect is **DuckDB** (standard SQL). Aliases need `AS` (`count(*) AS n`);
  `DELETE` needs a `WHERE`; writes need a `PRIMARY KEY` table. Full rules,
  including the vector + graph pillars: `dodil://k3/sql`.

### Vector — `data search` (semantic) or `data vsearch` (typed KNN) or pgvector SQL
```
# semantic, text in → ranked chunks (server-side embed + hybrid + RRF; the default):
data search "how do refunds work" -b docs
# typed KNN: --text embeds client-side, or pass a query embedding as --vector
data vsearch -b docs -t chunks --column embedding --text "how do refunds work" --metric cosine --top-k 10
# or pgvector over SQL: <=> cosine · <-> L2 · <#> neg inner product
data pg -b docs "SELECT id, body FROM chunks ORDER BY embedding <=> '[0.12,0.03,…]' LIMIT 10"
```
A vector is just a `VECTOR(<dim>)` column on a table — see the vector recipe.

### Graph — `data bolt` (Cypher)
```
data bolt -b social -g knows_g "MATCH (a)-[:knows*1..3]->(b) WHERE id(a)=1 RETURN b"
data bolt -b social -g knows_g                       # Cypher REPL
```
- `-g/--graph` selects the graph within the bucket; anchor traversals with
  `WHERE id(a)=<key>`. Create the graph first — see the graph recipe. Cypher can
  also run inline over pg: `SELECT * FROM cypher('knows_g','MATCH …')`.

### Bring your own client — `data connect`
```
data connect sales -o psql     # postgresql://…@pg.<region>.dodil.io:5432/sales?sslmode=require  → psql
data connect sales -o env      # export DATA_PG_URL=… DATA_BOLT_URI=bolt+s://… DATA_BOLT_DB=…
data connect sales             # human summary of pg / bolt / grpc endpoints
```
Endpoints are resolved client-side (no server round-trip). The bucket name is
the pg database and the Bolt session database; your login token is the
credential. So `data connect` launches psql / cypher-shell against your bucket.

**Both wires are TLS.** `data connect` emits `sslmode=require` on the pg URL and
`bolt+s://` for Bolt — the encrypted, working forms. Do NOT downgrade these:
- **pg** — `sslmode=require` is the floor (the password is your SA/token, so a
  silent plaintext fallback is a credential leak). `prefer`/`disable` are wrong
  here; `--insecure` opts out explicitly. For production use `verify-full`:
  drivers on system trust roots (Go pgx, Node pg, JVM pgJDBC) get it with zero
  setup; libpq clients (psql/psycopg/SQLAlchemy) need `sslrootcert=system`
  (psql 16+) or a path to the OS bundle (`/etc/ssl/cert.pem` on macOS) — bare
  `verify-full` fails on libpq out of the box.
- **bolt** — use `bolt+s://` (verifies public roots by default; nothing to
  configure). **Never `neo4j+s://`/`neo4j://`** — the door refuses the routing
  protocol ("routing is not supported"). `bolt+ssc://` (skip verify) is
  local-dev/self-signed only.

## Types across the doors — what round-trips, what degrades, what is refused

**The contract, in one line:** a value your declared column can hold round-trips
**exactly** on every path in and every path out, or it is **refused loudly** with a
real SQLSTATE. Silent truncation — a cent that vanishes, an id that rounds, a
timestamp that shifts — is never a legal outcome. Current as of engine version
**tabled v0.1.39**.

> **"Can I trust `NUMERIC(38,9)` over `data pg`?"** Yes. A declared-precision
> decimal is exact end to end on the pg door — SQL literal, text bind, binary bind
> and `COPY FROM STDIN`, read back in **both** text and binary format. A value that
> does not fit the declared precision is refused with **22003**; it is never stored
> rounded behind your back. 38 digits is the platform ceiling — see below.

### Which door carries the strongest guarantee today

| door | how you reach it | status at v0.1.39 |
|---|---|---|
| **pg wire** | `data pg`, `data connect -o psql`, any pg driver / BI tool, `COPY FROM STDIN` | **fully verified** — four entry paths x text *and* binary reads, and the advertised OID per declared type is asserted TRUE, not merely stable. Use it when the value matters. |
| **typed gRPC** | `data sql` (default `--via direct`), `data table …`, `data vsearch` | the **reference contract** — every other door is "what survives of this answer". Cross-door agreement with pg is checked. |
| **Bolt / Cypher** | `data bolt`, `bolt+s://` clients | **verified cell by cell** as of v0.1.38 — a `DATE` is a PackStream `Date`, a `TIMESTAMP` a `DateTime`, a `BYTEA` real `Bytes`, pinned at the byte level from both sides of the door. Negotiates Bolt 5.x, falls back to 4.4. |
| **Pinecone-compatible** | the Pinecone-compatible HTTP door (off by default) | **live and audited** — the same walk the pg door got, with its own wire-matrix leg. Stricter by necessity (see below). |
| **REST / JSON** | the HTTP surface | contract **declared**, type legs still **owed**. |

The matrix is re-run per release across pg, gRPC, Bolt and Pinecone. "Declared but
owed" means the engine states what each type must look like on that door but has not
yet pinned it with a test — not that it is unmeasured by accident. The caveats at the
end name the spots where today's behaviour is known to differ from the declared
contract.

### Numbers: the decimal ceiling and what `NUMERIC` means here

- **Precision 38 is a platform cap, not a tunable.** Arrow `Decimal128`, the Delta
  Lake protocol, and DuckDB each cap decimal precision at 38 independently — Delta's
  is the storage *format*. Moving past it would need the Delta protocol to gain a
  wider type *and* DuckDB to implement `Decimal256`; neither is on a roadmap. If you
  need Postgres's unconstrained `NUMERIC` (131072 integer digits, 16383 fractional),
  this engine cannot give it to you — declare what you actually need inside 38, or
  keep the value as `TEXT`.
- **Bare `NUMERIC` / `DECIMAL` is `decimal(38,9)`** — 29 integer digits + 9
  fractional, exactly BigQuery's `NUMERIC`. Postgres's bare `NUMERIC` keeps each
  value's own digits and rounds nothing; a fixed-scale format cannot reproduce that,
  so the engine picks. It **tells you**: `CREATE TABLE` emits a NOTICE naming the
  column, the type it actually got, what happens to extra digits, and the fix.
- **Engine-chosen scale refuses; your scale rounds.** Because pg would never have
  lost those digits, a bare `NUMERIC` column **refuses** a value it would have to
  round. A scale *you* declared rounds the way pg does — `1.005` into
  `NUMERIC(10,2)` stores `1.01`, not `1.00`.
- **Exponent forms are exact numerics, on every entry path.** `1e-6` into a column
  that can hold `0.000001` stores `0.000001` — Postgres §4.1.2.6 makes a constant
  carrying an exponent an exact `numeric`, and the engine reads mantissa + exponent
  at full `Decimal128` width through ONE parser shared by the SQL literal, the text
  bind, `COPY FROM STDIN` and the JSON/typed edges. `1e-45` into `NUMERIC(38,9)`
  rounds to zero exactly as pg does; `22003` is reserved for a magnitude that
  genuinely does not fit.
- **Overflow is `22003`, never a wrap or a NULL.** Past the declared precision
  (`999999.99` into `NUMERIC(5,2)`), out of `SMALLINT` range (`40000` no longer
  reads back `-25536`), a `REAL` overflow (no silent `inf`) — all refused.
- **Declaring for money and crypto:** `NUMERIC(38,18)` for 18-decimal token
  amounts, `NUMERIC(38,0)` for wei or integer minor units (27 integer digits fits
  comfortably). Both fit; one default cannot serve both, which is why the default is
  audible rather than re-tuned.
- **Decimals come back as strings, on purpose.** On the typed path a decimal is
  carried as canonical decimal text (`"123.45"`, no exponent), and the pg door
  prints the same digits, scale-padded. Never re-parse one into a float to "clean it
  up" — that is the exact defect the contract exists to prevent.

### The refusal vocabulary

Type refusals use two SQLSTATEs, and you should key any handling on the code, never
on the message text:

| SQLSTATE | means | you see it when |
|---|---|---|
| **`22003`** | numeric value out of range | a value exceeds the column's declared precision; `SMALLINT`/`INT32` out of range; a `REAL` overflow; a bare-`NUMERIC` column asked to round |
| **`22P02`** | invalid text representation | a value pg itself would reject — an impossible date (`2026-13-45`), a boolean spelling that is not a boolean, a non-uuid into a `UUID` column. Coercions that pg *accepts* (`'true'`→BOOLEAN, a datetime string→DATE, a bare date→TIMESTAMP) work instead of silently landing NULL |

Invalid UTF-8 in a `COPY` stream is also refused rather than stored lossily (it used
to become U+FFFD); Postgres answers that case with `22021`, but the engine docs do
not pin the code the engine itself returns — treat the exact spelling as
unconfirmed. For the rest of the error vocabulary you will actually meet —
`23505` duplicate key, `23514` CHECK violation, `40001` serialization conflict
(retry), `42P01` missing table, `42601`/`42703` bad SQL, `0A000` unsupported
feature, and the transient/retryable classes — read `dodil://k3/sql`.

### What each type looks like on each door

**e** = exact · **s** = string (lossless, typed down, documented) · **R** = refused.

| your column | pg wire | typed gRPC | Bolt | JSON / REST |
|---|---|---|---|---|
| `NUMERIC(38,s)` | plain decimal text, scale-padded, no exponent · **e** | canonical decimal string · **s** | `String` (Neo4j has no decimal type) · **s** | JSON string · **s** |
| `BIGINT` (incl. > 2^53) | plain decimal · **e** | native `int64` · **e** | `Integer` (i64, exact past 2^53) · **e** | JSON **string** by contract · **s** |
| `SMALLINT` | plain decimal, OID 21; out of range `22003` · **e** | `int64` carrier, width in the type code · **e** | `Integer` · **e** | JSON number · **e** |
| `TIMESTAMP` (UTC, µs) | `YYYY-MM-DD HH:MM:SS.ffffff+00` · **e** | `2026-07-13T09:15:00.000000Z` — UTC, `Z`, exactly 6 fractional digits · **e** | `DateTime{seconds, nanos, offset=0}` on Bolt 5.x; the pre-5.0 structure on 4.4, identical fields at UTC · **e** | RFC 3339 `…Z` · **e** |
| `DATE` | `YYYY-MM-DD` · **e** | `"YYYY-MM-DD"` · **e** | `Date{days}` · **e** | `"YYYY-MM-DD"` · **e** |
| `BYTEA` / `BINARY` | `\x`-hex (COPY text doubles the leading backslash; CSV does not) · **e** | native bytes · **e** | real `Bytes` · **e** | standard padded base64 · **s** |
| `BOOLEAN` | `t`/`f`; an unrecognised spelling is `22P02`, never `false` · **e** | native bool · **e** | `Boolean` · **e** | `true`/`false` · **e** |
| `UUID` | the 36 canonical chars, OID **2950**; binary is the 16 raw bytes; a non-uuid is `22P02` · **e** | `TYPE_CODE_UUID`, canonical 36 chars · **e** | `String` (Bolt has no uuid) · **s** | JSON string · **e** |
| `TEXT` / `VARCHAR` | escaped (text) / quote-doubled (CSV) · **e** | UTF-8 string · **e** | `String` · **e** | JSON string · **e** |
| `JSON` / `JSONB` | verbatim text — key order, duplicate keys and >2^53 numbers survive · **e** | verbatim text · **e** | `String` carrying the JSON text, never a map · **s** | embedded JSON value, **key order and duplicates not preserved** · **e** by value, not by text |
| `VECTOR(n)` f32 | pgvector text `[0.1,0.2,…]` · **s** | packed f32 array · **e** | `List<Float>` (f32→f64 widens exactly) · **e** | array of numbers · **e** |
| `NULL` | `\N` (COPY text) / unquoted empty (CSV; `""` is the empty **string**) · **e** | explicit null · **e** | `Null` · **e** | `null` · **e** |
| `DOUBLE` NaN / ±Inf | `NaN` / `Infinity` / `-Infinity` · **e** | native double · **e** | `Float` (IEEE 754) — but see the caveat below · **e** | the strings `"NaN"` / `"Infinity"` / `"-Infinity"` · **s** |

Two rules ride on top of that table. **No door may render an exact decimal as a
floating-point number** — a JSON or Bolt float in a `NUMERIC` cell is a bug, report
it. And **the value recovered on every door must be equal after canonicalisation**,
even where the spelling differs; spelling differences are legal only where the table
names them.

**Graph values carry their column's type too.** A Cypher property projection
(`RETURN n.born` over a labelled node) reads the node table's DECLARED type and
sends it through the same egress path SQL uses — so a `DATE` property reaches a
Neo4j driver as a real `Date{days}` structure, a `TIMESTAMP` as a `DateTime` in
UTC, and a `BYTEA` as `Bytes`, never as text that happens to look like them. A bare
`RETURN b` yields node keys and hop counters only, which is why projection is what
makes the Bolt column of the table above reachable at all.

The Pinecone-compatible door is stricter by necessity: metadata has no integer type
in Pinecone's own model — its numbers are f64 — so `NUMERIC` crosses as a **string**,
while an `int64`/`uint64` integer round-trips **exactly** here (better than Pinecone
itself, which rounds it) and anything past `uint64` is refused rather than rounded.
`BYTEA` and nested JSON are **refused** (no bytes type; nested objects unsupported),
a NULL means **omit the key**, and a record id must be <=512 ASCII characters.
Vectors are natively exact there (f32, n <= 20000; a value outside the f32 range is a
`400`, never an `inf` at rest).

### Known caveats — documented behaviour, not surprises

- **`COPY` is not atomic.** Rows flush per 4000-row chunk, so a value refused in
  chunk 2 leaves chunk 1 committed (measured: 4000 rows survived a refused
  4501-row `COPY`). Postgres rolls the whole `COPY` back. Treat a failed `COPY` as
  partially applied and re-drive it with a replay-safe write (`data table upsert`,
  or `INSERT … ON CONFLICT … DO UPDATE`).
- **`COPY … TO STDOUT` and `pg_dump` are not served** (`0A000`) — the door is
  `COPY … FROM STDIN` only, so there is no in-engine bulk export yet. Read rows out
  with an ordinary `SELECT`.
- **In-engine division truncates where pg rounds.** `CAST(2.01 / 2 AS DECIMAL(10,2))`
  gives `1.00` where Postgres gives `1.01` — an upstream DuckDB issue (duckdb#5288),
  tracked as watched. It is a real money-math error: wrap the division in an explicit
  `ROUND(…, s)` when the last digit matters.
- **There is one timestamp type, and it is `timestamptz`.** Offsets you send are
  converted (not sliced off) and stored/served as UTC microseconds; the wire OID and
  the catalog agree. Two consequences: an offset-LESS literal is read as **UTC**
  where Postgres would interpret it in the session `TimeZone`, and `TIMESTAMP
  WITHOUT TIME ZONE` gets conversion semantics rather than pg's naive ones (a DDL
  notice says so). Naive identity needs a second type vocabulary — a deliberate open
  design call, not a bug. `TIMESTAMP(p)` precision is accepted and discarded;
  storage is always µs.
- **JSON byte-identity lives on pg and gRPC only.** Those two serve your document
  verbatim. The JSON/REST view re-serialises, so key order and duplicate keys are
  not preserved there, and Bolt hands you the JSON *text* as a string rather than a
  map (a Bolt map would drop duplicate keys by spec and force every embedded number
  through int/float). If byte-identity matters, read from pg or the typed path.
- **`VARCHAR(n)` / `CHAR(n)` lengths are parsed and discarded.** `VARCHAR(5)`
  accepts a megabyte and `CHAR(10)` does not blank-pad. Enforce length yourself — or
  with a `CHECK` constraint, which IS enforced (`23514`).
- **A non-finite `double` is NULL before any door sees it.** `NaN` / `±Infinity` are
  lost in the plane's row-JSON rendering (JSON cannot spell them), one hop upstream
  of both the Bolt and REST encoders — each of which would carry the value
  correctly. Don't route non-finites through a `DOUBLE` column if you need them back.
- **The REST/JSON door's byte and number legs are still owed.** pg, typed and Bolt
  are pinned by the matrix; on REST the declared spellings (base64 for `BYTEA`,
  strings for `BIGINT`) are contract, not yet gate. Round-trip a binary column once
  on your client before trusting REST with it, or keep blobs in object storage and
  reference them by id.
- **Decimals nested inside an `ARRAY` or `STRUCT` are demoted to f64** — by design,
  and a real digit loss. Do not nest money; give it its own column.
- **A unique-index error advises a recovery object it never surfaces.** The message
  says `DROP TABLE <indexname>`, which answers `42P01` — the real object is
  `__uidx_<indexname>`. Cheap hygiene, open.

### What changed, release by release

**v0.1.39 — complete and correct answers.**

- **A transaction sees its own writes** (see the section below). The largest
  remaining hole in the pg story is closed.
- **Three vector-index defects**, each found by measuring an axis nobody had
  measured before: `hnsw_sq_f16` could not build at 768/2048 dimensions at all;
  `ivf_sq8` returned near-random results for a query outside its codebooks
  (recall@10 0.048 where the unquantized twin over the identical partition got
  0.995); `CREATE INDEX … USING ivfflat` on an empty — or all-NULL — vector column
  panicked the build.
- **`hnsw_sq_i8` on an inner-product column is refused at DDL**: i8 does not
  preserve the magnitudes IP ranks by, and the graph built fragmented. The error
  names `hnsw_sq_f16`.
- **An index that cannot prove every vector reachable is not a constructible
  artifact**: HNSW declares an exact scan tail, capped at 2% of the corpus, and
  every IVF build verifies partition completeness.

**v0.1.38 — every OTHER door stops losing things.**

- **The vector index silently lost vectors in production** — roughly 1 in 100–200
  stored vectors was unreachable by any search. Two independent upstream library
  defects, both fixed, both gated.
- **`GraphRows` carries column types**, so the Bolt door can tell a `DATE` from a
  `TEXT`. That one missing field was the root cause of every owed Bolt type cell;
  with it, plus Cypher property projection, none is owed.
- **Cypher v2** — `$name` parameters (typed end to end), `WHERE` on properties,
  `ORDER BY` / `LIMIT` / `count(*)`, and 2–3 hop fixed patterns. Every unsupported
  shape is refused by name with the supported alternative.
- **`uuid` became a real type** end to end — OID 2950, catalog `uuid`, 16 raw bytes
  on the binary wire, a non-uuid refused `22P02` instead of stored. Storage is still
  the canonical 36-char text (Arrow/Delta/Parquet have no uuid type); what changed is
  that the DECLARATION now survives.
- **The advertised integer widths are true, not merely stable.** `SMALLINT`→21,
  `INT32`→23, `REAL`→700 ride the proto `TypeCode` enum, which shipped on
  `proto-tables` main and is vendored here — so the old "the width rides a proto enum
  this CLI vendors" caveat is closed.
- **Exponent-form decimals round-trip exactly through ONE shared parser** instead of
  seven copies, two of which were live bugs. The old contradiction between "exact on
  the literal path" and "`22003` on `COPY`" is RESOLVED: exact everywhere.
- **The Pinecone door joined the type contract** — metadata integers past 2^53 no
  longer round inside the JSON parser, dropped `sparseValues` are refused instead of
  acked, two namespaces can no longer collide onto one table, and an unparseable
  distance no longer scores `0.0` (which sorts first).

**v0.1.37 — the pg door tells the truth about types.** Decimals stopped passing
through `f64`; `NUMERIC` became exact on both wire formats (it used to be loud from
psql and silently truncated from SQLx/JDBC); a `+03:00` offset is converted rather
than sliced off; out-of-range refuses instead of wrapping; `bytea` has one encoding;
JSON is served verbatim; coercions accept what pg accepts and refuse what pg
refuses, never NULL; and `COPY FROM STDIN` goes through the same declared-schema
encoder as `INSERT` (it had private parsers and had independently re-acquired the
whole defect family).

*Derived from the engine's own `DOOR_TYPE_CONTRACTS.md`, `TYPE_FIDELITY_AUDIT.md`
and the `[0.1.37]`–`[0.1.39]` changelog. Where those contradict this page, they win.*

## Reading back inside `BEGIN…COMMIT` — it works

A transaction **sees its own writes** (tabled >= v0.1.39). After an `INSERT`,
`UPDATE` or `DELETE` inside `BEGIN…COMMIT`, a `SELECT` in that same transaction
reads `committed ∪ pending`:

- point and filtered reads, scans, `ORDER BY` / `LIMIT` / `OFFSET`;
- `count` / `sum` / `min` / `max` / `avg` over the pending rows;
- a DELETE makes the row invisible; INSERT-then-DELETE of one key shows nothing;
  UPDATE-then-read shows the NEW value;
- joins and subqueries mixing a written table with an unwritten one.

So **the ledger pattern works as written**: insert the entries, `SELECT sum(delta)
…` to prove the invariant, then `COMMIT`. `RETURNING` still works and is still the
cheapest way to read back one row you just wrote.

**A few read shapes REFUSE instead**, naming the shape and the way out — never a
stale answer: a CTE whose name collides with a table the block wrote, a relation
carrying a table-function / time-travel / partition / JSON-path / `TABLESAMPLE` /
index-hint modifier, a read the parser cannot parse, and a written table with no
declared schema. There is no best-effort branch, by design: a quietly stale answer
would be the defect, not a smaller version of it. Move that one read outside the
transaction.

> **Older deployments (tabled < v0.1.39)** answered any read inside the block from
> the PRE-transaction state: the new row looked absent, an updated value read stale,
> and `count`/`sum` missed the pending rows. The writes themselves always landed
> correctly — only visibility was wrong. If you must target one, use `RETURNING`,
> compute the invariant client-side from the values you are writing, or verify after
> the commit.

## Tables — SQL tables in a bucket (with vector columns + graphs)

Structured HTAP tables. Query with `data sql` / `data pg` (above); manage with
`data table …`. No engine to enable — create a table and go.

### Create + write
```
# Keyed table (a PRIMARY KEY / merge-key is REQUIRED — writes are keyed).
# Types are SQL type strings: bigint|varchar|double|boolean|timestamp|date|json|
# blob and VECTOR(<dim>) — see dodil://k3/enums. For money use DECIMAL(p,s) with an
# explicit scale (p ≤ 38) — see "Types across the doors" for the round-trip contract.
data table create orders -b sales \
  --columns-json '[{"name":"id","type":"bigint"},{"name":"region","type":"varchar"},{"name":"amount","type":"double"}]' \
  --merge-key id

data table insert orders -b sales --row '{"id":1,"region":"MENA","amount":120.5}'

# Upsert = the managed keyed write. Matches on the table's PRIMARY KEY by default
# (override with --match-column). Full-row by default (or --merge for partial-
# column). Rows are immediately visible.
data table upsert orders -b sales --row '{"id":1,"region":"MENA","amount":130.0}'
```
- **Update / delete by predicate:**
  `data table update orders -b sales --predicate "region='MENA'" --updates-json '{"amount":0}'`
  · `data table delete-rows orders -b sales --predicate "amount < 80"`.
- **General MERGE:** `data table merge orders -b sales --match-column id --row '{…}'`
  with `--when-matched update|delete|skip` and `--when-not-matched insert|skip`.
- Prefer plain SQL for anything complex: `data sql -b sales "UPDATE … WHERE …"`.
- **A plain `INSERT` is NOT idempotent.** Re-inserting an existing PRIMARY KEY
  raises `duplicate key … (SQLSTATE 23505)` — by design, not a no-op. For a
  replay-safe keyed write use `data table upsert`, or over pg
  `INSERT … ON CONFLICT (<pk>) DO UPDATE SET …` (`DO UPDATE SET` accepts
  `EXCLUDED.col` or a literal/expression like `SET status='posted'`).
- **`data pg` DML reports the affected-row count** (`row_count` from the pg
  `CommandComplete` tag, e.g. `UPDATE 3`), so a conditional write's hit-vs-no-op is
  visible without a follow-up `SELECT`.

### Inspect + maintain
```
data table list -b sales                       # SHOW TABLES (name + pk_columns)
data table describe orders -b sales             # schema
data table query -b sales "SELECT * FROM orders LIMIT 20"
data table compact|optimize|vacuum orders -b sales   # fold write-log / cluster / GC
```
`data table view-url orders -b sales` mints a clickable console link to the
spreadsheet editor. `compact` is an optimization — reads already merge the
write-log, so it is never required for correctness. Prefer normalized tables
joined on a key over nesting child records.

## Vector — semantic search over a bucket's tables

### What you can promise your user — six claims, each checkable

Quote these verbatim; they are falsifiable, and the numbers are measured.

1. **No vector you store can be silently lost.** An index build that cannot
   prove every stored vector reachable fails instead of serving — a lossy index
   is not a constructible artifact.
2. **A distance you see is the true distance.** ANN and quantized indexes only
   select candidates; every candidate is re-ranked at full f32 precision before
   it is returned. An index changes which rows you get, never the distance
   reported for a row you got.
3. **A vector acked is a vector searchable** — no settle window, no index lag.
   *Verify it yourself: insert an embedding and query it back in the same
   session; it is there.*
4. **Recall holds as a collection grows, and memory stays bounded.** Vectors
   live in immutable ~100k-vector segments, each indexed once, so no single
   graph ever exceeds the size it is good at: measured recall@10 goes
   **0.695 → 0.960 at 50,000 x 2048 dimensions** when the same rows are
   segmented, while the build that took **44.5s as one graph takes 3.4s per
   segment**. Builds are admitted against the node's auto-detected memory
   budget, so an index build cannot OOM the node.
5. **Growth and deletion never trigger a rebuild.** New data seals new
   segments; nothing already written is re-indexed. A delete masks at read and
   is dropped at compaction.
6. **Combinations that would produce wrong answers are refused, with the
   correct alternative named.** `hnsw_sq_i8` on an inner-product column is
   refused at DDL — 8-bit quantization does not preserve the magnitudes inner
   product ranks by — and the error names `hnsw_sq_f16`. Read the refusal: it
   is informative, not a dead end.

Claims 1, 2 and 6 hold on every current deployment. Claims 3-5 need tabled
**>= v0.1.40**.

A vector is a **`VECTOR(<dim>)` column on a table**, not a separate store. Two
ways to get one:

**A. Bring your own embeddings** — a plain table + `VECTOR(<dim>)` column (via
`data table create --columns-json` or SQL DDL):
```
data table create chunks -b docs \
  --columns-json '[{"name":"id","type":"bigint"},{"name":"body","type":"varchar"},{"name":"embedding","type":"VECTOR(768)"}]' \
  --merge-key id
# write vectors as '[f1,f2,…]' literals (upsert matches on the PK by default)
data table upsert chunks -b docs --row '{"id":1,"body":"hello","embedding":"[0.12,0.03,…]"}'
```

**B. Auto-embed ingested docs** — a template-driven embed collection (a pipeline
that embeds ingested files into a vector table):
```
data vector templates -b docs                                  # embed templates (dims/model/metric come from these)
data vector collection add chunks -b docs --template text_embedding_index
data vector collection list -b docs                            # note the pipeline id
```
Then bind an ingest rule targeting that pipeline id (see the ingest recipe) and
upload docs with `data object create`.

### Search — two surfaces, pick by need
```
# DEFAULT: semantic search, text in → ranked chunks out (server-side embed + hybrid + RRF; ~seconds):
data search "how do refunds work" -b docs [--table chunks] [--rerank] [--top-k 5]

# raw KNN, pure similarity at plane speed:
data vsearch -b docs -t chunks --column embedding --text "how do refunds work"   # embeds client-side via ignite
data vsearch -b docs -t chunks --column embedding --vector "0.12,0.03,…"         # you already hold the embedding
# or pgvector over SQL:
data pg -b docs "SELECT id, body FROM chunks ORDER BY embedding <=> '[0.12,0.03,…]' LIMIT 10"
```
`data search` scores are similarity (higher = better); vsearch/pgvector return
distance (lower = closer). vsearch `--model` must match the model that embedded
the table (default arctic-embed-m-v2). Metrics: `cosine` (`<=>`),
`euclidean`/L2 (`<->`), `dot`/inner (`<#>`).

**The distances you get back are always exact.** With no index, KNN is an exact
brute-force scan — correct at any size, linear in table size. With an index, the
index only SELECTS candidates and they are **re-ranked exactly** before returning:
an ANN index changes *which* rows you get, never the distance reported for a row
you got.

### Indexes — create one, and pick the right kind

pgvector DDL, one column per index. The table needs a **single-column PRIMARY KEY**
(integer or string); a composite key serves exact scan.
```
data pg -b docs "CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 32, ef_construction = 200)"
data pg -b docs "CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops) WITH (quantization = 'f16')"
data pg -b docs "CREATE INDEX ON chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 200)"
data pg -b docs "SHOW VECTOR INDEXES"   # table | column | kind | metric | dim | state | built_at_version | row_count | error
```
Kinds: **`hnsw`** (default) · **`hnsw_sq_f16`** · **`hnsw_sq_i8`** · **`ivfflat`** ·
**`ivf_sq8`** — the kind name is also accepted directly after `USING`. Opclasses:
`vector_l2_ops` (default), `vector_cosine_ops`, `vector_ip_ops`; the index metric
must match the operator your queries use. `WITH (async)` registers the index and
returns immediately. An index moves `building → ready | failed`; a failed build
keeps its error and is retried by re-running `CREATE INDEX` (no automatic retry, to
avoid rebuild storms).

Choosing — measured against brute-force ground truth (the v0.1.39 recall matrix,
recall@10 at the serve defaults, realistic clustered embeddings):

- **Under ~20,000 vectors: `hnsw`.** Every engine measures >= 0.99 there and `hnsw`
  builds fastest. It is the default — don't override it for a small collection.
- **At or above ~50,000 realistic embeddings: `hnsw_sq_f16`.** Plain `hnsw` degrades
  steeply with size at embedding dimensions (0.998 → 0.869 → 0.434 at 20k / 50k /
  200k x 768) while `hnsw_sq_f16` holds >= 0.987 across the same range. At
  200k x 768 that is 0.434 vs 0.987 — not a margin. The cost is build time: an f16
  build at 768+ dims is several times slower. **The fleet default is still `hnsw`**;
  f16 at scale is an explicit choice you make.
- **`i8` is not a cheaper `f16`.** They tie on realistic clustered data and diverge
  badly on uniformly-random vectors (0.578 vs 0.788 at 20k x 768). Reach for f16
  unless you have measured your own corpus.
- **`hnsw_sq_i8` on an inner-product column is REFUSED at DDL** — i8 quantization
  does not preserve the magnitudes an inner-product metric ranks by, and the graph
  builds fragmented. The error names `hnsw_sq_f16` (same memory tier, clean on this
  metric) or `hnsw`.
- **`ivf_sq8`** is ~4x smaller than `ivfflat` and now scores identically to it in
  every measured cell; IVF recall depends on `ivfflat.probes` — raise it if your
  vectors are not well clustered.

**Every index is reachability-verified at build time**: a build that cannot prove
every stored vector reachable **fails**, because a lossy index is not a
constructible artifact. HNSW declares its exact residual as a scan tail (a tail past
2% of the corpus fails the build) and every IVF build verifies that every vector
lands in exactly one posting list.

Serving knobs: `SET hnsw.ef_search = 512` · `SET ivfflat.probes = 40` ·
`SET dodil.vector_consistency = eventual` (default `strong`: the index serves only
when it is current with no un-compacted writes, else an exact scan — correctness
never depends on index freshness) · `LOAD` / `RELEASE VECTOR INDEX chunks
(embedding)` to pin or evict. Filtered KNN over-fetches and re-checks the predicate
exactly, so the result is never silently under-filled.

See `dodil://k3/sql` (VECTOR pillar) for the full model.

## Graph — Cypher over a bucket's tables

A graph is **table-backed**: a node table (with an integer KEY column) + an edge
table (with integer SRC/DST columns) + `CREATE GRAPH`. Cypher lowers onto the same
engine and the same rows; traverse with `data bolt` or the `graph_*()` / `cypher()`
SQL functions. No engine to enable.

### Build the graph (via `data pg` — it owns `CREATE GRAPH`)
```
data pg -b social "CREATE TABLE person (id BIGINT PRIMARY KEY, name VARCHAR, born DATE)"
data pg -b social "INSERT INTO person VALUES (1,'alice','1990-04-02'),(2,'bob','1985-11-20'),(3,'carol','2001-01-09')"
data pg -b social "CREATE TABLE knows (src BIGINT, dst BIGINT, PRIMARY KEY (src,dst))"
data pg -b social "INSERT INTO knows VALUES (1,2),(2,3)"
data pg -b social "CREATE GRAPH social NODES (person KEY id) EDGES (knows SRC src DST dst)"
```
Node/edge tables need a `PRIMARY KEY` (writes are keyed). **Graph writes are SQL
DML on those tables — never Cypher.** An edge is an ordinary row, so transactions,
optimistic guards and atomic multi-table commits apply to graph mutations for free;
write Cypher (`CREATE`/`MERGE`/`SET`/`DELETE`) is refused pointing at the SQL path.

### Traverse
```
# Bolt / Cypher (anchor with WHERE id(a)=<key>):
data bolt -b social -g social "MATCH (a)-[:knows*1..2]->(b) WHERE id(a)=1 RETURN b"
# or over pg — the graph_*() table functions and the cypher() twin:
data pg -b social "SELECT * FROM graph_khop('social', 1, 2)"            # -> (node, hop_distance)
data pg -b social "SELECT * FROM graph_neighbors('social', 1)"          # -> (neighbor)
data pg -b social "SELECT * FROM graph_shortest_path('social', 1, 3)"   # -> (step, node)
data pg -b social "SELECT * FROM graph_pagerank('social')"              # also graph_components / graph_bfs
data pg -b social "SELECT * FROM cypher('social','MATCH (a)-[:knows]->(b) WHERE id(a)=1 RETURN b')"
```
`-g/--graph` selects the graph; `-b/--bucket` is the tenant. Each `graph_*()` takes
an optional direction (`out` | `in` | `both`) and freshness (`strong` | `eventual`);
`cypher()` takes freshness as its third argument. **`'strong'` merges the un-drained
edge WAL**, so a traversal sees edges you inserted in the same session — Cypher
read-your-writes, and properties are read at the traversal's own freshness.

`data connect social -o env` gives `DATA_BOLT_URI` + `DATA_BOLT_DB` for cypher-shell
or any official Neo4j driver: the **driver username is the bucket** and the session
`database=` names the **graph**. Bolt is autocommit-only (`RUN`/`PULL`); explicit
driver transactions are refused.

### The Cypher subset — what is accepted

```cypher
-- 1. k-hop, variable length -> (node, hop_distance); each node ONCE at its min depth
MATCH (a)-[:knows*1..2]->(b) WHERE id(a) = 1 RETURN b
-- 2. 1-hop neighbours -> (neighbor);  -->  <--  --  also work
MATCH (a)-[]->(b) WHERE id(a) = 1 RETURN b
-- 3. shortest path -> (step, node); unreachable = empty, not an error
MATCH p = shortestPath((a)-[*]-(b)) WHERE id(a) = 1 AND id(b) = 3 RETURN p
-- 4. fixed 2-3 hop chain, direction per hop -> the DEDUPLICATED terminal set
MATCH (a)-[:knows]->(b)-[:knows]->(c) WHERE id(a) = 1 RETURN c
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

- **Anchor on the pattern's LEFT node** — `id(a) = K` (or `a.id = K`), integer keys
  only. An anchored right node is refused with the rewrite rather than guessed at.
- `*1..k`, `*..k` and `*k` all mean **depth <= k**. Note `*k` means *exactly* k in
  Neo4j — filter on `hop_distance` when you want exact depth.
- A **label is a no-op filter for a bare `RETURN`** (a v1 graph has one node table
  and one edge table) but **load-bearing for a projection / WHERE / ORDER BY**: it
  names the table the properties and their declared types come from. A key with no
  row there is filtered out, a row with no value projects NULL, and an unknown
  property name is refused naming the table's actual columns.
- Projected columns come FIRST; the traversal's own `hop_distance` / `step` survives
  after them. Each keeps its **declared type**, so over Bolt a `DATE` property
  arrives as a real `Date` structure, a `TIMESTAMP` as a `DateTime` in UTC and a
  `BYTEA` as `Bytes` — never text that happens to look like them.
- **Values bind to the column's declared type exactly, or are refused at plan time**:
  `32768` against a `SMALLINT` refuses rather than wrapping; a `DECIMAL(p,s)`
  compares as decimal digits and refuses a fractional float; a `DATE`/`TIMESTAMP`
  takes `date('…')` / `datetime('…')` and refuses a bare string, naming the
  constructor; strings compare binary-collated, the same order the SQL door gives.
  NULL is not a match for any operator, `<>` included.
- **Parameters are a typed channel over Bolt.** An `Integer` stays exact past 2^53,
  a `Float` stays fractional, a driver `date`/`datetime` crosses as itself, and your
  query text is never rewritten. A refusal **names the parameter**. `None`, bytes,
  lists, maps, `LocalDateTime`, `Time`, `Duration` and `Point` are refused by name at
  the door. SQL's `cypher()` has **no** parameter channel — inline the value there.
- **Stated deviation from openCypher: `ORDER BY` puts NULLs LAST in BOTH
  directions** (openCypher puts them first on `DESC`). Ordering is typed — a `DATE`
  orders by the day, not its text — and stable, so ties keep traversal order.
- A chain caps at **3 hops**, and a per-hop frontier cap **refuses naming the hop**
  rather than truncating an answer.

**Every unsupported shape is refused BY NAME, with the supported alternative in the
message** — never a guessed mapping, never a silently wrong answer. Outside the
fence: write Cypher; `WITH` / `UNWIND` / `CALL` / `UNION` / `OPTIONAL MATCH`;
multiple MATCH clauses or patterns; `OR` / `NOT` / `IS NULL` / `STARTS WITH` / `IN`;
functions and expressions anywhere; aggregations other than `count(*)`; `DISTINCT`;
`SKIP`; inline property maps; `allShortestPaths`; unbounded expands outside
`shortestPath`; anonymous nodes; string keys; and returning an INTERMEDIATE node of
a chain. Read the error — it names the shape and the way around it, which is usually
"do that part in the enclosing SQL".

### Compose with SQL

A `graph_*()` call takes a **constant or a bound parameter** as its start key
(`graph_khop('social', :root, 5)` binds — no string-inlining) and composes in one
statement: join its output to tables, filter, order, or feed a **subquery / CTE /
aggregate**.
```
data pg -b social "SELECT p.name FROM graph_neighbors('social', 1) n JOIN person p ON p.id = n.neighbor"
data pg -b social "SELECT SUM(amount) FROM deals WHERE account_id IN (SELECT node FROM graph_khop('social', 1, 5))"
```
You just can't pass a **correlated column** (a per-row-changing key) as the node key
— that still needs a per-row step.

### Teardown
```
data pg -b social "DROP GRAPH social"           # then DROP TABLE the node/edge tables
```

## Ingest — turn files into vectors / rows

A **source** brings files in → an object lands → an **ingest rule** matches it by
glob → a **pipeline** runs (Scriptum) → it writes to a destination you query.
One bucket can run several pipelines; rules route file types to pipelines.

Every bucket has an auto-created internal S3 source (`data source list`). External
sources (Google Drive, SharePoint, Confluence, GitHub) authenticate via
`data credential …` (OAuth); the reliable path today is the internal source +
`data object create` uploads.

### Get data in, then verify (the step most often missed)
```
1. Upload:   data object create ./docs -b docs --recursive     # or a single file
2. Kick it:  data ingest trigger-discovery -b docs             # scan for new/changed objects now
             data ingest trigger -b docs --source <id>         # (re)run ingestion
3. Watch:    data ingest jobs -b docs [--status ...]           # list jobs; grab a JOB ID
             data ingest watch <job-id> -b docs                # block until completed|partial|failed
4. Confirm:  data search "…" -b docs | data sql …              # query the destination
```
Prefer `watch` over re-listing in a loop: it returns the final job with its
result counters (chunks, embeddings, rows, vectorStatus, error).

### Create an ingest rule (bind a source to a pipeline)
```
data ingest add docs_rule -b docs \
  --source <source-id> \
  --collection <pipeline-id> \
  --include "**/*.pdf" --include "**/*.md"
```
`collection` is the target pipeline's id (a vector-embed pipeline, a table
pipeline, or an object-destination pipeline) — it determines which pipeline runs.

### Job lifecycle (don't panic on `failed`)
`pending → processing → completed | partial | failed`, with `retrying` between.
Ingest retries transient errors ~5×; a terminal `failed` object is auto-requeued
by the sync poller every ~5 min (up to 10 attempts). Uploading changed content
requeues immediately. Manual override: `data ingest trigger --retry-failed`. A
job stuck `failed` with the same error is a real problem — read its error details.

Every job executes as a Scriptum thread; jobs expose `threadId`. For per-step
detail on a failure: `dodil scriptum thread steps <thread-id>` (or the
scriptum_thread_steps / scriptum_thread_watch MCP tools).

## One-command setups — `data recipe`

For common pipelines, prefer the deterministic recipe commands over wiring the
steps by hand — they provision the pipeline(s) + the ingest rule atomically, in
the right order, with the rule bound for you. There is no engine to enable.

```
data recipe list                                  # the catalog (id, group, what it does)
data recipe show <id>                             # the exact steps it will run (inspect first)
data recipe install <id> -b <bucket> [--set k=v] [--folder sub/] [--dry-run]
```

Recipes (id → what it stands up):
| id | stands up |
|---|---|
| `document-rag` / `code-rag` / `image-rag` | vector-embed pipeline + ingest rule for docs / code / images |
| `invoice-intake` | parse invoices into a table |
| `transcription` | transcribe audio/video, then index the text |
| `summarize-to-markdown` | summarize files back to `summaries/` |
| `summarize-then-rag` | summarize, then index the summaries |
| `generic` | vector index + classification/summarization tables |

Customize: `--set` passes template inputs (e.g. `--set language=en`); `--folder`
restricts ingestion to a subfolder and scopes the rule globs. Run `data recipe
show` (or `--dry-run`) first to see the resolved plan. After install, upload with
`data object create` and query with `data vsearch` / `data sql`.

## Actions — curated Scriptum actions over bucket data

Run curated actions against a selection (a table, some objects, or the whole
bucket) and stream their progress.

```
data actions list -b sales [--table orders] [--search summar]     # what's available
data actions run summarize -b sales --table orders --param language=en
```
- **Selection:** `--table <t>` scopes to a table, `--key <k>` (repeatable) to
  objects, otherwise the whole bucket. `--param key=value` (repeatable) passes
  action inputs.
- **`data actions run`** streams `ActionEvent`s live: `▶ started` → `· progress`
  steps → `✓ completed` (with output) or `✗ failed` (with the failed step). The
  run executes in a Scriptum thread; the started event carries `run_id`/`thread_id`.

## Reservation — billed hot/warm capacity

Reserve resident serving capacity on a bucket's data plane (metered). The plane
owns the sql/vector/graph split; optional floors set per-pillar minimums.

```
data reservation set -b sales --capacity-gb 32 --dedicated
data reservation set -b sales --capacity-gb 64 --sql-gb 16 --vector-gb 8   # with floors
data reservation get -b sales                                              # current + what the plane applied
data reservation delete -b sales                                           # release
```
`get`/`set` return `capacity_gb`, `floors`, a monotonic `generation`, and
`applied` (what the plane actually holds). Reservation is a gRPC-only pillar.

## Buckets & objects — the S3 foundation

A bucket is the data instance and the S3 namespace.

```
data bucket create sales [--description "…"]
data bucket list | data bucket get sales | data bucket delete sales
data bucket update sales [--description "…"] [--access-mode private|public|custom] [--storage-quota-bytes N]
data bucket policy set|get|delete sales     # S3-style access policy (JSON)
data bucket cors  set|get|delete sales      # CORS config (JSON)
```

Objects (S3-native; uploads go to the object gateway, addressed by bucket name):
```
data object create ./report.pdf -b sales [--key path/report.pdf]   # single file
data object create ./dir -b sales --recursive [--key prefix]        # directory tree
data object list -b sales | data object show <key> -b sales
data object url <key> -b sales                                       # presigned download URL
data object remove <key> -b sales
```

Object **destinations** are template-driven object pipelines whose transformed
outputs land under a prefix (destination + pipeline are created together, so a
`--template` is required):
```
data object destination create summaries -b sales --target-prefix "summaries/" --template <object-pipeline-template>
data object destination list -b sales
```

Mount a bucket as a filesystem (long-lived daemon; run via the shell, not the
in-process tool): `dodil data mount sales /tmp/sales` … `dodil data unmount /tmp/sales`.

External sources & OAuth: `data source create …` / `data source list`,
`data credential oauth-url …` → `data credential oauth-exchange …`.

## Ignite: deploy an app

**Two ways to ship — recommend the right one:**
1. **RECOMMENDED (production): git repo + CI + auto-deploy.** Put the code in a
   dodil git repo with `.github/workflows/*.yml` and a **`.dodil/deploy.yaml`**;
   every push builds in CI (registry creds auto-injected) and the runner deploys
   the manifest. You get history, review/PR gating, reproducible builds, and
   secrets by reference — no laptop-built archives in production. Setup:
   `git_repo_create` → push code + the two files → done (see the Git CI recipe).
   `git_ci_init` writes the workflow + deploy.yaml for you.
2. **Throwaway only: direct `ignite_app_deploy`.** Uploads a local archive
   (`--code`, ~1 MB compressed cap at the edge) or points at an image
   (`--image-ref`). The artifact is whatever was on the machine at that moment:
   no history, no review, no rebuildability. When a user asks to "deploy my
   app", use path 1 — this one only when they explicitly want a throwaway.

Tool: ignite_app_deploy (see dodil://help/ignite/app/deploy for flags).
Then ignite_app_get ["<app>"] to confirm — a healthy deploy shows
`deployment_state: "deployed"` (NOT "Ready"/"Running"; other states:
compiling/provisioning/activating = in progress, failed/cold = attention).
Pick the source mode first — this is the #1 deploy mistake. It's a CONCEPTUAL
choice about WHO OWNS THE PROCESS, not a per-language one (same rule for python /
rust / go / deno; details + per-language entry point: dodil://ignite/deployment):
  - Do YOU own the process — your own web framework / HTTP server (e.g. FastAPI or
    similar, in any language — anything with its own listen loop), and/or a
    **Dockerfile**? → **IMAGE mode.**
  - Does the PLATFORM own the runtime — your code is just a **plain handler function**
    (handler(payload, ctx)-style) with no Dockerfile and no server of its own?
    → **COMPILATION mode.**
  ⚠️ COMPILATION IGNORES YOUR DOCKERFILE. A compile deploy (`--runtime <lang>`) never
  reads your Dockerfile — it builds on the platform's fixed managed toolchain (one
  non-selectable version per runtime, e.g. python 3.12 / rust 1.93 / go 1.26 /
  deno 2.7.14) and REQUIRES the runtime's handler entry point. Passing an app that
  owns its own server (e.g. a FastAPI app or similar) plus a Dockerfile to a compile
  deploy is the classic failure: wrong entry point AND it builds on the compiler pod,
  not your Dockerfile. Tell: your Dockerfile pins one version, the draft reports the
  runtime's fixed version (e.g. 3.12) — that means compile mode never looked at your
  Dockerfile.

  - COMPILATION — supported language, plain function, NO Dockerfile. The managed build
    service compiles your source (faster/lighter build). Your code MUST expose the
    runtime's entry point (e.g. python: handler.py `def handler(payload, ctx)`; rust:
    `#[ignite::main]` in src/main.rs; go: `ignite.Start(...)`; deno: `start(handler)`):
      ignite_app_deploy args:["<app>"] code:"./src" --runtime python
    A --code directory is zipped (zip/tar.gz) and uploaded (inline cap ~1 MB compressed,
    the edge's limit; anything bigger ships by git push + CI).
  - IMAGE — HTTP servers, has-a-Dockerfile apps, system libs, custom base, or an
    unsupported language. Two lanes:
      • prebuilt (most reliable; uses NO platform build pod): build+push yourself, then
        ignite_app_deploy args:["<app>"] image-ref:"registry.dodil.io/<org>/<app>:<tag>"
        (+ registry-secret-ref for private) --port 8080 --health-path /healthz
      • platform-built: --git-url [+ --dockerfile-path], or --code <dir> --dockerfile-path
        Dockerfile — the Kaniko builder (a DIFFERENT pod path than the compiler) runs
        your Dockerfile and produces the image.

Deploy stuck on `compiling`/`failed` with a "Pod startup timeout" and ZERO build
logs = the build/compiler pod never started (wrong lane, or that runtime's compiler
image isn't on the target cluster) — it died before reaching your code. Switch to
IMAGE prebuilt (image-ref), which uses no platform build pod. See the
"Failure signatures" note in dodil://ignite/deployment.

## Ignite app-to-service auth: your code needs a SERVICE ACCOUNT
An Ignite app is a separate workload — it CANNOT use your (the deployer's) token.
If the app's binary/code calls K3, vbase, scriptum, or the models API, it must
authenticate with its own SERVICE ACCOUNT via client_credentials. Steps:
  1. Create an SA:   auth_service-account_create args:["<app>-sa"]
  2. Grant it the least-privilege role for EACH service it calls. Get the LIVE
     catalog (role names + which are conditionable) from
     auth_service-account_list-roles — don't assume, roles change per org:
       auth_service-account_grant-role args:["<sa-uuid>","<svc>-authorization-service","<role>"]
     Scope a CONDITIONABLE role to specific resources with on:["resource=<drn>"]
     (least privilege); org-wide-only roles reject a condition.
  3. Give the app the creds as RUNTIME env, the secret BY REFERENCE (never a literal
     in a tool argument, and never build secrets — those never reach the app):
       printf %s "<secret>" | dodil ignite secret create <app>-sa-secret --type env --from-stdin
       (MCP: ignite_secret_create args:["<app>-sa-secret"] type:"env" from-stdin:true)
       ignite_app_deploy / ignite_app_update env:["DODIL_SERVICE_ACCOUNT_ID=<full id>",
         "DODIL_SERVICE_ACCOUNT_SECRET=secret://<app>-sa-secret"]
     <full id> is the QUALIFIED serviceAccountId (name@<org>.sa; older .svcacc.dodil.io) from
     create/list — the bare name you created it with is rejected (401 invalid_client).
     The value is resolved into the pod at deploy; a missing secret fails the deploy
     naming it. Rotating: auth_service-account_rotate, re-create the secret, redeploy.
  4. In the app, exchange creds for a token and call the service:
     POST https://id.dodil.io/realms/dodil/protocol/openid-connect/token
       grant_type=client_credentials, client_id=<sa-id>, client_secret=<secret>
     -> access_token ; call the service with Authorization: Bearer <token>.

Ignite's OWN roles (for an SA/user that manages or invokes THIS platform), by
domain — run auth_service-account_list-roles for the live set + descriptions:
  - apps (view / deploy+invoke / full-admin): CONDITIONABLE — scope to specific
    apps with on:["resource=<app-drn>"], where the DRN is
    drn:dodil:ignite:<org>:app/<app> (the `drn` field from ignite_app_get).
  - models (invoke chat/embed/infer/transcribe): ORG-WIDE only (not app-scopable).
  - builds and secrets: ORG-WIDE only.
So an app that just calls managed models needs the org-wide model role; an app
that manages OTHER ignite apps can be scoped to exactly those app DRNs.

Full generic model: dodil://auth/service-accounts. Troubleshooting: 401/403 from a
service = the SA is missing that service's role (grant it); if a SCOPED grant is
rejected, that role isn't conditionable — check list-roles.
Cleanup: `ignite_app_delete` needs yes:true (`--yes`) — without it the CLI prompts
for confirmation and, over the non-interactive MCP/CLI path, silently no-ops
("Deletion cancelled"). The SA is NOT deleted with the app: also delete its SA —
auth_service-account_list filter:"<app>" to find it, then auth_service-account_delete
args:["<uuid>"] yes:true (refused without it). A leftover SA is a dangling credential.

## Ignite models (managed inference: chat / infer / embed / transcribe)
Discover: ignite_models_list (ids + capabilities), ignite_models_get args:["<model>"].
  - Chat (one-shot; pass the prompt, don't rely on interactive input over MCP):
    ignite_models_chat args:["<model>"] message:"Summarize dataflow programming." [system:"..."]
  - Text completion: ignite_models_infer args:["<model>"] prompt:"<text>"
  - Embeddings:      ignite_models_embed args:["<model>"] input:"<text>"
  - Transcription:   ignite_models_transcribe args:["<model>"] file:"/path/to/audio.wav"

### Chat about an image, video or document (attachments via k3)
ignite_models_chat carries files as content parts; ignite relocates bytes, never
transforms them, so send the original file. Local files are uploaded to YOUR k3
bucket and referenced as k3://bucket/key (the model reads them through ignite):
    ignite_models_chat args:["kimi-k3"] message:"What text is in this photo?" attach:["/path/photo.png"]
    ignite_models_chat args:["kimi-k3"] message:"Summarise" attach:["k3://my-bucket/reports/q3.pdf"]   # existing object
    ignite_models_chat args:["kimi-k3"] message:"Describe" attach:["https://example.com/a.jpg"]       # provider fetches / ignite relays
  - bucket:"<name>" picks the upload bucket (default ignite-assets, created on first use);
    key-prefix:"chat/" is prepended to the file basename.
  - inline:true embeds the file as a base64 data URI instead — use it when the
    deployment has no k3 ("asset storage is not available on this deployment").
  - The model decides what it accepts: images/video/PDF/DOCX/XLSX/CSV/TXT/MD on the
    kimi-k3 family (documents arrive as extracted text); audio is refused. Check
    ignite_models_get for the model's declared asset modalities.
  - payload:'{"messages":[...],"max_tokens":N}' (or payload:"@file.json") sends a raw
    OpenAI-shaped body when you need several turns or hand-built content parts.

### Calling models from your OWN app code (OpenAI SDK)
The models API is OpenAI-compatible and served on the standard gateway, so app code
uses the plain OpenAI SDK — point base_url at the gateway's /v1 and pass the SA token
(the access_token from the client_credentials exchange above) as api_key. Model names
are global (no org prefix):
    from openai import OpenAI
    client = OpenAI(base_url="https://api.dodil.io/v1", api_key=sa_access_token)
    client.chat.completions.create(model="kimi-k2.5", messages=[{"role":"user","content":"..."}])
    # embeddings: client.embeddings.create(model="<embed-model>", input="...")
api_key is the SA access_token, NOT an OpenAI key — the SDK sends it as
`Authorization: Bearer <token>`, exactly the InvokeApp-scoped token the gateway wants.
401 = token expired (re-exchange the creds); 403 = the SA lacks the ignite invoke role
(grant ignite.* per the auth steps above). Same token authorizes K3/vbase calls too.

## Continuous polling / cron-style batch jobs (no event-watcher service yet)
Dodil has no event-watcher/trigger microservice at this stage, so there is no
server-side "run on schedule / on new data" primitive. Two ways to run recurring or
polling work, pick by where it must live:
  - LOCAL (dev, or a host you keep on): use your agent's own scheduler / a host
    crontab entry that runs the CLI. Simple, but stops if the host sleeps.
    (There is no `scriptum schedule` command — Dodil has no server-side scheduler.)
  - REMOTE (cloud, always-on): deploy an Ignite app whose code runs its OWN long-lived
    poll loop (any language — a persistent entrypoint via --code/--git-url/--image-ref)
    and keep exactly one pod live with a warm floor:
      ignite_app_deploy args:["<poller>"] --reserved 1 --max-replicas 1
    --reserved 1 pins one warm pod so the loop never scales to zero and keeps polling;
    --max-replicas 1 keeps it a singleton (a poll loop shouldn't fan out). This is the
    current stand-in for a server-side scheduler for remote workloads.
Cost control: a poller mostly sleeps between polls, so don't pay for a big warm pod.
Use a small --tier, or right-size with custom limits: --tier unspecified --cpu
<millicores> --memory <MB>. Remember --reserved is billed continuously (see the
scaling guide in dodil://ignite/enums). The app still needs its own SERVICE ACCOUNT
to read the data sources and write results (see the app-to-service auth recipe above).

## Custom domain onboarding (requires the owner's DNS manager)
The flow crosses into a third-party system — the human must edit DNS:
1. `ignite_domain_add app-name:<app> args:["api.acme.com"]` → returns a TXT
   challenge + CNAME target. STOP and hand both records to the human to
   create at their DNS provider (Cloudflare: proxy OFF / "DNS only").
2. After they confirm (propagation: minutes): `ignite_domain_verify
   args:["api.acme.com"]` — "waiting on DNS: ..." names any missing record.
3. Poll `ignite_domain_get args:["api.acme.com"]` until `state:"active"`
   (TLS issues automatically) — only then is https://api.acme.com live.
Remove with `ignite_domain_remove` — the app + canonical URL are unaffected.

## Scriptum (agent workflow orchestrator — uses script names, NO bucket)
The .scriptum DSL is a small dataflow language: a file declares a script name
and version, imports tools (native built-ins + Ignite functions, referenced by
name), runs steps (do "label" with <tool> ... -> var), fans out with together /
(pipe x from list ... yield), and returns with emit/yield. To WRITE a script,
read the dodil://scriptum/language resource — it is the full syntax plus how to
deploy an inline Python Ignite function and use it as a scriptum tool. Inspect
the compiler view of any draft with scriptum_draft_compile show-ast:true or
show-ir:true.
Author/publish a script (draft lifecycle):
  1. scriptum_draft_save    args:["<name>"]  file:"/path/to/flow.scriptum"   (file is required)
  2. scriptum_draft_compile args:["<name>"]                                  (add show-ast/show-ir to debug)
  3. scriptum_draft_test    args:["<name>"]  input:"{\"key\":\"value\"}"      (input also accepts @file)
  4. scriptum_draft_publish args:["<name>"]  # promotes the compiled draft to a new version
Run a published script and get the result:
  - One shot:   scriptum_thread_run    args:["<script>"]  input:"{...}"  result:true
  - Or async:   scriptum_thread_create args:["<script>"]  input:"{...}"  -> take the thread id,
                then scriptum_thread_result args:["<thread-id>"] (scriptum_thread_steps / _watch for progress).
Discover available step tools with scriptum_tool_list. Check connectivity with scriptum_doctor / scriptum_health.
Access to scriptum itself (author/run scripts) uses a scriptum role — scriptum.viewer
(read), scriptum.developer (author/publish/run), scriptum.admin (full); run
auth_service-account_list-roles for the live set. Scriptum roles are CONDITIONABLE on
drn:dodil:scriptum, so a role can be scoped to specific scriptum resources with
on:["resource=<drn>"] (least privilege) rather than org-wide. Generic grant/scope
model: dodil://auth/service-accounts. (This is separate from the SA a running SCRIPT
uses to reach K3/vbase/S3 below, which needs those services' roles.)
Native tools that reach dodil services (k3_object_*, k3_table_*, vector_store_*,
s3_*) auth with a service account; K3 provides the creds + endpoints when it runs
your script. For standalone runs set them as env (K3 Objects default url
https://object.uk-lon-1.dodil.io, region us-east-1) — see dodil://scriptum/language.
Env vars for runs: scriptum_env_set args:["KEY","value"]; scriptum_env_import args:["/path/.env"];
then pass env:true to thread/draft run to load them.
Scheduling: dodil has no server-side scheduler yet. Two ways to run a script on a
schedule: (1) use YOUR OWN scheduler — most agent runtimes have a local scheduler —
to call scriptum_thread_run on your cadence; (2) for an always-on schedule/poller
that must run WITHOUT the agent (host-independent), deploy the logic as an Ignite app
with a warm pod (ignite --reserved 1) running a sleep/timeout loop — see the Ignite
"continuous polling" recipe.

### Git — create a repo, open a PR, run CI, merge

Goal: go from an empty repo to a merged pull request.

1. **Create the repo**: `git_repo_create <name>` → a `repo_id`. Later steps take the
   repo_id or the bare name. A bare name resolves in the login's org; for a repo in
   another org pass `org-name:"<ORG>"` (exact case, as in its URL) or the repo_id.
   `git_clone-url <repo>` prints both URLs — `git@git.dodil.io:<org>/<repo>.git`
   (SSH) and `https://git.dodil.io/<org>/<repo>.git`.
2. **Credentials to push.**
   - **A person, on their machine:** nothing to mint. `dodil git setup` once (in a
     terminal) registers their PERSONAL SSH key and installs the HTTPS helper. Both
     open every repo in every org where they hold a git role — plain `git clone` /
     `git push` just work, like GitHub.
   - **Headless (CI, bots):** mint an org key: `auth_apikey_issue role:"git.editor"`
     (push / open PRs; `git.admin` for settings) — the plane is inferred from the
     role, and `secret-only:true` returns just the `dk_…` value. NOT `git.ci`, which
     only reports CI checks and cannot push. A key opens its own org only.
3. **Push code** with the `git` CLI. A person: `git push` as usual. A `dk_` key: present
   it as the HTTP Basic-auth PASSWORD (any username), **via a credential helper — never
   baked into the remote URL**, which writes it into `.git/config` and leaks it in
   logs/`remote -v`:
   ```bash
   export DK_KEY=dk_…
   git -c credential.helper='!f(){ echo username=x; echo "password=$DK_KEY"; };f' \
     clone https://git.dodil.io/<ORG>/<repo>.git
   # (the same -c credential.helper=… works on git fetch/push)
   ```
   `repository not found` = no access or no such repo (the forge does not say
   which): no git role in that org, or a `dk_` key from another org. Can read but not
   write → 403 / `insufficient scope: git.write required`.
4. **Open a PR**: `git_pr_create <repo> --title … --head <feat> --base <base>`.
   Inspect with `git_pr_list <repo>` / `git_pr_get <repo> <number>`.
   **From a fork** (contributing to a repo you cannot push to): `git_repo_fork <repo>
   to-org:"<your org>"`, push your branch to the fork, then `git_pr_create <repo>
   head-repo:"<your org>/<fork>" head:<branch> base:<base> title:…`. The PR shows
   `head_label` (`org/repo:branch`). A fork from another org gets CI without secrets
   until a maintainer runs `git_pr_ci-approve` (only on the user's say-so).
5. **Merge**: `git_pr_merge <repo> <number> method:squash|merge_commit|fast_forward|rebase`
   (default merge_commit), or `git_pr_close` without merging.

**Branch protection (new repos are born OPEN).** A fresh repo's default branch
blocks only force-push + deletion — you can push (including fast-forward) and
merge PRs freely, no approvals or checks required. Check the current rule with
`git_protection_get <repo>`.

**Turn on gating** with `git_protection_set <repo> --branch main
--required-approvals 1 --require-green-checks`. A GATED branch then takes **NO
direct pushes** (fast-forward included) — every change must go through a PR that has:
  - an **approving review from a DIFFERENT principal than the PR author**
    (`git_pr_approve <repo> <number>` from a *second* identity; a self-approve is
    accepted but does not count), AND
  - a **green status-check rollup** — report checks with
    `git_check_create <repo> <sha> --name <n> --state passed` (states:
    queued|running|passed|failed|errored|skipped; passed or skipped are green),
    transition with `git_check_update <repo> <check-id> --state …`, and read the
    rollup via `git_check_list <repo> <sha>`.

`git_branch_list <repo>` shows branches + which is default.

### Git CI — workflows that build, test, and push to registry.dodil.io

Dodil git runs **GitHub Actions-compatible workflows**: drop YAML in
`.github/workflows/*.yml` and the forge executes it (via the `act` runner) on
`push` / `pull_request`. Each workflow job surfaces as a **status check** on the
commit — the same rollup that `git_protection_set --require-green-checks` gates on
(see "Turn on gating" above). So CI is how a PR earns its green check without
anyone calling `git_check_create` by hand.

- **Read CI results:** `git_check_list <repo> <sha>` shows every check + the
  rollup; drill in with `git_check_get`. A job that's still executing reports
  `running`; a failed step flips the check to `failed` with step detail.
  `<sha>` is the full sha **or at least 7 characters of it** (what
  `git log --oneline` prints). The forge expands it against the repo's CI runs:
  **404** = no run has that prefix (CI never fired for it, or a typo), **409** =
  the prefix matches several runs (the error lists them — add characters).
  A branch or tag name is refused (400); get the sha with
  `git rev-parse --short <branch>`.
- **Cancel or re-run a run:** `git_run_cancel <repo> <sha|check-id> branch:<b>`
  / `git_run_rerun …`. The selector is a sha (full or 7+ chars) or the `chk_…`
  id shown by `git_check_list`; `branch:` is the branch the run was pushed to.
  The reply means the cancel was **sent**, not that the run has stopped — a
  queued run is dropped before it starts, a running one has its pod deleted
  mid-step. Confirm on `git_check_list`: the check ends **`errored`** (there is
  no separate cancelled state). Runs on one branch are serialized, so the next
  push's run starts as soon as the cancelled one ends.
- **`git_check_create` / `git_check_update` are for EXTERNAL/custom CI only** —
  reporting a check from a system that isn't these in-repo workflows. If your CI
  is a `.github/workflows` file, the checks are produced for you; don't also
  report them manually.
- **Which identity runs it:** the forge runs the workflow; you don't push checks.
  To report checks from an *outside* pipeline, mint `git.ci`
  (`auth_apikey_issue service:"git" role:"git.ci"`) — it reports checks but
  **cannot push code** (pushing needs `git.editor`/`git.admin`).

#### Building an image and pushing to the org registry (the common case)

**The registry credentials are AUTO-INJECTED — do NOT create, mint, or store
them.** Every CI job receives two secrets, minted per-org by the control plane:

- `secrets.DODIL_REGISTRY_URL`   → `registry.dodil.io`
- `secrets.DODIL_REGISTRY_TOKEN` → a per-org `dk_…` push key (durable, reused per
  org; already scoped to push to `registry.dodil.io/<org>/*`)

Reference them straight from the workflow — there is no `auth_apikey_issue` step
for CI registry pushes. The canonical, copy-paste job:

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ${{ secrets.DODIL_REGISTRY_URL }}   # → registry.dodil.io — REQUIRED
          username: ci                                   # any non-empty value
          password: ${{ secrets.DODIL_REGISTRY_TOKEN }}
      - run: |
          IMG="${{ secrets.DODIL_REGISTRY_URL }}/<org>/<image>:${{ github.sha }}"
          docker build -t "$IMG" .
          docker push  "$IMG"
```

#### Deploying on push — `.dodil/deploy.yaml` (the way to ship an app)

The build above only pushes an image. Add **`.dodil/deploy.yaml`** and the forge's
CD runner deploys that image to ignite once the commit's checks are green — every
push to the deploy branch ships, with history, review and no upload cap. This,
not `ignite_app_deploy --code`, is how a real app ships.

`git_ci_init args:["<checkout dir>"] app:"<app>" port:8080 health-path:"/healthz"`
writes BOTH files (a build workflow and a commented deploy.yaml); it never
overwrites without force:true. What it writes:

```yaml
version: 1
create_if_missing: true          # the first deploy creates the ignite app
apps:
  - name: <app>                  # [a-z0-9.-]
    image: "{registry}/<org>/<app>:{sha}"   # what the build job pushed
    port: 8080
    health: {path: /healthz}
    env:                         # optional; REPLACES the app's env each deploy
      DODIL_SERVICE_ACCOUNT_ID: "${{ secrets.DODIL_SERVICE_ACCOUNT_ID }}"
      DODIL_SERVICE_ACCOUNT_SECRET: "${{ secrets.DODIL_SERVICE_ACCOUNT_SECRET }}"
when:
  branches: [main]
  require_checks: [build/build]  # "<workflow name>/<job id>" — deploy only what built
```

Walkthrough: `git_repo_create` → `git_ci_init` → set the secrets the env reads
on the REPO (`git_secret_set <repo> NAME` — the user supplies values; ignite
secrets are a different store) → `git_ci_verify` (checks both files against the
repo and the live org) → commit + push → `git_check_list <repo> <sha>` until
green → `ignite_app_get` shows `deployment_state: deployed`. Full key reference:
`dodil git ci init --help`.

Runner quirks:
- The docker-capable runner image (catthehacker/ubuntu:act-latest) has a
  PEP 668 system Python — `pip install` fails; make a venv first
  (`python -m venv .venv && . .venv/bin/activate`).
- `actions/setup-python` in parallel jobs on one agent can collide — prefer one
  job, or the image's python in a venv.
- The first run on a cold agent can take ~15 min (image pull); later runs are
  minutes.

#### Two failure signatures you WILL hit (and the fix)

1. **`Logging into docker.io...` / auth failure at the login step.**
   `docker/login-action@v3` silently defaults to **`docker.io`** when the
   `registry:` input is omitted — so it logs in to Docker Hub, not your org
   registry, and the push 401s. **Fix:** always pass
   `registry: ${{ secrets.DODIL_REGISTRY_URL }}`. This is the #1 CI mistake.

2. **`Error: Unable to locate executable file: docker`.** The **runner image**
   has no docker CLI. `docker build`/`push` and `docker/login-action` need docker
   present in the image that backs `runs-on: ubuntu-latest`. The default runner
   (`node:20-bullseye-slim`) has none. **This is fleet configuration — the
   workflow author CANNOT fix it from the YAML.** The fleet must map
   `ubuntu-latest` to a docker-capable act image (e.g.
   `catthehacker/ubuntu:act-latest`, which mirrors GitHub's `ubuntu-latest`).
   **Fix:** contact your platform/CI-fleet admin to override the runner image for
   the fleet; until then, docker-building CI won't run on a default fleet.

Mapping for a "why did my build fail" triage:
| symptom in CI logs | cause | fix |
|---|---|---|
| `Logging into docker.io...`, then 401 | `registry:` omitted → wrong host | pass `registry: ${{ secrets.DODIL_REGISTRY_URL }}` |
| `Unable to locate executable file: docker` | runner image lacks docker CLI | fleet must use a docker-capable act image (admin) |
| check stuck at `running`, no step detail | (historical) CI runner resource/mint issue | resolved in gitd ≥ 1.0.9 — CI now streams full step detail on failure |
| `failed to resolve host 'postgres'` | forge older than 1.6.7 (#210) | publish `ports:` and use 127.0.0.1, or upgrade |

#### Service containers (`services:` — e.g. Postgres for tests)

A job's services are reachable both ways, with or without `container:`:

- **By name** (from gitd 1.6.7): `host=postgres port=5432`. Use the service's
  key under `services:` and the container's own port.
- **By localhost:** publish a port and connect to 127.0.0.1.
  `ports: ["55432:5432"]` gives `127.0.0.1:55432` in a job without
  `container:`; this is GitHub's pattern.

```yaml
services:
  postgres:
    image: postgres:16
    env: { POSTGRES_PASSWORD: postgres }
    options: >-
      --health-cmd "pg_isready -U postgres" --health-interval 2s --health-retries 30
steps:
  - run: pytest   # PGHOST=postgres PGPORT=5432
```

Wait for the service to be ready (health options, or a retry loop) before your
tests connect. Names resolve from the start of the job's first step.

#### Notes

- **Non-docker CI** (unit tests, linters) needs none of the above — a plain
  `runs-on: ubuntu-latest` job runs on the default runner; only image builds need
  the docker-capable fleet.
- The registry push target is `registry.dodil.io/<org>/<image>` — org is
  lowercase in image paths. After a push, scan/list with the `registry_*` tools
  (`registry_repo_list`, `registry_vuln <repo> <tag>`).
- CI green + an approval from a different principal is exactly what a gated branch
  requires to merge — wire the build/test workflow first, then
  `git_protection_set --require-green-checks` so the check actually gates.

### Git — issues, labels, types, projects (GitHub's shapes)

Issues share ONE number space with pull requests per repo: `#N` is one thing,
so `git_issue_get` on a PR's number is a 404 and vice versa. Labels and issue
types are ORGANIZATION-scoped (one vocabulary for every repo). Lists are paged
(30 a page, max 100, newest first) and carry the repo's open/closed counts.

1. **Open an issue**: `git_issue_create args:["<repo>"] title:"…" body:"…"` —
   optional `label:["bug","help-wanted"]` (must already exist in the org, see
   `git_label_list`) and `type:"Bug"` (one per issue, see `git_issue-type_list`).
   The reply carries `number`.
2. **Work it**: `git_issue_comment args:["<repo>","<n>"] body:"…"` (reply with
   `reply-to:"<root comment id>"` — threads are one level deep);
   `git_issue_label_add args:["<repo>","<n>","bug","needs-repro"]`;
   `git_issue_edit args:["<repo>","<n>"] title:"…" type:"Feature"`.
3. **Link a PR**: put `Closes #<n>` (also fixes / resolves) in the PR body on
   `git_pr_create`. The PR shows `closes_issues`, the issue shows `linked_prs`
   (`git_issue_get`). **Merging into the DEFAULT branch closes the issue** and
   records the closer; merging elsewhere, or closing the PR without merging,
   closes nothing.
4. **Close / reopen explicitly**: `git_issue_close` / `git_issue_reopen` — a
   repeat transition is refused (422), never a silent no-op. Anyone with write
   access (`git.editor`+) may edit, close and reopen any issue.
5. **Boards**: `git_project_create args:["Release 1.0"]` (admin) → id; add cards
   from ANY repo in the org: `git_project_item_add args:["<project-id>","<repo>","<n>"]`
   (`kind:"pr"` for a pull request; `status:"In Progress"` to place it). Columns
   are the project's statuses (Todo / In Progress / Done); the server moves a
   card to the last column when its issue closes or PR merges, and back to the
   first on reopen — `git_project_get` shows the board.
6. **Milestones** (REPO-scoped, numbered per repo, shared by issues and PRs):
   `git_milestone_create args:["<repo>"] title:"v1.0" due:"2026-12-01"`; put an
   issue on it with `git_issue_edit args:["<repo>","<n>"] milestone:"v1.0"` (title
   or number; `clear-milestone:true` removes it) or `milestone:` on create; list
   its issues with `git_issue_list args:["<repo>"] milestone:"v1.0"` (`"none"` /
   `"*"` for no / any milestone). `git_milestone_close` marks it done;
   `git_milestone_delete … yes:true` removes it from its issues (they stay).
7. **Sub-issues** (one parent each, ≤100 children, ≤8 levels): create a child with
   `git_issue_create … parent:"<epic n>"`, or attach existing ones with
   `git_issue_sub_add args:["<repo>","<parent>","<child>",…]`.
   `git_issue_sub_list` shows children and done/total;
   `git_issue_edit … parent:"<n>" replace-parent:true` moves one;
   `clear-parent:true` detaches it.

Org-level tools (`git_label_*`, `git_issue-type_*`, `git_project_*`) act in the
login's org. For another org you are signed in to, add `org:"<org>"`; a dk_ key
carries no org claim, so pass `org:"<org id>"` with it (or read labels through a
repo: `git_label_list repo:"<repo>"`).
Creating/deleting labels, types and projects needs `git.admin`.

### Remix templates — making a repo remixable

A repo becomes a remix template with one file, `.dodil/remix.yaml`: what a
remix creates in the remixer's org (K3 buckets with a schema, AppID user pools,
service accounts whose credentials land in the new repo's CI secrets, incl.
`ignite.model-user` for Models) and the secrets the remixer supplies.
`.dodil/deploy.yaml` then deploys every copy with `${{ dodil.repo }}` names.

Read **dodil://git/remix** (CLI: `dodil guide remix`) before writing one: every
field, the 25-character bucket name limit, the deploy.yaml wiring and a complete
minimal template. Feedback loop: `git_remix_check args:["<repo>"]` (valid /
invalid + errors; the commit also gets a `dodil-ci/remix` check), then
`git_remix_plan args:["<repo>"] to-org:"<test org>"` (creates nothing).

Publish: `git_repo_topics args:["<repo>","set","dodil-challenge,dodil-challenge-<category>"]`
tags a template or an entry; a remixer publishes their copy with
`git_remix ... visibility:"public" topics:"a,b"` (applied only once it deployed).

### Registry — push an image, scan it, manage visibility

Goal: get a container image into the Dodil registry and manage it.
Host: `registry.dodil.io`. Images live under your lowercase org name:
`registry.dodil.io/<org>/<repo>:<tag>`.

1. **Mint a push key** (once): `auth_apikey_issue role:"registry.developer"` → a
   `dk_…` token (shown once; `secret-only:true` returns just the value).
   `registry.developer` can push and pull. The plane is inferred from the role's
   prefix — no `service` needed (a contradicting one is refused). Inside the forge's
   CI you need none of this: registry credentials are injected per job.
2. **Log in + push** with docker (the `dk_` key is the password; username is any):
   - `docker login registry.dodil.io -u ci -p dk_…`
   - `docker tag <image> registry.dodil.io/<org>/<repo>:<tag>`   (org lowercase)
   - `docker push registry.dodil.io/<org>/<repo>:<tag>`
   - Get the exact reference of an EXISTING image with `registry_pull-command <repo> [tag]`.
3. **See what's there**: `registry_repo_list`, then `registry_artifact_list <repo>`,
   and `registry_tag_list <repo> <tag-or-digest>`. (Lists page at 15 — use
   `page`/`page-size` for more; the output notes when it truncated.)
4. **Read the scan**: `registry_vuln <repo> <tag>`. Scanning is ASYNC — immediately
   after a push it returns `scan:"not_scanned"` (not yet run, NOT "clean"); wait and
   re-check for the real total/fixable CVEs.
5. **Share or lock down**: `registry_visibility <repo> public` / `… private`.
   ⚠ Visibility is org-wide (Harbor project): "public" makes EVERY repo in the
   org anonymously pullable, not just `<repo>`. Confirm with the user and pass
   `yes:true` (`--yes`) for public; without it the CLI refuses/prompts.
6. **Delete**: `registry_artifact_delete <repo> <tag-or-digest>` removes one image;
   `registry_repo_delete <repo>` (pass `yes:true`) removes the whole repo and all
   its artifacts.

# AppID: stand up an ERP-style app identity (pool -> settings -> roles -> tenants -> users)

The full admin-provisioned identity plane for an internal/ERP app:

    # 1. Pool with email+password enabled
    appid_pool_create args:["crm"] flags:{"with-local":true,"display-name":"Acme CRM"}

    # 2. Close public signup (ERP mode) and tighten passwords
    appid_settings_set args:["crm"] flags:{"allow-signup":false,"password-min-length":12}

    # 3. Define what roles MEAN (role -> permission catalog)
    appid_roles_set args:["crm","admin=users:*,invoices:*","approver=invoices:read,invoices:approve","clerk=invoices:create,invoices:read"]

    # 4. Subsidiaries as tenants
    appid_tenant_create args:["crm","acme-uk"] flags:{"display-name":"Acme UK"}

    # 5. Provision users (no password = INVITE: they set one via forgot-password)
    appid_user_create args:["crm","sam@acme.com"] flags:{"roles":"clerk"}
    #    -> note the returned user id (UUID)

    # 6. Tenant membership with tenant-scoped roles
    appid_tenant_member_set args:["crm","acme-uk","<user-uuid>","approver"]

End users then sign in on the pool's ISSUER (https://appid.dodil.io/{org}/crm)
— passing {"tenant":"acme-uk"} on the password grant pins the token: it gains
"tenant":"acme-uk" and a "permissions" claim merging global+tenant roles
through the catalog. The app authorizes by READING THE TOKEN (no round-trips).

Hooking up a relying party (e.g. the ignite ingress `--auth pool:` mode):

    appid_settings_set args:["crm"] flags:{"allow-signup":false,"redirect-uris":"https://myapp.apps.example.com/.dodil/auth/callback"}
    appid_pool_test-flow args:["crm","sam@acme.com","<password>"]   # proves authorize -> code -> tokens

Ongoing operations: appid_user_list (filter flag = email prefix),
appid_user_ban / appid_user_unban (immediate lockout / restore),
appid_user_revoke_sessions (sign out everywhere), appid_user_delete
(soft: frees the email; "hard" flag is permanent), appid_branding_set
(hosted login theme, public at {issuer}/branding), appid_pool_rotate_keys
(old keys stay in the JWKS until their tokens expire).

# AppID: move a pool's users into a k3 bucket (migration)

Binding (`appid_user-store_use-bucket`) points a pool at a new store but does
NOT move existing users. To relocate the users you already have — the
control-plane → bucket journey a growing app takes — use migrate, which copies
then cuts over:

    # 1. (once) a service account that can write the bucket, provisioned inline:
    #    appid_user-store_use-bucket flags:{"sa":"crm-identity","create-sa":true}
    #    (creates the SA + grants k3.editor ORG-WIDE, until k3 has per-bucket conditions)

    # 2. migrate: copies users+tenants+sessions, verifies counts, cuts over,
    #    then PURGES the source (add keep-source:true to retain it)
    appid_user-store_migrate args:["crm","bucket:crm-data"] flags:{"sa":"crm-identity"}
    #    → follows live: warm_copy → locked_delta → verifying → done

While migrating, the pool is briefly LOCKED: the issuer 503s (logins/signups
pause for the short cutover) — existing sessions are copied so users stay
signed in. If verification fails the migration auto-rolls-back and the pool
keeps serving the source. Watch or resume with appid_user-store_status; stop a
running one with appid_user-store_migrate-abort.

Deleting a pool: a bucket-backed pool KEEPS its identity rows in the customer's
bucket by default (appid_pool_delete). A control-plane pool's rows are removed
with it.

## Social / enterprise SSO for a pool ("Sign in with Google")

appid can delegate a pool's login to an upstream IdP (Google, Microsoft, or any
OIDC provider). The end-user flow is discovery-URL-driven; you only configure a
connection.

1. **Register the callback with the IdP.** In the provider's console, add an
   OAuth client and set its authorized redirect URI to appid's callback:

       https://appid.dodil.io/{org}/{pool}/authorize/callback

   You get back a `client_id` and `client_secret`.

2. **Add the connection** (secret via stdin so it never hits the command line):

       echo '{"client_id":"…","client_secret":"…",
              "discovery_url":"https://accounts.google.com/.well-known/openid-configuration",
              "scopes":"openid email profile"}' \
         | dodil appid connection add {pool} oauth:google --config - --enabled

   For Microsoft use `oauth:microsoft` with its discovery URL; for a generic
   OIDC provider use `oidc`. Instead of `discovery_url` you may pass explicit
   `authorization_endpoint` / `token_endpoint` / `userinfo_endpoint`.

3. **Ensure the pool has a redirect_uris allowlist** for the app that starts the
   login (the RP's own redirect, not appid's callback):

       dodil appid settings set {pool} --redirect-uris https://myapp.example/callback

4. **Done.** The hosted login page (`{issuer}/login`, reached via `/authorize`)
   now shows a "Continue with Google" button. On first login, a user whose
   upstream email is **verified** links to an existing local account with that
   email (or a new social account is created if signup is allowed); returning
   logins match on the provider subject.

Verify what a pool offers (no secrets) from its public branding:

    curl -s https://appid.dodil.io/{org}/{pool}/branding | jq .connections

### AppID M2M — a machine principal for YOUR app's API (service clients)

When one service must call your pool-protected API (not the dodil platform —
that's a platform service account, see dodil://auth/service-accounts), use a
pool **service client**: it authenticates with OAuth2 `client_credentials` and
its pool roles expand into the same `permissions` claim end-user tokens carry.

1. **Create** (the one-time secret is shown ONCE; output includes the issuer,
   token endpoint, and the roles' EFFECTIVE permissions from the pool catalog —
   check them: granting a broad role for one permission is a visible choice):
   `appid_service-client_create args:["<pool>"] client-id:"billing-worker" role:["invoices:write"]`
2. **Verify end to end** — mints a real token and prints the decoded identity /
   roles / permissions / expiry, never the raw token. Secret comes from the
   `DODIL_APPID_CLIENT_SECRET` env var (or stdin) — never a flag:
   `appid_service-client_test args:["<pool>","billing-worker"]`
3. **Your application mints its own tokens** with the canonical request (the
   portable path — plain OAuth, any language, no SDK):
   ```
   POST {issuer}/token          # issuer: https://appid.dodil.io/{org}/{pool}
   Content-Type: application/x-www-form-urlencoded
   grant_type=client_credentials&client_id=<id>&client_secret=<secret>
   ```
   → `{access_token, token_type, expires_in}`; send `Authorization: Bearer` to
   your API, which verifies against the pool JWKS and reads `permissions`.
   Note: pool discovery metadata does not yet advertise `client_credentials`
   in `grant_types_supported` — the grant works regardless (client_secret_post).
4. **Audit**: `appid_service-client_list` shows each client's roles;
   `set-roles` REPLACES the set (and reports the new effective permissions);
   `rotate` mints a new secret (old one dies instantly); `disable` blocks
   minting without deleting.

Least privilege: prefer a role whose permission list matches the machine's one
job; if only a broad role carries the needed permission, the effective-
permissions output shows exactly what extra power you are granting.

## Partner: a deal from quote to accepted milestone

    partner_deals_clients_create  name, invite-email            → crmClientId (re-list after the client joins)
    partner_deals_create          client, name                  → dealId
    partner_deals_quote_create    args:[deal], from-file        → quoteId   (products: partner_deals_catalog)
    partner_deals_quote_submit → partner_deals_quote_send yes:true
    (client accepts) partner_deals_contract_create args:[deal], quote, template
    partner_deals_contract_terms  governing-law, liability-cap, confirm:true
    partner_deals_contract_send yes:true → (client signs) → partner_deals_contract_countersign yes:true
    partner_deals_delivery_setup  args:[deal], client:"<client org>"   (Git project, repos, milestones, labels, links)
    partner_deals_delivery_milestone_status args:[deal, milestone]       (live from Git)
    partner_deals_delivery_milestone_submit args:[deal, milestone], note, yes:true  (signed snapshots)
    client side, org:"<client org>": partner_projects_milestone_accept args:[project, milestone], yes:true
    follow everything: partner_watch deal, since:<cursor>  (JSON lines; last line is the next cursor)

## Async tasks (long-running commands)
Long-running tools — deploy, invoke, model inference, builds, search, and script
run/test (ignite_app_deploy, ignite_invoke, scriptum_thread_run,
scriptum_draft_test, ...) — can run as background TASKS instead of blocking.
Their input schema advertises execution.taskSupport = "optional".
To run one as a task, add a "task" object to the tools/call params; you get a
task id back immediately:
  tools/call { name:"ignite_app_deploy", arguments:{args:["org:myfunc"],code:"./src"},
               task:{ ttl:600000 } }
Then poll/collect:
  tasks/get    { taskId:"<id>" }     -> status: working|completed|failed
  tasks/result { taskId:"<id>" }     -> waits for completion, returns the result
  tasks/list   {}                    -> all tasks
  tasks/cancel { taskId:"<id>" }     -> request cancellation
Prefer this for anything that can take more than a few seconds so the call
doesn't hold the connection open. (Without a "task" object the same tool just
runs synchronously.)

## Authentication
If a tool says you are not logged in, use a SERVICE ACCOUNT: call auth_login
with service-account-id and service-account-secret (or the
DODIL_SERVICE_ACCOUNT_ID / DODIL_SERVICE_ACCOUNT_SECRET env vars). Never start
the interactive browser/device login over MCP.
