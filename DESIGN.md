# Design and implementation decisions

## Architecture

Retain the official starter's four layers. Domain contains role-independent invariants and typed commands. Application owns permission checks, transactions, receipts, relationships and use cases. Infrastructure implements DataK3, Models, migration and operational logging. Doors translate HTTP/MCP identity and errors. Both doors call the same Boards service.

React is compiled into the same FastAPI/Ignite origin. This avoids a second host, credential handling in the frontend, CORS configuration and an external persistence service. OpenAPI generates command and response types. Feature routes and dialogs are split into lazy chunks; fonts and icons are local.

## Domain model

Workspace has one owner and active memberships. Board has workspace/private visibility. A board contains dynamic lists and cards. Each list has a stable semantic category independent of its display name. Cards have workspace-unique numbers, versions, integer positions, optional eligible assignees and calendar due dates. Reusable board labels, ordered checklist items and directed dependencies extend cards.

Dependencies must stay in the same board and form a DAG. Missing, archived or deleted prerequisites remain unresolved. My Tasks partitions completed, overdue, today, remaining current week, later upcoming and undated work. Monday begins the workspace-local week. The server derives calendar boundaries using zoneinfo; browser time is irrelevant to correctness.

Archive and delete are separate states. Parent archive hides descendants without rewriting their individual archive flags. Delete is a tombstone; activity remains auditable. Board deletion requires exact name confirmation.

## Authorization strategy

The gateway must attest pool-user context. Identity is pool plus immutable subject, never an email lookup. Application membership roles are independent of platform roles. Workspace owner controls membership, settings and board lifecycle; members control work; viewers have read-only content access. Personal preferences/favorites are permitted for all roles.

Every child lookup follows its board and workspace. An inaccessible resource returns a generic not-found error. Private boards require explicit inclusion, with the owner as the only implicit exception. Removing membership revokes grants and assignments atomically. Ownership transfer clears private assignments that the former owner can no longer access.

Invitation acceptance binds the authenticated subject to a hashed single-use token. The configured gateway contract does not attest verified email ownership, so the implemented production path requires owner approval. No fresh account is silently linked to a legacy email-based profile.

## DataK3 design and concurrency

Nineteen ab_* tables have explicit primary keys. UUIDs identify entities; deterministic compound strings identify membership/grant/association rows. A unique workspace/card-number index and transactionally updated workspace counter prevent duplicate human-readable numbers. Indexes stay within the documented single-column/unique-composite support.

SqlTransaction buffers changes and overlays reads. Commit flushes ordinary parameterized INSERT/UPDATE/DELETE statements. DataK3 FOR UPDATE registers read guards rather than blocking locks. Membership, workspace, board and affected cards/lists participate in mutation transactions, including empty-list moves. Full transactions retry up to three times for serialization/unique-claim conflicts. A stale supplied version always requires refresh.

Mutation receipts hash actor, workspace scope and operation ID. Content mismatch is rejected; authorization precedes replay. Receipt payloads omit invitation bearer tokens. Every actual card change and ordering shift records actor, UTC timestamp, before and after in the same transaction. No-op card saves preserve versions and create no invented history.

Keyword search filters and paginates in SQL inside the authorized transaction; DataK3 supplies all data. Vector ranking includes an authorized-board predicate and content-version match, followed by current-access hydration. Snapshot aggregation still favors implementation simplicity over large-workspace scalability; this is an explicit capacity-testing limitation.

## AI and background work

Dodil Models is the only model adapter. The system prompt treats task text as untrusted data. Checklist outputs are parsed and validated; preview and explicit append-save are separate. Model calls happen outside transactions, then authorization and relevant card versions are rechecked. Summary facts and generated suggestions are distinct fields with a snapshot time.

Embedding jobs are committed with relevant card changes. Leases survive process termination; expired leases recover after restart. Completion checks both content version and lease identity before saving. Up to five attempts use bounded delayed retry. Search triggers at most three recovery jobs; the running Ignite worker handles bounded batches. Scale-to-zero never depends on an unpersisted background task surviving.

The candidate embedding dimension is 512, with model/dimension/version metadata persisted. Deployment keeps the feature disabled until a genuine Models and vector contract test succeeds. A changed embedding model or dimension requires an explicit compatible migration/reindex; never mix vectors silently.

## MCP design

The official compatible MCPServer Streamable HTTP app exposes one logical endpoint with a slash alias. Both OAuth protected-resource metadata routes remain discoverable; application tools require pool identity and return structured domain failures. Tools express use cases, never raw SQL/table access.

Sixteen tools include all twelve required names plus member resolution, search, blockers and checklist saving. Callers discover authorized IDs and versions. Exact list names precede the explicit Doing alias. Workspace card numbers and duplicate names require scoped resolution. The current server date/timezone is included in show_board; this-week queries compute dates server-side.

## Remixability and delivery

Only destination-relative resource names occur in remix/deploy configuration. Generated service credentials are secret references. Bucket/pool collisions fail. CI verifies backend, generated contracts, frontend and browser behavior before publishing a lowercase image. The numeric nonroot container serves port 8080 and applies compatible additive migrations before starting.

Migration 001 creates namespaced tables, preserving original starter data. There is no unsafe email-based import. The fresh selected starter has no production data to migrate. Future changes must use additive ALTER/backfill/switch steps, not CREATE IF NOT EXISTS as a substitute for altering existing tables.

Health, platform self-check, real browser sign-in, MCP connector approval and actual fresh remix are separate acceptance gates. A local YAML pass does not establish cloud success. Previous successful images and additive schema compatibility provide the rollback path.

## Interface and trade-offs

Indigo accents, neutral surfaces and restrained layout keep work prominent. The vector mark, brand configuration and theme tokens are independent from application rules. Native dialogs manage focus, Escape and focus restoration. dnd-kit provides pointer/touch/keyboard input; explicit movement controls remain available. Positional sorting is disabled while filters hide cards. Polling/focus refresh is described accurately and paused during edits.

No comments/inbox/email service is included because those are conditional in the brief. Activity is recorded rather than fabricated. QA fixtures live only in tests, are loopback-restricted and visibly labeled, and are excluded from Docker. Their browser evidence validates UI mechanics, not live gateway or DataK3 guarantees.
